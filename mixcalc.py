
import json
import os
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import ctypes


APP_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "FlowerTrack")
DATA_DIR = Path(APP_DIR) / "data"
CONFIG_FILE = Path(APP_DIR) / "flowertrack_config.json"

def resolve_tracker_file() -> Path:
    try:
        if CONFIG_FILE.exists():
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(cfg.get("tracker"), dict):
                cfg = cfg.get("tracker", {})
            data_path = cfg.get("data_path") if isinstance(cfg, dict) else None
            if data_path:
                return Path(data_path)
    except Exception:
        pass
    return DATA_DIR / "tracker_data.json"

TRACKER_FILE = resolve_tracker_file()
LAST_PARSE_FILE = DATA_DIR / "last_parse.json"


roa_options = {"Vaped": 0.6, "Smoked": 0.3, "Eaten": 0.1}


def load_roa_options():
    global roa_options
    try:
        if CONFIG_FILE.exists():
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(cfg.get("tracker"), dict):
                cfg = cfg.get("tracker", {})
            if isinstance(cfg.get("roa_options"), dict):
                roa_options = {k: float(v) for k, v in cfg["roa_options"].items()}
    except Exception:
        pass

def load_tracker_flowers() -> list[dict]:
    """Return flowers from tracker data with grams_remaining > 0."""
    try:
        if TRACKER_FILE.exists():
            data = json.loads(TRACKER_FILE.read_text(encoding="utf-8"))
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
        if CONFIG_FILE.exists():
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(cfg.get("ui"), dict) and "dark_mode" in cfg.get("ui", {}):
                return bool(cfg["ui"].get("dark_mode", True))
            if isinstance(cfg.get("tracker"), dict) and "dark_mode" in cfg.get("tracker", {}):
                return bool(cfg["tracker"].get("dark_mode", True))
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
    target_ratio = ratio_var.get()
    item_a = items[idx_a]
    item_b = items[idx_b]
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

    name_a = item_a.get("name")
    name_b = item_b.get("name")

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
    root.destroy()




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
    if not blend_name:
        messagebox.showinfo("Blend name", "Please enter a name for the blend.")
        return
    target_ratio = ratio_var.get()
    item_a = items[idx_a]
    item_b = items[idx_b]
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

    name_a = item_a.get("name")
    name_b = item_b.get("name")

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
    root.destroy()

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

    target_ratio = ratio_var.get()
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
    bg = "#111" if dark else "#f7f7f7"
    fg = "#eee" if dark else "#111"
    ctrl_bg = "#222" if dark else "#e6e6e6"
    accent = "#7cc7ff" if dark else "#0b79d0"
    border = "#2a2a2a" if dark else "#cccccc"
    entry_bg = "#1a1a1a" if dark else "#ffffff"
    scroll = "#2b2b2b" if dark else "#dcdcdc"
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("TFrame", background=bg)
    style.configure("TLabel", background=bg, foreground=fg)
    style.configure(
        "TButton",
        background=ctrl_bg,
        foreground=fg,
        bordercolor=border,
        focusthickness=1,
        focuscolor=accent,
        padding=6,
    )
    style.map(
        "TButton",
        background=[("active", accent), ("pressed", accent)],
        foreground=[("active", bg if dark else "#fff"), ("pressed", bg if dark else "#fff")],
    )
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
    root.option_add("*TCombobox*Listbox*Background", entry_bg)
    root.option_add("*TCombobox*Listbox*Foreground", fg)
    root.option_add("*TCombobox*Listbox*selectBackground", accent if dark else "#0b79d0")
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
    root.after(50, lambda: _set_window_titlebar_dark(root, dark))
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
# Best-effort place near mouse if requested by parent
if os.environ.get("FT_MOUSE_LAUNCH") == "1":
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

main = ttk.Frame(root, padding=10)
main.pack(fill="both", expand=True)

dark_mode = load_dark_mode_default()
bg, fg = apply_theme(root, dark_mode)

if not items:
    ttk.Label(main, text="No stock found. Add stock in the tracker first.").pack(pady=10)
    ttk.Button(main, text="Close", command=root.destroy).pack()
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

ratio_var = tk.DoubleVar(value=1.0)
ttk.Label(controls, text="Target THC:CBD (X:1)").grid(row=0, column=2, sticky="e", padx=(12, 6))
ratio_scale = ttk.Scale(controls, from_=0.1, to=30.0, orient="horizontal", variable=ratio_var, length=360)
ratio_scale.grid(row=0, column=3, sticky="we")
controls.columnconfigure(3, weight=1)
ratio_val_lbl = ttk.Label(controls, text="1.0:1")
ratio_val_lbl.grid(row=0, column=4, padx=(6, 0))

def _update_ratio_label(*_):
    r = ratio_var.get()
    ratio_val_lbl.config(text=f"{r:.1f}:1")

ratio_var.trace_add("write", _update_ratio_label)

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
ttk.Button(left_actions, text="Close", command=root.destroy).pack(side="left", padx=4)

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
    ttk.Button(right_actions, text="Log dose", command=log_dose).grid(row=0, column=2, padx=(10, 0))

result_var = tk.StringVar(value="Select two flowers, set total grams and THC:CBD target ratio, then Calculate.")
result_lbl = ttk.Label(main, textvariable=result_var, justify="left")
result_lbl.pack(fill="x", pady=(4, 0))

root.mainloop()
