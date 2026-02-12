from __future__ import annotations

import re
import threading
import tkinter as tk

from theme import compute_colors


def capture_log(app, msg: str) -> None:
    app._update_pagination_progress_from_log(msg)
    if hasattr(app, "logger") and app.logger:
        app.logger.info(msg)
    else:
        app._log_console(msg)
    try:
        status_msg = app._friendly_status_text(msg)
        if status_msg:
            app.status.config(text=status_msg)
    except Exception as exc:
        app._debug_log(f"Suppressed exception: {exc}")
    lower = str(msg or "").lower()
    if "api pagination" in lower or "pagination fetch" in lower:
        app._set_pagination_busy(True)
    elif (
        "api capture fetched" in lower
        or "api items parsed" in lower
        or "no api data found" in lower
        or "api capture failed" in lower
    ):
        app._set_pagination_busy(False)


def friendly_status_text(_app, msg: str) -> str:
    text = str(msg or "").strip()
    if not text:
        return ""
    lower = text.lower()
    if "external command: show scraper window" in lower:
        return ""
    if "external command: start queued" in lower:
        return "Start requested; waiting for current run to finish."
    if "external command: start auto-capture" in lower:
        return "Starting auto-capture..."
    if "external command: stop auto-capture" in lower:
        return "Stopping auto-capture..."
    if "applying api capture" in lower:
        return "Processing latest data..."
    if (
        "api pagination fetch" in lower
        or "pagination fetch" in lower
        or "pagination:" in lower
        or "count fetch status" in lower
    ):
        return ""
    if lower.startswith("saved last parse to "):
        return "Latest parse saved."
    if "no api data found" in lower:
        return "No data found this run."
    if lower.startswith("sending windows notification:"):
        return "Sending desktop notification..."
    return text


def append_auth_bootstrap_log(app, msg: str, level: str = "info") -> None:
    widget = getattr(app, "auth_bootstrap_log_widget", None)
    if not widget:
        return
    try:
        if not tk.Text.winfo_exists(widget):
            app.auth_bootstrap_log_widget = None
            return
    except Exception:
        app.auth_bootstrap_log_widget = None
        return
    line = f"{msg}\n"
    try:
        colors = compute_colors(bool(app.dark_mode_var.get()))
        success_fg = "#2ecc71" if bool(app.dark_mode_var.get()) else "#1f7a1f"
        warn_fg = "#f39c12" if bool(app.dark_mode_var.get()) else "#9a6500"
        error_fg = "#e74c3c" if bool(app.dark_mode_var.get()) else "#a32020"
        widget.tag_configure("log_info", foreground=colors["fg"])
        widget.tag_configure("log_success", foreground=success_fg)
        widget.tag_configure("log_warning", foreground=warn_fg)
        widget.tag_configure("log_error", foreground=error_fg)
        tag = {
            "success": "log_success",
            "warning": "log_warning",
            "error": "log_error",
        }.get(str(level).lower(), "log_info")
        widget.configure(state="normal")
        widget.insert("end", line, tag)
        widget.see("end")
        widget.yview_moveto(1.0)
        widget.configure(state="disabled")
        widget.update_idletasks()
    except Exception:
        pass


def auth_bootstrap_log(app, msg: str, level: str = "info") -> None:
    app._capture_log(msg)
    try:
        if threading.current_thread() is app._ui_thread:
            app._append_auth_bootstrap_log(msg, level=level)
        else:
            app.after(0, lambda m=msg, lvl=level: app._append_auth_bootstrap_log(m, level=lvl))
    except Exception:
        pass


def set_pagination_busy(app, busy: bool) -> None:
    if app._pagination_busy == busy:
        return
    app._pagination_busy = busy
    if not busy:
        app._pagination_pages_seen = 0
        app._pagination_pages_expected = 0
    try:
        app.pagination_label.config(text=app._pagination_progress_text() if busy else "")
    except Exception as exc:
        app._debug_log(f"Suppressed exception: {exc}")


def pagination_progress_text(app) -> str:
    if not app._pagination_busy:
        return ""
    seen = max(0, int(app._pagination_pages_seen or 0))
    expected = max(0, int(app._pagination_pages_expected or 0))
    if expected > 0:
        return f"Fetching pages... {min(seen, expected)}/{expected}"
    if seen > 0:
        return f"Fetching pages... {seen}"
    return "Fetching pages..."


def update_pagination_progress_from_log(app, msg: str) -> None:
    text = str(msg or "")
    if not text:
        return
    lower = text.lower()
    if "api pagination:" in lower:
        match = re.search(r"total=(\d+)\s+take=(\d+)", text, flags=re.IGNORECASE)
        if match:
            total = max(0, int(match.group(1)))
            take = max(1, int(match.group(2)))
            expected = max(1, (total + take - 1) // take)
            app._pagination_pages_expected = expected
            app._pagination_pages_seen = 1
            app._set_pagination_busy(True)
            try:
                app.pagination_label.config(text=app._pagination_progress_text())
            except Exception:
                pass
        return
    if "api pagination fetch skip=" in lower:
        if "status=error" not in lower:
            app._pagination_pages_seen = max(1, int(app._pagination_pages_seen or 0)) + 1
        app._set_pagination_busy(True)
        try:
            app.pagination_label.config(text=app._pagination_progress_text())
        except Exception:
            pass
