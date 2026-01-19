from __future__ import annotations
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
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
from capture import ensure_browser_available, install_playwright_browsers, start_capture_worker
from exports import export_html_auto
from export_server import start_export_server as srv_start_export_server, stop_export_server as srv_stop_export_server
from ui_settings import open_settings_window
from app_core import (  # shared globals/imports
    _log_debug,
    _seed_brand_db_if_needed,
    _cleanup_and_record_export,
    _load_capture_config,
    _save_capture_config,
    _load_tracker_dark_mode,
    _save_tracker_dark_mode,
    BASE_DIR,
    ASSETS_DIR,
    EXPORTS_DIR_DEFAULT,
    CONFIG_FILE,
    BRAND_HINTS_FILE,
    LAST_PARSE_FILE,
    CHANGES_LOG_FILE,
    LAST_CHANGE_FILE,
    LAST_SCRAPE_FILE,
    DEFAULT_CAPTURE_CONFIG,
    load_last_parse,
    save_last_parse,
    append_change_log,
    load_last_change,
    save_last_change,
    load_last_scrape,
    save_last_scrape,
    APP_DIR,
    DATA_DIR,
    _port_ready,
    SCRAPER_STATE_FILE,
)
from config import decrypt_secret, encrypt_secret, load_capture_config, save_capture_config
from scraper_state import write_scraper_state
from parser import (
    _load_brand_hints,
    _save_brand_hints,
    format_brand,
    infer_brand,
    parse_clinic_text,
    make_item_key,
    make_identity_key,
    get_google_medicann_link,
)
from models import Item
import threading as _threading
from notifications import _maybe_send_windows_notification
from tray import create_tray_icon, stop_tray_icon, tray_supported, update_tray_icon, compute_tray_state
from logger import UILogger
from notifications import NotificationService
from theme import apply_style_theme, set_titlebar_dark, compute_colors

# Scraper UI constants
SCRAPER_TITLE = "Medicann Scraper"
SCRAPER_PLACEHOLDER = (
    "Go to script assist / Medicann and go to available products."
    "\n"
    "Select all the text on the page and copy / paste it here (or use Auto Capture below)."
    "\n"
    "Press Process (or start Auto Capture). Notifications will only send when there are new/removed items or price changes."
)

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
    def __init__(self):
        super().__init__()
        App._instance = self
        self.title(SCRAPER_TITLE)
        cfg = _load_capture_config()
        self.scraper_window_geometry = cfg.get("window_geometry", "900x720") or "900x720"
        self.scraper_settings_geometry = cfg.get("settings_geometry", "560x960") or "560x960"
        self.manual_parse_geometry = cfg.get("manual_parse_geometry", "720x520") or "720x520"
        self.geometry(self.scraper_window_geometry)
        self.assets_dir = ASSETS_DIR
        _log_debug("App init: launching scraper UI")
        self._config_dark = self._load_dark_mode()
        self.removed_data = []
        _seed_brand_db_if_needed()
        self.httpd = None
        self.http_thread = None
        self.server_port = 8765
        self._server_failed = False
        _log_debug(f"Init export server state. preferred_port={self.server_port} frozen={getattr(sys, '_MEIPASS', None) is not None}")
        self._placeholder = (
            "Go to script assist / Medicann and go to available products."
            "\n"
            "Select all the text on the page and copy / paste it here (or use Auto Capture below)."
            "\n"
            "Press Process (or start Auto Capture). Notifications will only send when there are new/removed items or price changes."
        )
        try:
            init_exports(ASSETS_DIR, EXPORTS_DIR_DEFAULT)
            set_exports_dir(EXPORTS_DIR_DEFAULT)
        except Exception:
            pass
        try:
            # Prefer bundled assets/icon.ico if present; fallback to old asset
            icon_path = ASSETS_DIR / "icon.ico"
            if icon_path.exists():
                self.iconbitmap(str(icon_path))
            else:
                self.iconbitmap(self._resource_path('assets/icon2.ico'))
        except Exception:
            pass
        # Start lightweight export server for consistent origin (favorites persistence)
        self._ensure_export_server()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.start_export_server()
        self.style = ttk.Style(self)
        self.dark_mode_var = tk.BooleanVar(value=self._config_dark)
        self.settings_window = None
        self.manual_parse_window = None
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
        # Hidden text buffer retained for processing; not displayed
        self.text = tk.Text(self, height=1)
        self.text.pack_forget()
        self._show_placeholder()
        btns = ttk.Frame(self)
        btns.pack(pady=5)
        ttk.Button(btns, text="Start Auto-Scraper", command=self.start_auto_capture).pack(side="left", padx=(5, 5))
        ttk.Button(btns, text="Stop Auto-Scraper", command=self.stop_auto_capture).pack(side="left", padx=5)
        ttk.Button(btns, text="Open browser", command=self.open_latest_export).pack(side="left", padx=5)
        ttk.Button(btns, text="Settings", command=self._open_settings_window).pack(side="left", padx=5)
        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.pack(fill="x", padx=10, pady=5)
        self.status = ttk.Label(self, text="Idle")
        self.status.pack(pady=(2, 2))
        # Capture status bookkeeping
        self.capture_status = "idle"
        self.error_count = 0
        self.error_threshold = 3
        self._empty_retry_pending = False
        # Console log at bottom
        console_frame = ttk.Frame(self)
        console_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        ttk.Label(console_frame, text="Console Log").pack(anchor="w")
        console_inner = ttk.Frame(console_frame)
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
            ts = load_last_scrape(LAST_SCRAPE_FILE)
            if ts:
                self.last_scrape_label.config(text=f"Last successful scrape: {ts}")
        except Exception:
            pass
        self.data = []
        self.price_up_count = 0
        self.price_down_count = 0
        self.q = Queue()
        self._polling = False
        # reset capture error state
        self.error_count = 0
        self.error_threshold = 3
        self._empty_retry_pending = False
        # Auto-capture state
        self.capture_thread: _threading.Thread | None = None
        self.capture_stop = _threading.Event()
        self._playwright_available = None
        self.cap_auto_notify_ha = tk.BooleanVar(value=False)
        self.cap_ha_webhook = tk.StringVar(value="")
        self.cap_ha_token = tk.StringVar(value="")
        self.cap_quiet_hours_enabled = tk.BooleanVar(value=False)
        self.cap_quiet_start = tk.StringVar(value="22:00")
        self.cap_quiet_end = tk.StringVar(value="07:00")
        self.cap_quiet_interval = tk.StringVar(value="3600")
        self.cap_notify_detail = tk.StringVar(value="full")
        self.last_change_summary = "none"
        self._build_capture_controls()
        # Tray behavior
        self.bind("<Unmap>", self._on_unmap)
        self.bind("<Map>", self._on_map)
        self.apply_theme()
        # Ensure dark titlebar sticks (especially in frozen builds)
        try:
            self.after(120, lambda: self._set_window_titlebar_dark(self, self.dark_mode_var.get()))
            self.after(150, lambda: self._set_win_titlebar_dark(self.dark_mode_var.get()))
        except Exception:
            pass
    def _show_placeholder(self) -> None:
        if not self.text.get("1.0", "end").strip():
            self.text.delete("1.0", "end")
            self.text.insert("1.0", self._placeholder)
            self.text.configure(foreground="#888888")
    def _on_text_focus_in(self, event=None) -> None:
        if self.text.get("1.0", "end").strip() == self._placeholder.strip():
            self.text.delete("1.0", "end")
            self.text.configure(foreground=self.style.lookup("TLabel", "foreground") or "#000000")
    def _on_text_focus_out(self, event=None) -> None:
        if not self.text.get("1.0", "end").strip():
            self._show_placeholder()
    def _clear_text(self) -> None:
        try:
            self.text.delete("1.0", "end")
        except Exception:
            pass
        self._show_placeholder()
        self._log_console("Cleared input text.")
    def _build_capture_controls(self):
        cfg = _load_capture_config()
        self.capture_window = None
        self.settings_window = None
        self.manual_parse_window = None
        if not hasattr(self, "scraper_window_geometry"):
            self.scraper_window_geometry = cfg.get("window_geometry", "900x720") or "900x720"
        if not hasattr(self, "scraper_settings_geometry"):
            self.scraper_settings_geometry = cfg.get("settings_geometry", "560x960") or "560x960"
        if not hasattr(self, "manual_parse_geometry"):
            self.manual_parse_geometry = cfg.get("manual_parse_geometry", "720x520") or "720x520"
        self.capture_config_path = Path(CONFIG_FILE)
        # Notification toggles from config
        self.notify_price_changes = tk.BooleanVar(value=cfg.get("notify_price_changes", True))
        self.notify_stock_changes = tk.BooleanVar(value=cfg.get("notify_stock_changes", True))
        self.notify_windows = tk.BooleanVar(value=cfg.get("notify_windows", True))
        self.cap_quiet_hours_enabled.set(bool(cfg.get("quiet_hours_enabled", False)))
        self.cap_quiet_start.set(cfg.get("quiet_hours_start", "22:00"))
        self.cap_quiet_end.set(cfg.get("quiet_hours_end", "07:00"))
        self.cap_quiet_interval.set(str(cfg.get("quiet_hours_interval_seconds", 3600)))
        self.cap_notify_detail.set(cfg.get("notification_detail", "full"))
        self.cap_url = tk.StringVar(value=cfg.get("url", ""))
        self.cap_interval = tk.StringVar(value=str(cfg.get("interval_seconds", 60)))
        self.cap_headless = tk.BooleanVar(value=bool(cfg.get("headless", True)))
        self.cap_login_wait = tk.StringVar(value=str(cfg.get("login_wait_seconds", 3)))
        self.cap_post_wait = tk.StringVar(value=str(cfg.get("post_nav_wait_seconds", 30)))
        self.cap_retry_attempts = tk.IntVar(value=int(cfg.get("retry_attempts", 3)))
        self.cap_retry_wait = tk.StringVar(value=str(cfg.get("retry_wait_seconds", cfg.get("post_nav_wait_seconds", 30))))
        self.cap_retry_backoff = tk.StringVar(value=str(cfg.get("retry_backoff_max", 4)))
        self.cap_scroll_times = tk.StringVar(value=str(cfg.get("scroll_times", 0)))
        self.cap_scroll_pause = tk.StringVar(value=str(cfg.get("scroll_pause_seconds", 0.5)))
        self.cap_dump_capture = tk.BooleanVar(value=bool(cfg.get("dump_capture_text", False)))
        self.cap_user = tk.StringVar(value=decrypt_secret(cfg.get("username", "")))
        self.cap_pass = tk.StringVar(value=decrypt_secret(cfg.get("password", "")))
        self.cap_user_sel = tk.StringVar(value=cfg.get("username_selector", ""))
        self.cap_pass_sel = tk.StringVar(value=cfg.get("password_selector", ""))
        self.cap_btn_sel = tk.StringVar(value=cfg.get("login_button_selector", ""))
        self.cap_org = tk.StringVar(value=cfg.get("organization", ""))
        self.cap_org_sel = tk.StringVar(value=cfg.get("organization_selector", ""))
        self.cap_auto_notify_ha.set(bool(cfg.get("auto_notify_ha", False)))
        self.cap_ha_webhook.set(cfg.get("ha_webhook_url", ""))
        self.cap_ha_token.set(decrypt_secret(cfg.get("ha_token", "")))
        self.minimize_to_tray = tk.BooleanVar(value=False)
        self.close_to_tray = tk.BooleanVar(value=False)
    def _open_settings_window(self):
        try:
            cfg = load_capture_config(
                Path(CONFIG_FILE),
                ["username", "password", "ha_token"],
                logger=None,
            )
            self.cap_url.set(cfg.get("url", ""))
            self.cap_interval.set(str(cfg.get("interval_seconds", 60)))
            self.cap_login_wait.set(str(cfg.get("login_wait_seconds", 3)))
            self.cap_post_wait.set(str(cfg.get("post_nav_wait_seconds", 30)))
            self.cap_retry_attempts.set(int(cfg.get("retry_attempts", 3)))
            self.cap_retry_wait.set(str(cfg.get("retry_wait_seconds", cfg.get("post_nav_wait_seconds", 30))))
            self.cap_retry_backoff.set(str(cfg.get("retry_backoff_max", 4)))
            self.cap_scroll_times.set(str(cfg.get("scroll_times", 0)))
            self.cap_scroll_pause.set(str(cfg.get("scroll_pause_seconds", 0.5)))
            self.cap_dump_capture.set(bool(cfg.get("dump_capture_text", False)))
            self.cap_user.set(cfg.get("username", ""))
            self.cap_pass.set(cfg.get("password", ""))
            self.cap_user_sel.set(cfg.get("username_selector", ""))
            self.cap_pass_sel.set(cfg.get("password_selector", ""))
            self.cap_btn_sel.set(cfg.get("login_button_selector", ""))
            self.cap_org.set(cfg.get("organization", ""))
            self.cap_org_sel.set(str(cfg.get("organization_selector", "")).strip())
            self.cap_headless.set(bool(cfg.get("headless", True)))
            self.cap_auto_notify_ha.set(bool(cfg.get("auto_notify_ha", False)))
            self.cap_ha_webhook.set(cfg.get("ha_webhook_url", ""))
            self.cap_ha_token.set(cfg.get("ha_token", ""))
            self.notify_price_changes.set(bool(cfg.get("notify_price_changes", True)))
            self.notify_stock_changes.set(bool(cfg.get("notify_stock_changes", True)))
            self.notify_windows.set(bool(cfg.get("notify_windows", True)))
            self.cap_quiet_hours_enabled.set(bool(cfg.get("quiet_hours_enabled", False)))
            self.cap_quiet_start.set(cfg.get("quiet_hours_start", "22:00"))
            self.cap_quiet_end.set(cfg.get("quiet_hours_end", "07:00"))
            self.cap_quiet_interval.set(str(cfg.get("quiet_hours_interval_seconds", 3600)))
            self.cap_notify_detail.set(cfg.get("notification_detail", "full"))
        except Exception:
            pass
        open_settings_window(self, self.assets_dir)
    def _require_playwright(self):
        if self._playwright_available is False:
            messagebox.showerror("Playwright missing", "Install playwright with:\n pip install playwright\n playwright install chromium")
            return None
        if self._playwright_available is True:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError  # type: ignore
            return sync_playwright, PlaywrightTimeoutError
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError  # type: ignore
            self._playwright_available = True
            return sync_playwright, PlaywrightTimeoutError
        except Exception:
            self._playwright_available = False
            messagebox.showerror("Playwright missing", "Install playwright with:\n pip install playwright\n playwright install chromium")
            return None
    def _install_playwright_browsers(self):
        """Attempt to download Playwright browsers (Chromium)."""
        try:
            self._capture_log("Downloading Playwright browser (this may take a minute)...")
            # Call playwright CLI in-process to avoid spawning a new GUI instance in a frozen exe
            try:
                import playwright.__main__ as pw_main  # type: ignore
            except Exception as exc:
                self._capture_log(f"Playwright module missing: {exc}")
                return False
            env_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", str(Path(APP_DIR) / "pw-browsers"))
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = env_path
            prev_argv = list(sys.argv)
            sys.argv = ["playwright", "install", "chromium"]
            try:
                pw_main.main()
            finally:
                sys.argv = prev_argv
            self._capture_log(f"Playwright browser installed to {env_path}.")
            return True
        except Exception as exc:
            self._capture_log(f"Playwright install failed: {exc}")
            return False
    def _write_scraper_state(self, status: str) -> None:
        try:
            write_scraper_state(SCRAPER_STATE_FILE, status, pid=os.getpid())
        except Exception:
            pass
    def start_auto_capture(self):
        if self.capture_thread and self.capture_thread.is_alive():
            self._log_console("Auto-capture already running.")
            return
        # Ensure playwright is available
        install_cb = lambda: install_playwright_browsers(Path(APP_DIR), self._capture_log)
        req = ensure_browser_available(Path(APP_DIR), self._capture_log, install_cb=install_cb)
        if not req:
            self._capture_log("Playwright is not installed or browsers missing.")
            messagebox.showerror("Playwright", "Playwright is missing and could not be installed.")
            return
        sync_playwright, PlaywrightTimeoutError = req
        url = self.cap_url.get().strip()
        if not url:
            self._log_console("URL is required.")
            return
        try:
            interval = float(self.cap_interval.get())
            if interval <= 0:
                raise ValueError
        except Exception:
            self._log_console("Interval must be a positive number.")
            return
        try:
            login_wait = float(self.cap_login_wait.get() or 0)
            if login_wait < 0:
                raise ValueError
        except Exception:
            self._log_console("Wait after login must be >= 0.")
            return
        try:
            post_wait = float(self.cap_post_wait.get() or 0)
            if post_wait < 0:
                raise ValueError
        except Exception:
            self._log_console("Wait after navigation must be >= 0.")
            return
        if post_wait < 5:
            post_wait = 5.0
            self.cap_post_wait.set(str(post_wait))
        try:
            retry_wait = float(self.cap_retry_wait.get() or 0)
            if retry_wait < 0:
                raise ValueError
        except Exception:
            self._log_console("Retry wait must be >= 0.")
            return
        try:
            retry_backoff = float(self.cap_retry_backoff.get() or 0)
            if retry_backoff < 1:
                retry_backoff = 1.0
                self.cap_retry_backoff.set(str(retry_backoff))
        except Exception:
            self._log_console("Retry backoff max must be >= 1.")
            return
        cfg = {
            "url": url,
            "interval_seconds": interval,
            "login_wait_seconds": login_wait,
            "post_nav_wait_seconds": post_wait,
            "retry_attempts": int(self.cap_retry_attempts.get() or 0),
            "retry_wait_seconds": float(self.cap_retry_wait.get() or 0),
            "retry_backoff_max": float(self.cap_retry_backoff.get() or 0),
            "scroll_times": int(float(self.cap_scroll_times.get() or 0)),
            "scroll_pause_seconds": float(self.cap_scroll_pause.get() or 0),
            "dump_capture_text": bool(self.cap_dump_capture.get()),
            "username": self.cap_user.get(),
            "password": self.cap_pass.get(),
            "username_selector": self.cap_user_sel.get(),
            "password_selector": self.cap_pass_sel.get(),
            "login_button_selector": self.cap_btn_sel.get(),
            "organization": self.cap_org.get(),
            "organization_selector": self.cap_org_sel.get(),
            "headless": self.cap_headless.get(),
            "auto_notify_ha": self.cap_auto_notify_ha.get(),
            "ha_webhook_url": self.cap_ha_webhook.get(),
            "ha_token": self.cap_ha_token.get(),
            "minimize_to_tray": False,
            "close_to_tray": False,
            "notify_price_changes": self.notify_price_changes.get(),
            "notify_stock_changes": self.notify_stock_changes.get(),
            "notify_windows": self.notify_windows.get(),
            "quiet_hours_enabled": self.cap_quiet_hours_enabled.get(),
            "quiet_hours_start": self.cap_quiet_start.get(),
            "quiet_hours_end": self.cap_quiet_end.get(),
            "quiet_hours_interval_seconds": float(self.cap_quiet_interval.get() or 0),
            "notification_detail": self.cap_notify_detail.get(),
        }
        _save_capture_config(cfg)
        self.capture_stop.clear()
        callbacks = {
            "stop_event": self.capture_stop,
            "capture_log": self._capture_log,
            "apply_text": self._apply_captured_text,
            "responsive_wait": self._responsive_wait,
            "on_status": self._on_capture_status,
            "on_stop": lambda: self._log_console("Auto-capture stopped."),
        }
        install_cb = lambda: install_playwright_browsers(Path(APP_DIR), self._capture_log)
        self.capture_thread = start_capture_worker(cfg, callbacks, Path(APP_DIR), install_cb)
        self._log_console("Auto-capture running...")
        try:
            self._write_scraper_state("running")
        except Exception:
            pass
        self._update_tray_status()
    def stop_auto_capture(self):
        self.capture_stop.set()
        if self.capture_thread and not self.capture_thread.is_alive():
            self._log_console("Auto-capture stopped.")
        try:
            self._write_scraper_state("stopped")
        except Exception:
            pass
        self._update_tray_status()
        # Reset counters so next start is clean
        self.error_count = 0
        self._empty_retry_pending = False
        self.capture_status = "idle"
    def open_latest_export(self):
        """Open the most recent HTML export in the browser (served from the local server if available)."""
        exports_dir = Path(EXPORTS_DIR_DEFAULT)
        exports_dir.mkdir(parents=True, exist_ok=True)
        html_files = sorted(exports_dir.glob("export-*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not html_files:
            try:
                self._log_console("No HTML exports found; generating a snapshot.")
                data = load_last_parse(LAST_PARSE_FILE) or []
                if not data:
                    self._log_console("No parsed data available to export.")
                    messagebox.showinfo("Exports", "No data available to export yet.")
                    return
                latest = export_html_auto(data, exports_dir=exports_dir, open_file=False, fetch_images=False)
                self._log_console(f"Exported snapshot: {latest.name}")
                html_files = [latest]
            except Exception as exc:
                messagebox.showinfo("Exports", f"Unable to generate export: {exc}")
                return
        latest = html_files[0]
        self._ensure_export_server()
        if hasattr(self, "server_port") and self.server_port:
            url = f"http://127.0.0.1:{self.server_port}/{latest.name}"
        else:
            url = latest.as_uri()
        try:
            webbrowser.open(url)
            self._capture_log(f"Opening {url}")
        except Exception:
            try:
                os.startfile(latest)
            except Exception as exc:
                messagebox.showerror("Open Export", f"Could not open export:\n{exc}")
    def _open_manual_parse_window(self):
        if self.manual_parse_window and tk.Toplevel.winfo_exists(self.manual_parse_window):
            try:
                self.manual_parse_window.deiconify()
                self.manual_parse_window.lift()
                self.manual_parse_window.focus_force()
            except Exception:
                pass
            return
        win = tk.Toplevel(self)
        win.title("Manual Parse")
        win.geometry(self.manual_parse_geometry or "720x520")
        win.minsize(600, 420)
        self.manual_parse_window = win
        try:
            dark = bool(self.dark_mode_var.get())
            colors = compute_colors(dark)
            apply_style_theme(self.style, colors)
            win.configure(bg=colors["bg"])
            win.after(50, lambda: set_titlebar_dark(win, dark))
        except Exception:
            pass
        def on_close():
            try:
                self.manual_parse_geometry = win.geometry()
            except Exception:
                pass
            try:
                self._save_capture_window()
            except Exception:
                pass
            try:
                win.destroy()
            except Exception:
                pass
            self.manual_parse_window = None
        win.protocol("WM_DELETE_WINDOW", on_close)
        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Paste page text below, then parse.").pack(anchor="w")
        text_frame = ttk.Frame(frame)
        text_frame.pack(fill="both", expand=True, pady=(6, 8))
        text_box = tk.Text(text_frame, wrap="word", height=18)
        scroll = ttk.Scrollbar(text_frame, orient="vertical", command=text_box.yview, style="Dark.Vertical.TScrollbar")
        text_box.configure(yscrollcommand=scroll.set)
        text_box.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        try:
            colors = compute_colors(bool(self.dark_mode_var.get()))
            text_box.configure(bg=colors["bg"], fg=colors["fg"], insertbackground=colors["fg"])
        except Exception:
            pass
        btns = ttk.Frame(frame)
        btns.pack(fill="x")
        def do_parse_export_open():
            raw = text_box.get("1.0", "end").strip()
            if not raw:
                messagebox.showwarning("Manual Parser", "Copy and paste your request repeat page here.")
                return
            try:
                self.text.delete("1.0", "end")
                self.text.insert("1.0", raw)
            except Exception:
                pass
            try:
                items = parse_clinic_text(raw)
            except Exception as exc:
                messagebox.showerror("Manual Parser", f"Could not parse text:\n{exc}")
                return
            if not items:
                messagebox.showwarning("Manual Parser", "No products parsed from the pasted text.")
                return
            self.data = list(items)
            self.removed_data = []
            try:
                save_last_parse(LAST_PARSE_FILE, self.data)
                self._update_last_scrape()
                self._log_console(f"Manual parse: {len(self.data)} items.")
            except Exception as exc:
                self._capture_log(f"Manual parse save error: {exc}")
            try:
                self._generate_change_export(self._get_export_items())
            except Exception as exc:
                messagebox.showinfo("Exports", f"Unable to generate export: {exc}")
                return
            self.open_latest_export()
        ttk.Button(btns, text="Parse and open browser", command=do_parse_export_open).pack(side="left")
        ttk.Button(btns, text="Close", command=on_close).pack(side="right")
    def _capture_log(self, msg: str):
        _log_debug(f"[capture] {msg}")
        if hasattr(self, "logger") and self.logger:
            self.logger.info(msg)
        else:
            self._log_console(msg)
        # Update status label for capture-related messages
        try:
            self.status.config(text=msg)
        except Exception:
            pass
    def _generate_change_export(self, items: list[dict] | None = None):
        """Generate an HTML snapshot for the latest items and keep only recent ones."""
        data = items if items is not None else self._get_export_items()
        if not data:
            return
        path = export_html_auto(data, exports_dir=EXPORTS_DIR_DEFAULT, open_file=False, fetch_images=False)
        _cleanup_and_record_export(path, max_files=20)
        self._capture_log(f"Exported snapshot: {path.name}")
    def _latest_export_url(self) -> str | None:
        """Return URL (or file://) for latest export, preferring local server."""
        exports_dir = Path(EXPORTS_DIR_DEFAULT)
        if not exports_dir.exists():
            return None
        html_files = sorted(exports_dir.glob("export-*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not html_files:
            return None
        latest = html_files[0]
        if getattr(self, "server_port", None):
            return f"http://127.0.0.1:{self.server_port}/{latest.name}"
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
        except Exception:
            pass
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
        except Exception:
            pass
    def _on_map(self, event):
        try:
            if event.widget is self:
                pass
        except Exception:
            pass
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
        except Exception:
            pass
    def _hide_settings_window(self):
        try:
            self._save_capture_window()
        except Exception:
            pass
        try:
            if self.settings_window and tk.Toplevel.winfo_exists(self.settings_window):
                self.settings_window.withdraw()
        except Exception:
            pass
    def _restore_settings_window(self):
        try:
            if self.settings_window and tk.Toplevel.winfo_exists(self.settings_window):
                self.settings_window.deiconify()
                self.settings_window.lift()
        except Exception:
            pass
    def _log_console(self, msg: str):
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
        except Exception:
            pass
        try:
            self.status.config(text=msg)
        except Exception:
            pass
    def _update_last_change(self, summary: str):
        ts_line = f"{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S%z')} | {summary}"
        save_last_change(LAST_CHANGE_FILE, ts_line)
        try:
            self.last_change_label.config(text=f"Last change detected: {ts_line}")
        except Exception:
            pass
    def _update_last_scrape(self):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_last_scrape(LAST_SCRAPE_FILE, ts)
        try:
            self.last_scrape_label.config(text=f"Last successful scrape: {ts}")
        except Exception:
            pass
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
                self.text.delete("1.0", "end")
                self.text.insert("1.0", text)
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
        except Exception:
            pass
        while time.time() < end:
            if self.capture_stop.is_set():
                return True
            remaining = end - time.time()
            if label and (time.time() - last_update) >= 0.5:
                msg = f"{label}: {remaining:.1f}s remaining"
                try:
                    self.after(0, lambda m=msg: self.status.config(text=m))
                except Exception:
                    pass
                last_update = time.time()
            try:
                elapsed = time.time() - start
                pct = min(100, max(0, (elapsed / target * 100) if target else 100))
                self.after(0, lambda v=pct: self.progress.config(value=v))
            except Exception:
                pass
            time.sleep(min(0.2, remaining))
        # status reset handled by worker status callbacks
        try:
            self.after(0, lambda: self.progress.config(value=0))
        except Exception:
            pass
        return self.capture_stop.is_set()
    def _on_capture_status(self, status: str, msg: str | None = None):
        """Handle worker status updates; reflect in UI/tray."""
        self.capture_status = status
        try:
            if msg:
                self.status.config(text=msg)
            else:
                self.status.config(text=f"Status: {status}")
        except Exception:
            pass
        self._update_tray_status()
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
        self.cap_scroll_times.set(str(cfg.get("scroll_times", 0)))
        self.cap_scroll_pause.set(str(cfg.get("scroll_pause_seconds", 0.5)))
        self.cap_dump_capture.set(bool(cfg.get("dump_capture_text", False)))
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
        self.notify_windows.set(cfg.get("notify_windows", True))
        self.cap_quiet_hours_enabled.set(bool(cfg.get("quiet_hours_enabled", False)))
        self.cap_quiet_start.set(cfg.get("quiet_hours_start", "22:00"))
        self.cap_quiet_end.set(cfg.get("quiet_hours_end", "07:00"))
        self.cap_quiet_interval.set(str(cfg.get("quiet_hours_interval_seconds", 3600)))
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
        cfg = {
            "url": self.cap_url.get(),
            "interval_seconds": float(self.cap_interval.get() or 0),
            "login_wait_seconds": float(self.cap_login_wait.get() or 0),
            "post_nav_wait_seconds": float(self.cap_post_wait.get() or 0),
            "retry_attempts": int(self.cap_retry_attempts.get() or 0),
            "retry_wait_seconds": float(self.cap_retry_wait.get() or 0),
            "retry_backoff_max": float(self.cap_retry_backoff.get() or 0),
            "scroll_times": int(float(self.cap_scroll_times.get() or 0)),
            "scroll_pause_seconds": float(self.cap_scroll_pause.get() or 0),
            "dump_capture_text": bool(self.cap_dump_capture.get()),
            "username": self.cap_user.get(),
            "password": self.cap_pass.get(),
            "username_selector": self.cap_user_sel.get(),
            "password_selector": self.cap_pass_sel.get(),
            "login_button_selector": self.cap_btn_sel.get(),
            "organization": self.cap_org.get(),
            "organization_selector": self.cap_org_sel.get(),
            "headless": self.cap_headless.get(),
            "auto_notify_ha": self.cap_auto_notify_ha.get(),
            "ha_webhook_url": self.cap_ha_webhook.get(),
            "ha_token": self.cap_ha_token.get(),
            "notify_price_changes": self.notify_price_changes.get(),
            "notify_stock_changes": self.notify_stock_changes.get(),
            "notify_windows": self.notify_windows.get(),
            "quiet_hours_enabled": self.cap_quiet_hours_enabled.get(),
            "quiet_hours_start": self.cap_quiet_start.get(),
            "quiet_hours_end": self.cap_quiet_end.get(),
            "quiet_hours_interval_seconds": float(self.cap_quiet_interval.get() or 0),
            "notification_detail": self.cap_notify_detail.get(),
            "minimize_to_tray": bool(self.minimize_to_tray.get()),
            "close_to_tray": bool(self.close_to_tray.get()),
            "window_geometry": self.geometry(),
            "settings_geometry": (self.settings_window.geometry() if self.settings_window and tk.Toplevel.winfo_exists(self.settings_window) else self.scraper_settings_geometry),
            "manual_parse_geometry": (self.manual_parse_window.geometry() if self.manual_parse_window and tk.Toplevel.winfo_exists(self.manual_parse_window) else self.manual_parse_geometry),
        }
        try:
            save_capture_config(self.capture_config_path, cfg, ["username", "password", "ha_token"])
        except Exception as exc:
            messagebox.showerror("Capture Config", f"Could not save config:\n{exc}")
            return
        messagebox.showinfo("Capture Config", f"Saved capture config to {path}")
    def _save_capture_window(self):
        target = Path(self.capture_config_path) if getattr(self, "capture_config_path", None) else Path(CONFIG_FILE)
        cfg = {
            "url": self.cap_url.get(),
            "interval_seconds": float(self.cap_interval.get() or 0),
            "login_wait_seconds": float(self.cap_login_wait.get() or 0),
            "post_nav_wait_seconds": float(self.cap_post_wait.get() or 0),
            "retry_attempts": int(self.cap_retry_attempts.get() or 0),
            "retry_wait_seconds": float(self.cap_retry_wait.get() or 0),
            "retry_backoff_max": float(self.cap_retry_backoff.get() or 0),
            "scroll_times": int(float(self.cap_scroll_times.get() or 0)),
            "scroll_pause_seconds": float(self.cap_scroll_pause.get() or 0),
            "dump_capture_text": bool(self.cap_dump_capture.get()),
            "username": self.cap_user.get(),
            "password": self.cap_pass.get(),
            "username_selector": self.cap_user_sel.get(),
            "password_selector": self.cap_pass_sel.get(),
            "login_button_selector": self.cap_btn_sel.get(),
            "organization": self.cap_org.get(),
            "organization_selector": self.cap_org_sel.get(),
            "headless": self.cap_headless.get(),
            "auto_notify_ha": self.cap_auto_notify_ha.get(),
            "ha_webhook_url": self.cap_ha_webhook.get(),
            "ha_token": self.cap_ha_token.get(),
            "notify_price_changes": self.notify_price_changes.get(),
            "notify_stock_changes": self.notify_stock_changes.get(),
            "notify_windows": self.notify_windows.get(),
            "quiet_hours_enabled": self.cap_quiet_hours_enabled.get(),
            "quiet_hours_start": self.cap_quiet_start.get(),
            "quiet_hours_end": self.cap_quiet_end.get(),
            "quiet_hours_interval_seconds": float(self.cap_quiet_interval.get() or 0),
            "notification_detail": self.cap_notify_detail.get(),
            "minimize_to_tray": bool(self.minimize_to_tray.get()),
            "close_to_tray": bool(self.close_to_tray.get()),
            "window_geometry": self.geometry(),
            "settings_geometry": (self.settings_window.geometry() if self.settings_window and tk.Toplevel.winfo_exists(self.settings_window) else self.scraper_settings_geometry),
            "manual_parse_geometry": (self.manual_parse_window.geometry() if self.manual_parse_window and tk.Toplevel.winfo_exists(self.manual_parse_window) else self.manual_parse_geometry),
        }
        try:
            save_capture_config(target, cfg, ["username", "password", "ha_token"])
            self._log_console(f"Saved config to {target}")
        except Exception as exc:
            self._log_console(f"Failed to save config: {exc}")
    def _post_process_actions(self):
        # Called after poll completes processing
        items = getattr(self, "data", [])
        if not items:
            return
        # Ensure we have at least one HTML snapshot after the first successful scrape
        try:
            exports_dir = Path(EXPORTS_DIR_DEFAULT)
            exports_dir.mkdir(parents=True, exist_ok=True)
            has_html = any(exports_dir.glob("export-*.html"))
            if not has_html:
                self._generate_change_export(self._get_export_items())
        except Exception:
            pass
        if self.cap_auto_notify_ha.get():
            self.send_home_assistant(log_only=False)
        else:
            # Still log changes even if HA notifications are disabled
            self.send_home_assistant(log_only=True)
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
    def send_home_assistant(self, log_only: bool = False):
        url = self.cap_ha_webhook.get().strip()
        if not url and not log_only:
            messagebox.showerror("Home Assistant", "Webhook URL is required.")
            return
        items = getattr(self, "data", [])
        prev_items = getattr(self, "prev_items", [])
        prev_keys = getattr(self, "prev_keys", set())
        identity_cache = _build_identity_cache(items + prev_items)
        # Fallback to persisted last parse if in-memory cache is empty
        if (not prev_items or not prev_keys) and LAST_PARSE_FILE.exists():
            try:
                prev_items = load_last_parse(LAST_PARSE_FILE)
                prev_keys = { _identity_key_cached(it, identity_cache) for it in prev_items }
            except Exception:
                pass
        current_keys = { _identity_key_cached(it, identity_cache) for it in items }
        new_items = [it for it in items if _identity_key_cached(it, identity_cache) not in prev_keys]
        removed_keys = prev_keys - current_keys
        removed_items = [it for it in prev_items if _identity_key_cached(it, identity_cache) in removed_keys]
        price_changes = []
        stock_changes = []
        prev_price_map = {}
        prev_stock_map = {}
        for pit in prev_items:
            try:
                prev_price_map[_identity_key_cached(pit, identity_cache)] = float(pit.get("price")) if pit.get("price") is not None else None
            except Exception:
                prev_price_map[_identity_key_cached(pit, identity_cache)] = None
            prev_stock_map[_identity_key_cached(pit, identity_cache)] = pit.get("stock")
        for it in items:
            ident = _identity_key_cached(it, identity_cache)
            try:
                cur_price = float(it.get("price")) if it.get("price") is not None else None
            except Exception:
                cur_price = None
            prev_price = prev_price_map.get(ident)
            if cur_price is not None and isinstance(prev_price, (int, float)) and cur_price != prev_price:
                price_changes.append(
                    {
                        **it,
                        "price_delta": cur_price - prev_price,
                        "price_before": prev_price,
                        "price_after": cur_price,
                    }
                )
            prev_stock = prev_stock_map.get(ident)
            cur_stock = it.get("stock")
            if prev_stock is not None and cur_stock is not None and str(prev_stock) != str(cur_stock):
                stock_changes.append(
                    {
                        **it,
                        "stock_before": prev_stock,
                        "stock_after": cur_stock,
                    }
                )
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
        new_flowers = [_flower_label(it) for it in new_items if (it.get("product_type") or "").lower() == "flower"]
        removed_flowers = [_flower_label(it) for it in removed_items if (it.get("product_type") or "").lower() == "flower"]
        new_item_summaries = [_item_label(it) for it in new_items]
        removed_item_summaries = [_item_label(it) for it in removed_items]
        if not new_items and not removed_items and not price_changes and not stock_changes:
            self._capture_log("No changes detected; skipping HA notification.")
            return
        self._log_console(
            f"Notify HA | new={len(new_items)} removed={len(removed_items)} "
            f"price_changes={len(price_changes)} stock_changes={len(stock_changes)}"
        )
        # Build compact human text for price changes
        price_change_summaries = []
        price_change_compact = []
        for it in price_changes:
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
            price_change_summaries.append(f"{label} {direction}{delta_str}")
            price_change_compact.append(
                {
                    "label": label,
                    "price_before": before,
                    "price_after": after,
                    "price_delta": delta,
                    "direction": "up" if delta and delta > 0 else "down",
                }
            )
        stock_change_summaries = []
        stock_change_compact = []
        for it in stock_changes:
            brand = it.get("brand") or it.get("producer") or ""
            strain = it.get("strain") or ""
            label = " ".join([p for p in (brand, strain) if p]).strip() or "Unknown"
            before = it.get("stock_before")
            after = it.get("stock_after")
            stock_change_summaries.append(f"{label}: {before} → {after}")
            stock_change_compact.append(
                {
                    "label": label,
                    "stock_before": before,
                    "stock_after": after,
                }
            )
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "count": len(items),
            "new_count": len(new_items),
            "removed_count": len(removed_items),
            "price_changes": price_changes,
            "new_flowers": new_flowers,
            "removed_flowers": removed_flowers,
            "new_item_summaries": new_item_summaries,
            "removed_item_summaries": removed_item_summaries,
            "price_change_summaries": price_change_summaries,
            "stock_changes": stock_changes,
            "stock_change_summaries": stock_change_summaries,
            "new_items": new_items,
            "removed_items": removed_items,
            "price_up": getattr(self, "price_up_count", 0),
            "price_down": getattr(self, "price_down_count", 0),
            "items": items,
        }
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
                    for it in new_items
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
                    for it in removed_items
                ],
                "price_changes": price_change_compact,
                "stock_changes": stock_change_compact,
            }
            append_change_log(CHANGES_LOG_FILE, log_record)
        except Exception:
            pass
        headers = {
            "Content-Type": "application/json",
        }
        token = self.cap_ha_token.get().strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = json.dumps(payload).encode("utf-8")
        summary = (
            f"+{len(new_items)} new, -{len(removed_items)} removed, "
            f"{len(price_changes)} price changes, {len(stock_changes)} stock changes"
        )
        quiet_hours = self._quiet_hours_active()
        if quiet_hours:
            self._capture_log("Quiet hours active; skipping notifications.")
            self._update_last_change(summary)
        # Build detailed desktop notification text and launch target
        windows_body = self.notify_service.format_windows_body(payload, summary, detail=self.cap_notify_detail.get())
        launch_url = self.cap_url.get().strip() or self._latest_export_url()
        icon_path = ASSETS_DIR / "icon.ico"
        # Windows toast (always allowed when enabled)
        if (not quiet_hours) and self.notify_windows.get():
            self._capture_log(f"Sending Windows notification: {windows_body}")
            ok_win = self.notify_service.send_windows("Medicann update", windows_body, icon_path, launch_url=launch_url)
            if not ok_win:
                self._capture_log("Windows notification failed to send.")
        # If log-only or quiet hours, skip HA network send
        if not (log_only or quiet_hours):
            ok, status, body = self.notify_service.send_home_assistant(payload)
            if ok and status:
                self._update_last_change(summary)
            else:
                self._capture_log(f"HA response status: {status} body: {str(body)[:200] if body else ''}")
        try:
            if items:
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
        quiet_hours = self._quiet_hours_active()
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
            launch_url = self.cap_url.get().strip() or self._latest_export_url()
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
            _log_debug("[server] ensure_export_server: already running")
            return True
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
        except Exception:
            pass
        try:
            self.capture_stop.set()
        except Exception:
            pass
        try:
            self.stop_export_server()
        except Exception:
            pass
        try:
            if self.settings_window and tk.Toplevel.winfo_exists(self.settings_window):
                self.settings_window.destroy()
        except Exception:
            pass
        try:
            self._hide_tray_icon()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
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
    def _on_text_right_click(self, event=None) -> None:
        try:
            clip = self.clipboard_get()
        except Exception:
            clip = ""
        if clip:
            if self.text.get("1.0", "end").strip() == self._placeholder.strip():
                self.text.delete("1.0", "end")
            self.text.insert("insert", clip)
    def _on_click_anywhere(self, event) -> None:
        # If click is outside the text widget, clear selection and focus
        widget = event.widget
        if not self._is_descendant(self.text, widget):
            try:
                self.text.tag_remove("sel", "1.0", "end")
            except Exception:
                pass
            try:
                widget.focus_set()
            except Exception:
                pass
    @staticmethod
    def _is_descendant(parent, widget) -> bool:
        while widget:
            if widget == parent:
                return True
            widget = getattr(widget, "master", None)
        return False
    def process(self):
        raw = self.text.get("1.0", "end")
        items = parse_clinic_text(raw)
        prev_items = load_last_parse(LAST_PARSE_FILE)
        identity_cache = _build_identity_cache(prev_items)
        prev_keys = { _identity_key_cached(it, identity_cache) for it in prev_items }
        prev_price_map = {}
        for pit in prev_items:
            try:
                prev_price_map[_identity_key_cached(pit, identity_cache)] = float(pit.get("price")) if pit.get("price") is not None else None
            except Exception:
                prev_price_map[_identity_key_cached(pit, identity_cache)] = None
        self.prev_items = prev_items
        self.prev_keys = prev_keys
        self.removed_data = []
        seen = set()
        deduped = []
        price_up = 0
        price_down = 0
        for it in items:
            ident_key = make_identity_key(it)
            if ident_key in seen:
                continue
            seen.add(ident_key)
            it = dict(it)
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
            deduped.append(it)
        self.data = []
        try:
            self.progress.config(mode='determinate', maximum=len(deduped))
            self.progress['value'] = 0
        except Exception:
            pass
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
                    except Exception:
                        pass
                elif msg[0] == "error":
                    _, err = msg
                    self.progress.stop()
                    self.status.config(text=f"Error: {err}")
                    messagebox.showerror("Processing Error", err)
                elif msg[0] == "done":
                    try:
                        self.progress['value'] = self.progress['maximum']
                    except Exception:
                        pass
                    # Recompute price change counts from current data to ensure status reflects deltas
                    up = down = 0
                    for it in self.data:
                        delta = it.get("price_delta")
                        if isinstance(delta, (int, float)) and delta:
                            if delta > 0:
                                up += 1
                            elif delta < 0:
                                down += 1
                    self.price_up_count = up
                    self.price_down_count = down
                    current_keys = {make_item_key(it) for it in self.data}
                    prev_items = getattr(self, "prev_items", [])
                    prev_keys = getattr(self, "prev_keys", set())
                    identity_cache = _build_identity_cache(self.data + prev_items)
                    new_count = len({ _identity_key_cached(it, identity_cache) for it in self.data} - prev_keys)
                    removed_keys = prev_keys - { _identity_key_cached(it, identity_cache) for it in self.data}
                    removed_items = [dict(it, is_removed=True, is_new=False) for it in prev_items if _identity_key_cached(it, identity_cache) in removed_keys]
                    removed_count = len(removed_items)
                    self.removed_data = removed_items
                    if not self.data:
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
                    save_last_parse(LAST_PARSE_FILE, self.data)
                    self._update_last_scrape()
                    self.status.config(
                        text=(
                            f"Done | {len(self.data)} items | "
                            f"+{new_count} new | -{removed_count} removed | "
                            f"{self.price_up_count} price increases | {self.price_down_count} price decreases"
                        )
                    )
                    self._log_console(
                        f"Done | {len(self.data)} items | +{new_count} new | -{removed_count} removed | "
                        f"{self.price_up_count} price increases | {self.price_down_count} price decreases"
                    )
                    self._post_process_actions()
                    try:
                        self._set_next_capture_timer(float(self.cap_interval.get() or 0))
                    except Exception:
                        pass
                    # Update prev cache for next run after notifications are sent
                    self.prev_items = list(self.data)
                    self.prev_keys = { _identity_key_cached(it, identity_cache) for it in self.data}
                    self._polling = False
                    return
        except Empty:
            pass
        if self._polling:
            self.after(50, self.poll)
        # Update last change label periodically
        try:
            ts = load_last_change(LAST_CHANGE_FILE)
            if ts:
                self.last_change_label.config(text=f"Last change detected: {ts}")
        except Exception:
            pass
        try:
            ts = load_last_scrape(LAST_SCRAPE_FILE)
            if ts:
                self.last_scrape_label.config(text=f"Last successful scrape: {ts}")
        except Exception:
            pass
    def _get_export_items(self):
        combined = list(self.data)
        if getattr(self, "removed_data", None):
            combined.extend(self.removed_data)
        return combined
    # Export functions removed (no longer used)
    def clear_cache(self):
        self.data.clear()
        self.prev_items = []
        self.prev_keys = set()
        self.removed_data = []
        try:
            if LAST_PARSE_FILE.exists():
                LAST_PARSE_FILE.unlink()
        except Exception:
            pass
        try:
            self.progress['value'] = 0
        except Exception:
            pass
        self.status.config(text="Cache cleared")
        messagebox.showinfo("Cleared", "Cache cleared (including previous parse).")
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
                except Exception:
                    pass
                self.status.config(text="Idle")
        except Exception:
            pass
    def open_parser_settings(self):
        hints = [dict(brand=h.get("brand"), patterns=list(h.get("patterns") or h.get("phrases") or []), display=h.get("display")) for h in _load_brand_hints()]
        win = tk.Toplevel(self)
        win.title("Parser Settings - Brands")
        win.geometry("620x520")
        try:
            win.iconbitmap(self._resource_path('assets/icon2.ico'))
        except Exception:
            pass
        dark = self.dark_mode_var.get()
        bg = "#111" if dark else "#f4f4f4"
        fg = "#eee" if dark else "#111"
        accent = "#4a90e2" if dark else "#666666"
        list_bg = "#1e1e1e" if dark else "#ffffff"
        list_fg = fg
        entry_bg = list_bg
        win.configure(bg=bg)
        brand_var = tk.StringVar()
        pattern_var = tk.StringVar()
        entry_style = "ParserEntry.TEntry"
        try:
            self.style.configure(entry_style, fieldbackground=entry_bg, background=entry_bg, foreground=fg, insertcolor=fg)
        except Exception:
            pass
        left = ttk.Frame(win, padding=8)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(win, padding=8)
        right.pack(side="right", fill="both", expand=True)
        ttk.Label(left, text="Brands").pack(anchor="w")
        brand_list = tk.Listbox(left, height=14, bg=list_bg, fg=list_fg, selectbackground=accent, selectforeground=bg, highlightbackground=bg, relief="flat")
        brand_list.pack(fill="both", expand=True, pady=4)
        ttk.Label(right, text="Patterns").pack(anchor="w")
        pattern_list = tk.Listbox(right, height=14, bg=list_bg, fg=list_fg, selectbackground=accent, selectforeground=bg, highlightbackground=bg, relief="flat")
        pattern_list.pack(fill="both", expand=True, pady=4)
        brand_entry = ttk.Entry(left, textvariable=brand_var, style=entry_style)
        brand_entry.pack(fill="x", pady=2)
        pattern_entry = ttk.Entry(right, textvariable=pattern_var, style=entry_style)
        pattern_entry.pack(fill="x", pady=2)
        def sort_hints():
            hints.sort(key=lambda h: (h.get("brand") or "").lower())
        def refresh_brands(sel_index=0):
            sort_hints()
            brand_list.delete(0, tk.END)
            for h in hints:
                brand_list.insert(tk.END, h.get("brand") or "")
            if hints:
                idx = min(sel_index, len(hints) - 1)
                brand_list.select_set(idx)
                brand_list.event_generate("<<ListboxSelect>>")
        def refresh_patterns():
            pattern_list.delete(0, tk.END)
            sel = brand_list.curselection()
            if not sel:
                return
            pats = hints[sel[0]].get("patterns") or []
            for p in pats:
                pattern_list.insert(tk.END, p)
        def on_brand_select(event=None):
            sel = brand_list.curselection()
            if not sel:
                return
            brand_var.set(hints[sel[0]].get("brand") or "")
            refresh_patterns()
        brand_list.bind("<<ListboxSelect>>", on_brand_select)
        def add_brand():
            name = brand_var.get().strip()
            if not name:
                messagebox.showinfo("Brand", "Enter a brand name.")
                return
            hints.append({"brand": name, "patterns": []})
            refresh_brands(len(hints) - 1)
        def update_brand():
            sel = brand_list.curselection()
            if not sel:
                messagebox.showinfo("Brand", "Select a brand to rename.")
                return
            name = brand_var.get().strip()
            if not name:
                messagebox.showinfo("Brand", "Enter a brand name.")
                return
            hints[sel[0]]["brand"] = name
            refresh_brands(sel[0])
        def delete_brand():
            sel = brand_list.curselection()
            if not sel:
                return
            del hints[sel[0]]
            refresh_brands(max(sel[0] - 1, 0))
        def add_pattern():
            sel = brand_list.curselection()
            if not sel:
                messagebox.showinfo("Pattern", "Select a brand first.")
                return
            pat = pattern_var.get().strip()
            if not pat:
                messagebox.showinfo("Pattern", "Enter a pattern.")
                return
            pats = hints[sel[0]].setdefault("patterns", [])
            if pat not in pats:
                pats.append(pat)
                refresh_patterns()
        def replace_pattern():
            bsel = brand_list.curselection()
            psel = pattern_list.curselection()
            if not bsel or not psel:
                messagebox.showinfo("Pattern", "Select a pattern to replace.")
                return
            pat = pattern_var.get().strip()
            if not pat:
                messagebox.showinfo("Pattern", "Enter a pattern.")
                return
            pats = hints[bsel[0]].setdefault("patterns", [])
            pats[psel[0]] = pat
            refresh_patterns()
            pattern_list.select_set(psel[0])
        def delete_pattern():
            bsel = brand_list.curselection()
            psel = pattern_list.curselection()
            if not bsel or not psel:
                return
            pats = hints[bsel[0]].get("patterns") or []
            if 0 <= psel[0] < len(pats):
                del pats[psel[0]]
            refresh_patterns()
        def save_and_close():
            _save_brand_hints(hints)
            messagebox.showinfo("Saved", "Parser brand settings saved.")
            win.destroy()
        ttk.Button(left, text="Add Brand", command=add_brand).pack(fill="x", pady=2)
        ttk.Button(left, text="Rename Brand", command=update_brand).pack(fill="x", pady=2)
        ttk.Button(left, text="Delete Brand", command=delete_brand).pack(fill="x", pady=2)
        ttk.Button(right, text="Add Pattern", command=add_pattern).pack(fill="x", pady=2)
        ttk.Button(right, text="Replace Pattern", command=replace_pattern).pack(fill="x", pady=2)
        ttk.Button(right, text="Delete Pattern", command=delete_pattern).pack(fill="x", pady=2)
        ttk.Button(win, text="Save & Close", command=save_and_close).pack(fill="x", padx=10, pady=8)
        # Apply simple dark/light styling to the popup background
        for widget in (left, right):
            widget.configure(style="TFrame")
        for lbl in win.winfo_children():
            if isinstance(lbl, ttk.Label):
                lbl.configure(background=bg, foreground=fg)
        win.configure(bg=bg)
        self.after(50, lambda: self._set_window_titlebar_dark(win, dark))
        refresh_brands()
    def apply_theme(self):
        dark = self.dark_mode_var.get()
        colors = compute_colors(dark)
        apply_style_theme(self.style, colors)
        self.configure(bg=colors["bg"])
        self.text.configure(bg=colors["bg"], fg=colors["fg"], insertbackground=colors["fg"])
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
        self.option_add("*TCombobox*Listbox*Background", colors["ctrl_bg"])
        self.option_add("*TCombobox*Listbox*Foreground", colors["fg"])
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
        # Apply option database overrides for classic Tk scrollbars (used by ScrolledText)
        try:
            self.option_add("*Scrollbar.background", colors["ctrl_bg"])
            self.option_add("*Scrollbar.troughColor", colors["bg"])
            self.option_add("*Scrollbar.activeBackground", colors["accent"])
            self.option_add("*Scrollbar.arrowColor", colors["fg"])
            self.option_add("*Scrollbar.relief", "flat")
            self.option_add("*Scrollbar.borderWidth", 0)
            self.option_add("*Scrollbar.highlightThickness", 0)
        except Exception:
            pass
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
                    selectforeground=colors["bg"],
                    highlightthickness=0,
                    borderwidth=0,
                )
                try:
                    if hasattr(self, "console_scroll"):
                        self.console_scroll.configure(style="Dark.Vertical.TScrollbar")
                except Exception:
                    pass
            except Exception:
                pass
        try:
            ts = load_last_change(LAST_CHANGE_FILE)
            if ts:
                self.last_change_label.config(text=f"Last change detected: {ts}")
        except Exception:
            pass
        try:
            ts = load_last_scrape(LAST_SCRAPE_FILE)
            if ts:
                self.last_scrape_label.config(text=f"Last successful scrape: {ts}")
        except Exception:
            pass
        self.after(50, lambda: set_titlebar_dark(self, dark))
        if self.capture_window and tk.Toplevel.winfo_exists(self.capture_window):
            self._apply_theme_to_window(self.capture_window)
        # Ensure main titlebar follows theme
        try:
            self._set_window_titlebar_dark(self, dark)
        except Exception:
            pass
    def toggle_theme(self):
        self.apply_theme()
        _save_tracker_dark_mode(self.dark_mode_var.get())
    def _load_dark_mode(self) -> bool:
        return _load_tracker_dark_mode(True)
    def _resource_path(self, relative: str) -> str:
        """Return absolute path to resource, works for dev and PyInstaller."""
        path = Path(BASE_DIR) / relative
        if not path.exists():
            alt = ASSETS_DIR / relative
            if alt.exists():
                path = alt
        return str(path)
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
        except Exception:
            pass
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
        except Exception:
            pass
    def _apply_theme_recursive(self, widget, bg, fg, ctrl_bg, accent, dark):
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
                except Exception:
                    pass
            elif isinstance(widget, ttk.Labelframe):
                try:
                    widget.configure(style="Parser.TLabelframe")
                    self.style.configure("Parser.TLabelframe", background=bg, foreground=fg, bordercolor=accent, relief="groove")
                    self.style.configure("Parser.TLabelframe.Label", background=bg, foreground=fg)
                except Exception:
                    pass
            elif isinstance(widget, ttk.Frame):
                try:
                    widget.configure(style="TFrame")
                except Exception:
                    pass
            elif isinstance(widget, ttk.Label):
                try:
                    widget.configure(style="TLabel")
                except Exception:
                    pass
            elif isinstance(widget, ttk.Button):
                try:
                    widget.configure(style="TButton")
                except Exception:
                    pass
            elif isinstance(widget, ttk.Entry):
                try:
                    widget.configure(style="TEntry")
                except Exception:
                    pass
            elif isinstance(widget, ttk.Checkbutton):
                try:
                    widget.configure(style="TCheckbutton")
                except Exception:
                    pass
            if isinstance(widget, tk.Listbox):
                widget.configure(bg=bg if dark else "#ffffff", fg=fg, selectbackground=accent, selectforeground="#000" if dark else "#fff", highlightbackground=bg)
            elif isinstance(widget, tk.Text):
                widget.configure(bg=bg, fg=fg, insertbackground=fg, highlightbackground=bg)
            else:
                # Attempt generic background/foreground where supported (covers frames/labels/buttons)
                for opt, val in (("background", bg), ("foreground", fg)):
                    try:
                        widget.configure(**{opt: val})
                    except Exception:
                        pass
            for child in widget.winfo_children():
                self._apply_theme_recursive(child, bg, fg, ctrl_bg, accent, dark)
        except Exception:
            pass
    def _apply_theme_to_window(self, window):
        dark = self.dark_mode_var.get()
        colors = compute_colors(dark)
        bg = colors["bg"]
        fg = colors["fg"]
        ctrl_bg = colors["ctrl_bg"]
        accent = colors["accent"]
        try:
            window.configure(bg=bg)
            for widget in window.winfo_children():
                self._apply_theme_recursive(widget, bg, fg, ctrl_bg, accent, dark)
            self._set_window_titlebar_dark(window, dark)
            self._set_win_titlebar_dark(dark)
        except Exception:
            pass
if __name__ == "__main__":
    App().mainloop()
