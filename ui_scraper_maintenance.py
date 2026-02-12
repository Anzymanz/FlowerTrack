from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from app_core import APP_DIR, CHANGES_LOG_FILE, LAST_PARSE_FILE, SCRAPER_STATE_FILE
from capture import CaptureWorker
from scraper_state import update_scraper_state
from unread_changes import clear_unread_changes


def clear_parse_cache(app, notify: bool = True) -> bool:
    cleared = False
    app.data.clear()
    app.prev_items = []
    app.prev_keys = set()
    app.removed_data = []
    try:
        if LAST_PARSE_FILE.exists():
            LAST_PARSE_FILE.unlink()
            cleared = True
    except Exception as exc:
        app._debug_log(f"Suppressed exception: {exc}")
    try:
        if clear_unread_changes():
            cleared = True
    except Exception as exc:
        app._debug_log(f"Suppressed exception: {exc}")
    if notify:
        app.status.config(text="Parse cache cleared")
        messagebox.showinfo("Cleared", "Parsed cache cleared.")
    return cleared


def clear_change_history(app, notify: bool = True) -> bool:
    cleared = False
    try:
        if CHANGES_LOG_FILE.exists():
            CHANGES_LOG_FILE.unlink()
            cleared = True
    except Exception as exc:
        app._debug_log(f"Suppressed exception: {exc}")
    if notify:
        app.status.config(text="Change history cleared")
        messagebox.showinfo("Cleared", "Change history log cleared.")
    return cleared


def clear_scraper_state_cache(app, notify: bool = True) -> bool:
    try:
        app.progress["value"] = 0
    except Exception as exc:
        app._debug_log(f"Suppressed exception: {exc}")
    try:
        app.last_change_label.config(text="Last change detected: none")
        app.last_scrape_label.config(text="Last successful scrape: none")
    except Exception as exc:
        app._debug_log(f"Suppressed exception: {exc}")
    update_scraper_state(SCRAPER_STATE_FILE, last_change=None, last_scrape=None)
    if notify:
        app.status.config(text="Scraper state cleared")
        messagebox.showinfo("Cleared", "Scraper state markers cleared.")
    return True


def clear_cache(app) -> None:
    app._clear_parse_cache(notify=False)
    app._clear_change_history(notify=False)
    app._clear_scraper_state_cache(notify=False)
    app.status.config(text="Cache cleared")
    messagebox.showinfo("Cleared", "Cleared parsed cache, change history, and scraper state.")


def clear_auth_cache(app) -> None:
    if app.capture_thread and app.capture_thread.is_alive():
        messagebox.showwarning("Auth Cache", "Stop auto-capture before clearing auth cache.")
        return
    try:
        worker = CaptureWorker.__new__(CaptureWorker)
        worker.app_dir = APP_DIR
        worker.callbacks = {"capture_log": app._log_console}
        cleared = worker.clear_auth_cache()
    except Exception as exc:
        app._log_console(f"Auth cache clear failed: {exc}")
        cleared = False
    if cleared:
        app._log_console("Auth cache cleared; next capture will bootstrap auth.")
        messagebox.showinfo("Auth Cache", "Auth cache cleared; next capture will re-authenticate.")
    else:
        messagebox.showinfo("Auth Cache", "No auth cache found to clear.")
