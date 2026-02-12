from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from app_core import APP_DIR, DEFAULT_CAPTURE_CONFIG
from capture import ensure_browser_available, install_playwright_browsers, start_capture_worker


def collect_capture_cfg(app) -> dict:
    def _parse_float(raw: str | None, default: float, label: str) -> float:
        try:
            return float((raw or "").strip())
        except Exception:
            app._log_console(f"Invalid {label} value '{raw}'; using {default}.")
            return float(default)

    def _parse_int(raw: str | None, default: int, label: str) -> int:
        try:
            return int(float((raw or "").strip()))
        except Exception:
            app._log_console(f"Invalid {label} value '{raw}'; using {default}.")
            return int(default)

    def _get_bool_var(name: str, default: bool = False) -> bool:
        var = getattr(app, name, None)
        if var is None:
            return default
        try:
            return bool(var.get())
        except Exception:
            return default

    return {
        "url": app.cap_url.get(),
        "interval_seconds": _parse_float(app.cap_interval.get(), DEFAULT_CAPTURE_CONFIG["interval_seconds"], "interval_seconds"),
        "login_wait_seconds": _parse_float(
            app.cap_login_wait.get(), DEFAULT_CAPTURE_CONFIG["login_wait_seconds"], "login_wait_seconds"
        ),
        "post_nav_wait_seconds": _parse_float(
            app.cap_post_wait.get(), DEFAULT_CAPTURE_CONFIG["post_nav_wait_seconds"], "post_nav_wait_seconds"
        ),
        "retry_attempts": _parse_int(
            app.cap_retry_attempts.get(), DEFAULT_CAPTURE_CONFIG["retry_attempts"], "retry_attempts"
        ),
        "retry_wait_seconds": _parse_float(
            app.cap_retry_wait.get(), DEFAULT_CAPTURE_CONFIG["retry_wait_seconds"], "retry_wait_seconds"
        ),
        "retry_backoff_max": _parse_float(
            app.cap_retry_backoff.get(), DEFAULT_CAPTURE_CONFIG["retry_backoff_max"], "retry_backoff_max"
        ),
        "dump_capture_html": bool(app.cap_dump_html.get()),
        "dump_html_keep_files": _parse_int(
            app.cap_dump_html_keep.get(), DEFAULT_CAPTURE_CONFIG["dump_html_keep_files"], "dump_html_keep_files"
        ),
        "dump_api_json": bool(app.cap_dump_api.get()),
        "dump_api_keep_files": _parse_int(
            app.cap_dump_api_keep.get(), DEFAULT_CAPTURE_CONFIG["dump_api_keep_files"], "dump_api_keep_files"
        ),
        "dump_api_full": bool(app.cap_dump_api.get()),
        "show_log_window": bool(app.cap_show_log_window.get()),
        "username": app.cap_user.get(),
        "password": app.cap_pass.get(),
        "username_selector": app.cap_user_sel.get(),
        "password_selector": app.cap_pass_sel.get(),
        "login_button_selector": app.cap_btn_sel.get(),
        "organization": app.cap_org.get(),
        "organization_selector": app.cap_org_sel.get(),
        "headless": bool(app.cap_headless.get()),
        "auto_notify_ha": bool(app.cap_auto_notify_ha.get()),
        "ha_webhook_url": app.cap_ha_webhook.get(),
        "ha_token": app.cap_ha_token.get(),
        "notify_price_changes": bool(app.notify_price_changes.get()),
        "notify_stock_changes": bool(app.notify_stock_changes.get()),
        "notify_out_of_stock": bool(app.notify_out_of_stock.get()),
        "notify_restock": bool(app.notify_restock.get()),
        "notify_new_items": bool(app.notify_new_items.get()),
        "notify_removed_items": bool(app.notify_removed_items.get()),
        "notify_windows": bool(app.notify_windows.get()),
        "log_window_hidden_height": float(getattr(app, "scraper_log_hidden_height", 210.0) or 210.0),
        "quiet_hours_enabled": bool(app.cap_quiet_hours_enabled.get()),
        "quiet_hours_start": app.cap_quiet_start.get(),
        "quiet_hours_end": app.cap_quiet_end.get(),
        "quiet_hours_interval_seconds": _parse_float(
            app.cap_quiet_interval.get(),
            DEFAULT_CAPTURE_CONFIG["quiet_hours_interval_seconds"],
            "quiet_hours_interval_seconds",
        ),
        "include_inactive": bool(app.cap_include_inactive.get()),
        "requestable_only": bool(app.cap_requestable_only.get()),
        "in_stock_only": bool(app.cap_in_stock_only.get()),
        "filter_flower": _get_bool_var("cap_filter_flower", False),
        "filter_oil": _get_bool_var("cap_filter_oil", False),
        "filter_vape": _get_bool_var("cap_filter_vape", False),
        "filter_pastille": _get_bool_var("cap_filter_pastille", False),
        "notification_detail": app.cap_notify_detail.get(),
        "minimize_to_tray": bool(app.minimize_to_tray.get()),
        "close_to_tray": bool(app.close_to_tray.get()),
        "window_geometry": app.geometry(),
        "settings_geometry": (
            app.settings_window.geometry()
            if app.settings_window and tk.Toplevel.winfo_exists(app.settings_window)
            else app.scraper_settings_geometry
        ),
        "history_window_geometry": (
            app.history_window.geometry()
            if getattr(app, "history_window", None) and tk.Toplevel.winfo_exists(app.history_window)
            else getattr(app, "history_window_geometry", "900x600")
        ),
        "screen_resolution": app._current_screen_resolution() if hasattr(app, "_current_screen_resolution") else "",
    }


def start_auto_capture(app) -> None:
    if app._is_capture_running():
        app._capture_log("Auto-capture already running.")
        return
    try:
        app._save_capture_window()
    except Exception as exc:
        app._debug_log(f"Suppressed exception: {exc}")
    cfg = app._collect_capture_cfg()
    if not cfg.get("url"):
        messagebox.showwarning("Auto-capture", "Please set the target URL before starting.")
        return
    app.capture_stop.clear()
    app._manual_bootstrap_prompt_shown = False
    app.error_count = 0
    app._empty_retry_pending = False
    app._update_tray_status()
    app._write_scraper_state("running")

    def install_cb():
        return install_playwright_browsers(Path(APP_DIR), app._capture_log)

    if not cfg.get("api_only", True):
        req = ensure_browser_available(Path(APP_DIR), app._capture_log, install_cb=install_cb)
        if not req:
            messagebox.showerror("Auto-capture", "Playwright is not available. See logs for details.")
            return
        app._playwright_available = req
    callbacks = {
        "capture_log": app._capture_log,
        "apply_text": app._apply_captured_text,
        "on_status": app._on_capture_status,
        "responsive_wait": app._responsive_wait,
        "stop_event": app.capture_stop,
        "prompt_manual_login": app._prompt_manual_login,
    }
    app.capture_thread = start_capture_worker(cfg, callbacks, app_dir=Path(APP_DIR), install_fn=install_cb)
    app._capture_log("Auto-capture running...")
    app._update_tray_status()


def prompt_manual_login(app) -> None:
    if getattr(app, "_manual_bootstrap_prompt_shown", False):
        return
    app._manual_bootstrap_prompt_shown = True
    app._capture_log("Manual login required: complete login in the opened browser window.")
    try:
        app.after(
            0,
            lambda: messagebox.showinfo(
                "Manual Login Required",
                "Credentials are missing or incomplete.\n\n"
                "A browser has been opened.\n"
                "Please log in manually, then wait for token capture to complete.",
            ),
        )
    except Exception as exc:
        app._debug_log(f"Suppressed exception: {exc}")


def stop_auto_capture(app) -> None:
    if not app.capture_stop.is_set():
        app.capture_stop.set()
    app._capture_log("Auto-capture stopped.")
    app._set_pagination_busy(False)
    app._update_tray_status()
    app._write_scraper_state("stopped")


def set_next_capture_timer(app, seconds: float) -> None:
    try:
        if seconds and seconds > 0:
            app.status.config(text=f"Next capture in {int(seconds)}s")
    except Exception as exc:
        app._debug_log(f"Suppressed exception: {exc}")
