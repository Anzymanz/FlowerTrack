from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


def show_tooltip(app, text: str, event: tk.Event | None = None) -> None:
    try:
        pending = getattr(app, "_tooltip_after_id", None)
        if pending is not None:
            app.root.after_cancel(pending)
    except Exception:
        pass
    app._tooltip_after_id = None
    hide_tooltip(app)
    try:
        app._tooltip_win = tk.Toplevel(app.root)
        app._tooltip_win.wm_overrideredirect(True)
        x = event.x_root + 10 if event else app.root.winfo_pointerx() + 10
        y = event.y_root + 10 if event else app.root.winfo_pointery() + 10
        app._tooltip_win.wm_geometry(f"+{x}+{y}")
        label = ttk.Label(app._tooltip_win, text=text, relief="solid", padding=4)
        label.pack()
    except Exception:
        app._tooltip_win = None


def hide_tooltip(app) -> None:
    try:
        pending = getattr(app, "_tooltip_after_id", None)
        if pending is not None:
            app.root.after_cancel(pending)
    except Exception:
        pass
    app._tooltip_after_id = None
    if app._tooltip_win and tk.Toplevel.winfo_exists(app._tooltip_win):
        app._tooltip_win.destroy()
    app._tooltip_win = None


def bind_tooltip(app, widget: tk.Widget, text: str, delay_ms: int = 400) -> None:
    def on_enter(e: tk.Event) -> None:
        try:
            pending = getattr(app, "_tooltip_after_id", None)
            if pending is not None:
                app.root.after_cancel(pending)
        except Exception:
            pass
        app._tooltip_after_id = None
        if delay_ms > 0:
            app._tooltip_after_id = app.root.after(delay_ms, lambda: show_tooltip(app, text, None))
        else:
            show_tooltip(app, text, e)

    def on_leave(_e: tk.Event) -> None:
        hide_tooltip(app)

    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)


def bind_log_thc_cbd_tooltip(app) -> None:
    if not hasattr(app, "log_tree"):
        return
    message = "THC/CBD values are estimates based on flower potency and selected RoA efficiency."

    def on_motion(event):
        try:
            region = app.log_tree.identify_region(event.x, event.y)
            if region != "heading":
                hide_tooltip(app)
                return
            col = app.log_tree.identify_column(event.x)
            if col in ("#5", "#6"):
                show_tooltip(app, message, event)
            else:
                hide_tooltip(app)
        except Exception:
            pass

    app.log_tree.bind("<Motion>", on_motion)
    app.log_tree.bind("<Leave>", lambda _e: hide_tooltip(app))


def status_tooltip_text(app, resolve_status: Callable[[list], tuple[bool, bool]]) -> str:
    muted = bool(getattr(app, "scraper_notifications_muted", False))
    muted_txt = "Muted" if muted else "Unmuted"
    state_txt = "Stopped"
    try:
        running, warn = resolve_status(getattr(app, "child_procs", []))
        if running:
            state_txt = "Running"
        elif warn:
            state_txt = "Errored"
    except Exception:
        pass
    if app.network_mode == "client":
        state, missed = app._client_connection_state()
        label = {
            "good": "Connected",
            "interrupted": "Connection interrupted",
            "down": "Disconnected",
        }.get(state, "Unknown")
        return (
            f"Client connection: {label}\n"
            f"Missed polls: {missed}\n"
            "Green: connected | Orange: interrupted | Red: disconnected"
        )
    if app.network_mode == "host":
        active = app._host_active_connections_count()
        return (
            f"Host mode | Active clients: {active}\n"
            f"Scraper: {state_txt} | Notifications: {muted_txt}\n"
            "Double-click: Start/Stop scraper\n"
            "Right-click: Mute/Unmute notifications"
        )
    return (
        f"Scraper: {state_txt} | Notifications: {muted_txt}\n"
        "Double-click: Start/Stop scraper\n"
        "Right-click: Mute/Unmute notifications"
    )


def on_status_enter(app, delay_ms: int = 400) -> None:
    try:
        pending = getattr(app, "_status_tooltip_after_id", None)
        if pending is not None:
            app.root.after_cancel(pending)
        app._status_tooltip_after_id = app.root.after(
            delay_ms, lambda: show_tooltip(app, app._status_tooltip_text(), None)
        )
    except Exception:
        pass


def on_status_leave(app) -> None:
    try:
        pending = getattr(app, "_status_tooltip_after_id", None)
        if pending is not None:
            app.root.after_cancel(pending)
    except Exception:
        pass
    app._status_tooltip_after_id = None
    hide_tooltip(app)
