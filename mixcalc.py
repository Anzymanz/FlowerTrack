
import json
from mix_utils import validate_blend_names
import os
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
from theme import apply_style_theme, apply_rounded_buttons, compute_colors, set_titlebar_dark
import ctypes
from config import load_tracker_config, save_tracker_config
from resources import resource_path


APP_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "FlowerTrack")
DATA_DIR = Path(APP_DIR) / "data"
CONFIG_FILE = Path(APP_DIR) / "flowertrack_config.json"

def resolve_tracker_file() -> Path:
    try:
        cfg = load_tracker_config(CONFIG_FILE)
        if isinstance(cfg, dict):
            data_path = cfg.get("data_path")
            if data_path:
                return Path(data_path)
    except Exception:
        pass
    return DATA_DIR / "tracker_data.json"

LAST_PARSE_FILE = DATA_DIR / "last_parse.json"


roa_options = {"Vaped": 0.6, "Smoked": 0.3, "Eaten": 0.1}
MIX_MODE = os.environ.get("FT_MIX_MODE", "").strip().lower()
IS_STOCK_MODE = MIX_MODE in {"stock", "blend", "stockblend"}


def load_roa_options():
    global roa_options
    try:
        cfg = load_tracker_config(CONFIG_FILE)
        if isinstance(cfg, dict) and isinstance(cfg.get("roa_options"), dict):
            roa_options = {k: float(v) for k, v in cfg["roa_options"].items()}
    except Exception:
        pass

def load_tracker_flowers() -> list[dict]:
    """Return flowers from tracker data with grams_remaining > 0."""
    try:
        tracker_file = resolve_tracker_file()
        if tracker_file.exists():
            data = json.loads(tracker_file.read_text(encoding="utf-8"))
            flowers = data.get("flowers")
            if isinstance(flowers, list):
                return [f for f in flowers if float(f.get("grams_remaining", 0) or 0) > 0]
    except Exception:
        pass
    return []


def load_last_parse() -> list[dict]:
    try:
        if LAST_PARSE_FILE.exists():
            data = json.loads(LAST_PARSE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def load_dark_mode_default() -> bool:
    try:
        cfg = load_tracker_config(CONFIG_FILE)
        if isinstance(cfg, dict) and "dark_mode" in cfg:
            return bool(cfg.get("dark_mode", True))
    except Exception:
        pass
    return True


def format_item(it: dict) -> str:
    # Prefer tracker fields
    if "name" in it and "grams_remaining" in it:
        name = it.get("name") or "Unknown"
        thc = it.get("thc_pct")
        cbd = it.get("cbd_pct")
        grams = float(it.get("grams_remaining", 0) or 0)
        pot = []
        if thc is not None:
            pot.append(f"THC {thc}%")
        if cbd is not None:
            pot.append(f"CBD {cbd}%")
        pot_text = " / ".join(pot) if pot else ""
        extra = f" {pot_text}" if pot_text else ""
        return f"{name} ({grams:.2f} g available){extra}"
    brand = it.get("brand") or it.get("producer") or "Unknown"
    strain = it.get("strain") or "Unknown"
    thc = it.get("thc")
    thc_u = it.get("thc_unit") or ""
    cbd = it.get("cbd")
    cbd_u = it.get("cbd_unit") or ""
    parts = [f"{brand} - {strain}"]
    pot = []
    if thc is not None:
        pot.append(f"THC {thc}{thc_u}")
    if cbd is not None:
        pot.append(f"CBD {cbd}{cbd_u}")
    if pot:
        parts.append(f"({' / '.join(pot)})")
    return " ".join(parts)


def mg_per_g(val, unit):
    if val is None:
        return None
    u = str(unit or "").lower()
    try:
        v = float(val)
    except Exception:
        return None
    if "%" in u or u == "":
        return v * 10.0  # % of 1000 mg
    if "mg/g" in u:
        return v
    if "mg/ml" in u:
        return v  # approximate
    return None


def solve_for_ratio(total_g, target_ratio, t1, c1, t2, c2):
    """Solve grams of item1 to meet target THC:CBD ratio (X:1)."""
    if (c1 is None or c1 == 0) and (c2 is None or c2 == 0):
        return None
    if None in (t1, c1, t2, c2):
        return None
    G = total_g
    R = target_ratio
    denom = (t1 - t2) - R * (c1 - c2)
    if abs(denom) < 1e-9:
        return None
    ga = G * (R * c2 - t2) / denom
    gb = G - ga
    if ga < -1e-6 or gb < -1e-6:
        return None
    ga = max(0.0, min(G, ga))
    gb = G - ga
    return ga, gb


def potency(it, key):
    if key == "thc":
        return it.get("thc_pct") if "thc_pct" in it else it.get("thc")
    return it.get("cbd_pct") if "cbd_pct" in it else it.get("cbd")


def compute_mix(total_g, target_ratio, item_a, item_b):
    t1 = mg_per_g(potency(item_a, "thc"), item_a.get("thc_unit") or "%")
    t2 = mg_per_g(potency(item_b, "thc"), item_b.get("thc_unit") or "%")
    c1 = mg_per_g(potency(item_a, "cbd"), item_a.get("cbd_unit") or "%")
    c2 = mg_per_g(potency(item_b, "cbd"), item_b.get("cbd_unit") or "%")
    if None in (t1, t2, c1, c2):
        return None, "Both flowers need THC and CBD values to compute a ratio."
    solved = solve_for_ratio(total_g, target_ratio, t1, c1, t2, c2)
    if solved is None:
        return None, "Cannot reach that THC:CBD ratio with the selected flowers."
    ga, gb = solved
    total_thc_mg = ga * t1 + gb * t2
    total_cbd_mg = ga * c1 + gb * c2
    blended_thc_pct = (total_thc_mg / (total_g * 1000)) * 100 if total_g > 0 else 0
    blended_cbd_pct = (total_cbd_mg / (total_g * 1000)) * 100 if total_g > 0 else 0
    return (ga, gb, total_thc_mg, total_cbd_mg, blended_thc_pct, blended_cbd_pct), None




def log_dose():
    idx_a = combo_a.current()
    idx_b = combo_b.current()
    if idx_a < 0 or idx_b < 0:
        messagebox.showinfo("Select items", "Please select one item in each dropdown.")
        return
    try:
        total_g = float(total_var.get())
    except Exception:
        messagebox.showinfo("Weight", "Enter a valid total grams value.")
        return
    if total_g <= 0:
        messagebox.showinfo("Weight", "Total grams must be greater than zero.")
        return
    target_ratio = _get_target_ratio()
    if target_ratio is None:
        return
    item_a = items[idx_a]
    item_b = items[idx_b]
    name_a = str(item_a.get("name", "")).strip()
    name_b = str(item_b.get("name", "")).strip()
    result, err = compute_mix(total_g, target_ratio, item_a, item_b)
    if err:
        messagebox.showinfo("Cannot log", err)
        return
    ga, gb, total_thc_mg, total_cbd_mg, blended_thc_pct, blended_cbd_pct = result

    if not ("name" in item_a and "grams_remaining" in item_a and "name" in item_b and "grams_remaining" in item_b):
        messagebox.showinfo("Cannot log", "Logging requires flowers from tracker stock with remaining grams.")
        return

    try:
        data = json.loads(TRACKER_FILE.read_text(encoding="utf-8")) if TRACKER_FILE.exists() else {}
    except Exception:
        data = {}
    flowers = data.get("flowers") if isinstance(data, dict) else None
    if not isinstance(flowers, list):
        messagebox.showinfo("Cannot log", "Tracker data not available.")
        return

    def find_flower(name):
        for f in flowers:
            if f.get("name") == name:
                return f
        return None

    fa = find_flower(name_a)
    fb = find_flower(name_b)
    if fa is None or fb is None:
        messagebox.showinfo("Cannot log", "Selected flowers not found in tracker data.")
        return

    if float(fa.get("grams_remaining", 0)) + 1e-9 < ga or float(fb.get("grams_remaining", 0)) + 1e-9 < gb:
        messagebox.showinfo("Not enough stock", "Not enough grams remaining for one of the flowers.")
        return

    fa["grams_remaining"] = float(fa.get("grams_remaining", 0)) - ga
    fb["grams_remaining"] = float(fb.get("grams_remaining", 0)) - gb

    def is_cbd_dom(item):
        try:
            c = float(potency(item, "cbd") or 0)
            return c >= 5.0
        except Exception:
            return False

    is_cbd_a = is_cbd_dom(item_a)
    is_cbd_b = is_cbd_dom(item_b)

    eff = roa_options.get(roa_var.get(), 1.0)
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_display = now.strftime("%H:%M")
    time_full = now.strftime("%Y-%m-%d %H:%M")

    logs = data.get("logs") if isinstance(data, dict) else None
    if not isinstance(logs, list):
        logs = []
        data["logs"] = logs

    mix_name = f"Mix: {name_a} + {name_b}"
    mix_thc_pct = float(f"{blended_thc_pct:.2f}")
    mix_cbd_pct = float(f"{blended_cbd_pct:.2f}")

    def mix_matches(flower):
        try:
            return abs(float(flower.get("thc_pct", 0)) - mix_thc_pct) <= 1e-3 and abs(float(flower.get("cbd_pct", 0)) - mix_cbd_pct) <= 1e-3
        except Exception:
            return False

    mix_flower = find_flower(mix_name)
    if mix_flower is not None and not mix_matches(mix_flower):
        mix_name = f"{mix_name} ({time_display})"
        mix_flower = None

    if mix_flower is None:
        mix_flower = {
            "name": mix_name,
            "thc_pct": mix_thc_pct,
            "cbd_pct": mix_cbd_pct,
            "grams_remaining": 0.0,
        }
        flowers.append(mix_flower)

    logs.append({
        "time": time_full,
        "date": date_str,
        "flower": mix_name,
        "grams_used": total_g,
        "thc_mg": total_thc_mg * eff,
        "cbd_mg": total_cbd_mg * eff,
        "remaining": mix_flower.get("grams_remaining", 0),
        "time_display": time_display,
        "roa": roa_var.get() or "Unknown",
        "efficiency": eff,
        "is_cbd_dominant": mix_cbd_pct >= 5.0,
        "mix_sources": [
            {"name": name_a, "grams": ga},
            {"name": name_b, "grams": gb},
        ],
        "mix_thc_pct": mix_thc_pct,
        "mix_cbd_pct": mix_cbd_pct,
        "mix_ratio": float(target_ratio),
    })

    try:
        TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
        TRACKER_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        messagebox.showerror("Save failed", f"Could not save tracker data: {e}")
        return

    try:
        ctypes.windll.user32.PostMessageW(0xffff, 0x0400 + 1, 0, 0)
    except Exception:
        pass

    messagebox.showinfo("Logged", "Dose logged to tracker.")
    _close_and_save()





def add_to_stock():
    idx_a = combo_a.current()
    idx_b = combo_b.current()
    if idx_a < 0 or idx_b < 0:
        messagebox.showinfo("Select items", "Please select one item in each dropdown.")
        return
    try:
        total_g = float(total_var.get())
    except Exception:
        messagebox.showinfo("Weight", "Enter a valid total grams value.")
        return
    if total_g <= 0:
        messagebox.showinfo("Weight", "Total grams must be greater than zero.")
        return
    blend_name = blend_name_var.get().strip()
    target_ratio = _get_target_ratio()
    if target_ratio is None:
        return
    item_a = items[idx_a]
    item_b = items[idx_b]
    name_a = str(item_a.get("name", "")).strip()
    name_b = str(item_b.get("name", "")).strip()
    err = validate_blend_names(name_a, name_b, blend_name)
    if err:
        messagebox.showinfo("Blend name", err)
        return
    result, err = compute_mix(total_g, target_ratio, item_a, item_b)
    if err:
        messagebox.showinfo("Cannot blend", err)
        return
    ga, gb, total_thc_mg, total_cbd_mg, blended_thc_pct, blended_cbd_pct = result

    if not ("name" in item_a and "grams_remaining" in item_a and "name" in item_b and "grams_remaining" in item_b):
        messagebox.showinfo("Cannot blend", "Blending to stock requires flowers from tracker stock.")
        return

    try:
        data = json.loads(TRACKER_FILE.read_text(encoding="utf-8")) if TRACKER_FILE.exists() else {}
    except Exception:
        data = {}
    flowers = data.get("flowers") if isinstance(data, dict) else None
    if not isinstance(flowers, list):
        messagebox.showinfo("Cannot blend", "Tracker data not available.")
        return

    def find_flower(name):
        for f in flowers:
            if f.get("name") == name:
                return f
        return None

    fa = find_flower(name_a)
    fb = find_flower(name_b)
    if fa is None or fb is None:
        messagebox.showinfo("Cannot blend", "Selected flowers not found in tracker data.")
        return

    if float(fa.get("grams_remaining", 0)) + 1e-9 < ga or float(fb.get("grams_remaining", 0)) + 1e-9 < gb:
        messagebox.showinfo("Not enough stock", "Not enough grams remaining for one of the flowers.")
        return

    fa["grams_remaining"] = float(fa.get("grams_remaining", 0)) - ga
    fb["grams_remaining"] = float(fb.get("grams_remaining", 0)) - gb

    existing = find_flower(blend_name)
    if existing is not None:
        try:
            existing_thc = float(existing.get("thc_pct"))
            existing_cbd = float(existing.get("cbd_pct"))
        except Exception:
            existing_thc = None
            existing_cbd = None
        if (
            existing_thc is None
            or existing_cbd is None
            or abs(existing_thc - blended_thc_pct) > 1e-3
            or abs(existing_cbd - blended_cbd_pct) > 1e-3
        ):
            messagebox.showinfo(
                "Blend exists",
                "A flower with this name already exists with different potency. Choose a new name.",
            )
            return
        existing["grams_remaining"] = float(existing.get("grams_remaining", 0)) + total_g
    else:
        flowers.append(
            {
                "name": blend_name,
                "thc_pct": float(f"{blended_thc_pct:.2f}"),
                "cbd_pct": float(f"{blended_cbd_pct:.2f}"),
                "grams_remaining": total_g,
            }
        )

    try:
        TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
        TRACKER_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        messagebox.showerror("Save failed", f"Could not save tracker data: {e}")
        return

    try:
        ctypes.windll.user32.PostMessageW(0xffff, 0x0400 + 1, 0, 0)
    except Exception:
        pass

    messagebox.showinfo("Blend added", "Blend added to stock.")
    _close_and_save()

def calculate():
    idx_a = combo_a.current()
    idx_b = combo_b.current()
    if idx_a < 0 or idx_b < 0:
        messagebox.showinfo("Select items", "Please select one item in each dropdown.")
        return
    try:
        total_g = float(total_var.get())
    except Exception:
        messagebox.showinfo("Weight", "Enter a valid total grams value.")
        return
    if total_g <= 0:
        messagebox.showinfo("Weight", "Total grams must be greater than zero.")
        return

    target_ratio = _get_target_ratio()
    if target_ratio is None:
        return
    item_a = items[idx_a]
    item_b = items[idx_b]
    result, err = compute_mix(total_g, target_ratio, item_a, item_b)
    if err:
        messagebox.showinfo("Not possible", err)
        return

    ga, gb, total_thc_mg, total_cbd_mg, blended_thc_pct, blended_cbd_pct = result
    lines = [
        f"Mix: {ga:.2f} g of A + {gb:.2f} g of B (target THC:CBD {target_ratio:.1f}:1)",
        f"Total THC: {total_thc_mg:.1f} mg",
        f"Total CBD: {total_cbd_mg:.1f} mg",
        f"Blended potency: THC {blended_thc_pct:.2f}% | CBD {blended_cbd_pct:.2f}%",
    ]
    result_var.set("\n".join(lines))


def swap_items():
    a = combo_a.current()
    b = combo_b.current()
    if a < 0 or b < 0:
        return
    combo_a.current(b)
    combo_b.current(a)


def apply_theme(root, dark: bool):
    colors = compute_colors(dark)
    bg = colors["bg"]
    fg = colors["fg"]
    ctrl_bg = colors["ctrl_bg"]
    accent = colors["accent"]
    border = colors.get("border", ctrl_bg)
    entry_bg = ctrl_bg
    list_bg = colors.get("list_bg", entry_bg)
    scroll = border
    style = ttk.Style(root)
    try:
        apply_style_theme(style, colors)
    except Exception:
        pass
    root.configure(bg=bg)
    style.configure(
        "TEntry",
        fieldbackground=entry_bg,
        background=entry_bg,
        foreground=fg,
        insertcolor=fg,
        bordercolor=border,
    )
    style.configure(
        "TCombobox",
        fieldbackground=entry_bg,
        background=entry_bg,
        foreground=fg,
        arrowcolor=fg,
        bordercolor=border,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", entry_bg)],
        background=[("active", entry_bg), ("readonly", entry_bg)],
        foreground=[("readonly", fg)],
        arrowcolor=[("active", fg), ("!active", fg)],
        bordercolor=[("active", border), ("!active", border)],
    )
    # Combobox dropdown list colors
    root.option_add("*TCombobox*Listbox*Background", list_bg)
    root.option_add("*TCombobox*Listbox*Foreground", fg)
    root.option_add("*TCombobox*Listbox*selectBackground", accent)
    root.option_add("*TCombobox*Listbox*selectForeground", "#ffffff")
    style.configure(
        "Vertical.TScrollbar",
        background=scroll,
        troughcolor=bg,
        arrowcolor=fg,
        bordercolor=border,
        lightcolor=border,
        darkcolor=border,
    )
    style.map(
        "Vertical.TScrollbar",
        background=[("disabled", scroll), ("!disabled", scroll)],
        arrowcolor=[("disabled", fg), ("!disabled", fg)],
        troughcolor=[("disabled", bg), ("!disabled", bg)],
    )
    style.configure(
        "TScale",
        background=accent,          # slider fill
        troughcolor=scroll,         # track
        bordercolor=border,
        lightcolor=accent,
        darkcolor=accent,
        sliderlength=18,
        sliderrelief="flat",
    )
    style.map(
        "TScale",
        background=[("active", accent), ("!active", accent)],
        troughcolor=[("active", scroll), ("!active", scroll)],
    )
    apply_rounded_buttons(style, colors)
    root.after(50, lambda: set_titlebar_dark(root, dark))
    return bg, fg


def _set_window_titlebar_dark(window, enable: bool):
    if os.name != 'nt':
        return
    try:
        hwnd = window.winfo_id()
        GetParent = ctypes.windll.user32.GetParent
        parent = GetParent(hwnd)
        while parent:
            hwnd = parent
            parent = GetParent(hwnd)
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19
        BOOL = ctypes.c_int
        value = BOOL(1 if enable else 0)
        if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)) != 0:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass


raw_items = load_tracker_flowers()
if not raw_items:
    raw_items = load_last_parse()
items = raw_items
labels = [format_item(it) for it in items]

root = tk.Tk()
root.title("Mix Calculator" if not IS_STOCK_MODE else "Blend Calculator (stock)")
try:
    root.withdraw()
    root.attributes("-alpha", 0.0)
except Exception:
    pass
try:
    icon_path = resource_path("icon.ico")
    if os.path.exists(icon_path):
        root.iconbitmap(icon_path)
except Exception:
    pass

main = ttk.Frame(root, padding=10)
main.pack(fill="both", expand=True)

dark_mode = load_dark_mode_default()
bg, fg = apply_theme(root, dark_mode)

def _load_saved_geometry() -> None:
    try:
        cfg = load_tracker_config(CONFIG_FILE)
    except Exception:
        return
    key = "mixcalc_stock_geometry" if IS_STOCK_MODE else "mixcalc_geometry"
    geom = str(cfg.get(key) or "").strip()
    if geom:
        try:
            root.geometry(geom)
        except Exception:
            pass

def _save_geometry() -> None:
    try:
        cfg = load_tracker_config(CONFIG_FILE)
    except Exception:
        cfg = {}
    key = "mixcalc_stock_geometry" if IS_STOCK_MODE else "mixcalc_geometry"
    try:
        cfg[key] = root.winfo_geometry()
    except Exception:
        return
    try:
        save_tracker_config(CONFIG_FILE, cfg)
    except Exception:
        pass

def _close_and_save() -> None:
    try:
        _save_geometry()
    except Exception:
        pass
    try:
        root.destroy()
    except Exception:
        pass

_save_geometry_job = None
def _schedule_save_geometry(event=None) -> None:
    global _save_geometry_job
    try:
        if _save_geometry_job is not None:
            root.after_cancel(_save_geometry_job)
    except Exception:
        pass
    try:
        _save_geometry_job = root.after(300, _save_geometry)
    except Exception:
        pass

def _place_near_mouse() -> None:
    if os.environ.get("FT_MOUSE_LAUNCH") != "1":
        return
    try:
        x = root.winfo_pointerx()
        y = root.winfo_pointery()
        root.update_idletasks()
        w = root.winfo_reqwidth()
        h = root.winfo_reqheight()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        pos_x = min(max(0, x - w // 2), max(sw - w, 0))
        pos_y = min(max(0, y - h // 2), max(sh - h, 0))
        root.geometry(f"+{pos_x}+{pos_y}")
    except Exception:
        pass

def _show_root() -> None:
    try:
        _set_window_titlebar_dark(root, dark_mode)
    except Exception:
        pass
    try:
        root.deiconify()
        root.attributes("-alpha", 1.0)
        root.lift()
    except Exception:
        pass

if not items:
    ttk.Label(main, text="No stock found. Add stock in the tracker first.").pack(pady=10)
    ttk.Button(main, text="Close", command=_close_and_save).pack()
    _place_near_mouse()
    _show_root()
    root.mainloop()
    raise SystemExit

lists_frame = ttk.Frame(main)
lists_frame.pack(fill="x", expand=True, pady=(0, 8))

ttk.Label(lists_frame, text="Flower A").grid(row=0, column=0, sticky="w")
ttk.Label(lists_frame, text="Flower B").grid(row=0, column=1, sticky="w", padx=(12, 0))

combo_a = ttk.Combobox(lists_frame, values=labels, state="readonly")
combo_b = ttk.Combobox(lists_frame, values=labels, state="readonly")
combo_a.grid(row=1, column=0, sticky="we", padx=(0, 6))
combo_b.grid(row=1, column=1, sticky="we", padx=(6, 0))
def _clear_combo_selection(event=None):
    widget = getattr(event, "widget", None)
    if widget is None:
        return
    try:
        widget.selection_clear()
    except Exception:
        try:
            widget.tk.call(widget._w, "selection", "clear")
        except Exception:
            pass
    try:
        widget.icursor("end")
    except Exception:
        pass
combo_a.bind("<FocusOut>", _clear_combo_selection)
combo_a.bind("<<ComboboxSelected>>", _clear_combo_selection)
combo_b.bind("<FocusOut>", _clear_combo_selection)
combo_b.bind("<<ComboboxSelected>>", _clear_combo_selection)
lists_frame.columnconfigure(0, weight=1)
lists_frame.columnconfigure(1, weight=1)

if labels:
    combo_a.current(0)
    combo_b.current(1 if len(labels) > 1 else 0)
    # Try to auto-select a CBD-dominant option for B if available
    def is_cbd(item):
        try:
            return float(item.get("cbd_pct") or item.get("cbd") or 0) >= float(item.get("thc_pct") or item.get("thc") or 0)
        except Exception:
            return False
    cbd_indices = [idx for idx, it in enumerate(items) if is_cbd(it)]
    if cbd_indices:
        combo_b.current(cbd_indices[0])

controls = ttk.Frame(main)
controls.pack(fill="x", pady=8)

ttk.Label(controls, text="Total grams").grid(row=0, column=0, sticky="e", padx=(0, 6))
total_var = tk.StringVar(value="0.150")
ttk.Entry(controls, textvariable=total_var, width=8).grid(row=0, column=1, sticky="w")

ttk.Label(controls, text="Target THC:CBD").grid(row=0, column=2, sticky="e", padx=(12, 6))
ratio_a_var = tk.StringVar(value="1")
ratio_b_var = tk.StringVar(value="1")
ratio_frame = ttk.Frame(controls)
ratio_frame.grid(row=0, column=3, sticky="w")
ttk.Entry(ratio_frame, textvariable=ratio_a_var, width=4).pack(side="left")
ttk.Label(ratio_frame, text=":").pack(side="left", padx=(4, 4))
ttk.Entry(ratio_frame, textvariable=ratio_b_var, width=4).pack(side="left")
controls.columnconfigure(3, weight=1)

def _get_target_ratio():
    try:
        a = float(ratio_a_var.get())
        b = float(ratio_b_var.get())
    except Exception:
        messagebox.showinfo("Ratio", "Enter a valid THC:CBD ratio (e.g., 1 : 1 or 60 : 40).")
        return None
    if a <= 0 or b <= 0:
        messagebox.showinfo("Ratio", "Ratio values must be greater than zero.")
        return None
    return a / b

blend_name_var = tk.StringVar()
if IS_STOCK_MODE:
    ttk.Label(controls, text="Blend name").grid(row=1, column=0, sticky="e", padx=(0, 6), pady=(6, 0))
    ttk.Entry(controls, textvariable=blend_name_var, width=20).grid(
        row=1, column=1, columnspan=2, sticky="w", pady=(6, 0)
    )

actions = ttk.Frame(main)
actions.pack(fill="x", pady=8)

left_actions = ttk.Frame(actions)
left_actions.pack(side="left")
ttk.Button(left_actions, text="Swap A/B", command=swap_items).pack(side="left", padx=4)
ttk.Button(left_actions, text="Calculate", command=calculate).pack(side="left", padx=4)
ttk.Button(left_actions, text="Close", command=_close_and_save).pack(side="left", padx=4)

right_actions = ttk.Frame(actions)
right_actions.pack(side="right")
if IS_STOCK_MODE:
    ttk.Button(right_actions, text="Add to stock", command=add_to_stock).grid(row=0, column=0)
else:
    roa_var = tk.StringVar()
    ttk.Label(right_actions, text="Route").grid(row=0, column=0, sticky="e", padx=(0, 6))
    roa_combo = ttk.Combobox(right_actions, state="readonly", textvariable=roa_var, width=10)
    roa_combo.grid(row=0, column=1, sticky="e")
    roa_keys = list(roa_options.keys()) or ["Vaped"]
    roa_combo["values"] = roa_keys
    if roa_keys:
        roa_combo.current(0)
    roa_combo.bind("<FocusOut>", _clear_combo_selection)
    roa_combo.bind("<<ComboboxSelected>>", _clear_combo_selection)
    ttk.Button(right_actions, text="Log dose", command=log_dose).grid(row=0, column=2, padx=(10, 0))

result_var = tk.StringVar(value="Select two flowers, set total grams and THC:CBD target ratio, then Calculate.")
result_lbl = ttk.Label(main, textvariable=result_var, justify="left")
result_lbl.pack(fill="x", pady=(4, 0))

_load_saved_geometry()
_place_near_mouse()
_show_root()
root.bind("<Configure>", _schedule_save_geometry)
root.protocol("WM_DELETE_WINDOW", _close_and_save)
root.mainloop()
