import ctypes
import json
import os
import shutil
import sys
import tkinter as tk
from pathlib import Path
from tkinter import Tk, Toplevel, StringVar, BooleanVar, ttk, messagebox, filedialog
from theme import apply_style_theme, compute_colors, set_titlebar_dark
from logger import log_event
from config import load_library_config, save_library_config, load_tracker_config, save_tracker_config
from resources import resource_path


APP_ROOT = Path(os.getenv("APPDATA", Path.home())) / "FlowerTrack"
DATA_DIR = APP_ROOT / "data"
APP_ROOT.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATA_FILE = DATA_DIR / "library_data.json"
TRACKER_CONFIG_FILE = Path(os.getenv("APPDATA", Path.home())) / "FlowerTrack" / "flowertrack_config.json"


def load_entries() -> list[dict]:
    """Load entries from disk if the JSON file exists."""
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            messagebox.showwarning("Load Warning", f"Could not read {DATA_FILE.name}, starting with an empty list.")
    return []


def save_entries(entries: list[dict]) -> None:
    """Persist entries to disk."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATA_FILE.with_suffix(DATA_FILE.suffix + ".tmp")
    if DATA_FILE.exists():
        try:
            shutil.copy2(DATA_FILE, DATA_FILE.with_suffix(DATA_FILE.suffix + ".bak"))
        except Exception:
            pass
    tmp.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    tmp.replace(DATA_FILE)


def load_settings() -> dict:
    return load_library_config(TRACKER_CONFIG_FILE)


def save_settings(settings: dict) -> None:
    save_library_config(TRACKER_CONFIG_FILE, settings)


def _load_tracker_dark_mode(default: bool = True) -> bool:
    try:
        cfg = load_tracker_config(TRACKER_CONFIG_FILE)
        if isinstance(cfg, dict) and "dark_mode" in cfg:
            return bool(cfg.get("dark_mode", default))
    except Exception:
        pass
    return default


def _save_tracker_dark_mode(enabled: bool) -> None:
    try:
        cfg = load_tracker_config(TRACKER_CONFIG_FILE)
        if not isinstance(cfg, dict):
            cfg = {}
        cfg["dark_mode"] = bool(enabled)
        save_tracker_config(TRACKER_CONFIG_FILE, cfg)
    except Exception:
        pass


def _resource_path(filename: str) -> str:
    return resource_path(filename)


class FlowerLibraryApp:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("Medical Cannabis Flower Library")
        try:
            self.root.iconbitmap(_resource_path('icon3.ico'))
        except Exception:
            pass

        self.entries: list[dict] = load_entries()
        self.settings = load_settings()
        self.window_geometry = self.settings.get("window_geometry", "")
        shared_dark = _load_tracker_dark_mode(self.settings.get("dark_mode", True))
        self.is_dark = BooleanVar(value=shared_dark)
        self.windows: list = [self.root]
        self.sort_state: dict[str, bool] = {}
        self._geometry_save_job = None

        self.text_fields = ["brand", "cultivator", "packager", "strain"]
        self.float_fields = ["thc", "cbd", "price"]
        self.rating_fields = ["taste", "smell", "strength", "effects", "value"]

        self.style = ttk.Style(self.root)
        self.apply_theme()
        # Ensure title bar matches theme once window is realized
        self.root.after(50, lambda: self._apply_titlebar_dark())
        self.root.bind("<Map>", lambda _e: self._schedule_titlebar_updates(self.root))
        self.root.bind("<Visibility>", lambda _e: self._schedule_titlebar_updates(self.root))
        self.root.bind("<FocusIn>", lambda _e: self._schedule_titlebar_updates(self.root))
        self._schedule_titlebar_updates(self.root)

        self._build_topbar()
        self._build_table()
        self._build_buttons()
        self.refresh_table()
        if self.window_geometry:
            try:
                self.root.geometry(self.window_geometry)
            except Exception:
                pass
        self.root.bind("<Configure>", self._schedule_geometry_save)

    def apply_theme(self) -> None:
        colors = compute_colors(self.is_dark.get())
        base = colors["bg"]
        panel = colors["ctrl_bg"]
        entry_bg = colors["ctrl_bg"]
        text_color = colors["fg"]
        accent = colors["accent"]
        border = colors["ctrl_bg"]
        selected_bg = colors["accent"]
        selected_fg = "#ffffff"
        cursor = text_color

        self.root.configure(bg=base)
        self.current_base_color = base

        apply_style_theme(self.style, colors)
        font_body = ("", 10)
        self.style.configure("Topbar.TFrame", background=panel)
        self.style.configure("TLabel", background=base, foreground=text_color, font=font_body)
        self.style.configure("Topbar.TLabel", background=panel, foreground=text_color, font=font_body)
        self.style.configure(
            "TButton",
            font=font_body,
        )
        self.style.configure(
            "TEntry",
            background=entry_bg,
            foreground=text_color,
            fieldbackground=entry_bg,
            insertcolor=cursor,
        )
        self.style.configure(
            "TSpinbox",
            background=entry_bg,
            foreground=text_color,
            fieldbackground=entry_bg,
            insertcolor=cursor,
        )
        self.style.configure(
            "Treeview",
            background=base,
            fieldbackground=base,
            foreground=text_color,
            bordercolor=border,
            font=font_body,
        )
        self.style.map(
            "Treeview",
            background=[("selected", selected_bg)],
            foreground=[("selected", selected_fg)],
        )
        self.style.configure(
            "Treeview.Heading",
            background=panel,
            foreground=text_color,
            font=font_body,
        )
        self.style.map(
            "Treeview.Heading",
            background=[("active", accent)],
            foreground=[("active", "#ffffff")],
        )
        self.style.configure("TCheckbutton", background=base, foreground=text_color)
        self.style.map(
            "TCheckbutton",
            background=[("active", accent)],
            foreground=[("active", "#ffffff")],
        )
        self.root.option_add("*TCombobox*Listbox*Background", entry_bg)
        self.root.option_add("*TCombobox*Listbox*Foreground", text_color)
        self.root.option_add("*TCombobox*Listbox*selectBackground", accent)
        self.root.option_add("*TCombobox*Listbox*selectForeground", "#ffffff")

        if hasattr(self, "tree"):
            self.tree.tag_configure("odd", background=panel)
            self.tree.tag_configure("even", background=base)

        for window in self.windows:
            try:
                window.configure(bg=base)
            except Exception:
                pass

    def _build_topbar(self) -> None:
        container = ttk.Frame(self.root, padding=(10, 6), style="Topbar.TFrame")
        container.pack(fill="x")
        ttk.Label(container, text="Flower Library", style="Topbar.TLabel").pack(side="left")

    def _build_table(self) -> None:
        columns = (
            "brand",
            "strain",
            "cultivator",
            "packager",
            "thc",
            "cbd",
            "price",
            "smell",
            "taste",
            "effects",
            "strength",
            "value",
            "overall",
        )
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings", height=14)
        heading_labels = {
            "thc": "THC %",
            "cbd": "CBD %",
            "price": "Price /g",
            "overall": "Overall",
        }
        for col in columns:
            heading = heading_labels.get(col, col.capitalize())
            self.tree.heading(col, text=heading, command=lambda c=col: self.sort_by(c))
            width = self.settings.get("column_widths", {}).get(col, 90)
            self.tree.column(col, width=width, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_button_release)

    def _build_buttons(self) -> None:
        container = ttk.Frame(self.root, padding=10)
        container.pack(fill="x")
        ttk.Button(container, text="Add Flower", command=self.add_flower).pack(side="left", padx=4)
        ttk.Button(container, text="Edit Flower", command=self.edit_flower).pack(side="left", padx=4)
        ttk.Button(container, text="Delete Flower", command=self.delete_selected).pack(side="left", padx=4)
        ttk.Button(container, text="Export Library", command=self.export_library).pack(side="right", padx=4)

    def _make_form_vars(self, initial: dict | None = None) -> dict[str, StringVar]:
        initial = initial or {}
        vars_map: dict[str, StringVar] = {}
        for field in self.text_fields + self.float_fields + self.rating_fields:
            if field in self.rating_fields:
                default = str(initial.get(field, 5))
            else:
                default = str(initial.get(field, ""))
            vars_map[field] = StringVar(value=default)
        return vars_map

    def _validated_entry(self, form_vars: dict[str, StringVar]) -> dict | None:
        entry: dict[str, str | float | int] = {}
        for key in self.text_fields:
            entry[key] = form_vars[key].get().strip()

        for key in self.float_fields:
            raw = form_vars[key].get().strip()
            if raw:
                try:
                    entry[key] = round(float(raw), 2)
                except ValueError:
                    messagebox.showerror("Validation Error", f"{key.upper()} must be a number.")
                    return None
            else:
                entry[key] = ""

        for key in self.rating_fields:
            raw = form_vars[key].get().strip() or "0"
            try:
                value = float(raw)
                if not 1 <= value <= 10:
                    raise ValueError
                entry[key] = round(value, 1)
            except ValueError:
                messagebox.showerror("Validation Error", f"{key.capitalize()} rating must be between 1 and 10.")
                return None

        entry["overall"] = self._compute_overall(entry)
        return entry

    def _compute_overall(self, entry: dict) -> float:
        total = sum(entry.get(field, 0) or 0 for field in self.rating_fields)
        return round(total / len(self.rating_fields), 2)

    def _build_form_window(self, mode: str, index: int | None = None) -> None:
        title = "Add Flower" if mode == "add" else "Edit Flower"
        initial = self.entries[index] if index is not None else {}
        form_vars = self._make_form_vars(initial)

        window = Toplevel(self.root)
        window.title(title)
        try:
            window.iconbitmap(_resource_path('icon3.ico'))
        except Exception:
            pass
        window.transient(self.root)
        window.grab_set()
        self.windows.append(window)
        self.apply_theme()
        self._prepare_toplevel(window)
        self._set_window_titlebar_dark(window, self.is_dark.get())
        self.root.after(50, lambda w=window: self._set_window_titlebar_dark(w, self.is_dark.get()))
        self.root.after(200, lambda w=window: self._set_window_titlebar_dark(w, self.is_dark.get()))
        window.bind("<Map>", lambda _evt, w=window: self._set_window_titlebar_dark(w, self.is_dark.get()))
        window.bind("<Visibility>", lambda _evt, w=window: self._schedule_titlebar_updates(w))
        window.bind("<FocusIn>", lambda _evt, w=window: self._schedule_titlebar_updates(w))
        self._schedule_titlebar_updates(window)
        try:
            window.wm_attributes("-theme", "dark")
        except Exception:
            pass

        container = ttk.Frame(window, padding=12)
        container.pack(fill="both", expand=True)

        row = 0
        for label_text, key in [
            ("Brand", "brand"),
            ("Cultivator", "cultivator"),
            ("Packager", "packager"),
            ("Strain", "strain"),
        ]:
            ttk.Label(container, text=label_text).grid(row=row, column=0, sticky="w", padx=4, pady=3)
            ttk.Entry(container, textvariable=form_vars[key], width=32).grid(row=row, column=1, sticky="ew", padx=4, pady=3)
            row += 1

        for label_text, key in [("THC %", "thc"), ("CBD %", "cbd"), ("Price /g", "price")]:
            ttk.Label(container, text=label_text).grid(row=row, column=0, sticky="w", padx=4, pady=3)
            ttk.Entry(container, textvariable=form_vars[key], width=12).grid(row=row, column=1, sticky="w", padx=4, pady=3)
            row += 1

        for label_text, key in [
            ("Taste (1-10)", "taste"),
            ("Smell (1-10)", "smell"),
            ("Strength (1-10)", "strength"),
            ("Effects (1-10)", "effects"),
            ("Value (1-10)", "value"),
        ]:
            ttk.Label(container, text=label_text).grid(row=row, column=0, sticky="w", padx=4, pady=3)
            ttk.Spinbox(
                container,
                from_=1.0,
                to=10.0,
                increment=0.1,
                format="%.1f",
                textvariable=form_vars[key],
                width=6,
            ).grid(row=row, column=1, sticky="w", padx=4, pady=3)
            row += 1

        button_bar = ttk.Frame(container)
        button_bar.grid(row=row, column=0, columnspan=2, pady=(10, 0))

        def close_window() -> None:
            if window in self.windows:
                self.windows.remove(window)
            window.destroy()
            self.apply_theme()
            _save_tracker_dark_mode(self.is_dark.get())

        def submit() -> None:
            entry = self._validated_entry(form_vars)
            if entry is None:
                return
            if mode == "add":
                self.entries.append(entry)
            else:
                if index is not None:
                    self.entries[index] = entry
            self.refresh_table()
            self._persist_entries()
            close_window()

        ttk.Button(button_bar, text="Save", command=submit).pack(side="left", padx=4)
        ttk.Button(button_bar, text="Cancel", command=close_window).pack(side="left", padx=4)

        window.protocol("WM_DELETE_WINDOW", close_window)
        # Prepare after layout to avoid flash/white title
        self._prepare_toplevel(window)

    def add_flower(self) -> None:
        self._build_form_window(mode="add")

    def edit_flower(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Edit Flower", "Please select a row to edit.")
            return
        index = self.tree.index(selection[0])
        self._build_form_window(mode="edit", index=index)

    def delete_selected(self) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        index = self.tree.index(selection[0])
        del self.entries[index]
        self.refresh_table()
        self._persist_entries()

    def export_library(self) -> None:
        """Export current library to a JSON file."""
        path = filedialog.asksaveasfilename(
            title="Export flower library",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            Path(path).write_text(json.dumps(self.entries, indent=2), encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("Export failed", f"Could not write file:\n{exc}")
        else:
            messagebox.showinfo("Exported", f"Library exported to:\n{path}")

    def refresh_table(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        changed = False
        for entry in self.entries:
            if "overall" not in entry:
                entry["overall"] = self._compute_overall(entry)
                changed = True
            values = [
                entry.get("brand", ""),
                entry.get("strain", ""),
                entry.get("cultivator", ""),
                entry.get("packager", ""),
                entry.get("thc", ""),
                entry.get("cbd", ""),
                entry.get("price", ""),
                entry.get("smell", ""),
                entry.get("taste", ""),
                entry.get("effects", ""),
                entry.get("strength", ""),
                entry.get("value", ""),
                entry.get("overall", ""),
            ]
            self.tree.insert("", "end", values=values)

        if changed:
            self._persist_entries()

    def _persist_entries(self) -> None:
        save_entries(self.entries)
        self._persist_settings()

    def _persist_settings(self) -> None:
        save_settings(self.settings)

    def _schedule_geometry_save(self, _event=None) -> None:
        if self._geometry_save_job is not None:
            try:
                self.root.after_cancel(self._geometry_save_job)
            except Exception:
                pass
        self._geometry_save_job = self.root.after(300, self._persist_geometry)

    def _persist_geometry(self) -> None:
        try:
            self.settings["window_geometry"] = self.root.geometry()
            self._persist_settings()
        finally:
            self._geometry_save_job = None

    def sort_by(self, column: str) -> None:
        ascending = self.sort_state.get(column, True)
        numeric_cols = {"thc", "cbd", "price", "smell", "taste", "effects", "strength", "value", "overall"}

        def sort_key(item: dict):
            value = item.get(column, "")
            if column in numeric_cols:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return -float("inf") if ascending else float("inf")
            return str(value).lower()

        self.entries.sort(key=sort_key, reverse=not ascending)
        self.sort_state[column] = not ascending
        self.refresh_table()

    def on_toggle_dark_mode(self) -> None:
        self.settings["dark_mode"] = self.is_dark.get()
        self._persist_settings()
        self.apply_theme()
        _save_tracker_dark_mode(self.is_dark.get())
        self._apply_titlebar_dark()

    def on_tree_button_release(self, event) -> None:
        if self.tree.identify_region(event.x, event.y) in {"separator", "heading"}:
            widths = {col: self.tree.column(col, option="width") for col in self.tree["columns"]}
            if widths != self.settings.get("column_widths", {}):
                self.settings["column_widths"] = widths
                self._persist_settings()

    def _apply_titlebar_dark(self) -> None:
        """Schedule dark title bar for all tracked windows after they are realized."""
        for window in list(self.windows):
            try:
                self._set_window_titlebar_dark(window, self.is_dark.get())
                self._set_titlebar_dark_native(window, self.is_dark.get())
            except Exception:
                continue
            self._schedule_titlebar_updates(window)

    def _prepare_toplevel(self, window: Toplevel) -> None:
        """Apply dark title bar and bg to a child window before showing."""
        try:
            window.withdraw()
            window.configure(bg=getattr(self, "current_base_color", "#121212"))
            window.update_idletasks()
            self._place_window_at_pointer(window)
            self._set_window_titlebar_dark(window, self.is_dark.get())
            window.deiconify()
            window.lift()
            window.update_idletasks()
            try:
                window.update()
            except Exception:
                pass
            self._set_window_titlebar_dark(window, self.is_dark.get())
            self.root.after(50, lambda w=window: self._set_window_titlebar_dark(w, self.is_dark.get()))
            self.root.after(200, lambda w=window: self._set_window_titlebar_dark(w, self.is_dark.get()))
            self._schedule_titlebar_updates(window)
            try:
                window.wm_attributes("-theme", "dark")
            except Exception:
                pass
        except Exception:
            try:
                self._set_window_titlebar_dark(window, self.is_dark.get())
            except Exception:
                pass

    def _set_window_titlebar_dark(self, window, enable: bool) -> None:
        """On Windows 10/11, ask DWM for a dark title bar to match the theme."""
        if os.name != "nt":
            return
        try:
            self._dwm_set_titlebar(window, enable)
        except Exception:
            pass

    def _set_titlebar_dark_native(self, window, enable: bool) -> None:
        if os.name != "nt":
            return
        try:
            hwnd = window.winfo_id()
            GetAncestor = ctypes.windll.user32.GetAncestor
            GA_ROOT = 2
            GA_ROOTOWNER = 3
            root = GetAncestor(hwnd, GA_ROOT)
            if root:
                hwnd = root
            root_owner = GetAncestor(hwnd, GA_ROOTOWNER)
            if root_owner:
                hwnd = root_owner
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19
            value = ctypes.c_int(1 if enable else 0)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)
            ) != 0:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1, ctypes.byref(value), ctypes.sizeof(value)
                )
        except Exception:
            pass

    def _schedule_titlebar_updates(self, window) -> None:
        for delay in (60, 200, 500, 900, 1500):
            try:
                window.after(delay, lambda w=window: self._apply_titlebar_for_window(w))
            except Exception:
                pass

    def _apply_titlebar_for_window(self, window) -> None:
        try:
            window.update_idletasks()
        except Exception:
            pass
        try:
            set_titlebar_dark(window, self.is_dark.get())
        except Exception:
            pass
        try:
            result = self._dwm_set_titlebar(window, self.is_dark.get())
        except Exception:
            result = None
        try:
            self._set_window_titlebar_dark(window, self.is_dark.get())
        except Exception:
            pass
        try:
            self._set_titlebar_dark_native(window, self.is_dark.get())
        except Exception:
            pass
        try:
            if result and not getattr(window, "_titlebar_logged", False):
                setattr(window, "_titlebar_logged", True)
                log_event("flowerlibrary.titlebar", result, file_name="app.log")
        except Exception:
            pass

    def _dwm_set_titlebar(self, window, enable: bool) -> dict:
        hwnd = window.winfo_id()
        value = ctypes.c_int(1 if enable else 0)
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19

        rc20_hwnd = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)
        )
        rc19_hwnd = 0
        if rc20_hwnd != 0:
            rc19_hwnd = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1, ctypes.byref(value), ctypes.sizeof(value)
            )

        GetAncestor = ctypes.windll.user32.GetAncestor
        GA_ROOT = 2
        GA_ROOTOWNER = 3
        root = GetAncestor(hwnd, GA_ROOT) or 0
        root_owner = GetAncestor(hwnd, GA_ROOTOWNER) or 0
        target_root = root or hwnd

        rc20_root = None
        rc19_root = None
        if target_root and target_root != hwnd:
            rc20_root = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                target_root, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)
            )
            rc19_root = 0
            if rc20_root != 0:
                rc19_root = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    target_root, DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1, ctypes.byref(value), ctypes.sizeof(value)
                )

        rc20_owner = None
        rc19_owner = None
        if root_owner and root_owner not in {hwnd, target_root}:
            rc20_owner = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                root_owner, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)
            )
            rc19_owner = 0
            if rc20_owner != 0:
                rc19_owner = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    root_owner, DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1, ctypes.byref(value), ctypes.sizeof(value)
                )

        return {
            "hwnd": int(hwnd),
            "root": int(root) if root else None,
            "owner": int(root_owner) if root_owner else None,
            "enable": bool(enable),
            "rc20_hwnd": int(rc20_hwnd),
            "rc19_hwnd": int(rc19_hwnd),
            "rc20_root": None if rc20_root is None else int(rc20_root),
            "rc19_root": None if rc19_root is None else int(rc19_root),
            "rc20_owner": None if rc20_owner is None else int(rc20_owner),
            "rc19_owner": None if rc19_owner is None else int(rc19_owner),
        }

    def _place_window_at_pointer(self, win: Toplevel) -> None:
        """Place window with its top-left near the current mouse pointer."""
        try:
            x = self.root.winfo_pointerx()
            y = self.root.winfo_pointery()
            win.update_idletasks()
            width = win.winfo_reqwidth()
            height = win.winfo_reqheight()
            x_pos = max(0, x - width - 10)
            y_pos = max(0, y - height - 10)
            win.geometry(f"+{x_pos}+{y_pos}")
        except Exception:
            pass
def main() -> None:
    root = Tk()
    FlowerLibraryApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
