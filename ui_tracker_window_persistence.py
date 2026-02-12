from __future__ import annotations

import tkinter as tk


def persist_tree_widths(app) -> None:
    try:
        if hasattr(app, "stock_tree"):
            app.stock_column_widths = {
                col: int(app.stock_tree.column(col, option="width")) for col in app.stock_tree["columns"]
            }
        if hasattr(app, "log_tree"):
            app.log_column_widths = {
                col: int(app.log_tree.column(col, option="width")) for col in app.log_tree["columns"]
            }
    except Exception:
        pass


def on_root_configure(app, event: tk.Event) -> None:
    if event.widget is not app.root:
        return
    if app._geometry_save_job is not None:
        try:
            app.root.after_cancel(app._geometry_save_job)
        except Exception:
            pass
    app._geometry_save_job = app.root.after(500, app._persist_geometry)


def persist_geometry(app) -> None:
    try:
        app.window_geometry = app.root.geometry()
        app._persist_tree_widths()
        app._save_config()
    except Exception:
        pass


def schedule_settings_geometry(app, win: tk.Toplevel) -> None:
    try:
        if getattr(app, "_settings_geometry_job", None) is not None:
            try:
                app.root.after_cancel(app._settings_geometry_job)
            except Exception:
                pass
        app._settings_geometry_job = app.root.after(500, lambda: app._persist_settings_geometry(win))
    except Exception:
        app._persist_settings_geometry(win)


def persist_settings_geometry(app, win: tk.Toplevel) -> None:
    try:
        if win and tk.Toplevel.winfo_exists(win):
            app.settings_window_geometry = win.geometry()
            app._save_config()
    except Exception:
        pass


def current_screen_resolution(app) -> str:
    try:
        return f"{app.root.winfo_screenwidth()}x{app.root.winfo_screenheight()}"
    except Exception:
        return ""


def parse_resolution(value: str) -> tuple[int, int] | None:
    if not value:
        return None
    text = str(value).lower().replace(" ", "")
    if "x" not in text:
        return None
    try:
        w_str, h_str = text.split("x", 1)
        return int(float(w_str)), int(float(h_str))
    except Exception:
        return None


def apply_resolution_safety(app) -> None:
    try:
        current = app._parse_resolution(app._current_screen_resolution())
        saved = app._parse_resolution(app.screen_resolution)
        if not current or not saved:
            app.screen_resolution = app._current_screen_resolution()
            return
        if current[0] < saved[0] or current[1] < saved[1]:
            app.window_geometry = ""
            app.settings_window_geometry = ""
            app._force_center_on_start = True
            app._force_center_settings = True
            app.screen_resolution = app._current_screen_resolution()
    except Exception:
        pass
