from __future__ import annotations
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import time
import ctypes
import threading
from pathlib import Path
from datetime import datetime, timezone
from queue import Queue, Empty
from capture import ensure_browser_available, install_playwright_browsers, start_capture_worker, CaptureWorker
from exports import export_html_auto, export_size_warning, init_exports, set_exports_dir
from export_server import start_export_server as srv_start_export_server, stop_export_server as srv_stop_export_server
from ui_settings import open_settings_window
from app_core import (  # shared globals/imports
    _log_debug,
    _cleanup_and_record_export,
    _load_capture_config,
    _save_capture_config,
    _load_tracker_dark_mode,
    _save_tracker_dark_mode,
    BASE_DIR,
    ASSETS_DIR,
    EXPORTS_DIR_DEFAULT,
    CONFIG_FILE,
    LAST_PARSE_FILE,
    CHANGES_LOG_FILE,
    DEFAULT_CAPTURE_CONFIG,
    load_last_parse,
    save_last_parse,
    append_change_log,
    APP_DIR,
    DATA_DIR,
    _port_ready,
    SCRAPER_STATE_FILE,
)
from config import decrypt_secret, encrypt_secret, load_capture_config, save_capture_config, load_tracker_config
from scraper_state import write_scraper_state, get_last_change, get_last_scrape, update_scraper_state
from parser import (
    parse_api_payloads,
    make_item_key,
    make_identity_key,
)
from diff_engine import compute_diffs
from models import Item
import threading as _threading
from notifications import _maybe_send_windows_notification
from tray import create_tray_icon, stop_tray_icon, tray_supported, update_tray_icon, compute_tray_state
from logger import UILogger
from notifications import NotificationService
from theme import apply_style_theme, set_titlebar_dark, compute_colors, set_palette_overrides
from resources import resource_path
from history_viewer import open_history_window

# Scraper UI constants
SCRAPER_TITLE = "Medicann Scraper"
SCRAPER_COMMAND_FILE = Path(APP_DIR) / "data" / "scraper_command.json"
def _should_stop_on_empty(error_count: int, error_threshold: int) -> bool:
    return error_count >= error_threshold
def _identity_key_cached(item: dict, cache: dict) -> str:
    key = id(item)
    cached = cache.get(key)
    if cached is None:
        cached = make_identity_key(item)
        cache[key] = cached
    return cached
def _build_identity_cache(items: list[dict]) -> dict:
    cache = {}
    for it in items:
        cache[id(it)] = make_identity_key(it)
    return cache
class App(tk.Tk):
    _instance = None
    @classmethod
    def instance(cls):
        return cls._instance
    def __init__(self, start_hidden: bool = False):
        super().__init__()
        App._instance = self
        self._start_hidden = bool(start_hidden)
        self._ui_thread = threading.current_thread()
        try:
            self.attributes("-alpha", 0.0)
            self.withdraw()
        except Exception:
            pass
        self.title(SCRAPER_TITLE)
        cfg = _load_capture_config()
        self.scraper_window_geometry = cfg.get("window_geometry", "769x420") or "769x420"
        self.scraper_settings_geometry = cfg.get("settings_geometry", "560x960") or "560x960"
        self.history_window_geometry = cfg.get("history_window_geometry", "900x600") or "900x600"
        self.screen_resolution = str(cfg.get("screen_resolution", "")).strip()
        self._apply_resolution_safety()
        self.geometry(self.scraper_window_geometry)
        self.assets_dir = ASSETS_DIR
        _log_debug("App init: launching scraper UI")
        self._config_dark = self._load_dark_mode()
        self._palette_signature = ""
        self.removed_data = []
        self.httpd = None
        self.http_thread = None
        self.server_port = 8765
        self._server_failed = False
        _log_debug(f"Init export server state. preferred_port={self.server_port} frozen={getattr(sys, '_MEIPASS', None) is not None}")
        try:
            init_exports(ASSETS_DIR, EXPORTS_DIR_DEFAULT)
            set_exports_dir(EXPORTS_DIR_DEFAULT)
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        try:
            # Prefer bundled assets/icon.ico if present; fallback to old asset
            icon_path = ASSETS_DIR / "icon.ico"
            if icon_path.exists():
                self.iconbitmap(str(icon_path))
            else:
                self.iconbitmap(self._resource_path('assets/icon2.ico'))
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        # Start lightweight export server for consistent origin (favorites persistence)
        self._ensure_export_server()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.start_export_server()
        self.style = ttk.Style(self)
        self.dark_mode_var = tk.BooleanVar(value=self._config_dark)
        self.settings_window = None
        self.capture_window = None
        self.history_window = None
        self.auth_bootstrap_log_widget = None
        self.auth_bootstrap_log_frame = None
        self.tray_icon = None
        self.capture_status = "idle"
        self.error_count = 0
        self.error_threshold = 3
        self._last_parse_empty = False
        self._empty_retry = False
        log_file = Path(APP_DIR) / "logs" / "flowertrack.log"
        self.logger = UILogger(console_fn=self._log_console, tray_fn=None, file_path=log_file, also_stdout=True)
        self.notify_service = NotificationService(
            ha_webhook=lambda: self.cap_ha_webhook.get(),
            ha_token=lambda: self.cap_ha_token.get(),
            send_ha=lambda: self.cap_auto_notify_ha.get(),
            notify_windows=lambda: self.notify_windows.get(),
            logger=self._log_console,
        )
        btns = ttk.Frame(self)
        btns.pack(pady=5)
        ttk.Button(btns, text="Start Auto-Scraper", command=self.start_auto_capture).pack(side="left", padx=(5, 5))
        ttk.Button(btns, text="Stop Auto-Scraper", command=self.stop_auto_capture).pack(side="left", padx=5)
        ttk.Button(btns, text="Open browser", command=self.open_latest_export).pack(side="left", padx=5)
        ttk.Button(btns, text="History", command=self._open_history_window).pack(side="left", padx=5)
        ttk.Button(btns, text="Settings", command=self._open_settings_window).pack(side="left", padx=5)
        self.progress = ttk.Progressbar(self, mode="determinate", style="Scraper.Horizontal.TProgressbar")
        self.progress.pack(fill="x", padx=10, pady=5)
        self.status = ttk.Label(self, text="Idle")
        self.status.pack(pady=(2, 2))
        self.pagination_label = ttk.Label(self, text="", font=("", 9))
        self.pagination_label.pack()
        self._pagination_busy = False
        # Capture status bookkeeping
        self.capture_status = "idle"
        self._write_scraper_state("idle")
        self.error_count = 0
        self.error_threshold = 3
        self._empty_retry_pending = False
        # Console log at bottom
        self.console_frame = ttk.Frame(self)
        self.console_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        ttk.Label(self.console_frame, text="Console Log").pack(anchor="w")
        console_inner = ttk.Frame(self.console_frame)
        console_inner.pack(fill="both", expand=True)
        self.console = tk.Text(console_inner, height=10, wrap="word", state="disabled", relief="flat", borderwidth=0)
        self.console_scroll = ttk.Scrollbar(
            console_inner, orient="vertical", command=self.console.yview, style="Dark.Vertical.TScrollbar"
        )
        self.console.configure(yscrollcommand=self.console_scroll.set)
        self.console.pack(side="left", fill="both", expand=True)
        self.console_scroll.pack(side="right", fill="y")
        self.last_change_label = ttk.Label(self, text="Last change detected: none")
        self.last_change_label.pack(pady=(0, 8))
        self.last_scrape_label = ttk.Label(self, text="Last successful scrape: none")
        self.last_scrape_label.pack(pady=(0, 8))
        try:
            ts = get_last_scrape(SCRAPER_STATE_FILE)
            if ts:
                self.last_scrape_label.config(text=f"Last successful scrape: {ts}")
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        self.data = []
        self.price_up_count = 0
        self.price_down_count = 0
        self.q = Queue()
        self._polling = False
        self._last_external_command_ts = 0.0
        self._pending_external_start = False
        # reset capture error state
        self.error_count = 0
        self.error_threshold = 3
        self._empty_retry_pending = False
        # Auto-capture state
        self.capture_thread: _threading.Thread | None = None
        self.capture_stop = _threading.Event()
        self._playwright_available = None
        self.last_change_summary = "none"
        self._log_window_last_full_height = None
        self._build_capture_controls()
        # Tray behavior
        self.bind("<Unmap>", self._on_unmap)
        self.bind("<Map>", self._on_map)
        self.bind("<Configure>", self._on_configure)
        try:
            self._refresh_palette_overrides_from_config()
        except Exception:
            pass
        self.apply_theme()
        self.after(2000, self._refresh_theme_from_config)
        self._apply_log_window_visibility()
        # Ensure dark titlebar sticks (especially in frozen builds)
        try:
            self.after(120, lambda: self._set_window_titlebar_dark(self, self.dark_mode_var.get()))
            self.after(150, lambda: self._set_win_titlebar_dark(self.dark_mode_var.get()))
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        if self._start_hidden:
            self.after(0, lambda: self.attributes("-alpha", 0.0))
            self.after(0, self.withdraw)
        else:
            self.after(0, self._show_scraper_window)
        self.after(50, self._apply_log_window_visibility)
        self.after(500, self._poll_external_commands)

    def _show_scraper_window(self) -> None:
        try:
            # Enforce compact geometry before showing when log window is hidden.
            self._apply_log_window_visibility()
        except Exception:
            pass
        try:
            self.update_idletasks()
            self.deiconify()
            self.attributes("-alpha", 1.0)
            self.lift()
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        try:
            self._apply_log_window_visibility()
        except Exception:
            pass

    def _poll_external_commands(self) -> None:
        try:
            payload = self._read_external_command()
            if payload:
                self._apply_external_command(payload)
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        try:
            self.after(800, self._poll_external_commands)
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")

    def _read_external_command(self) -> dict | None:
        path = SCRAPER_COMMAND_FILE
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(data, dict):
            return None
        cmd = str(data.get("cmd", "")).strip().lower()
        ts_raw = data.get("ts", 0)
        try:
            ts = float(ts_raw)
        except Exception:
            ts = 0.0
        if cmd not in ("start", "stop", "show"):
            return None
        if ts <= float(getattr(self, "_last_external_command_ts", 0.0)):
            return None
        self._last_external_command_ts = ts
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        return {"cmd": cmd, "ts": ts}

    def _apply_external_command(self, payload: dict) -> None:
        cmd = str(payload.get("cmd", "")).strip().lower()
        if cmd == "start":
            if self._is_capture_running():
                self._pending_external_start = True
                self._capture_log("External command: start queued until capture fully stops.")
                self.after(250, self._try_pending_external_start)
            else:
                self._pending_external_start = False
                self._capture_log("External command: start auto-capture.")
                self.start_auto_capture()
        elif cmd == "stop":
            self._pending_external_start = False
            if self.capture_thread:
                self._capture_log("External command: stop auto-capture.")
                self.stop_auto_capture()
        elif cmd == "show":
            self._capture_log("External command: show scraper window.")
            self._show_scraper_window()

    def _try_pending_external_start(self) -> None:
        if not self._pending_external_start:
            return
        if self._is_capture_running():
            self.after(250, self._try_pending_external_start)
            return
        self._pending_external_start = False
        self._capture_log("External command: start auto-capture.")
        self.start_auto_capture()
    def _build_capture_controls(self) -> None:
        cfg = _load_capture_config()
        self.capture_config_path = Path(CONFIG_FILE)
        self.cap_url = tk.StringVar(value=cfg.get("url", ""))
        self.cap_interval = tk.StringVar(value=str(cfg.get("interval_seconds", 60)))
        self.cap_headless = tk.BooleanVar(value=bool(cfg.get("headless", True)))
        self.cap_login_wait = tk.StringVar(value=str(cfg.get("login_wait_seconds", 3)))
        self.cap_post_wait = tk.StringVar(value=str(cfg.get("post_nav_wait_seconds", 30)))
        self.cap_retry_attempts = tk.StringVar(value=str(cfg.get("retry_attempts", 3)))
        self.cap_retry_wait = tk.StringVar(value=str(cfg.get("retry_wait_seconds", cfg.get("post_nav_wait_seconds", 30))))
        self.cap_retry_backoff = tk.StringVar(value=str(cfg.get("retry_backoff_max", 4)))
        self.cap_user = tk.StringVar(value=decrypt_secret(cfg.get("username", "")))
        self.cap_pass = tk.StringVar(value=decrypt_secret(cfg.get("password", "")))
        self.cap_user_sel = tk.StringVar(value=cfg.get("username_selector", ""))
        self.cap_pass_sel = tk.StringVar(value=cfg.get("password_selector", ""))
        self.cap_btn_sel = tk.StringVar(value=cfg.get("login_button_selector", ""))
        self.cap_org = tk.StringVar(value=cfg.get("organization", ""))
        self.cap_org_sel = tk.StringVar(value=cfg.get("organization_selector", ""))
        self.cap_dump_html = tk.BooleanVar(value=bool(cfg.get("dump_capture_html", False)))
        self.cap_dump_html_keep = tk.StringVar(value=str(cfg.get("dump_html_keep_files", 10)))
        dump_api_enabled = bool(cfg.get("dump_api_json", False) or cfg.get("dump_api_full", False))
        self.cap_dump_api = tk.BooleanVar(value=dump_api_enabled)
        self.cap_dump_api_keep = tk.StringVar(value=str(cfg.get("dump_api_keep_files", 10)))
        self.cap_show_log_window = tk.BooleanVar(value=bool(cfg.get("show_log_window", False)))
        try:
            self.scraper_log_hidden_height = float(self._clamp_hidden_log_height(cfg.get("log_window_hidden_height", 210)))
        except Exception:
            self.scraper_log_hidden_height = 210.0
        try:
            self.cap_show_log_window.trace_add("write", lambda *_: self._apply_log_window_visibility())
        except Exception:
            pass
        self.cap_auto_notify_ha = tk.BooleanVar(value=bool(cfg.get("auto_notify_ha", False)))
        self.cap_ha_webhook = tk.StringVar(value=cfg.get("ha_webhook_url", ""))
        self.cap_ha_token = tk.StringVar(value=decrypt_secret(cfg.get("ha_token", "")))
        self.notify_price_changes = tk.BooleanVar(value=bool(cfg.get("notify_price_changes", True)))
        self.notify_stock_changes = tk.BooleanVar(value=bool(cfg.get("notify_stock_changes", True)))
        self.notify_out_of_stock = tk.BooleanVar(value=bool(cfg.get("notify_out_of_stock", True)))
        self.notify_restock = tk.BooleanVar(value=bool(cfg.get("notify_restock", True)))
        self.notify_new_items = tk.BooleanVar(value=bool(cfg.get("notify_new_items", True)))
        self.notify_removed_items = tk.BooleanVar(value=bool(cfg.get("notify_removed_items", True)))
        self.notify_windows = tk.BooleanVar(value=bool(cfg.get("notify_windows", True)))
        self.cap_quiet_hours_enabled = tk.BooleanVar(value=bool(cfg.get("quiet_hours_enabled", False)))
        self.cap_quiet_start = tk.StringVar(value=cfg.get("quiet_hours_start", "22:00"))
        self.cap_quiet_end = tk.StringVar(value=cfg.get("quiet_hours_end", "07:00"))
        self.cap_quiet_interval = tk.StringVar(value=str(cfg.get("quiet_hours_interval_seconds", 3600)))
        self.cap_include_inactive = tk.BooleanVar(value=bool(cfg.get("include_inactive", False)))
        self.cap_requestable_only = tk.BooleanVar(value=bool(cfg.get("requestable_only", True)))
        self.cap_in_stock_only = tk.BooleanVar(value=bool(cfg.get("in_stock_only", False)))
        self.cap_filter_flower = tk.BooleanVar(value=bool(cfg.get("filter_flower", False)))
        self.cap_filter_oil = tk.BooleanVar(value=bool(cfg.get("filter_oil", False)))
        self.cap_filter_vape = tk.BooleanVar(value=bool(cfg.get("filter_vape", False)))
        self.cap_filter_pastille = tk.BooleanVar(value=bool(cfg.get("filter_pastille", False)))
        self.cap_notify_detail = tk.StringVar(value=cfg.get("notification_detail", "full"))
        self.minimize_to_tray = tk.BooleanVar(value=bool(cfg.get("minimize_to_tray", False)))
        self.close_to_tray = tk.BooleanVar(value=bool(cfg.get("close_to_tray", False)))

    def _collect_capture_cfg(self) -> dict:
        def _parse_float(raw: str | None, default: float, label: str) -> float:
            if raw is None:
                return float(default)
            text = str(raw).strip()
            if not text:
                return float(default)
            try:
                return float(text)
            except Exception:
                self._log_console(f"Invalid {label} value '{raw}'; using {default}.")
                return float(default)
        def _parse_int(raw: str | None, default: int, label: str) -> int:
            if raw is None:
                return int(default)
            text = str(raw).strip()
            if not text:
                return int(default)
            try:
                return int(float(text))
            except Exception:
                self._log_console(f"Invalid {label} value '{raw}'; using {default}.")
                return int(default)
        def _get_bool_var(name: str, default: bool = False) -> bool:
            var = getattr(self, name, None)
            if var is None:
                return bool(default)
            try:
                return bool(var.get())
            except Exception:
                return bool(var)
        return {
            "url": self.cap_url.get(),
            "interval_seconds": _parse_float(self.cap_interval.get(), DEFAULT_CAPTURE_CONFIG["interval_seconds"], "interval_seconds"),
            "login_wait_seconds": _parse_float(self.cap_login_wait.get(), DEFAULT_CAPTURE_CONFIG["login_wait_seconds"], "login_wait_seconds"),
            "post_nav_wait_seconds": _parse_float(self.cap_post_wait.get(), DEFAULT_CAPTURE_CONFIG["post_nav_wait_seconds"], "post_nav_wait_seconds"),
            "retry_attempts": _parse_int(self.cap_retry_attempts.get(), DEFAULT_CAPTURE_CONFIG["retry_attempts"], "retry_attempts"),
            "retry_wait_seconds": _parse_float(self.cap_retry_wait.get(), DEFAULT_CAPTURE_CONFIG["retry_wait_seconds"], "retry_wait_seconds"),
            "retry_backoff_max": _parse_float(self.cap_retry_backoff.get(), DEFAULT_CAPTURE_CONFIG["retry_backoff_max"], "retry_backoff_max"),
            "dump_capture_html": bool(self.cap_dump_html.get()),
            "dump_html_keep_files": _parse_int(self.cap_dump_html_keep.get(), DEFAULT_CAPTURE_CONFIG["dump_html_keep_files"], "dump_html_keep_files"),
            "dump_api_json": bool(self.cap_dump_api.get()),
            "dump_api_keep_files": _parse_int(self.cap_dump_api_keep.get(), DEFAULT_CAPTURE_CONFIG["dump_api_keep_files"], "dump_api_keep_files"),
            # Keep writing legacy key so older imports/versions continue to read the same state.
            "dump_api_full": bool(self.cap_dump_api.get()),
            "show_log_window": bool(self.cap_show_log_window.get()),
            "username": self.cap_user.get(),
            "password": self.cap_pass.get(),
            "username_selector": self.cap_user_sel.get(),
            "password_selector": self.cap_pass_sel.get(),
            "login_button_selector": self.cap_btn_sel.get(),
            "organization": self.cap_org.get(),
            "organization_selector": self.cap_org_sel.get(),
            "headless": bool(self.cap_headless.get()),
            "auto_notify_ha": bool(self.cap_auto_notify_ha.get()),
            "ha_webhook_url": self.cap_ha_webhook.get(),
            "ha_token": self.cap_ha_token.get(),
            "notify_price_changes": bool(self.notify_price_changes.get()),
            "notify_stock_changes": bool(self.notify_stock_changes.get()),
            "notify_out_of_stock": bool(self.notify_out_of_stock.get()),
            "notify_restock": bool(self.notify_restock.get()),
            "notify_new_items": bool(self.notify_new_items.get()),
            "notify_removed_items": bool(self.notify_removed_items.get()),
            "notify_windows": bool(self.notify_windows.get()),
            "log_window_hidden_height": float(getattr(self, "scraper_log_hidden_height", 210.0) or 210.0),
            "quiet_hours_enabled": bool(self.cap_quiet_hours_enabled.get()),
            "quiet_hours_start": self.cap_quiet_start.get(),
            "quiet_hours_end": self.cap_quiet_end.get(),
            "quiet_hours_interval_seconds": _parse_float(
                self.cap_quiet_interval.get(),
                DEFAULT_CAPTURE_CONFIG["quiet_hours_interval_seconds"],
                "quiet_hours_interval_seconds",
            ),
            "include_inactive": bool(self.cap_include_inactive.get()),
            "requestable_only": bool(self.cap_requestable_only.get()),
            "in_stock_only": bool(self.cap_in_stock_only.get()),
            "filter_flower": _get_bool_var("cap_filter_flower", False),
            "filter_oil": _get_bool_var("cap_filter_oil", False),
            "filter_vape": _get_bool_var("cap_filter_vape", False),
            "filter_pastille": _get_bool_var("cap_filter_pastille", False),
            "notification_detail": self.cap_notify_detail.get(),
            "minimize_to_tray": bool(self.minimize_to_tray.get()),
            "close_to_tray": bool(self.close_to_tray.get()),
            "window_geometry": self.geometry(),
            "settings_geometry": (self.settings_window.geometry() if self.settings_window and tk.Toplevel.winfo_exists(self.settings_window) else self.scraper_settings_geometry),
            "history_window_geometry": (
                self.history_window.geometry()
                if getattr(self, "history_window", None) and tk.Toplevel.winfo_exists(self.history_window)
                else getattr(self, "history_window_geometry", "900x600")
            ),
            "screen_resolution": (
                self._current_screen_resolution() if hasattr(self, "_current_screen_resolution") else ""
            ),
        }

    def start_auto_capture(self):
        if self._is_capture_running():
            self._capture_log("Auto-capture already running.")
            return
        try:
            self._save_capture_window()
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        cfg = self._collect_capture_cfg()
        if not cfg.get("url"):
            messagebox.showwarning("Auto-capture", "Please set the target URL before starting.")
            return
        self.capture_stop.clear()
        self._manual_bootstrap_prompt_shown = False
        self.error_count = 0
        self._empty_retry_pending = False
        self._update_tray_status()
        self._write_scraper_state("running")
        def install_cb():
            return install_playwright_browsers(Path(APP_DIR), self._capture_log)
        if not cfg.get("api_only", True):
            req = ensure_browser_available(Path(APP_DIR), self._capture_log, install_cb=install_cb)
            if not req:
                messagebox.showerror("Auto-capture", "Playwright is not available. See logs for details.")
                return
            self._playwright_available = req
        callbacks = {
            "capture_log": self._capture_log,
            "apply_text": self._apply_captured_text,
            "on_status": self._on_capture_status,
            "responsive_wait": self._responsive_wait,
            "stop_event": self.capture_stop,
            "prompt_manual_login": self._prompt_manual_login,
        }
        self.capture_thread = start_capture_worker(cfg, callbacks, app_dir=Path(APP_DIR), install_fn=install_cb)
        self._capture_log("Auto-capture running...")
        self._update_tray_status()

    def _prompt_manual_login(self) -> None:
        # Show once per auto-capture session to avoid repetitive popups while retrying.
        if getattr(self, "_manual_bootstrap_prompt_shown", False):
            return
        self._manual_bootstrap_prompt_shown = True
        self._capture_log("Manual login required: complete login in the opened browser window.")
        try:
            self.after(
                0,
                lambda: messagebox.showinfo(
                    "Manual Login Required",
                    "Credentials are missing or incomplete.\n\n"
                    "A browser has been opened.\n"
                    "Please log in manually, then wait for token capture to complete.",
                ),
            )
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")

    def stop_auto_capture(self):
        if not self.capture_stop.is_set():
            self.capture_stop.set()
        self._capture_log("Auto-capture stopped.")
        self._set_pagination_busy(False)
        self._update_tray_status()
        self._write_scraper_state("stopped")

    def _set_next_capture_timer(self, seconds: float) -> None:
        try:
            if seconds and seconds > 0:
                self.status.config(text=f"Next capture in {int(seconds)}s")
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
    def _open_settings_window(self):
        if self.settings_window and tk.Toplevel.winfo_exists(self.settings_window):
            try:
                self.settings_window.deiconify()
                self.settings_window.lift()
                self.settings_window.focus_force()
            except Exception as exc:
                self._debug_log(f"Suppressed exception: {exc}")
            return
        try:
            self.settings_window = open_settings_window(self, self.assets_dir)
            self._apply_theme_to_window(self.settings_window)
        except Exception as exc:
            messagebox.showerror("Settings", f"Could not open settings:\n{exc}")

    def _open_history_window(self):
        if self.history_window and tk.Toplevel.winfo_exists(self.history_window):
            try:
                self.history_window.deiconify()
                self.history_window.lift()
                self.history_window.focus_force()
                self._apply_theme_to_window(self.history_window)
            except Exception as exc:
                self._debug_log(f"Suppressed exception: {exc}")
            return
        try:
            self.history_window = open_history_window(self, CHANGES_LOG_FILE)
            self._apply_theme_to_window(self.history_window)
        except Exception as exc:
            messagebox.showerror("History", f"Could not open history:\n{exc}")

    def _capture_log(self, msg: str):
        if hasattr(self, "logger") and self.logger:
            self.logger.info(msg)
        else:
            self._log_console(msg)
        # Update status label for capture-related messages
        try:
            self.status.config(text=msg)
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        lower = str(msg or "").lower()
        if "api pagination" in lower or "pagination fetch" in lower:
            self._set_pagination_busy(True)
        elif (
            "api capture fetched" in lower
            or "api items parsed" in lower
            or "no api data found" in lower
            or "api capture failed" in lower
        ):
            self._set_pagination_busy(False)

    def _append_auth_bootstrap_log(self, msg: str) -> None:
        widget = getattr(self, "auth_bootstrap_log_widget", None)
        if not widget:
            return
        try:
            if not tk.Text.winfo_exists(widget):
                self.auth_bootstrap_log_widget = None
                return
        except Exception:
            self.auth_bootstrap_log_widget = None
            return
        line = f"{msg}\n"
        try:
            widget.configure(state="normal")
            widget.insert("end", line)
            widget.see("end")
            widget.yview_moveto(1.0)
            widget.configure(state="disabled")
            widget.update_idletasks()
        except Exception:
            pass

    def _auth_bootstrap_log(self, msg: str) -> None:
        self._capture_log(msg)
        try:
            if threading.current_thread() is self._ui_thread:
                self._append_auth_bootstrap_log(msg)
            else:
                self.after(0, lambda m=msg: self._append_auth_bootstrap_log(m))
        except Exception:
            pass

    def _set_pagination_busy(self, busy: bool) -> None:
        if self._pagination_busy == busy:
            return
        self._pagination_busy = busy
        try:
            if busy:
                self.pagination_label.config(text="Fetching pages...")
            else:
                self.pagination_label.config(text="")
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
    def _generate_change_export(self, items: list[dict] | None = None, silent: bool = False):
        """Generate an HTML snapshot for the latest items and keep only recent ones."""
        data = items if items is not None else self._get_export_items()
        if not data:
            if not silent:
                try:
                    messagebox.showinfo("Open Export", "No data available to export yet.")
                except Exception as exc:
                    self._debug_log(f"Suppressed exception: {exc}")
            return
        try:
            path = export_html_auto(data, exports_dir=EXPORTS_DIR_DEFAULT, open_file=False, fetch_images=False)
            _cleanup_and_record_export(path, max_files=1)
            self._capture_log(f"Exported snapshot: {path.name}")
            warn = export_size_warning(path)
            if warn:
                self._capture_log(warn)
                if not silent:
                    try:
                        messagebox.showwarning("Export size warning", warn)
                    except Exception as exc:
                        self._debug_log(f"Suppressed exception: {exc}")
        except Exception as exc:
            if silent:
                self._capture_log(f"Export generation failed: {exc}")
            else:
                messagebox.showerror("Open Export", f"Could not generate export:\n{exc}")
            return


    def open_fresh_export(self):
        try:
            if not self.data and LAST_PARSE_FILE.exists():
                self.data = load_last_parse(LAST_PARSE_FILE)
            if self.data:
                self._generate_change_export(self._get_export_items())
            else:
                messagebox.showinfo("Open Export", "No data available to export yet.")
                return
        except Exception as exc:
            messagebox.showerror("Open Export", f"Could not generate export:\n{exc}")
            return
        self.open_latest_export()

    def open_latest_export(self):
        try:
            if not self.data and LAST_PARSE_FILE.exists():
                self.data = load_last_parse(LAST_PARSE_FILE)
            if self.data:
                self._generate_change_export(self._get_export_items())
            else:
                messagebox.showinfo("Open Export", "No data available to export yet.")
                return
        except Exception as exc:
            messagebox.showerror("Open Export", f"Could not generate export:\n{exc}")
            return
        url = self._latest_export_url()
        if not url:
            messagebox.showinfo("Open Export", "No exports available yet.")
            return
        self._ensure_export_server()
        try:
            latest_path = None
            exports_dir = Path(EXPORTS_DIR_DEFAULT)
            html_files = sorted(exports_dir.glob("export-*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
            if html_files:
                latest_path = html_files[0]
            if latest_path and url.startswith("http://"):
                self._open_url_with_fallback(url, latest_path)
            else:
                webbrowser.open(url)
        except Exception as exc:
            messagebox.showerror("Open Export", f"Could not open export:\n{exc}")

    def _latest_export_url(self) -> str | None:
        """Return URL (or file://) for latest export, preferring local server."""
        exports_dir = Path(EXPORTS_DIR_DEFAULT)
        if not exports_dir.exists():
            return None
        html_files = sorted(exports_dir.glob("export-*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not html_files:
            return None
        latest = html_files[0]
        if getattr(self, "server_port", None) and _port_ready("127.0.0.1", self.server_port):
            return f"http://127.0.0.1:{self.server_port}/flowerbrowser"
        return latest.as_uri()
    # ------------- Tray helpers -------------
    def _tray_supported(self) -> bool:
        return tray_supported()
    def _minimize_to_tray(self):
        """Hide the scraper window while keeping capture running (no tray icon)."""
        try:
            self._hide_settings_window()
            self.withdraw()
            self._capture_log("Scraper window hidden.")
        except Exception as exc:
            self._log_console(f"Hide failed; falling back. ({exc})")
            self.iconify()
    def _restore_from_tray(self):
        try:
            self.deiconify()
            self.state("normal")
            self.lift()
            self.focus_force()
            self._restore_settings_window()
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
    def _exit_from_tray(self, icon=None, item=None):
        self.after(0, self._exit_app)
    def _show_tray_icon(self):
        # Scraper no longer owns a tray icon; tracker controls tray visibility/status.
        return
    def _hide_tray_icon(self):
        self.tray_icon = None
    def _on_unmap(self, event):
        try:
            if event.widget is self:
                self.after(50, self._minimize_to_tray)
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
    def _on_map(self, event):
        try:
            if event.widget is self:
                pass
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
    def _is_capture_running(self) -> bool:
        return bool(self.capture_thread and self.capture_thread.is_alive())
    def _update_tray_status(self):
        """Update tray icon color based on capture running state."""
        try:
            if self.tray_icon and self._tray_supported():
                running, warn = compute_tray_state(
                    self._is_capture_running(),
                    status=getattr(self, "capture_status", None),
                    error_count=getattr(self, "error_count", 0),
                    empty_retry=getattr(self, "_empty_retry_pending", False),
                )
                update_tray_icon(self.tray_icon, running, warn)
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
    def _hide_settings_window(self):
        try:
            self._save_capture_window()
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        try:
            if self.settings_window and tk.Toplevel.winfo_exists(self.settings_window):
                self.settings_window.withdraw()
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
    def _restore_settings_window(self):
        try:
            if self.settings_window and tk.Toplevel.winfo_exists(self.settings_window):
                self.settings_window.deiconify()
                self.settings_window.lift()
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
    def _debug_log(self, msg: str) -> None:
        try:
            _log_debug(msg)
        except Exception:
            pass
    def _log_console(self, msg: str):
        if threading.current_thread() is not getattr(self, "_ui_thread", None):
            try:
                self.after(0, lambda m=msg: self._log_console_ui(m))
            except Exception as exc:
                self._debug_log(f"Suppressed exception: {exc}")
            return
        self._log_console_ui(msg)
    def _log_console_ui(self, msg: str):
        # If already timestamped, don't double-stamp.
        if msg.startswith("[") and "]" in msg[:12]:
            line = f"{msg}\n"
        else:
            ts = datetime.now().strftime("%H:%M:%S")
            line = f"[{ts}] {msg}\n"
        try:
            self.console.configure(state="normal")
            self.console.insert("end", line)
            self.console.see("end")
            self.console.configure(state="disabled")
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        try:
            self.status.config(text=msg)
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")

    def _clamp_hidden_log_height(self, height: float | int | None) -> int:
        # Fixed compact height when log is hidden.
        return 190

    def _apply_log_window_visibility(self) -> None:
        try:
            show = bool(self.cap_show_log_window.get()) if hasattr(self, "cap_show_log_window") else True
            self.update_idletasks()
            target_shown_height = 420
            if show:
                if not self.console_frame.winfo_ismapped():
                    self.console_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8), before=self.last_change_label)
                    self.update_idletasks()
                    self.geometry(f"{self.winfo_width()}x{target_shown_height}")
                else:
                    self.geometry(f"{self.winfo_width()}x{target_shown_height}")
            else:
                if self.console_frame.winfo_ismapped():
                    self.console_frame.pack_forget()
                    self.update_idletasks()
                    hidden_height = self._clamp_hidden_log_height(getattr(self, "scraper_log_hidden_height", 210))
                    self.geometry(f"{self.winfo_width()}x{hidden_height}")
                    self.update_idletasks()
                    self.scraper_log_hidden_height = float(self._clamp_hidden_log_height(self.winfo_height()))
                else:
                    hidden_height = self._clamp_hidden_log_height(getattr(self, "scraper_log_hidden_height", 210))
                    if hidden_height:
                        self.geometry(f"{self.winfo_width()}x{hidden_height}")
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")

    def _on_configure(self, _event=None) -> None:
        try:
            if hasattr(self, "cap_show_log_window") and not self.cap_show_log_window.get():
                height = self.winfo_height()
                if height:
                    self.scraper_log_hidden_height = float(self._clamp_hidden_log_height(height))
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
    def _update_last_change(self, summary: str):
        ts_line = f"{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S%z')} | {summary}"
        write_scraper_state(SCRAPER_STATE_FILE, last_change=ts_line)
        try:
            self.last_change_label.config(text=f"Last change detected: {ts_line}")
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
    def _update_last_scrape(self):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        write_scraper_state(SCRAPER_STATE_FILE, last_scrape=ts)
        try:
            self.last_scrape_label.config(text=f"Last successful scrape: {ts}")
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
    def _goto_with_log(self, page, url: str, PlaywrightTimeoutError):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except PlaywrightTimeoutError:
            self._capture_log("Navigation timed out; continuing.")
        except Exception as exc:
            self._capture_log(f"Navigation error: {exc}")
    def _attempt_login(self, page, cfg: dict, PlaywrightTimeoutError):
        self._capture_log("Attempting login...")
        try:
            org_value = (cfg.get("organization") or "").strip()
            if org_value and cfg.get("organization_selector"):
                try:
                    page.select_option(cfg["organization_selector"], label=org_value, timeout=5000)
                    self._capture_log("Selected organization via select option.")
                except Exception:
                    try:
                        page.click(cfg["organization_selector"], timeout=5000)
                        page.click(f"text={org_value}")
                        self._capture_log("Selected organization via dropdown.")
                    except Exception:
                        self._capture_log("Organization selector not found.")
            if cfg.get("username") and cfg.get("username_selector"):
                page.fill(cfg["username_selector"], cfg["username"], timeout=5000)
            if cfg.get("password") and cfg.get("password_selector"):
                page.fill(cfg["password_selector"], cfg["password"], timeout=5000)
            if cfg.get("login_button_selector"):
                page.click(cfg["login_button_selector"], timeout=5000)
            else:
                page.keyboard.press("Enter")
        except PlaywrightTimeoutError:
            self._capture_log("Login timed out.")
        except Exception as exc:
            self._capture_log(f"Login error: {exc}")
    def _wait_after_navigation(self, seconds: float):
        if seconds and seconds > 0:
            self._capture_log(f"Waiting {seconds}s after navigation")
            self._responsive_wait(seconds, label="Waiting after navigation")
    def _apply_captured_text(self, text: str):
        def _apply():
            try:
                self._capture_log("Applying API capture...")
                self.process()
            except Exception as exc:
                self._capture_log(f"Apply error: {exc}")
        self.after(0, _apply)
    def _responsive_wait(self, seconds: float, label: str | None = None) -> bool:
        """Wait in small slices so Stop reacts quickly. Returns True if stop was requested."""
        target = max(0.0, float(seconds or 0))
        end = time.time() + target
        last_update = 0
        start = time.time()
        try:
            self.after(0, lambda: self.progress.config(mode="determinate", maximum=100, value=0))
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        while time.time() < end:
            if self.capture_stop.is_set():
                return True
            remaining = end - time.time()
            if label and (time.time() - last_update) >= 0.5:
                msg = f"{label}: {remaining:.1f}s remaining"
                try:
                    self.after(0, lambda m=msg: self.status.config(text=m))
                except Exception as exc:
                    self._debug_log(f"Suppressed exception: {exc}")
                last_update = time.time()
            try:
                elapsed = time.time() - start
                pct = min(100, max(0, (elapsed / target * 100) if target else 100))
                self.after(0, lambda v=pct: self.progress.config(value=v))
            except Exception as exc:
                self._debug_log(f"Suppressed exception: {exc}")
            time.sleep(min(0.2, remaining))
        # status reset handled by worker status callbacks
        try:
            self.after(0, lambda: self.progress.config(value=0))
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        return self.capture_stop.is_set()
    def _on_capture_status(self, status: str, msg: str | None = None):
        """Handle worker status updates; reflect in UI/tray."""
        self.capture_status = status
        try:
            if msg:
                self.status.config(text=msg)
            else:
                self.status.config(text=f"Status: {status}")
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        if status in {"idle", "stopped", "faulted", "retrying"}:
            self._set_pagination_busy(False)
            if self._pending_external_start:
                self.after(0, self._try_pending_external_start)
        self._update_tray_status()
    def _write_scraper_state(self, status: str) -> None:
        try:
            write_scraper_state(SCRAPER_STATE_FILE, status, pid=os.getpid())
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
    def load_capture_config(self):
        path = filedialog.askopenfilename(
            title="Select capture config JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            defaultextension=".json",
            initialdir=str(Path(CONFIG_FILE).parent),
            initialfile=Path(CONFIG_FILE).name,
        )
        if not path:
            return
        try:
            cfg = load_capture_config(
                Path(path),
                ["username", "password", "ha_token"],
                logger=None,
            )
        except Exception as exc:
            messagebox.showerror("Capture Config", f"Could not load config:\n{exc}")
            return
        self.capture_config_path = Path(path)
        self.cap_url.set(cfg.get("url", ""))
        self.cap_interval.set(str(cfg.get("interval_seconds", 60)))
        self.cap_login_wait.set(str(cfg.get("login_wait_seconds", 3)))
        self.cap_post_wait.set(str(cfg.get("post_nav_wait_seconds", 30)))
        self.cap_retry_attempts.set(int(cfg.get("retry_attempts", 3)))
        self.cap_retry_wait.set(str(cfg.get("retry_wait_seconds", cfg.get("post_nav_wait_seconds", 30))))
        self.cap_retry_backoff.set(str(cfg.get("retry_backoff_max", 4)))
        self.cap_dump_html.set(bool(cfg.get("dump_capture_html", False)))
        self.cap_dump_html_keep.set(str(cfg.get("dump_html_keep_files", DEFAULT_CAPTURE_CONFIG["dump_html_keep_files"])))
        self.cap_dump_api.set(bool(cfg.get("dump_api_json", False) or cfg.get("dump_api_full", False)))
        self.cap_dump_api_keep.set(str(cfg.get("dump_api_keep_files", DEFAULT_CAPTURE_CONFIG["dump_api_keep_files"])))
        self.cap_user.set(decrypt_secret(cfg.get("username", "")))
        self.cap_pass.set(decrypt_secret(cfg.get("password", "")))
        self.cap_user_sel.set(cfg.get("username_selector", ""))
        self.cap_pass_sel.set(cfg.get("password_selector", ""))
        self.cap_btn_sel.set(cfg.get("login_button_selector", ""))
        self.cap_org.set(cfg.get("organization", ""))
        self.cap_org_sel.set(cfg.get("organization_selector", ""))
        self.cap_headless.set(bool(cfg.get("headless", True)))
        self.cap_auto_notify_ha.set(bool(cfg.get("auto_notify_ha", False)))
        self.cap_ha_webhook.set(cfg.get("ha_webhook_url", ""))
        self.cap_ha_token.set(decrypt_secret(cfg.get("ha_token", "")))
        self.notify_price_changes.set(cfg.get("notify_price_changes", True))
        self.notify_stock_changes.set(cfg.get("notify_stock_changes", True))
        self.notify_out_of_stock.set(cfg.get("notify_out_of_stock", True))
        self.notify_restock.set(cfg.get("notify_restock", True))
        self.notify_new_items.set(cfg.get("notify_new_items", True))
        self.notify_removed_items.set(cfg.get("notify_removed_items", True))
        self.notify_windows.set(cfg.get("notify_windows", True))
        try:
            self.scraper_log_hidden_height = float(self._clamp_hidden_log_height(cfg.get("log_window_hidden_height", 210)))
        except Exception:
            self.scraper_log_hidden_height = 210.0
        self.cap_quiet_hours_enabled.set(bool(cfg.get("quiet_hours_enabled", False)))
        self.cap_quiet_start.set(cfg.get("quiet_hours_start", "22:00"))
        self.cap_quiet_end.set(cfg.get("quiet_hours_end", "07:00"))
        self.cap_quiet_interval.set(str(cfg.get("quiet_hours_interval_seconds", 3600)))
        self.cap_filter_flower.set(bool(cfg.get("filter_flower", False)))
        self.cap_filter_oil.set(bool(cfg.get("filter_oil", False)))
        self.cap_filter_vape.set(bool(cfg.get("filter_vape", False)))
        self.cap_filter_pastille.set(bool(cfg.get("filter_pastille", False)))
        self.cap_notify_detail.set(cfg.get("notification_detail", "full"))
        self.minimize_to_tray.set(cfg.get("minimize_to_tray", False))
        self.close_to_tray.set(cfg.get("close_to_tray", False))
        messagebox.showinfo("Capture Config", f"Loaded capture config from {path}")
    def save_capture_config(self):
        path = filedialog.asksaveasfilename(
            title="Save capture config JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            defaultextension=".json",
            initialdir=str(Path(CONFIG_FILE).parent),
            initialfile=Path(CONFIG_FILE).name,
        )
        if not path:
            return
        self.capture_config_path = Path(path)
        cfg = self._collect_capture_cfg()
        try:
            save_capture_config(self.capture_config_path, cfg, ["username", "password", "ha_token"])
        except Exception as exc:
            messagebox.showerror("Capture Config", f"Could not save config:\n{exc}")
            return
        messagebox.showinfo("Capture Config", f"Saved capture config to {path}")
    def _save_capture_window(self):
        target = Path(self.capture_config_path) if getattr(self, "capture_config_path", None) else Path(CONFIG_FILE)
        cfg = self._collect_capture_cfg()
        try:
            save_capture_config(target, cfg, ["username", "password", "ha_token"])
            self._log_console(f"Saved config to {target}")
        except Exception as exc:
            self._log_console(f"Failed to save config: {exc}")
        try:
            self._apply_log_window_visibility()
        except Exception:
            pass

    def _current_screen_resolution(self) -> str:
        try:
            return f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}"
        except Exception:
            return ""

    @staticmethod
    def _parse_resolution(value: str) -> tuple[int, int] | None:
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

    def _apply_resolution_safety(self) -> None:
        try:
            current = self._parse_resolution(self._current_screen_resolution())
            saved = self._parse_resolution(self.screen_resolution)
            if not current or not saved:
                self.screen_resolution = self._current_screen_resolution()
                return
            if current[0] < saved[0] or current[1] < saved[1]:
                self.scraper_window_geometry = "769x420"
                self.scraper_settings_geometry = "560x960"
                self.history_window_geometry = "900x600"
                self.screen_resolution = self._current_screen_resolution()
        except Exception:
            pass

    def _schedule_settings_geometry(self, win: tk.Toplevel) -> None:
        try:
            if getattr(self, "_settings_geometry_job", None) is not None:
                try:
                    self.after_cancel(self._settings_geometry_job)
                except Exception:
                    pass
            self._settings_geometry_job = self.after(500, lambda: self._persist_settings_geometry(win))
        except Exception:
            self._persist_settings_geometry(win)

    def _persist_settings_geometry(self, win: tk.Toplevel) -> None:
        try:
            if win and tk.Toplevel.winfo_exists(win):
                self.scraper_settings_geometry = win.geometry()
                self._save_capture_window()
        except Exception:
            pass

    def _schedule_history_geometry(self, win: tk.Toplevel) -> None:
        try:
            if getattr(self, "_history_geometry_job", None) is not None:
                try:
                    self.after_cancel(self._history_geometry_job)
                except Exception:
                    pass
            self._history_geometry_job = self.after(500, lambda: self._persist_history_geometry(win))
        except Exception:
            self._persist_history_geometry(win)

    def _persist_history_geometry(self, win: tk.Toplevel) -> None:
        try:
            if win and tk.Toplevel.winfo_exists(win):
                self.history_window_geometry = win.geometry()
                self._save_capture_window()
        except Exception:
            pass
    def _post_process_actions(self, diff: dict | None = None, items: list[dict] | None = None):
        # Called after poll completes processing
        items = list(items if items is not None else getattr(self, "data", []))
        if not items:
            return
        auto_notify = bool(self.cap_auto_notify_ha.get())
        diff_snapshot = dict(diff) if isinstance(diff, dict) else None
        def worker():
            try:
                exports_dir = Path(EXPORTS_DIR_DEFAULT)
                exports_dir.mkdir(parents=True, exist_ok=True)
                has_changes = False
                if diff_snapshot:
                    has_changes = any(
                        diff_snapshot.get(key)
                        for key in (
                            "new_items",
                            "removed_items",
                            "price_changes",
                            "stock_changes",
                            "out_of_stock_changes",
                            "restock_changes",
                        )
                    )
                    if not has_changes:
                        has_changes = bool(diff_snapshot.get("stock_change_count", 0))
                if has_changes:
                    self._generate_change_export(self._get_export_items(), silent=True)
            except Exception as exc:
                self._capture_log(f"Export preflight failed: {exc}")
            try:
                if auto_notify:
                    self.send_home_assistant(
                        log_only=False,
                        ui_errors=False,
                        diff_override=diff_snapshot,
                        items_override=items,
                    )
                else:
                    self.send_home_assistant(
                        log_only=True,
                        ui_errors=False,
                        diff_override=diff_snapshot,
                        items_override=items,
                    )
            except Exception as exc:
                self._capture_log(f"Notification processing failed: {exc}")
        threading.Thread(target=worker, daemon=True).start()

    def _quiet_hours_active(self) -> bool:
        if not self.cap_quiet_hours_enabled.get():
            return False
        def _parse(t):
            parts = str(t).strip().split(":")
            if len(parts) < 2:
                return None
            try:
                h = int(parts[0])
                m = int(parts[1])
                return h, m
            except Exception:
                return None
        start = _parse(self.cap_quiet_start.get())
        end = _parse(self.cap_quiet_end.get())
        if not start or not end:
            return False
        now = datetime.now().time()
        start_t = now.replace(hour=start[0], minute=start[1], second=0, microsecond=0)
        end_t = now.replace(hour=end[0], minute=end[1], second=0, microsecond=0)
        if start_t <= end_t:
            return start_t <= now < end_t
        return now >= start_t or now < end_t
    def send_home_assistant(
        self,
        log_only: bool = False,
        ui_errors: bool = True,
        diff_override: dict | None = None,
        items_override: list[dict] | None = None,
    ):
        debug_log = getattr(self, "_debug_log", _log_debug)
        url = self.cap_ha_webhook.get().strip()
        if not url and not log_only:
            if ui_errors:
                messagebox.showerror("Home Assistant", "Webhook URL is required.")
            else:
                self._capture_log("Home Assistant webhook URL missing; skipping notification.")
            return
        items = list(items_override if items_override is not None else getattr(self, "data", []))
        diff = diff_override
        if diff is None:
            prev_items = getattr(self, "prev_items", [])
            prev_keys = getattr(self, "prev_keys", set())
            identity_cache = _build_identity_cache(items + prev_items)
            # Fallback to persisted last parse if in-memory cache is empty
            if (not prev_items or not prev_keys) and LAST_PARSE_FILE.exists():
                try:
                    prev_items = load_last_parse(LAST_PARSE_FILE)
                    prev_keys = { _identity_key_cached(it, identity_cache) for it in prev_items }
                except Exception as exc:
                    debug_log(f"Suppressed exception: {exc}")
            diff = compute_diffs(items, prev_items)
        new_items = diff["new_items"]
        removed_items = diff["removed_items"]
        price_changes = diff["price_changes"]
        stock_changes = diff["stock_changes"]
        restock_changes = diff["restock_changes"]
        out_of_stock_changes = diff["out_of_stock_changes"]
        all_new_items = new_items
        all_removed_items = removed_items
        all_price_changes = price_changes
        all_stock_changes = stock_changes
        all_restock_changes = restock_changes
        all_out_of_stock_changes = out_of_stock_changes
        if not all_new_items and not all_removed_items and not all_price_changes and not all_stock_changes and not all_restock_changes and not all_out_of_stock_changes:
            return
        log_price_change_compact = []
        for it in all_price_changes:
            brand = it.get("brand") or it.get("producer") or ""
            strain = it.get("strain") or ""
            label = " ".join([p for p in (brand, strain) if p]).strip() or "Unknown"
            log_price_change_compact.append({
                "label": label,
                "price_before": it.get("price_before"),
                "price_after": it.get("price_after"),
                "price_delta": it.get("price_delta"),
                "direction": "up" if it.get("price_delta") and it.get("price_delta") > 0 else "down",
            })
        def _notify_flag(name: str, default: bool = True) -> bool:
            var = getattr(self, name, None)
            if hasattr(var, 'get'):
                try:
                    return bool(var.get())
                except Exception:
                    return default
            if isinstance(var, bool):
                return var
            return default

        log_stock_change_compact = []
        for it in all_stock_changes:
            brand = it.get("brand") or it.get("producer") or ""
            strain = it.get("strain") or ""
            label = " ".join([p for p in (brand, strain) if p]).strip() or "Unknown"
            log_stock_change_compact.append({
                "label": label,
                "stock_before": it.get("stock_before"),
                "stock_after": it.get("stock_after"),
            })
        log_out_of_stock_change_compact = []
        for it in all_out_of_stock_changes:
            brand = it.get("brand") or it.get("producer") or ""
            strain = it.get("strain") or ""
            label = " ".join([p for p in (brand, strain) if p]).strip() or "Unknown"
            log_out_of_stock_change_compact.append({
                "label": label,
                "stock_before": it.get("stock_before"),
                "stock_after": it.get("stock_after"),
            })
        log_restock_change_compact = []
        for it in all_restock_changes:
            brand = it.get("brand") or it.get("producer") or ""
            strain = it.get("strain") or ""
            label = " ".join([p for p in (brand, strain) if p]).strip() or "Unknown"
            log_restock_change_compact.append({
                "label": label,
                "stock_before": it.get("stock_before"),
                "stock_after": it.get("stock_after"),
            })
        if not _notify_flag('notify_new_items', True):
            new_items = []
        if not _notify_flag('notify_removed_items', True):
            removed_items = []
        if not _notify_flag('notify_price_changes', True):
            price_changes = []
        if not _notify_flag('notify_stock_changes', True):
            stock_changes = []
        if not _notify_flag('notify_out_of_stock', True):
            out_of_stock_changes = []
        if not _notify_flag('notify_restock', True):
            restock_changes = []
        def _flower_label(entry: dict) -> str:
            brand = entry.get("brand") or entry.get("producer") or ""
            strain = entry.get("strain") or ""
            label = " ".join([p for p in (brand, strain) if p]).strip()
            return label or "Unknown"
        def _item_label(entry: dict) -> str:
            parts = []
            for key in ("brand", "producer", "strain", "product_id"):
                val = entry.get(key)
                if val:
                    parts.append(str(val))
            return " ".join(parts).strip() or "Unknown"
        def _build_notification_payload(items: list[dict], diff: dict) -> tuple[dict, str]:
            new_items_local = diff["new_items"]
            removed_items_local = diff["removed_items"]
            price_changes_local = diff["price_changes"]
            stock_changes_local = diff["stock_changes"]
            restock_changes_local = diff["restock_changes"]
            out_of_stock_changes_local = diff["out_of_stock_changes"]
            new_flowers_local = [_flower_label(it) for it in new_items_local if (it.get("product_type") or "").lower() == "flower"]
            removed_flowers_local = [_flower_label(it) for it in removed_items_local if (it.get("product_type") or "").lower() == "flower"]
            new_item_summaries_local = [_item_label(it) for it in new_items_local]
            removed_item_summaries_local = [_item_label(it) for it in removed_items_local]
            price_change_summaries_local = []
            price_change_compact_local = []
            for it in price_changes_local:
                brand = it.get("brand") or it.get("producer") or ""
                strain = it.get("strain") or ""
                label = " ".join([p for p in (brand, strain) if p]).strip() or "Unknown"
                delta = it.get("price_delta")
                before = it.get("price_before")
                after = it.get("price_after")
                direction = "↑" if delta and delta > 0 else "↓"
                try:
                    delta_str = f"{delta:+.2f}" if isinstance(delta, (int, float)) else str(delta)
                except Exception:
                    delta_str = str(delta)
                price_change_summaries_local.append(f"{label} {direction}{delta_str}")
                price_change_compact_local.append(
                    {
                        "label": label,
                        "price_before": before,
                        "price_after": after,
                        "price_delta": delta,
                        "direction": "up" if delta and delta > 0 else "down",
                    }
                )
            stock_change_summaries_local = []
            for it in stock_changes_local:
                brand = it.get("brand") or it.get("producer") or ""
                strain = it.get("strain") or ""
                label = " ".join([p for p in (brand, strain) if p]).strip() or "Unknown"
                before = it.get("stock_before")
                after = it.get("stock_after")
                stock_change_summaries_local.append(f"{label}: {before} -> {after}")
            out_of_stock_change_summaries_local = []
            for it in out_of_stock_changes_local:
                brand = it.get("brand") or it.get("producer") or ""
                strain = it.get("strain") or ""
                label = " ".join([p for p in (brand, strain) if p]).strip() or "Unknown"
                before = it.get("stock_before")
                after = it.get("stock_after")
                out_of_stock_change_summaries_local.append(f"{label}: {before} -> {after}")
            restock_change_summaries_local = []
            for it in restock_changes_local:
                brand = it.get("brand") or it.get("producer") or ""
                strain = it.get("strain") or ""
                label = " ".join([p for p in (brand, strain) if p]).strip() or "Unknown"
                before = it.get("stock_before")
                after = it.get("stock_after")
                restock_change_summaries_local.append(f"{label}: {before} -> {after}")
            payload_local = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "count": len(items),
                "new_count": len(new_items_local),
                "removed_count": len(removed_items_local),
                "price_changes": price_changes_local,
                "new_flowers": new_flowers_local,
                "removed_flowers": removed_flowers_local,
                "new_item_summaries": new_item_summaries_local,
                "removed_item_summaries": removed_item_summaries_local,
                "price_change_summaries": price_change_summaries_local,
                "stock_changes": stock_changes_local,
                "stock_change_summaries": stock_change_summaries_local,
                "out_of_stock_changes": out_of_stock_changes_local,
                "out_of_stock_change_summaries": out_of_stock_change_summaries_local,
                "restock_changes": restock_changes_local,
                "restock_change_summaries": restock_change_summaries_local,
                "new_items": new_items_local,
                "removed_items": removed_items_local,
                "price_up": getattr(self, "price_up_count", 0),
                "price_down": getattr(self, "price_down_count", 0),
                "items": items,
            }
            summary_local = (
                f"+{len(new_items_local)} new, -{len(removed_items_local)} removed, "
                f"{len(price_changes_local)} price changes, {len(stock_changes_local)} stock changes, "
                f"{len(out_of_stock_changes_local)} out of stock, {len(restock_changes_local)} restocks"
            )
            return payload_local, summary_local, price_change_compact_local, stock_change_summaries_local, out_of_stock_change_summaries_local, restock_change_summaries_local
        new_flowers = [_flower_label(it) for it in new_items if (it.get("product_type") or "").lower() == "flower"]
        removed_flowers = [_flower_label(it) for it in removed_items if (it.get("product_type") or "").lower() == "flower"]
        new_item_summaries = [_item_label(it) for it in new_items]
        removed_item_summaries = [_item_label(it) for it in removed_items]
        notify_allowed = True
        if not new_items and not removed_items and not price_changes and not stock_changes and not out_of_stock_changes and not restock_changes:
            self._capture_log("Changes detected but notifications are disabled; skipping notifications.")
            notify_allowed = False
        self._log_console(
            f"Notify HA | new={len(new_items)} removed={len(removed_items)} "
            f"price_changes={len(price_changes)} stock_changes={len(stock_changes)} out_of_stock={len(out_of_stock_changes)} restocks={len(restock_changes)}"
        )
        diff_filtered = dict(diff)
        diff_filtered["new_items"] = new_items
        diff_filtered["removed_items"] = removed_items
        diff_filtered["price_changes"] = price_changes
        diff_filtered["stock_changes"] = stock_changes
        diff_filtered["out_of_stock_changes"] = out_of_stock_changes
        diff_filtered["restock_changes"] = restock_changes
        payload, summary, price_change_compact, stock_change_summaries, out_of_stock_change_summaries, restock_change_summaries = _build_notification_payload(items, diff_filtered)
        # Append structured change log for later analysis
        try:
            log_record = {
                "timestamp": payload["timestamp"],
                "new_items": [
                    {
                        "brand": it.get("brand"),
                        "producer": it.get("producer"),
                        "strain": it.get("strain"),
                        "product_id": it.get("product_id"),
                        "price": it.get("price"),
                        "product_type": it.get("product_type"),
                    }
                    for it in all_new_items
                ],
                "removed_items": [
                    {
                        "brand": it.get("brand"),
                        "producer": it.get("producer"),
                        "strain": it.get("strain"),
                        "product_id": it.get("product_id"),
                        "price": it.get("price"),
                        "product_type": it.get("product_type"),
                    }
                    for it in all_removed_items
                ],
                "price_changes": log_price_change_compact,
                "stock_changes": log_stock_change_compact,
                "out_of_stock_changes": log_out_of_stock_change_compact,
                "restock_changes": log_restock_change_compact,
            }
            append_change_log(CHANGES_LOG_FILE, log_record, max_entries=2000)
        except Exception as exc:
            debug_log(f"Suppressed exception: {exc}")
        headers = {
            "Content-Type": "application/json",
        }
        token = self.cap_ha_token.get().strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = json.dumps(payload).encode("utf-8")
        quiet_hours = self._quiet_hours_active() if hasattr(self, '_quiet_hours_active') else False
        if quiet_hours:
            self._capture_log("Quiet hours active; skipping notifications.")
            self._update_last_change(summary)
        # Build detailed desktop notification text and launch target
        detail = self.cap_notify_detail.get() if hasattr(self, 'cap_notify_detail') else 'summary'
        try:
            windows_body = self.notify_service.format_windows_body(payload, summary, detail=detail)
        except TypeError:
            windows_body = self.notify_service.format_windows_body(payload, summary)
        launch_url = self.cap_url.get().strip() if hasattr(self, 'cap_url') else ''
        export_generated = False
        if items:
            try:
                self._generate_change_export(self._get_export_items(), silent=True)
                launch_url = self._latest_export_url() or launch_url
                export_generated = True
            except Exception as exc:
                debug_log(f"Suppressed exception: {exc}")
        if not launch_url:
            try:
                launch_url = self._latest_export_url()
            except Exception:
                launch_url = None
        icon_path = ASSETS_DIR / "icon.ico"
        # Windows toast (always allowed when enabled)
        if notify_allowed and (not quiet_hours) and self.notify_windows.get():
            self._capture_log(f"Sending Windows notification: {windows_body}")
            ok_win = self.notify_service.send_windows("Medicann update", windows_body, icon_path, launch_url=launch_url)
            if not ok_win:
                self._capture_log("Windows notification failed to send.")
        elif notify_allowed and not quiet_hours:
            self._capture_log("Windows notifications disabled; skipping.")
        # If log-only or quiet hours, skip HA network send
        if notify_allowed and not (log_only or quiet_hours):
            ok, status, body = self.notify_service.send_home_assistant(payload)
            if ok and status:
                self._update_last_change(summary)
            else:
                self._capture_log(f"HA response status: {status} body: {str(body)[:200] if body else ''}")
        elif notify_allowed and not quiet_hours:
            if log_only:
                self._capture_log("HA notifications set to log-only; skipping network send.")
            else:
                self._capture_log("HA notifications disabled; skipping.")
        if items and not export_generated:
            try:
                self._generate_change_export(self._get_export_items())
            except Exception as exc:
                self._capture_log(f"Export generation error: {exc}")
    def _send_ha_error(self, message: str):
        url = self.cap_ha_webhook.get().strip()
        if not url:
            return
        headers = {"Content-Type": "application/json"}
        token = self.cap_ha_token.get().strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        payload = {"error": message, "timestamp": datetime.now(timezone.utc).isoformat()}
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
            self._capture_log(f"Sent error to Home Assistant (status {status}).")
        except Exception as exc:
            self._capture_log(f"Home Assistant error notify failed: {exc}")
    def send_test_notification(self):
        """Send a simple test payload to Home Assistant to validate settings."""
        url = self.cap_ha_webhook.get().strip()
        if not url:
            messagebox.showerror("Home Assistant", "Webhook URL is required for test.")
            return
        payload = {
            "test": True,
            "message": "Medicann Scraper test notification",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        quiet_hours = self._quiet_hours_active() if hasattr(self, '_quiet_hours_active') else False
        ok, status, body = self.notify_service.send_home_assistant_test(payload)
        if ok:
            self._log_console(f"Test notification sent (status {status}).")
            messagebox.showinfo("Home Assistant", f"Test notification sent (status {status}).")
        else:
            self._log_console(f"Test notification error: status={status} body={str(body)[:200] if body else ''}")
            messagebox.showerror("Home Assistant", f"Test notification failed:\nstatus={status}\nbody={body}")
        # Also send a Windows test notification if enabled
        if (not quiet_hours) and self.notify_windows.get():
            icon_path = ASSETS_DIR / "icon.ico"
            self._log_console("Sending Windows test notification.")
            test_body = (
                f"HA test status: {status or 'error'} | "
                "New: Alpha Kush, Beta OG | Removed: None | Price: Gamma Glue GBP 2.50; Delta Dream GBP 1.00 | "
                "Stock: Zeta Zen: 10 -> 8"
            )
            launch_url = self.cap_url.get().strip() if hasattr(self, "cap_url") else ""
            if not launch_url:
                try:
                    launch_url = self._latest_export_url()
                except Exception:
                    launch_url = None
                if launch_url is None:
                    try:
                        data = self._get_export_items()
                        if data:
                            self._generate_change_export(data)
                            launch_url = self._latest_export_url()
                    except Exception:
                        launch_url = None
            _maybe_send_windows_notification("Medicann test", test_body, icon_path, launch_url=launch_url)
    def open_exports_folder(self):
        messagebox.showinfo("Exports", "Exports disabled; only HA notifications and local cache remain.")
    def open_recent_export(self):
        messagebox.showinfo("Exports", "Exports disabled; only HA notifications and local cache remain.")
    def start_export_server(self):
        if self.httpd:
            _log_debug(f"[server] already running on port {self.server_port}")
            return True
        exports_dir = Path(EXPORTS_DIR_DEFAULT)
        httpd, thread, port = srv_start_export_server(self.server_port, exports_dir, _log_debug)
        if not httpd:
            if port:
                self.server_port = port
                return True
            if not self._server_failed:
                self._server_failed = True
                messagebox.showerror("Export Server", "Could not start export server on localhost. Exports will open from file:// instead.")
            return False
        self.httpd = httpd
        self.http_thread = thread
        self.server_port = port
        return True
    def _ensure_export_server(self):
        if self.httpd:
            if _port_ready("127.0.0.1", self.server_port):
                _log_debug("[server] ensure_export_server: already running")
                return True
            _log_debug("[server] ensure_export_server: port not ready; restarting server")
            try:
                self.stop_export_server()
            except Exception as exc:
                self._debug_log(f"Suppressed exception: {exc}")
        ok = self.start_export_server()
        if not ok and not self._server_failed:
            self._server_failed = True
            messagebox.showerror(
                "Export Server", "Could not start export server on localhost. Exports will open from file:// instead."
            )
        if not ok:
            _log_debug("[server] ensure_server failed; falling back to file://")
        else:
            _log_debug("[server] ensure_export_server: server available")
        return ok
    def stop_export_server(self):
        if self.httpd:
            srv_stop_export_server(self.httpd, self.http_thread, _log_debug)
            self.httpd = None
            self.http_thread = None
    def _on_close(self):
        # Always hide instead of exiting; capture continues running
        self._minimize_to_tray()
    def _exit_app(self):
        try:
            # mark scraper stopped
            self._write_scraper_state("stopped")
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        try:
            self.capture_stop.set()
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        try:
            self.stop_export_server()
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        try:
            if self.settings_window and tk.Toplevel.winfo_exists(self.settings_window):
                self.settings_window.destroy()
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        try:
            self._hide_tray_icon()
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        try:
            self.destroy()
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
    def _open_url_with_fallback(self, url: str, file_path: Path) -> None:
        """
        Try to hit the server URL; if unreachable, fall back to opening the file:// version.
        This avoids a browser "connection reset" if the embedded server is blocked/closed.
        """
        ok = False
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=2) as resp:
                ok = (200 <= resp.status < 400)
        except Exception as e:
            _log_debug(f"[export] probe failed for {url}: {e}")
            ok = False
        if ok:
            _log_debug(f"[export] opening URL {url}")
            webbrowser.open(url)
        else:
            _log_debug(f"[export] falling back to file:// for {file_path}")
            webbrowser.open(file_path.as_uri())
    def process(self):
        api_items = []
        try:
            payloads = None
            latest_path = DATA_DIR / "api_latest.json"
            if latest_path.exists():
                payloads = json.loads(latest_path.read_text(encoding="utf-8"))
            else:
                api_files = sorted(DATA_DIR.glob("api_dump_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
                if api_files:
                    payloads = json.loads(api_files[0].read_text(encoding="utf-8"))
            if payloads:
                api_items = parse_api_payloads(payloads)
        except Exception:
            api_items = []
        if not api_items:
            self._capture_log("No API data found; skipping parse.")
            return
        items = list(api_items)
        self._capture_log(f"API items parsed: {len(items)}")
        if items:
            seen_ids = set()
            deduped_api = []
            for it in items:
                pid = it.get("product_id")
                if pid:
                    key = f"id:{pid}"
                else:
                    key = f"name:{it.get('title') or ''}|brand:{it.get('brand') or ''}|g:{it.get('grams') or ''}|ml:{it.get('ml') or ''}"
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                deduped_api.append(it)
            if len(deduped_api) != len(items):
                self._capture_log(f"Deduped {len(items) - len(deduped_api)} items with duplicate IDs.")
            items = deduped_api
        prev_items = load_last_parse(LAST_PARSE_FILE)
        identity_cache = _build_identity_cache(prev_items)
        prev_keys = { _identity_key_cached(it, identity_cache) for it in prev_items }
        prev_price_map = {}
        prev_stock_map = {}
        prev_rem_map = {}
        for pit in prev_items:
            try:
                prev_price_map[_identity_key_cached(pit, identity_cache)] = float(pit.get("price")) if pit.get("price") is not None else None
            except Exception:
                prev_price_map[_identity_key_cached(pit, identity_cache)] = None
            prev_stock_map[_identity_key_cached(pit, identity_cache)] = pit.get("stock")
            prev_rem_map[_identity_key_cached(pit, identity_cache)] = pit.get("stock_remaining")
        self.prev_items = prev_items
        self.prev_keys = prev_keys
        self.removed_data = []
        price_up = 0
        price_down = 0
        deduped = []
        for it in items:
            it = dict(it)
            ident_key = make_identity_key(it)
            it["is_new"] = ident_key not in prev_keys
            # Price delta vs prior parse
            delta = None
            try:
                cur_price = float(it["price"]) if it.get("price") is not None else None
            except Exception:
                cur_price = None
            prev_price = prev_price_map.get(ident_key)
            if cur_price is not None and isinstance(prev_price, (int, float)):
                delta = cur_price - prev_price
                # tiny differences are noise
                if abs(delta) < 1e-3:
                    delta = 0.0
            if isinstance(delta, (int, float)) and delta:
                if delta > 0:
                    price_up += 1
                elif delta < 0:
                    price_down += 1
            it["price_delta"] = delta
            # Stock delta / restock flag for export highlighting
            stock_delta = None
            prev_rem = prev_rem_map.get(ident_key)
            cur_rem = it.get("stock_remaining")
            try:
                if prev_rem is not None and cur_rem is not None:
                    stock_delta = float(cur_rem) - float(prev_rem)
            except Exception:
                stock_delta = None
            if isinstance(stock_delta, (int, float)) and abs(stock_delta) < 1e-6:
                stock_delta = 0.0
            if stock_delta is not None:
                it["stock_delta"] = stock_delta
                if stock_delta > 0:
                    it["is_restock"] = True
            deduped.append(it)
        self.data = []
        try:
            self.progress.config(mode='determinate', maximum=len(deduped))
            self.progress['value'] = 0
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        self.status.config(text="Processing.")
        def worker():
            try:
                total = len(deduped)
                for idx, item in enumerate(deduped, 1):
                    self.q.put(("item", idx, total, item))
                    time.sleep(0.005)
            except Exception as e:
                self.q.put(("error", str(e)))
            finally:
                self.q.put(("done", len(deduped)))
        threading.Thread(target=worker, daemon=True).start()
        if not self._polling:
            self._polling = True
        self.after(50, self.poll)
    def _stage_parse(self) -> list[dict]:
        """Parse stage (data already collected); returns a stable list snapshot."""
        items = list(self.data)
        try:
            selected = set()
            if self.cap_filter_flower.get():
                selected.add("flower")
            if self.cap_filter_oil.get():
                selected.add("oil")
            if self.cap_filter_vape.get():
                selected.add("vape")
            if self.cap_filter_pastille.get():
                selected.add("pastille")
            if not selected:
                return items
            filtered = []
            for item in items:
                raw_type = item.get("product_type") if isinstance(item, dict) else None
                norm_type = str(raw_type).strip().lower() if raw_type else "flower"
                if norm_type in selected:
                    filtered.append(item)
            if len(filtered) != len(items):
                self._capture_log(f"Filters applied: {len(filtered)} / {len(items)} items kept.")
            return filtered
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
            return items

    def _stage_diff(self, items: list[dict]) -> dict:
        """Diff stage: compute changes vs previous parse and update counters."""
        prev_items = getattr(self, "prev_items", [])
        diff = compute_diffs(items, prev_items)
        self.removed_data = diff["removed_items"]
        self.price_up_count = diff["price_up"]
        self.price_down_count = diff["price_down"]
        return diff

    def _stage_notify(self, diff: dict, item_count: int, items: list[dict] | None = None) -> None:
        """Notify stage: update UI status/logs and trigger post-process actions."""
        new_count = len(diff["new_items"])
        removed_count = len(diff["removed_items"])
        stock_change_count = diff["stock_change_count"]
        self.status.config(
            text=(
                f"Done | {item_count} items | "
                f"+{new_count} new | -{removed_count} removed | "
                f"{self.price_up_count} price increases | {self.price_down_count} price decreases | "
                f"{stock_change_count} stock changes"
            )
        )
        self._log_console(
            f"Done | {item_count} items | +{new_count} new | -{removed_count} removed | "
            f"{self.price_up_count} price increases | {self.price_down_count} price decreases | "
            f"{stock_change_count} stock changes"
        )
        if (
            new_count == 0
            and removed_count == 0
            and self.price_up_count == 0
            and self.price_down_count == 0
            and stock_change_count == 0
        ):
            self._capture_log("No changes detected; skipping notifications.")
        self._post_process_actions(diff, items or getattr(self, "data", []))

    def _stage_persist(self, diff: dict, items: list[dict]) -> None:
        """Persist stage: save last parse and update prev cache/timers."""
        try:
            save_last_parse(LAST_PARSE_FILE, items)
            self._capture_log(f"Saved last parse to {LAST_PARSE_FILE}")
        except Exception as exc:
            self._capture_log(f"Failed to save last parse: {exc}")
        try:
            self._set_next_capture_timer(float(self.cap_interval.get() or 0))
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        # Update prev cache for next run after notifications are sent
        self.prev_items = list(items)
        self.prev_keys = diff.get("current_keys", set())
        self._polling = False

    def poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if msg[0] == "item":
                    _, idx, total, payload = msg
                    self.data.append(payload)
                    self.status.config(text=f"Processing {idx} / {total}")
                    try:
                        self.progress['value'] = idx
                    except Exception as exc:
                        self._debug_log(f"Suppressed exception: {exc}")
                elif msg[0] == "error":
                    _, err = msg
                    self.progress.stop()
                    self.status.config(text=f"Error: {err}")
                    messagebox.showerror("Processing Error", err)
                elif msg[0] == "done":
                    try:
                        self.progress['value'] = self.progress['maximum']
                    except Exception as exc:
                        self._debug_log(f"Suppressed exception: {exc}")
                    # Parse stage (already collected in worker)
                    parsed_items = self._stage_parse()
                    if not parsed_items:
                        self.error_count += 1
                        self._empty_retry_pending = True
                        self._update_tray_status()
                        self.status.config(text="No products parsed; retrying shortly.")
                        self._log_console("No products parsed; retrying shortly.")
                        if _should_stop_on_empty(self.error_count, self.error_threshold):
                            msg = "Repeated empty captures; auto-scraper stopped."
                            self._log_console(msg)
                            self.notify_service.send_windows("Medicann error", msg, ASSETS_DIR / "icon.ico")
                            if self.cap_auto_notify_ha.get():
                                self._send_ha_error(msg)
                            self.stop_auto_capture()
                        self._polling = False
                        return
                    self.error_count = 0
                    self._empty_retry_pending = False
                    self._update_tray_status()
                    self._update_last_scrape()
                    diff = self._stage_diff(parsed_items)
                    self._stage_notify(diff, len(parsed_items), parsed_items)
                    self._stage_persist(diff, parsed_items)
                    return
        except Empty:
            pass
        if self._polling:
            self.after(50, self.poll)
        # Update last change label periodically
        try:
            ts = get_last_change(SCRAPER_STATE_FILE)
            if ts:
                self.last_change_label.config(text=f"Last change detected: {ts}")
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        try:
            ts = get_last_scrape(SCRAPER_STATE_FILE)
            if ts:
                self.last_scrape_label.config(text=f"Last successful scrape: {ts}")
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
    def _get_export_items(self):
        combined = list(self.data)
        if getattr(self, "removed_data", None):
            combined.extend(self.removed_data)
        return combined
    # Export functions removed (no longer used)
    def _clear_parse_cache(self, notify: bool = True) -> bool:
        cleared = False
        self.data.clear()
        self.prev_items = []
        self.prev_keys = set()
        self.removed_data = []
        try:
            if LAST_PARSE_FILE.exists():
                LAST_PARSE_FILE.unlink()
                cleared = True
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        if notify:
            self.status.config(text="Parse cache cleared")
            messagebox.showinfo("Cleared", "Parsed cache cleared.")
        return cleared

    def _clear_change_history(self, notify: bool = True) -> bool:
        cleared = False
        try:
            if CHANGES_LOG_FILE.exists():
                CHANGES_LOG_FILE.unlink()
                cleared = True
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        if notify:
            self.status.config(text="Change history cleared")
            messagebox.showinfo("Cleared", "Change history log cleared.")
        return cleared

    def _clear_scraper_state_cache(self, notify: bool = True) -> bool:
        try:
            self.progress['value'] = 0
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        try:
            self.last_change_label.config(text="Last change detected: none")
            self.last_scrape_label.config(text="Last successful scrape: none")
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        update_scraper_state(SCRAPER_STATE_FILE, last_change=None, last_scrape=None)
        if notify:
            self.status.config(text="Scraper state cleared")
            messagebox.showinfo("Cleared", "Scraper state markers cleared.")
        return True

    def clear_cache(self):
        self._clear_parse_cache(notify=False)
        self._clear_change_history(notify=False)
        self._clear_scraper_state_cache(notify=False)
        self.status.config(text="Cache cleared")
        messagebox.showinfo("Cleared", "Cleared parsed cache, change history, and scraper state.")
    def _clear_auth_cache(self) -> None:
        if self.capture_thread and self.capture_thread.is_alive():
            messagebox.showwarning("Auth Cache", "Stop auto-capture before clearing auth cache.")
            return
        try:
            worker = CaptureWorker.__new__(CaptureWorker)
            worker.app_dir = APP_DIR
            worker.callbacks = {"capture_log": self._log_console}
            cleared = worker.clear_auth_cache()
        except Exception as exc:
            self._log_console(f"Auth cache clear failed: {exc}")
            cleared = False
        if cleared:
            self._log_console("Auth cache cleared; next capture will bootstrap auth.")
            messagebox.showinfo("Auth Cache", "Auth cache cleared; next capture will re-authenticate.")
        else:
            messagebox.showinfo("Auth Cache", "No auth cache found to clear.")
    def _run_auth_bootstrap(self) -> None:
        if self.capture_thread and self.capture_thread.is_alive():
            messagebox.showwarning("Auth Token", "Stop auto-capture before bootstrapping auth.")
            return
        try:
            self._save_capture_window()
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        cfg = self._collect_capture_cfg()
        if not cfg.get("url"):
            messagebox.showwarning("Auth Token", "Please set the target URL before bootstrapping.")
            return
        if not cfg.get("username") or not cfg.get("password") or not cfg.get("organization"):
            cfg = dict(cfg)
            cfg["headless"] = False
            messagebox.showinfo(
                "Auth Token",
                "Missing account details. A browser will open for manual login.",
            )
        stop_event = threading.Event()

        def install_cb():
            return install_playwright_browsers(Path(APP_DIR), self._capture_log)

        def worker():
            try:
                self._auth_bootstrap_log("Auth bootstrap starting...")
                cw = CaptureWorker.__new__(CaptureWorker)
                cw.cfg = cfg
                cw.app_dir = APP_DIR
                cw.install_fn = install_cb
                cw.callbacks = {
                    "capture_log": self._auth_bootstrap_log,
                    "responsive_wait": self._responsive_wait,
                    "stop_event": stop_event,
                    "prompt_manual_login": self._prompt_manual_login,
                }
                cw._auth_bootstrap_failures = 0
                payloads = cw._bootstrap_auth_with_playwright()
                if payloads:
                    try:
                        cw._persist_auth_cache(payloads)
                        self._auth_bootstrap_log("Auth bootstrap complete; token cached.")
                        messagebox.showinfo("Auth Token", "Auth token captured and cached.")
                    except Exception as exc:
                        self._auth_bootstrap_log(f"Auth cache write failed: {exc}")
                        messagebox.showwarning("Auth Token", f"Token captured but cache write failed:\n{exc}")
                else:
                    self._auth_bootstrap_log("Auth bootstrap did not capture a token.")
                    messagebox.showwarning("Auth Token", "Auth bootstrap did not capture a token.")
            except Exception as exc:
                self._auth_bootstrap_log(f"Auth bootstrap failed: {exc}")
                messagebox.showerror("Auth Token", f"Auth bootstrap failed:\n{exc}")

        threading.Thread(target=worker, daemon=True).start()
    def _set_busy_ui(self, busy, message=None):
        try:
            if busy:
                self.progress.config(mode='indeterminate')
                self.progress.start(10)
                self.status.config(text=message or "Working.")
            else:
                try:
                    self.progress.stop()
                    self.progress.config(mode='determinate', value=0)
                except Exception as exc:
                    self._debug_log(f"Suppressed exception: {exc}")
                self.status.config(text="Idle")
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
    def apply_theme(self):
        dark = self.dark_mode_var.get()
        colors = compute_colors(dark)
        apply_style_theme(self.style, colors)
        self.configure(bg=colors["bg"])
        self.status.configure(background=colors["bg"], foreground=colors["fg"])
        # Scrollbar theming (tk + ttk)
        self.option_add("*Scrollbar.background", colors["ctrl_bg"])
        self.option_add("*Scrollbar.troughColor", colors["bg"])
        self.option_add("*Scrollbar.activeBackground", colors["accent"])
        self.option_add("*TScrollbar*background", colors["ctrl_bg"])
        self.option_add("*TScrollbar*troughColor", colors["bg"])
        self.option_add("*TScrollbar*arrowcolor", colors["fg"])
        self.option_add("*Menu*Background", colors["ctrl_bg"])
        self.option_add("*Menu*Foreground", colors["fg"])
        self.option_add("*Menu*ActiveBackground", colors["accent"])
        self.option_add("*Menu*ActiveForeground", colors["bg"])
        highlight = colors.get("highlight", colors["accent"])
        highlight_text = colors.get("highlight_text", "#ffffff")
        self.option_add("*TCombobox*Listbox*Background", colors["ctrl_bg"])
        self.option_add("*TCombobox*Listbox*Foreground", colors["fg"])
        self.option_add("*TCombobox*Listbox*selectBackground", highlight)
        self.option_add("*TCombobox*Listbox*selectForeground", highlight_text)
        # Alias patterns improve reliability across Tk builds/themes.
        self.option_add("*TCombobox*Listbox.background", colors["ctrl_bg"])
        self.option_add("*TCombobox*Listbox.foreground", colors["fg"])
        self.option_add("*TCombobox*Listbox.selectBackground", highlight)
        self.option_add("*TCombobox*Listbox.selectForeground", highlight_text)
        self.option_add("*TCombobox*Entry*selectBackground", highlight)
        self.option_add("*TCombobox*Entry*selectForeground", highlight_text)
        self.option_add("*TCombobox*Entry*inactiveselectBackground", highlight)
        self.option_add("*TCombobox*Entry*inactiveselectForeground", highlight_text)
        self.option_add("*Entry*selectBackground", highlight)
        self.option_add("*Entry*selectForeground", highlight_text)
        self.option_add("*Entry*inactiveselectBackground", highlight)
        self.option_add("*Entry*inactiveselectForeground", highlight_text)
        # ttk scrollbar styling
        self.style.configure(
            "Vertical.TScrollbar",
            background=colors["ctrl_bg"],
            troughcolor=colors["bg"],
            arrowcolor=colors["fg"],
            bordercolor=colors["ctrl_bg"],
            lightcolor=colors["ctrl_bg"],
            darkcolor=colors["ctrl_bg"],
        )
        self.style.configure(
            "Horizontal.TScrollbar",
            background=colors["ctrl_bg"],
            troughcolor=colors["bg"],
            arrowcolor=colors["fg"],
            bordercolor=colors["ctrl_bg"],
            lightcolor=colors["ctrl_bg"],
            darkcolor=colors["ctrl_bg"],
        )
        self.style.configure(
            "Scraper.Horizontal.TProgressbar",
            background=colors["accent"],
            troughcolor=colors["ctrl_bg"],
            bordercolor=colors.get("border", colors["ctrl_bg"]),
            lightcolor=colors.get("border", colors["ctrl_bg"]),
            darkcolor=colors.get("border", colors["ctrl_bg"]),
        )
        self.style.map(
            "Scraper.Horizontal.TProgressbar",
            background=[("disabled", colors["accent"]), ("!disabled", colors["accent"])],
            troughcolor=[("disabled", colors["ctrl_bg"]), ("!disabled", colors["ctrl_bg"])],
        )
        # Apply option database overrides for classic Tk scrollbars (used by ScrolledText)
        try:
            self.option_add("*Scrollbar.background", colors["ctrl_bg"])
            self.option_add("*Scrollbar.troughColor", colors["bg"])
            self.option_add("*Scrollbar.activeBackground", colors["accent"])
            self.option_add("*Scrollbar.arrowColor", colors["fg"])
            self.option_add("*Scrollbar.relief", "flat")
            self.option_add("*Scrollbar.borderWidth", 0)
            self.option_add("*Scrollbar.highlightThickness", 0)
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        for child in self.winfo_children():
            if isinstance(child, tk.Text):
                child.configure(bg=colors["bg"], fg=colors["fg"], insertbackground=colors["fg"])
            if isinstance(child, ttk.Frame):
                child.configure(style="TFrame")
        if hasattr(self, "console"):
            try:
                self.console.configure(
                    bg=colors["ctrl_bg"],
                    fg=colors["fg"],
                    insertbackground=colors["fg"],
                    selectbackground=colors["accent"],
                    selectforeground=highlight_text,
                    highlightthickness=0,
                    borderwidth=0,
                )
                try:
                    if hasattr(self, "console_scroll"):
                        self.console_scroll.configure(style="Dark.Vertical.TScrollbar")
                except Exception as exc:
                    self._debug_log(f"Suppressed exception: {exc}")
            except Exception as exc:
                self._debug_log(f"Suppressed exception: {exc}")
        try:
            self.progress.configure(style="Scraper.Horizontal.TProgressbar")
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        if hasattr(self, "auth_bootstrap_log_widget") and self.auth_bootstrap_log_widget:
            try:
                self.auth_bootstrap_log_widget.configure(
                    bg=colors["ctrl_bg"],
                    fg=colors["fg"],
                    insertbackground=colors["fg"],
                    selectbackground=colors["accent"],
                    selectforeground=highlight_text,
                    highlightthickness=0,
                    borderwidth=0,
                )
            except Exception as exc:
                self._debug_log(f"Suppressed exception: {exc}")
        if hasattr(self, "auth_bootstrap_log_frame") and self.auth_bootstrap_log_frame:
            try:
                self.auth_bootstrap_log_frame.configure(
                    bg=colors["ctrl_bg"],
                    highlightthickness=1,
                    highlightbackground=colors.get("border", colors["ctrl_bg"]),
                    highlightcolor=colors.get("border", colors["ctrl_bg"]),
                    bd=0,
                )
            except Exception as exc:
                self._debug_log(f"Suppressed exception: {exc}")
        try:
            ts = get_last_change(SCRAPER_STATE_FILE)
            if ts:
                self.last_change_label.config(text=f"Last change detected: {ts}")
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        try:
            ts = get_last_scrape(SCRAPER_STATE_FILE)
            if ts:
                self.last_scrape_label.config(text=f"Last successful scrape: {ts}")
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        self.after(50, lambda: set_titlebar_dark(self, dark))
        if self.capture_window and tk.Toplevel.winfo_exists(self.capture_window):
            self._apply_theme_to_window(self.capture_window)
        if self.settings_window and tk.Toplevel.winfo_exists(self.settings_window):
            self._apply_theme_to_window(self.settings_window)
        if self.history_window and tk.Toplevel.winfo_exists(self.history_window):
            self._apply_theme_to_window(self.history_window)
        # Ensure main titlebar follows theme
        try:
            self._set_window_titlebar_dark(self, dark)
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
    def _refresh_theme_from_config(self):
        try:
            desired = bool(self._load_dark_mode())
            palette_changed = self._refresh_palette_overrides_from_config()
            if desired != bool(self.dark_mode_var.get()) or palette_changed:
                self.dark_mode_var.set(desired)
                self.apply_theme()
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        try:
            self.after(2000, self._refresh_theme_from_config)
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")

    def _refresh_palette_overrides_from_config(self) -> bool:
        try:
            cfg = load_tracker_config(Path(CONFIG_FILE))
        except Exception:
            return False
        dark = cfg.get("theme_palette_dark", {})
        light = cfg.get("theme_palette_light", {})
        if not isinstance(dark, dict):
            dark = {}
        if not isinstance(light, dict):
            light = {}
        sig = json.dumps({"dark": dark, "light": light}, sort_keys=True)
        if sig == getattr(self, "_palette_signature", ""):
            return False
        self._palette_signature = sig
        try:
            set_palette_overrides(dark, light)
        except Exception:
            return False
        return True
    def toggle_theme(self):
        self.apply_theme()
        _save_tracker_dark_mode(self.dark_mode_var.get())
    def _load_dark_mode(self) -> bool:
        return _load_tracker_dark_mode(True)
    def _resource_path(self, relative: str) -> str:
        return resource_path(relative)
    def _set_win_titlebar_dark(self, enable: bool):
        """On Windows 10/11, ask DWM for a dark title bar to match the theme."""
        if os.name != 'nt':
            return
        try:
            hwnd = self.winfo_id()
            # Tk may give a child handle; walk up to the top-level window
            GetParent = ctypes.windll.user32.GetParent
            parent = GetParent(hwnd)
            while parent:
                hwnd = parent
                parent = GetParent(hwnd)
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19
            BOOL = ctypes.c_int
            value = BOOL(1 if enable else 0)
            # Try newer attribute, fallback to older if it fails
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)) != 0:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1, ctypes.byref(value), ctypes.sizeof(value))
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
    def _set_window_titlebar_dark(self, window, enable: bool):
        """Apply dark title bar to a specific window."""
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
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
    def _apply_theme_recursive(self, widget, bg, fg, ctrl_bg, accent, highlight, highlight_text, dark):
        """Lightweight recursive theming for child widgets."""
        try:
            if isinstance(widget, ttk.Notebook):
                try:
                    self.style.configure("Settings.TNotebook", background=bg, borderwidth=0, tabmargins=2)
                    self.style.configure("Settings.TNotebook.Tab", background=ctrl_bg, foreground=fg, padding=[10, 4])
                    self.style.map(
                        "Settings.TNotebook.Tab",
                        background=[("selected", accent), ("!selected", ctrl_bg)],
                        foreground=[("selected", "#000" if dark else "#fff"), ("!selected", fg)],
                    )
                except Exception as exc:
                    self._debug_log(f"Suppressed exception: {exc}")
            elif isinstance(widget, ttk.Labelframe):
                try:
                    widget.configure(style="Parser.TLabelframe")
                    self.style.configure("Parser.TLabelframe", background=bg, foreground=fg, bordercolor=accent, relief="groove")
                    self.style.configure("Parser.TLabelframe.Label", background=bg, foreground=fg)
                except Exception as exc:
                    self._debug_log(f"Suppressed exception: {exc}")
            elif isinstance(widget, ttk.Frame):
                try:
                    widget.configure(style="TFrame")
                except Exception as exc:
                    self._debug_log(f"Suppressed exception: {exc}")
            elif isinstance(widget, ttk.Label):
                try:
                    widget.configure(style="TLabel")
                except Exception as exc:
                    self._debug_log(f"Suppressed exception: {exc}")
            elif isinstance(widget, ttk.Button):
                try:
                    widget.configure(style="TButton")
                except Exception as exc:
                    self._debug_log(f"Suppressed exception: {exc}")
            elif isinstance(widget, ttk.Entry):
                try:
                    widget.configure(style="TEntry")
                except Exception as exc:
                    self._debug_log(f"Suppressed exception: {exc}")
            elif isinstance(widget, ttk.Checkbutton):
                try:
                    widget.configure(style="TCheckbutton")
                except Exception as exc:
                    self._debug_log(f"Suppressed exception: {exc}")
            if isinstance(widget, tk.Listbox):
                widget.configure(
                    bg=bg if dark else "#ffffff",
                    fg=fg,
                    selectbackground=highlight,
                    selectforeground=highlight_text,
                    highlightbackground=bg,
                )
            elif isinstance(widget, tk.Text):
                widget.configure(bg=bg, fg=fg, insertbackground=fg, highlightbackground=bg)
            elif isinstance(widget, ttk.Widget):
                pass
            else:
                # Attempt generic background/foreground where supported (covers frames/labels/buttons)
                for opt, val in (("background", bg), ("foreground", fg)):
                    try:
                        if opt in widget.keys():
                            widget.configure(**{opt: val})
                    except Exception as exc:
                        self._debug_log(f"Suppressed exception: {exc}")
            for child in widget.winfo_children():
                self._apply_theme_recursive(child, bg, fg, ctrl_bg, accent, highlight, highlight_text, dark)
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
    def _apply_theme_to_window(self, window):
        dark = self.dark_mode_var.get()
        colors = compute_colors(dark)
        bg = colors["bg"]
        fg = colors["fg"]
        ctrl_bg = colors["ctrl_bg"]
        accent = colors["accent"]
        highlight = colors.get("highlight", colors["accent"])
        highlight_text = colors.get("highlight_text", "#ffffff")
        border = colors.get("border", ctrl_bg)
        muted = colors.get("muted", fg)
        def _clear_entry_selection(widget):
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
        def _bind_entry_clear(widget):
            try:
                widget.bind("<FocusOut>", lambda _e: _clear_entry_selection(widget))
            except Exception:
                pass
        try:
            window.configure(bg=bg)
            for widget in window.winfo_children():
                self._apply_theme_recursive(widget, bg, fg, ctrl_bg, accent, highlight, highlight_text, dark)
            self._apply_entry_clear_bindings(window)
            self._set_window_titlebar_dark(window, dark)
            self._set_win_titlebar_dark(dark)
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        try:
            self.style.map(
                "TEntry",
                bordercolor=[("focus", border), ("!focus", border)],
                lightcolor=[("focus", border), ("!focus", border)],
                darkcolor=[("focus", border), ("!focus", border)],
                focuscolor=[("focus", border), ("!focus", border)],
            )
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        try:
            self.style.configure(
                "Scraper.TEntry",
                fieldbackground=ctrl_bg,
                foreground=fg,
                insertcolor=fg,
                bordercolor=border,
                lightcolor=border,
                darkcolor=border,
                focuscolor=ctrl_bg,
                borderwidth=1,
            )
            self.style.map(
                "Scraper.TEntry",
                fieldbackground=[("readonly", ctrl_bg)],
                foreground=[("readonly", fg)],
                bordercolor=[("focus", border), ("!focus", border)],
                lightcolor=[("focus", border), ("!focus", border)],
                darkcolor=[("focus", border), ("!focus", border)],
                focuscolor=[("focus", ctrl_bg), ("!focus", ctrl_bg)],
            )
            self.style.layout(
                "Scraper.TEntry",
                [
                    (
                        "Entry.field",
                        {
                            "sticky": "nswe",
                            "border": "1",
                            "children": [
                                (
                                    "Entry.padding",
                                    {
                                        "sticky": "nswe",
                                        "children": [
                                            ("Entry.textarea", {"sticky": "nswe"})
                                        ],
                                    },
                                )
                            ],
                        },
                    )
                ],
            )
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        try:
            self.style.configure(
                "Scraper.TCombobox",
                fieldbackground=ctrl_bg,
                background=ctrl_bg,
                foreground=fg,
                bordercolor=border,
                lightcolor=border,
                darkcolor=border,
                arrowcolor=fg,
                focuscolor=ctrl_bg,
                borderwidth=1,
            )
            self.style.map(
                "Scraper.TCombobox",
                bordercolor=[("focus", border), ("!focus", border)],
                lightcolor=[("focus", border), ("!focus", border)],
                darkcolor=[("focus", border), ("!focus", border)],
                focuscolor=[("focus", ctrl_bg), ("!focus", ctrl_bg)],
            )
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
        try:
            highlight = colors.get("highlight", muted if dark else "#d6d6d6")
            self.option_add("*Entry*selectBackground", highlight)
            self.option_add("*Entry*selectForeground", colors.get("highlight_text", "#ffffff"))
            self.option_add("*Entry*inactiveselectBackground", highlight)
            self.option_add("*Entry*inactiveselectForeground", colors.get("highlight_text", "#ffffff"))
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")

    def _apply_entry_clear_bindings(self, widget):
        def _clear_entry_selection(entry_widget):
            try:
                entry_widget.selection_clear()
            except Exception:
                try:
                    entry_widget.tk.call(entry_widget._w, "selection", "clear")
                except Exception:
                    pass
            try:
                entry_widget.icursor("end")
            except Exception:
                pass

        def _bind_entry_clear(entry_widget):
            try:
                entry_widget.bind("<FocusOut>", lambda _e: _clear_entry_selection(entry_widget))
            except Exception:
                pass

        try:
            if isinstance(widget, ttk.Entry):
                _bind_entry_clear(widget)
            for child in widget.winfo_children():
                self._apply_entry_clear_bindings(child)
        except Exception as exc:
            self._debug_log(f"Suppressed exception: {exc}")
if __name__ == "__main__":
    App().mainloop()
