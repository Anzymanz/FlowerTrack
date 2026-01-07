import json
import os
import platform
import ctypes
import sys
import tkinter as tk
from pathlib import Path
from tkinter import Tk, Toplevel, StringVar, BooleanVar, ttk, messagebox, filedialog


APP_DIR = Path(os.getenv("APPDATA", Path.home())) / "FlowerTrack" / "data"
APP_DIR.mkdir(parents=True, exist_ok=True)
DATA_FILE = APP_DIR / "library_data.json"
SETTINGS_FILE = APP_DIR / "library_config.json"
LEGACY_APP_DATA_FILE = APP_DIR / "library.json"
LEGACY_APP_SETTINGS_FILE = APP_DIR / "settings.json"
LEGACY_DATA_FILE = Path(__file__).with_name("library.json")
LEGACY_SETTINGS_FILE = Path(__file__).with_name("settings.json")
TRACKER_CONFIG_FILE = Path(os.getenv("APPDATA", Path.home())) / "FlowerTrack" / "tracker_config.json"


def load_entries() -> list[dict]:
    """Load entries from disk if the JSON file exists."""
    sources = [
        DATA_FILE,
        LEGACY_APP_DATA_FILE,  # previous appdata filename
        LEGACY_DATA_FILE,      # script folder legacy
    ]
    for source in sources:
        if source.exists():
            try:
                data = json.loads(source.read_text(encoding="utf-8"))
                if source != DATA_FILE:
                    save_entries(data)
                return data
            except (json.JSONDecodeError, OSError):
                messagebox.showwarning("Load Warning", f"Could not read {source.name}, starting with an empty list.")
    return []


def save_entries(entries: list[dict]) -> None:
    """Persist entries to disk."""
    DATA_FILE.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def load_settings() -> dict:
    for source in (SETTINGS_FILE, LEGACY_APP_SETTINGS_FILE, LEGACY_SETTINGS_FILE):
        if source.exists():
            try:
                data = json.loads(source.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    if source != SETTINGS_FILE:
                        save_settings(data)
                    return data
            except (json.JSONDecodeError, OSError):
                pass
    return {"dark_mode": True, "column_widths": {}}


def save_settings(settings: dict) -> None:
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def _load_tracker_dark_mode(default: bool = True) -> bool:
    try:
        if TRACKER_CONFIG_FILE.exists():
            data = json.loads(TRACKER_CONFIG_FILE.read_text(encoding="utf-8"))
            if "dark_mode" in data:
                return bool(data["dark_mode"])
    except Exception:
        pass
    return default


def _save_tracker_dark_mode(enabled: bool) -> None:
    try:
        cfg = {}
        if TRACKER_CONFIG_FILE.exists():
            cfg = json.loads(TRACKER_CONFIG_FILE.read_text(encoding="utf-8")) or {}
        cfg["dark_mode"] = bool(enabled)
        TRACKER_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        TRACKER_CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception:
        pass


def _resource_path(filename: str) -> str:
    base_path = getattr(sys, "_MEIPASS", None) or os.getcwd()
    asset_path = os.path.join(base_path, 'assets', filename)
    if os.path.exists(asset_path):
        return asset_path
    return os.path.join(base_path, filename)


def _set_title_bar_dark(window, dark: bool) -> None:
    """Best-effort request for a dark title bar on Windows 10/11."""
    if platform.system() != "Windows":
        return
    try:
        hwnd = window.winfo_id()
        # Walk up to top-level in case Tk returns a child
        GetParent = ctypes.windll.user32.GetParent
        parent = GetParent(hwnd)
        while parent:
            hwnd = parent
            parent = GetParent(hwnd)
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19
        BOOL = ctypes.c_int
        value = BOOL(1 if dark else 0)
        size = ctypes.sizeof(value)
        if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), size) != 0:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1, ctypes.byref(value), size)
    except Exception:
        # If it fails, ignore; default title bar will be used.
        pass


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
        shared_dark = _load_tracker_dark_mode(self.settings.get("dark_mode", True))
        self.is_dark = BooleanVar(value=shared_dark)
        self.windows: list = [self.root]
        self.sort_state: dict[str, bool] = {}

        self.text_fields = ["brand", "cultivator", "packager", "strain"]
        self.float_fields = ["thc", "cbd", "price"]
        self.rating_fields = ["taste", "smell", "strength", "effects", "value"]

        self.style = ttk.Style(self.root)
        self._init_palette()
        self.apply_theme()
        # Ensure title bar matches theme once window is realized
        self.root.after(50, lambda: self._apply_titlebar_dark())

        self._build_topbar()
        self._build_table()
        self._build_buttons()
        self.refresh_table()

    def _init_palette(self) -> None:
        # Match FlowerTracker look-and-feel
        self.dark_palette = {
            "base": "#121212",
            "panel": "#1c1c1c",
            "entry": "#222222",
            "text": "#f5f5f5",
            "subtext": "#c0c0c0",
            "accent": "#4a90e2",
            "border": "#2c2c2c",
            "selected_bg": "#4a90e2",
            "selected_fg": "#ffffff",
            "cursor": "#ffffff",
        }
        self.light_palette = {
            "base": "#f5f5f5",
            "panel": "#ffffff",
            "entry": "#ffffff",
            "text": "#111111",
            "subtext": "#444444",
            "accent": "#2f6fed",
            "border": "#d0d0d0",
            "selected_bg": "#2f6fed",
            "selected_fg": "#ffffff",
            "cursor": "#111111",
        }

    def apply_theme(self) -> None:
        """Apply the chosen palette to all widgets and windows."""
        palette = self.dark_palette if self.is_dark.get() else self.light_palette
        base = palette["base"]
        panel = palette["panel"]
        entry_bg = palette["entry"]
        text = palette["text"]
        accent = palette["accent"]
        border = palette["border"]
        selected_bg = palette["selected_bg"]
        selected_fg = palette["selected_fg"]
        cursor = palette["cursor"]

        self.root.configure(bg=base)
        self.current_base_color = base

        self.style.theme_use("clam")
        font_body = ("", 10)
        self.style.configure("TFrame", background=base)
        self.style.configure("Topbar.TFrame", background=panel)
        self.style.configure("TLabel", background=base, foreground=text, font=font_body)
        self.style.configure("Topbar.TLabel", background=panel, foreground=text, font=font_body)
        self.style.configure(
            "TButton",
            background=panel,
            foreground=text,
            bordercolor=border,
            focusthickness=1,
            font=font_body,
        )
        self.style.map(
            "TButton",
            background=[("active", accent), ("pressed", accent)],
            foreground=[("active", "#ffffff"), ("pressed", "#ffffff")],
            relief=[("pressed", "sunken")],
        )
        self.style.configure(
            "Treeview",
            background=panel,
            foreground=text,
            fieldbackground=panel,
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
            background=border,
            foreground=text,
            relief="flat",
            font=font_body,
        )
        self.style.map(
            "Treeview.Heading",
            background=[("active", accent)],
            foreground=[("active", "#ffffff")],
        )
        self.style.configure(
            "TEntry",
            fieldbackground=entry_bg,
            foreground=text,
            background=entry_bg,
            insertcolor=cursor,
            font=font_body,
        )
        self.style.configure(
            "TSpinbox",
            fieldbackground=entry_bg,
            foreground=text,
            background=entry_bg,
            insertcolor=cursor,
            font=font_body,
        )
        self.style.configure("TCheckbutton", background=base, foreground=text, font=font_body)
        self.style.configure("Topbar.TCheckbutton", background=panel, foreground=text, font=font_body)
        self.style.map(
            "TCheckbutton",
            background=[("active", accent)],
            foreground=[("active", "#ffffff")],
        )

        for window in list(self.windows):
            try:
                window.configure(bg=base)
                self._set_dark_title_bar(self.is_dark.get(), target=window)
            except Exception:
                continue
        # Apply dark title bar after windows are realized
        self._apply_titlebar_dark()
        try:
            self.root.option_add("*insertBackground", cursor)
            self.root.option_add("*Entry.insertBackground", cursor)
            self.root.option_add("*Text.insertBackground", cursor)
            self.root.option_add("*TEntry.insertBackground", cursor)
            self.root.option_add("*TCombobox*Entry*insertBackground", cursor)
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
        self._force_dark_title_bar(window)

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
        if platform.system() != "Windows":
            return
        for window in list(self.windows):
            try:
                self._force_dark_title_bar(window)
            except Exception:
                continue

    def _force_dark_title_bar(self, window: Toplevel) -> None:
        """Best-effort dark title bar with retry while window realizes."""
        if platform.system() != "Windows":
            return
        try:
            self._set_dark_title_bar(self.is_dark.get(), target=window)
        except Exception:
            pass
        try:
            window.after(80, lambda w=window: self._set_dark_title_bar(self.is_dark.get(), target=w))
            window.after(180, lambda w=window: self._set_dark_title_bar(self.is_dark.get(), target=w))
        except Exception:
            pass

    def _prepare_toplevel(self, window: Toplevel) -> None:
        """Apply dark title bar and bg to a child window before showing."""
        try:
            window.withdraw()
            window.configure(bg=getattr(self, "current_base_color", "#121212"))
            window.update_idletasks()
            self._place_window_at_pointer(window)
            self._set_dark_title_bar(self.is_dark.get(), target=window)
            window.deiconify()
            window.lift()
            window.update_idletasks()
            self._force_dark_title_bar(window)
        except Exception:
            try:
                self._force_dark_title_bar(window)
            except Exception:
                pass

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
    def _set_dark_title_bar(self, enable: bool, target: tk.Tk | Toplevel | None = None) -> None:
        """On Windows 10/11, ask DWM for a dark title bar to match the theme."""
        if os.name != "nt":
            return
        try:
            widget = target or self.root
            hwnd = widget.winfo_id()
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19
            BOOL = ctypes.c_int
            value = BOOL(1 if enable else 0)
            def apply(handle: int) -> None:
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    handle, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)
                ) != 0:
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        handle,
                        DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1,
                        ctypes.byref(value),
                        ctypes.sizeof(value),
                    )

            # Apply to the window itself
            apply(hwnd)
            # Also walk parents (some Tk windows need parent hwnd to take the flag)
            try:
                get_parent = ctypes.windll.user32.GetParent
                parent = get_parent(hwnd)
                seen = set()
                while parent and parent not in seen:
                    seen.add(parent)
                    apply(parent)
                    parent = get_parent(parent)
            except Exception:
                pass
        except Exception:
            pass


def main() -> None:
    root = Tk()
    FlowerLibraryApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
