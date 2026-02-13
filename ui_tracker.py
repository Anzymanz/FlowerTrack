from __future__ import annotations
import json
import csv
import os
import secrets
import sys
import webbrowser
import time
import tkinter as tk
from datetime import date, datetime, timedelta
import threading
import ctypes
import subprocess
import shutil
import tempfile
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk, colorchooser
import importlib.util
import importlib.machinery
import traceback
from app_core import APP_DIR, EXPORTS_DIR_DEFAULT, LAST_PARSE_FILE, _load_capture_config, _save_capture_config, SCRAPER_STATE_FILE  # use shared app data root
from tray import tray_supported, update_tray_icon, stop_tray_icon, make_tray_image, create_tray_icon
from scraper_state import resolve_scraper_status as resolve_scraper_status_core, read_scraper_state
from theme import apply_style_theme, compute_colors, set_titlebar_dark, set_palette_overrides, get_default_palettes
from ui_window_chrome import apply_dark_titlebar
from ui_tracker_settings import open_tracker_settings
from ui_tracker_settings_state import save_tracker_settings as _save_tracker_settings
from ui_tracker_status import (
    bind_log_thc_cbd_tooltip as _status_bind_log_thc_cbd_tooltip,
    bind_tooltip as _status_bind_tooltip,
    hide_tooltip as _status_hide_tooltip,
    on_status_enter as _status_on_enter,
    on_status_leave as _status_on_leave,
    show_tooltip as _status_show_tooltip,
    status_tooltip_text as _status_tooltip_text_helper,
)
from ui_tracker_layout import (
    apply_split_ratio as _layout_apply_split_ratio,
    apply_stock_form_visibility as _layout_apply_stock_form_visibility,
    finalize_split_restore as _layout_finalize_split_restore,
    on_split_release as _layout_on_split_release,
    persist_split_ratio as _layout_persist_split_ratio,
    schedule_split_apply as _layout_schedule_split_apply,
    schedule_split_persist as _layout_schedule_split_persist,
    toggle_stock_form as _layout_toggle_stock_form,
)
from ui_tracker_window_persistence import (
    apply_resolution_safety as _persist_apply_resolution_safety,
    current_screen_resolution as _persist_current_screen_resolution,
    on_root_configure as _persist_on_root_configure,
    parse_resolution as _persist_parse_resolution,
    persist_geometry as _persist_persist_geometry,
    persist_settings_geometry as _persist_persist_settings_geometry,
    persist_tree_widths as _persist_persist_tree_widths,
    schedule_settings_geometry as _persist_schedule_settings_geometry,
)
from ui_tracker_visibility import (
    apply_mix_button_visibility as _visibility_apply_mix_button_visibility,
    apply_roa_visibility as _visibility_apply_roa_visibility,
    apply_scraper_status_visibility as _visibility_apply_scraper_status_visibility,
    bind_scraper_status_actions as _visibility_bind_scraper_status_actions,
)
from ui_tracker_stock import (
    add_stock as _stock_add_stock,
    apply_stock_sort as _stock_apply_stock_sort,
    clear_stock_inputs as _stock_clear_stock_inputs,
    delete_stock as _stock_delete_stock,
    mark_stock_form_dirty as _stock_mark_stock_form_dirty,
    maybe_clear_log_selection as _stock_maybe_clear_log_selection,
    maybe_clear_stock_selection as _stock_maybe_clear_stock_selection,
    on_stock_select as _stock_on_stock_select,
    refresh_stock as _stock_refresh_stock,
    sort_stock as _stock_sort_stock,
)
from ui_tracker_log import (
    change_day as _log_change_day,
    delete_log_entry as _log_delete_log_entry,
    edit_log_entry as _log_edit_log_entry,
    log_dose as _log_log_dose,
    refresh_log as _log_refresh_log,
    resolve_roa as _log_resolve_roa,
    restore_mix_stock as _log_restore_mix_stock,
)
from resources import resource_path as _resource_path
from inventory import (
    TRACKER_DATA_FILE,
    TRACKER_LIBRARY_FILE,
    TRACKER_CONFIG_FILE,
    load_tracker_data,
    save_tracker_data,
)
from storage import load_last_parse
from inventory import is_cbd_dominant
from exports import export_html_auto, export_size_warning
from export_server import start_export_server as srv_start_export_server, stop_export_server as srv_stop_export_server
from config import load_tracker_config, save_tracker_config
from inventory import Flower
from network_mode import MODE_CLIENT, MODE_HOST, MODE_STANDALONE, get_mode as get_network_mode
from network_sync import (
    DEFAULT_EXPORT_PORT,
    DEFAULT_NETWORK_PORT,
    fetch_tracker_meta,
    fetch_library_data,
    fetch_tracker_data,
    network_ping,
    push_library_data,
    push_tracker_data,
    start_network_data_server,
    stop_network_data_server,
)
try:
    from PIL import Image, ImageDraw, ImageTk
except ImportError:  # Pillow may not be installed; tray icon will be disabled
    Image = None
    ImageDraw = None
    ImageTk = None
try:
    from tkcolorpicker import ColorPicker as TkColorPicker
except Exception:
    TkColorPicker = None
def resolve_scraper_status(child_procs) -> tuple[bool, bool]:
    return resolve_scraper_status_core(child_procs, SCRAPER_STATE_FILE)
def _build_scraper_status_image(child_procs):
    try:
        running, warn = resolve_scraper_status_core(child_procs, SCRAPER_STATE_FILE)
        return make_tray_image(running=running, warn=warn)
    except Exception:
        return None


def _overlay_mute_icon(base_img):
    if Image is None or ImageDraw is None or base_img is None:
        return base_img
    try:
        img = base_img.copy().convert("RGBA")
        draw = ImageDraw.Draw(img)
        w, h = img.size
        r = max(8, min(w, h) // 6)
        cx = w - r - 3
        cy = h - r - 3
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(230, 70, 70, 245), outline=(255, 255, 255, 245), width=2)
        draw.line((cx - r + 3, cy - r + 3, cx + r - 3, cy + r - 3), fill=(255, 255, 255, 255), width=2)
        draw.line((cx - r + 3, cy + r - 3, cx + r - 3, cy - r + 3), fill=(255, 255, 255, 255), width=2)
        return img
    except Exception:
        return base_img
 
class CannabisTracker:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("FlowerTrack - Medical Cannabis Tracker")
        self._set_window_icon()
        self.child_procs: list[subprocess.Popen] = []
        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")
        self.dark_var = tk.BooleanVar(value=False)
        self.total_green_threshold = 30.0
        self.total_red_threshold = 5.0
        self.single_green_threshold = 10.0
        self.single_red_threshold = 2.0
        self.cbd_total_green_threshold = self.total_green_threshold
        self.cbd_total_red_threshold = self.total_red_threshold
        self.cbd_single_green_threshold = self.single_green_threshold
        self.cbd_single_red_threshold = self.single_red_threshold
        self.track_cbd_flower = False
        self.target_daily_cbd_grams = 0.0
        self.target_daily_grams = 1.0
        self.avg_usage_days = 30
        self.settings_window: tk.Toplevel | None = None
        self.combo_style = "App.TCombobox"
        self.vscroll_style = "App.Vertical.TScrollbar"
        self.hscroll_style = "App.Horizontal.TScrollbar"
        self.tree_style = "App.Treeview"
        self.tree_heading_style = "App.Treeview.Heading"
        self.stock_sort_column = "grams"
        self.stock_sort_reverse = True
        self.text_color = "#111111"
        self.muted_color = "#666666"
        self.accent_green = "#2ecc71"
        self.accent_red = "#e74c3c"
        self.total_thc_high_color = "#2ecc71"
        self.total_thc_low_color = "#e74c3c"
        self.total_cbd_high_color = "#2ecc71"
        self.total_cbd_low_color = "#e74c3c"
        self.single_thc_high_color = "#2ecc71"
        self.single_thc_low_color = "#e74c3c"
        self.single_cbd_high_color = "#2ecc71"
        self.single_cbd_low_color = "#e74c3c"
        self.remaining_thc_high_color = "#2ecc71"
        self.remaining_thc_low_color = "#e74c3c"
        self.remaining_cbd_high_color = "#2ecc71"
        self.remaining_cbd_low_color = "#e74c3c"
        self.days_thc_high_color = "#2ecc71"
        self.days_thc_low_color = "#e74c3c"
        self.days_cbd_high_color = "#2ecc71"
        self.days_cbd_low_color = "#e74c3c"
        self.used_thc_under_color = "#2ecc71"
        self.used_thc_over_color = "#e74c3c"
        self.used_cbd_under_color = "#2ecc71"
        self.used_cbd_over_color = "#e74c3c"
        default_dark, default_light = get_default_palettes()
        self.theme_palette_dark = dict(default_dark)
        self.theme_palette_light = dict(default_light)
        self._theme_color_buttons: dict[tuple[str, str], list[tk.Button]] = {}
        self._threshold_color_buttons: dict[str, list[tk.Button]] = {}
        self.stock_form_source: str | None = None
        self.stock_form_dirty = False
        self.current_base_color = "#f5f5f5"
        self.data_path = TRACKER_DATA_FILE
        self.library_data_path = TRACKER_LIBRARY_FILE
        self.minimize_to_tray = False
        self.close_to_tray = False
        self.show_scraper_status_icon = True
        self.scraper_status_running_color = "#2ecc71"
        self.scraper_status_stopped_color = "#e74c3c"
        self.scraper_status_error_color = "#f39c12"
        self.show_scraper_buttons = True
        self.scraper_notify_windows = True
        self.scraper_notifications_muted = False
        self._scraper_notify_restore: dict | None = None
        self.enable_stock_coloring = True
        self.enable_stock_coloring_thc = True
        self.enable_stock_coloring_cbd = True
        self.enable_usage_coloring = True
        self.hide_roa_options = False
        self.hide_mixed_dose = False
        self.hide_mix_stock = False
        self.show_stock_form = True
        self.roa_options = {
            "Vaped": 0.60,
            "Eaten": 0.10,
            "Smoked": 0.30,
        }
        self.font_body = ("", 10)
        self.font_bold_small = ("", 10, "bold")
        self.font_bold_mid = ("", 12, "bold")
        self._tooltip_win: tk.Toplevel | None = None
        self.tray_icon = None
        self.export_server = None
        self.export_thread = None
        self.export_port = DEFAULT_EXPORT_PORT
        self.network_mode = get_network_mode()
        self.network_host = "127.0.0.1"
        self.network_bind_host = "0.0.0.0"
        self.network_port = DEFAULT_NETWORK_PORT
        self.network_access_key = ""
        self.network_rate_limit_requests_per_minute = 0
        self.network_server = None
        self.network_server_thread = None
        self._network_error_shown = False
        self._network_tracker_mtime = 0.0
        self._client_disconnect_since = None
        self._client_disconnect_timeout_s = 30.0
        self._client_disconnect_closing = False
        self._client_poll_inflight = False
        self._client_poll_lock = threading.Lock()
        self._client_missed_pings = 0
        self._client_ever_connected = False
        self._network_bootstrap_ready = False
        self._host_services_starting = False
        self.tray_thread: threading.Thread | None = None
        self.is_hidden_to_tray = False
        self.tools_window: tk.Toplevel | None = None
        self.flowers: dict[str, Flower] = {}
        self.logs: list[dict[str, str | float]] = []
        self.window_geometry = ""
        self.settings_window_geometry = ""
        self.screen_resolution = ""
        self._force_center_on_start = False
        self._force_center_settings = False
        self.main_split_ratio = 0.48
        self.stock_column_widths: dict[str, int] = {}
        self.log_column_widths: dict[str, int] = {}
        self._geometry_save_job = None
        self._split_save_job = None
        self._restoring_split = True
        self._split_stabilize_job = None
        self._split_dragging = False
        self._split_apply_job = None
        self.current_date: date = date.today()
        self._last_seen_date: date = date.today()
        self._data_mtime: float | None = None
        self._build_ui()
        self._ensure_storage_dirs()
        self._load_config()
        # Defer network/data startup until after first paint to keep window open smooth.
        self.root.after(1200, self._startup_data_init)
        self.root.after(50, lambda: self._set_dark_title_bar(self.dark_var.get()))
        self.apply_theme(self.dark_var.get())
        if self._force_center_on_start:
            try:
                self._center_window_on_screen(self.root)
            except Exception:
                pass
        self._refresh_stock()
        self._refresh_log()
        try:
            # Run a short startup stabilization so late child geometry requests
            # cannot permanently displace the restored center sash.
            self.root.after(120, self._finalize_split_restore)
        except Exception:
            self._restoring_split = False
        self._update_scraper_status_icon()

    def _startup_data_init(self) -> None:
        try:
            if self.network_mode == MODE_HOST:
                # Load tracker UI data first, then bring up host services in the
                # background so server binds never stall the main thread.
                self.load_data()
                self._ensure_network_access_key()
                self._network_bootstrap_ready = True
                self._start_host_services_async()
            elif self.network_mode == MODE_CLIENT:
                # Non-blocking client bootstrap: populate when network fetch completes.
                self._network_bootstrap_ready = True
                self._request_client_network_poll(initial=True)
            else:
                self.load_data()
                self._network_bootstrap_ready = True
        except Exception as exc:
            # Never allow network-mode startup failures to crash the tracker UI.
            print(f"[network] startup fallback: {exc}")
            traceback.print_exc()
            try:
                messagebox.showwarning(
                    "Networking startup",
                    f"Network startup failed ({exc}). Falling back to local mode for this session.",
                )
            except Exception:
                pass
            self.network_mode = MODE_STANDALONE
            self.network_server = None
            self.network_server_thread = None
            try:
                self.load_data()
            except Exception:
                # Leave empty state rather than crashing.
                self.flowers = {}
                self.logs = []
            self._network_bootstrap_ready = True
        # load_data can update theme-affecting values; re-apply after startup load.
        self.apply_theme(self.dark_var.get())
        self._refresh_stock()
        self._refresh_log()

    def _ensure_network_access_key(self) -> None:
        if self.network_mode != MODE_HOST:
            return
        if str(getattr(self, "network_access_key", "") or "").strip():
            return
        try:
            self.network_access_key = secrets.token_urlsafe(24)
            self._save_config()
            self._log_network("[network] generated new access key for host mode")
        except Exception:
            pass

    def _start_host_services_async(self) -> None:
        if self.network_mode != MODE_HOST:
            return
        if (self.network_server and self.network_port) and (self.export_server and self.export_port):
            return
        if self._host_services_starting:
            return
        self._host_services_starting = True

        def worker() -> None:
            try:
                self._ensure_network_server()
                # Keep browser endpoint available for clients even if host never
                # manually opens the browser button.
                self._ensure_export_server()
            finally:
                try:
                    self.root.after(0, lambda: setattr(self, "_host_services_starting", False))
                except Exception:
                    self._host_services_starting = False

        threading.Thread(target=worker, daemon=True, name="flowertrack-host-services").start()

    def _request_client_network_poll(self, initial: bool = False) -> None:
        if self.network_mode != MODE_CLIENT:
            return
        with self._client_poll_lock:
            if self._client_poll_inflight:
                return
            self._client_poll_inflight = True
        host = (self.network_host or "").strip()
        port = int(self.network_port)
        access_key = str(getattr(self, "network_access_key", "") or "")
        prev_mtime = float(getattr(self, "_network_tracker_mtime", 0.0) or 0.0)

        def worker() -> None:
            result: dict[str, object] = {"ok": False, "initial": initial}
            try:
                meta = fetch_tracker_meta(host, port, timeout=0.75, access_key=access_key)
                if not isinstance(meta, dict) or not meta.get("ok"):
                    result = {"ok": False, "initial": initial}
                else:
                    try:
                        remote_mtime = float(meta.get("mtime") or 0.0)
                    except Exception:
                        remote_mtime = 0.0
                    result = {"ok": True, "mtime": remote_mtime, "initial": initial}
                    if initial or (remote_mtime > 0 and remote_mtime > prev_mtime):
                        data = fetch_tracker_data(
                            host,
                            port,
                            timeout=1.5 if initial else 1.0,
                            access_key=access_key,
                        )
                        if isinstance(data, dict):
                            result["data"] = data
                        else:
                            result = {"ok": False, "initial": initial}
            except Exception:
                result = {"ok": False, "initial": initial}
            finally:
                with self._client_poll_lock:
                    self._client_poll_inflight = False
                try:
                    self.root.after(0, lambda r=result: self._consume_client_network_result(r))
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True, name="flowertrack-client-poll").start()

    def _consume_client_network_result(self, result: dict[str, object]) -> None:
        if self.network_mode != MODE_CLIENT:
            return
        if not bool(result.get("ok")):
            self._client_missed_pings = int(getattr(self, "_client_missed_pings", 0) or 0) + 1
            now = time.monotonic()
            since = getattr(self, "_client_disconnect_since", None)
            if since is None:
                self._client_disconnect_since = now
            elif (now - float(since)) >= float(getattr(self, "_client_disconnect_timeout_s", 30.0)):
                if not self._client_disconnect_closing:
                    self._client_disconnect_closing = True
                    try:
                        messagebox.showerror(
                            "Host disconnected",
                            "Connection to the host was lost for too long. The client will now close.",
                        )
                    except Exception:
                        pass
                    try:
                        self.root.after(0, self._on_main_close)
                    except Exception:
                        self._on_main_close()
            return

        self._client_ever_connected = True
        self._client_missed_pings = 0
        self._client_disconnect_since = None
        try:
            remote_mtime = float(result.get("mtime") or 0.0)
        except Exception:
            remote_mtime = 0.0
        if remote_mtime > 0:
            self._network_tracker_mtime = remote_mtime
        data = result.get("data")
        if isinstance(data, dict):
            self._apply_loaded_tracker_data(data, remote_mtime=remote_mtime)
            self._refresh_stock()
            self._refresh_log()
    def _scraper_process_alive_from_state(self) -> bool:
        try:
            state = read_scraper_state(SCRAPER_STATE_FILE)
            pid = int(state.get("pid") or 0)
            if pid <= 0:
                return False
            if os.name == "nt":
                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                if not handle:
                    return False
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            try:
                os.kill(pid, 0)
                return True
            except Exception:
                return False
        except Exception:
            return False

    def open_parser(self, show_window: bool = True) -> None:
        """Launch the scraper UI in a separate process."""
        if self.network_mode == MODE_CLIENT:
            try:
                messagebox.showinfo("Client mode", "Medicann Scraper is disabled in client mode.")
            except Exception:
                pass
            return
        def focus_existing() -> bool:
            try:
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.WinDLL("user32", use_last_error=True)
                HWND = wintypes.HWND
                LPARAM = wintypes.LPARAM
                WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, LPARAM)
                found = []
                def enum_proc(hwnd, lParam):
                    buf = ctypes.create_unicode_buffer(512)
                    user32.GetWindowTextW(hwnd, buf, 512)
                    title = buf.value
                    if "Medicann Scraper" in title or "FlowerTrack" in title and "Scraper" in title:
                        found.append(hwnd)
                    return True
                user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
                if found:
                    hwnd = found[0]
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    user32.SetForegroundWindow(hwnd)
                    return True
            except Exception:
                pass
            return False
        try:
            # First try to focus an existing scraper window only when explicitly requested.
            if show_window:
                self._send_scraper_command("show")
                if focus_existing():
                    return
            if self._scraper_process_alive_from_state():
                return
            if getattr(sys, "frozen", False):
                args = [sys.executable, "--scraper"]
                if os.getenv("FLOWERTRACK_CONSOLE") == "1":
                    args.append("--console")
                if not show_window:
                    args.append("--scraper-hidden")
                proc = subprocess.Popen(args)
            else:
                exe = sys.executable
                target = Path(__file__).resolve().parent / "flowertracker.py"
                args = [exe, str(target), "--scraper"]
                if os.getenv("FLOWERTRACK_CONSOLE") == "1":
                    args.append("--console")
                if not show_window:
                    args.append("--scraper-hidden")
                proc = subprocess.Popen(args)
            try:
                self.child_procs.append(proc)
                self._update_scraper_status_icon()
            except Exception:
                pass
        except Exception as exc:
            messagebox.showerror("Open Scraper", f"Could not launch parser:\n{exc}")
    def open_flower_browser(self) -> None:
        if self.network_mode == MODE_CLIENT:
            host = (self.network_host or "127.0.0.1").strip() or "127.0.0.1"
            url = f"http://{host}:{int(self.export_port)}/flowerbrowser"
            try:
                webbrowser.open(url)
            except Exception as exc:
                messagebox.showerror("Flower Browser", f"Could not open host browser page:\n{exc}")
            return
        exports_dir = Path(EXPORTS_DIR_DEFAULT)
        exports_dir.mkdir(parents=True, exist_ok=True)
        html_files = sorted(exports_dir.glob("export-*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
        def _needs_template_refresh(path: Path) -> bool:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                return False
            return ("header-logo-link" not in text) or ("Medicann.png" not in text)
        if not html_files:
            try:
                data = load_last_parse(LAST_PARSE_FILE) or []
                if not data:
                    messagebox.showinfo("Flower Browser", "No data available to export yet.")
                    return
                latest = export_html_auto(data, exports_dir=exports_dir, open_file=False, fetch_images=False, max_files=1)
                warn = export_size_warning(latest)
                if warn:
                    messagebox.showwarning("Export size warning", warn)
                html_files = [latest]
            except Exception as exc:
                messagebox.showinfo("Flower Browser", f"Unable to generate export: {exc}")
                return
        latest = html_files[0]
        if _needs_template_refresh(latest):
            try:
                data = load_last_parse(LAST_PARSE_FILE) or []
                if data:
                    latest = export_html_auto(data, exports_dir=exports_dir, open_file=False, fetch_images=False, max_files=1)
                    html_files = [latest]
            except Exception:
                pass
        url = latest.as_uri()
        if self._ensure_export_server() and self.export_port:
            browser_host = "127.0.0.1"
            if self.network_mode == MODE_HOST:
                browser_host = (self.network_host or "127.0.0.1").strip() or "127.0.0.1"
            url = f"http://{browser_host}:{self.export_port}/flowerbrowser"
        try:
            webbrowser.open(url)
        except Exception:
            try:
                os.startfile(latest)
            except Exception as exc:
                messagebox.showerror("Flower Browser", f"Could not open export:\n{exc}")
    def _log_export(self, msg: str) -> None:
        try:
            print(msg)
        except Exception:
            pass

    def _log_network(self, msg: str) -> None:
        try:
            print(msg)
        except Exception:
            pass

    def _ensure_network_server(self) -> bool:
        if self.network_mode != MODE_HOST:
            return False
        try:
            self._ensure_network_access_key()
            if self.network_server and self.network_port:
                return True
            tracker_path = Path(self.data_path or TRACKER_DATA_FILE)
            library_path = Path(self.library_data_path or TRACKER_LIBRARY_FILE)
            httpd, thread, port = start_network_data_server(
                bind_host=self.network_bind_host,
                preferred_port=self.network_port,
                tracker_data_path=tracker_path,
                library_data_path=library_path,
                log=self._log_network,
                access_key=str(getattr(self, "network_access_key", "") or ""),
                rate_limit_requests_per_minute=int(
                    max(0, int(getattr(self, "network_rate_limit_requests_per_minute", 0) or 0))
                ),
            )
            if httpd and port:
                self.network_server = httpd
                self.network_server_thread = thread
                self.network_port = int(port)
                return True
        except Exception as exc:
            self._log_network(f"[network] failed to start: {exc}")
        return False

    def _stop_network_server(self) -> None:
        try:
            stop_network_data_server(self.network_server, self.network_server_thread, self._log_network)
        except Exception:
            pass
        self.network_server = None
        self.network_server_thread = None

    def _fetch_network_tracker_data(self) -> dict | None:
        host = (self.network_host or "").strip()
        if not host:
            return None
        data = fetch_tracker_data(
            host,
            int(self.network_port),
            access_key=str(getattr(self, "network_access_key", "") or ""),
        )
        if isinstance(data, dict):
            self._network_error_shown = False
            return data
        return None

    def _push_network_tracker_data(self, data: dict) -> bool:
        host = (self.network_host or "").strip()
        if not host:
            return False
        ok = push_tracker_data(
            host,
            int(self.network_port),
            data,
            access_key=str(getattr(self, "network_access_key", "") or ""),
        )
        if ok:
            self._network_error_shown = False
        return ok

    def _fetch_network_library_data(self) -> list[dict] | None:
        host = (self.network_host or "").strip()
        if not host:
            return None
        data = fetch_library_data(
            host,
            int(self.network_port),
            access_key=str(getattr(self, "network_access_key", "") or ""),
        )
        if isinstance(data, list):
            self._network_error_shown = False
            return data
        return None

    def _push_network_library_data(self, data: list[dict]) -> bool:
        host = (self.network_host or "").strip()
        if not host:
            return False
        ok = push_library_data(
            host,
            int(self.network_port),
            data,
            access_key=str(getattr(self, "network_access_key", "") or ""),
        )
        if ok:
            self._network_error_shown = False
        return ok

    def _ensure_export_server(self) -> bool:
        try:
            if self.export_server and self.export_port:
                return True
            exports_dir = Path(EXPORTS_DIR_DEFAULT)
            bind_host = "127.0.0.1"
            if self.network_mode == MODE_HOST:
                bind_host = self.network_bind_host
            httpd, thread, port = srv_start_export_server(
                self.export_port,
                exports_dir,
                self._log_export,
                bind_host=bind_host,
            )
            if httpd and port:
                self.export_server = httpd
                self.export_thread = thread
                self.export_port = port
                return True
            if port and not httpd:
                self.export_port = port
                return True
        except Exception:
            pass
        return False
    def _stop_export_server(self) -> None:
        try:
            srv_stop_export_server(self.export_server, self.export_thread, self._log_export)
        except Exception:
            pass
        self.export_server = None
        self.export_thread = None
    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.grid(row=0, column=0, sticky="nsew")
        self.main_content = main
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.protocol("WM_DELETE_WINDOW", self._on_main_close)
        self.root.bind("<Unmap>", self._on_unmap)
        self.root.bind("<Configure>", self._on_root_configure)
        top_bar = ttk.Frame(main, padding=(0, 0, 0, 8))
        top_bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Button(top_bar, text="Settings", command=self.open_settings).grid(row=0, column=0, padx=(0, 8))
        self.scraper_button = ttk.Button(top_bar, text="Medicann Scraper", command=self.open_parser)
        self.scraper_button.grid(row=0, column=1, padx=(8, 0))
        ttk.Button(top_bar, text="Flower Library", command=self.launch_flower_library).grid(row=0, column=2, padx=(8, 0))
        self.flower_browser_button = ttk.Button(top_bar, text="Flower Browser", command=self.open_flower_browser)
        self.flower_browser_button.grid(row=0, column=3, padx=(8, 0))
        time_font = ("", 14, "bold")
        self.clock_label = ttk.Label(top_bar, text="", font=time_font)
        self.clock_label.grid(row=0, column=4, sticky="e", padx=(12, 0))
        self.top_date_label = ttk.Label(top_bar, text="", font=time_font)
        self.top_date_label.grid(row=0, column=5, sticky="e", padx=(6, 0))
        self.host_clients_label = ttk.Label(top_bar, text="", font=("", 10, "bold"))
        self.host_clients_label.grid(row=0, column=6, sticky="e", padx=(8, 0))
        self.scraper_status_img = None
        self.scraper_status_label = ttk.Label(top_bar, text="", padding=0)
        self.scraper_status_label.grid(row=0, column=7, sticky="e", padx=(6, 0))
        self._bind_scraper_status_actions()
        self._apply_scraper_controls_visibility()
        top_bar.columnconfigure(4, weight=1)
        # Draggable center splitter for stock (left) vs dose/log (right)
        self.main_split = tk.PanedWindow(
            main,
            orient="horizontal",
            sashwidth=8,
            sashpad=1,
            sashrelief="flat",
            bd=0,
            relief="flat",
        )
        self.main_split.grid(row=1, column=0, columnspan=2, sticky="nsew")
        # Keep both grid columns weighted so the spanning paned window expands to full width.
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(1, weight=1)
        # Stock list
        self.stock_wrap = tk.Frame(self.main_split, highlightthickness=2)
        self.stock_wrap.columnconfigure(0, weight=1)
        self.stock_wrap.rowconfigure(0, weight=1)
        stock_frame = ttk.LabelFrame(
            self.stock_wrap,
            padding=10,
            style="Panel.TLabelframe",
            borderwidth=0,
            relief="flat",
            labelanchor="nw",
        )
        stock_label_wrap = ttk.Frame(stock_frame)
        stock_label = ttk.Label(stock_label_wrap, text="Flower Stock", style="Panel.TLabelframe.Label")
        stock_label.grid(padx=(6, 0), pady=(2, 0))
        stock_frame.configure(labelwidget=stock_label_wrap)
        stock_frame.grid(row=0, column=0, sticky="nsew")
        columns = ("name", "thc", "cbd", "grams")
        self.stock_tree = ttk.Treeview(
            stock_frame,
            columns=columns,
            show="headings",
            height=8,
            style=self.tree_style,
        )
        headings = {
            "name": ("Name", False),
            "thc": ("THC (%)", True),
            "cbd": ("CBD (%)", True),
            "grams": ("Remaining (g)", True),
        }
        for col, (text, is_numeric) in headings.items():
            # Plain ASCII labels to avoid garbled heading text
            self.stock_tree.heading(
                col,
                text=str(text),
                command=lambda c=col, numeric=is_numeric: self._sort_stock(c, numeric),
            )
        self.stock_tree.column("name", width=140)
        self.stock_tree.column("thc", width=80, anchor="center")
        self.stock_tree.column("cbd", width=80, anchor="center")
        self.stock_tree.column("grams", width=120, anchor="center")
        self.stock_tree.grid(row=0, column=0, sticky="nsew")
        self._bind_tree_resize(self.stock_tree, "stock_column_widths")
        stock_scroll = ttk.Scrollbar(stock_frame, orient="vertical", command=self.stock_tree.yview, style=self.vscroll_style)
        self.stock_tree.configure(yscrollcommand=stock_scroll.set)
        stock_scroll.grid(row=0, column=1, sticky="ns")
        stock_frame.rowconfigure(0, weight=1)
        stock_frame.columnconfigure(0, weight=1)
        # Stock controls
        stock_header = ttk.Frame(stock_frame)
        stock_header.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 0))
        self.stock_form_toggle = ttk.Label(stock_header, text="˅", cursor="hand2")
        self.stock_form_toggle.pack(side="top", anchor="center", pady=(0, 0))
        self.stock_form_toggle.bind("<Button-1>", lambda _e: self._toggle_stock_form())
        form = ttk.Frame(stock_frame, padding=(0, 0, 0, 0))
        form.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.stock_form_frame = form
        stock_frame.columnconfigure(0, weight=1)
        ttk.Label(form, text="Name").grid(row=0, column=0, sticky="w")
        self.name_entry = ttk.Entry(form, width=18)
        self.name_entry.grid(row=1, column=0, padx=(0, 8))
        ttk.Label(form, text="THC %").grid(row=0, column=1, sticky="w")
        self.thc_entry = ttk.Entry(form, width=8)
        self.thc_entry.grid(row=1, column=1, padx=(0, 8))
        ttk.Label(form, text="CBD %").grid(row=0, column=2, sticky="w")
        self.cbd_entry = ttk.Entry(form, width=8)
        self.cbd_entry.grid(row=1, column=2, padx=(0, 8))
        ttk.Label(form, text="Grams").grid(row=0, column=3, sticky="w")
        self.grams_entry = ttk.Entry(form, width=10)
        self.grams_entry.grid(row=1, column=3, padx=(0, 8))
        for widget in (self.name_entry, self.thc_entry, self.cbd_entry, self.grams_entry):
            widget.bind("<Key>", self._mark_stock_form_dirty)
        add_btn = ttk.Button(form, text="Add / Update Stock", command=self.add_stock)
        add_btn.grid(row=1, column=4, padx=(0, 8))
        self.mix_stock_button = ttk.Button(form, text="Mix stock", command=lambda: self.launch_mix_calculator(mode="stock"))
        self.mix_stock_button.grid(row=1, column=6, padx=(0, 8))
        self._mix_stock_grid = self.mix_stock_button.grid_info()
        self._mix_stock_grid = self.mix_stock_button.grid_info()
        delete_btn = ttk.Button(form, text="Delete Selected", command=self.delete_stock)
        delete_btn.grid(row=1, column=7)
        totals_frame = ttk.Frame(stock_frame)
        totals_frame.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.total_label = ttk.Label(totals_frame, text="Total THC flower stock: 0.00 g", font=self.font_bold_small)
        self.total_label.pack(side="left", padx=(0, 10))
        self.total_cbd_label = ttk.Label(totals_frame, text="Total CBD flower stock: 0.00 g", font=self.font_bold_small)
        self.total_cbd_label.pack(side="left")
        self.days_label = ttk.Label(stock_frame, text="Days of THC flower usage left - target: N/A | actual: N/A", font=self.font_body)
        self.days_label.grid(row=4, column=0, columnspan=2, sticky="w", pady=(2, 0))
        self.days_label_cbd = ttk.Label(
        stock_frame, text="Days of CBD flower usage left - target: N/A | actual: N/A", font=self.font_body
        )
        self.days_label_cbd.grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 2))
        self.days_label_cbd.grid_remove()
        # Dose + log area
        right = ttk.Frame(self.main_split)
        self.right_content = right
        self.dose_wrap = tk.Frame(right, highlightthickness=2)
        self.dose_wrap.grid(row=0, column=0, sticky="ew")
        self.dose_wrap.columnconfigure(0, weight=1)
        dose_frame = ttk.LabelFrame(
            self.dose_wrap,
            padding=10,
            style="Panel.TLabelframe",
            borderwidth=0,
            relief="flat",
            labelanchor="nw",
        )
        dose_label_wrap = ttk.Frame(dose_frame)
        dose_label = ttk.Label(dose_label_wrap, text="Log Dose", style="Panel.TLabelframe.Label")
        dose_label.grid(padx=(6, 0), pady=(2, 0))
        dose_frame.configure(labelwidget=dose_label_wrap)
        dose_frame.grid(row=0, column=0, sticky="ew")
        ttk.Label(dose_frame, text="Flower").grid(row=0, column=0, sticky="w")
        self.flower_choice = ttk.Combobox(dose_frame, state="readonly", width=35, values=[], style=self.combo_style)
        self.flower_choice.grid(row=1, column=0, padx=(0, 12))
        self.flower_choice.bind("<FocusOut>", self._clear_combo_selection)
        self.flower_choice.bind("<<ComboboxSelected>>", self._clear_combo_selection)
        ttk.Label(dose_frame, text="Dose (g)").grid(row=0, column=1, sticky="w")
        self.dose_entry = ttk.Entry(dose_frame, width=10)
        self.dose_entry.grid(row=1, column=1, padx=(0, 12))
        self.roa_label = ttk.Label(dose_frame, text="Route")
        self.roa_label.grid(row=0, column=2, sticky="w")
        self.roa_choice = ttk.Combobox(
            dose_frame,
            state="readonly",
            width=12,
            values=list(self.roa_options.keys()),
            style=self.combo_style,
        )
        self.roa_choice.grid(row=1, column=2, padx=(0, 12))
        # Default order: Vaped, Eaten, Smoked; preselect Vaped
        self.roa_choice.set("Vaped")
        log_btn = ttk.Button(dose_frame, text="Log Dose", command=self.log_dose)
        log_btn.grid(row=1, column=3)
        self.mixed_dose_button = ttk.Button(dose_frame, text="Mixed dose", command=self.launch_mix_calculator)
        self.mixed_dose_button.grid(row=1, column=4, padx=(8, 0))
        self._mixed_dose_grid = self.mixed_dose_button.grid_info()
        self._apply_stock_form_visibility()
        self._mixed_dose_grid = self.mixed_dose_button.grid_info()
        self.note_label = None
        self.remaining_today_label = ttk.Label(
            dose_frame, text="Remaining today (THC): 0.00 g", font=self.font_bold_mid
        )
        self.remaining_today_label.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.remaining_today_cbd_label = ttk.Label(
            dose_frame, text="Remaining today (CBD): 0.00 g", font=self.font_bold_mid
        )
        self.remaining_today_cbd_label.grid(row=4, column=0, columnspan=3, sticky="w", pady=(2, 0))
        self.remaining_today_cbd_label.grid_remove()
        self.log_wrap = tk.Frame(right, highlightthickness=2)
        self.log_wrap.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        self.log_wrap.columnconfigure(0, weight=1)
        self.log_wrap.rowconfigure(0, weight=1)
        log_frame = ttk.LabelFrame(
            self.log_wrap,
            padding=10,
            style="Panel.TLabelframe",
            borderwidth=0,
            relief="flat",
            labelanchor="nw",
        )
        log_label_wrap = ttk.Frame(log_frame)
        log_label = ttk.Label(log_label_wrap, text="Usage Log", style="Panel.TLabelframe.Label")
        log_label.grid(padx=(6, 0), pady=(2, 0))
        log_frame.configure(labelwidget=log_label_wrap)
        log_frame.grid(row=0, column=0, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        try:
            self.main_split.add(self.stock_wrap, minsize=220, stretch="always")
            self.main_split.add(right, minsize=260, stretch="always")
            self.main_split.bind("<ButtonPress-1>", lambda _e: setattr(self, "_split_dragging", True))
            self.main_split.bind("<ButtonRelease-1>", lambda _e: self._on_split_release())
            self.main_split.bind("<Configure>", lambda _e: self._schedule_split_apply())
        except Exception:
            pass
        nav = ttk.Frame(log_frame)
        nav.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        prev_btn = ttk.Button(nav, text="< Prev", width=8, command=lambda: self._change_day(-1))
        prev_btn.grid(row=0, column=0, padx=(0, 6))
        self.date_label = ttk.Label(nav, text="", font=("", 12, "bold"))
        self.date_label.grid(row=0, column=1)
        next_btn = ttk.Button(nav, text="Next >", width=8, command=lambda: self._change_day(1))
        next_btn.grid(row=0, column=2, padx=(6, 0))
        nav.columnconfigure(1, weight=1)
        log_cols = ("time", "flower", "roa", "grams", "thc_mg", "cbd_mg")
        self.log_tree = ttk.Treeview(log_frame, columns=log_cols, show="headings", height=12, style=self.tree_style)
        self.log_tree["displaycolumns"] = log_cols
        headings = {
            "time": "Time",
            "flower": "Flower",
            "roa": "ROA",
            "grams": "Dose (g)",
            "thc_mg": "THC (mg)",
            "cbd_mg": "CBD (mg)",
        }
        for col, text in headings.items():
            self.log_tree.heading(col, text=text)
        self.log_tree.column("time", width=60, anchor="center")
        self.log_tree.column("flower", width=250, anchor="center")
        self.log_tree.column("roa", width=60, anchor="center")
        self.log_tree.column("grams", width=90, anchor="center")
        self.log_tree.column("thc_mg", width=70, anchor="center")
        self.log_tree.column("cbd_mg", width=70, anchor="center")
        self.log_tree.grid(row=2, column=0, sticky="nsew")
        self._bind_log_thc_cbd_tooltip()
        self._bind_tree_resize(self.log_tree, "log_column_widths")
        log_scroll = ttk.Scrollbar(
            log_frame, orient="vertical", command=self.log_tree.yview, style=self.vscroll_style
        )
        self.log_tree.configure(yscrollcommand=log_scroll.set)
        log_scroll.grid(row=2, column=1, sticky="ns")
        log_frame.rowconfigure(2, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_actions = ttk.Frame(log_frame, padding=(0, 6, 0, 0))
        log_actions.grid(row=3, column=0, columnspan=2, sticky="ew")
        ttk.Button(log_actions, text="Edit Selected Log", command=self.edit_log_entry).grid(
            row=0, column=0, padx=(0, 8), sticky="w"
        )
        ttk.Button(log_actions, text="Delete Selected Log", command=self.delete_log_entry).grid(
            row=0, column=1, sticky="w"
        )
        self.day_total_label = ttk.Label(log_actions, text="Total used this day (THC): 0.000 g", font=self.font_bold_mid)
        self.day_total_label.grid(row=0, column=2, padx=(12, 12), sticky="w")
        self.day_total_cbd_label = ttk.Label(log_actions, text="Total used this day (CBD): 0.000 g", font=self.font_bold_mid)
        self.day_total_cbd_label.grid(row=1, column=2, padx=(12, 12), sticky="w")
        self.day_total_cbd_label.grid_remove()
        log_actions.columnconfigure(2, weight=1)
        ttk.Button(log_actions, text="Stats", width=8, command=lambda: self._show_stats_window("day")).grid(
            row=0, column=3, sticky="e"
        )
        self.stock_tree.bind("<<TreeviewSelect>>", self._on_stock_select)
        self.stock_tree.bind("<ButtonRelease-1>", self._maybe_clear_stock_selection)
        self.log_tree.bind("<ButtonRelease-1>", self._maybe_clear_log_selection)
        self._update_clock()
    def _on_stock_select(self, event: tk.Event) -> None:
        _stock_on_stock_select(self, event)

    def _maybe_clear_stock_selection(self, event: tk.Event) -> None:
        _stock_maybe_clear_stock_selection(self, event)

    def _maybe_clear_log_selection(self, event: tk.Event) -> None:
        _stock_maybe_clear_log_selection(self, event)

    def add_stock(self) -> None:
        _stock_add_stock(self)

    def delete_stock(self) -> None:
        _stock_delete_stock(self)

    def _clear_stock_inputs(self) -> None:
        _stock_clear_stock_inputs(self)
    def log_dose(self) -> None:
        _log_log_dose(self)

    def _resolve_roa(self) -> str:
        return _log_resolve_roa(self)
    def edit_log_entry(self) -> None:
        _log_edit_log_entry(self)
    def _restore_mix_stock(self, log: dict) -> None:
        _log_restore_mix_stock(self, log)
    def delete_log_entry(self) -> None:
        _log_delete_log_entry(self)
    def _refresh_stock(self) -> None:
        _stock_refresh_stock(self)
    def _refresh_log(self) -> None:
        _log_refresh_log(self)
    def _change_day(self, delta_days: int) -> None:
        _log_change_day(self, delta_days)
    def _color_for_value(self, value: float, high: float, low: float, high_color: str, low_color: str) -> str:
        """Return hex color between high_color and low_color based on thresholds."""
        green = self._hex_to_rgb(high_color, fallback=(46, 204, 113))
        red = self._hex_to_rgb(low_color, fallback=(231, 76, 60))
        if value >= high:
            return f"#{green[0]:02x}{green[1]:02x}{green[2]:02x}"
        if value <= low:
            return f"#{red[0]:02x}{red[1]:02x}{red[2]:02x}"
        ratio = (value - low) / max(high - low, 1e-6)
        r = int(red[0] + (green[0] - red[0]) * ratio)
        g = int(red[1] + (green[1] - red[1]) * ratio)
        b = int(red[2] + (green[2] - red[2]) * ratio)
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _hex_to_rgb(value: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
        text = (value or "").strip().lstrip("#")
        if len(text) == 3:
            text = "".join(ch * 2 for ch in text)
        if len(text) != 6:
            return fallback
        try:
            return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
        except Exception:
            return fallback

    @staticmethod
    def _normalize_hex(value: str) -> str | None:
        text = (value or "").strip().lstrip("#")
        if len(text) == 3:
            text = "".join(ch * 2 for ch in text)
        if len(text) != 6:
            return None
        try:
            int(text, 16)
        except Exception:
            return None
        return f"#{text.lower()}"

    def _register_threshold_color_button(self, button: tk.Button, key: str) -> None:
        self._threshold_color_buttons.setdefault(key, []).append(button)

    def _update_threshold_color_buttons(self) -> None:
        for key, buttons in self._threshold_color_buttons.items():
            color = getattr(self, key, None)
            if not color:
                continue
            for btn in buttons:
                try:
                    border_color = "#ffffff" if self.dark_var.get() else "#000000"
                    btn.configure(
                        bg=color,
                        activebackground=color,
                        activeforeground=self.text_color if getattr(self, "text_color", "") else "#eee",
                        relief="solid",
                        bd=1,
                        highlightthickness=1,
                        highlightbackground=border_color,
                        highlightcolor=border_color,
                    )
                except Exception:
                    pass

    def _register_theme_color_button(self, mode: str, key: str, button: tk.Button) -> None:
        self._theme_color_buttons.setdefault((mode, key), []).append(button)

    def _update_theme_color_buttons(self) -> None:
        for (mode, key), buttons in self._theme_color_buttons.items():
            palette = self.theme_palette_dark if mode == "dark" else self.theme_palette_light
            color = palette.get(key)
            if not color:
                continue
            for btn in buttons:
                try:
                    border_color = "#ffffff" if self.dark_var.get() else "#000000"
                    btn.configure(
                        bg=color,
                        activebackground=color,
                        activeforeground=self.text_color if getattr(self, "text_color", "") else "#eee",
                        relief="solid",
                        bd=1,
                        highlightthickness=1,
                        highlightbackground=border_color,
                        highlightcolor=border_color,
                    )
                except Exception:
                    pass

    def _set_palette_color(self, mode: str, key: str, color: str) -> None:
        palette = self.theme_palette_dark if mode == "dark" else self.theme_palette_light
        palette[key] = color
        set_palette_overrides(self.theme_palette_dark, self.theme_palette_light)
        self.apply_theme(self.dark_var.get())
        self._update_theme_color_buttons()
        self._save_config()

    def _apply_picker_theme(self, picker: tk.Toplevel) -> None:
        base = getattr(self, "current_base_color", "#111")
        ctrl_bg = getattr(self, "current_ctrl_bg", "#222")
        fg = getattr(self, "text_color", "#eee")
        border = getattr(self, "current_border_color", "#2a2a2a")
        try:
            picker.configure(bg=base)
        except Exception:
            pass
        try:
            style = ttk.Style(picker)
            style.theme_use("clam")
            style.configure("TFrame", background=base)
            style.configure("TLabel", background=base, foreground=fg)
            style.configure("TButton", background=ctrl_bg, foreground=fg, bordercolor=border, focusthickness=0)
            style.map("TButton", background=[("active", ctrl_bg)], foreground=[("active", fg)])
            style.configure("TEntry", fieldbackground=ctrl_bg, foreground=fg, background=ctrl_bg)
            style.configure("TSpinbox", fieldbackground=ctrl_bg, foreground=fg, background=ctrl_bg)
        except Exception:
            pass

        try:
            default_label_bg = tk.Label(picker).cget("background")
            default_frame_bg = tk.Frame(picker).cget("background")
        except Exception:
            default_label_bg = None
            default_frame_bg = None

        def _style_widget(widget: tk.Widget) -> None:
            try:
                if isinstance(widget, (tk.Frame, tk.Toplevel)):
                    if default_frame_bg is None or widget.cget("background") == default_frame_bg:
                        widget.configure(bg=base)
                elif isinstance(widget, (tk.Label, tk.LabelFrame)):
                    bg = widget.cget("background")
                    if default_label_bg is None or bg == default_label_bg:
                        widget.configure(bg=base, fg=fg)
                elif isinstance(widget, (tk.Entry, tk.Spinbox)):
                    widget.configure(bg=ctrl_bg, fg=fg, insertbackground=fg)
                elif isinstance(widget, tk.Button):
                    widget.configure(bg=ctrl_bg, fg=fg, activebackground=ctrl_bg, activeforeground=fg)
            except Exception:
                pass
            for child in widget.winfo_children():
                _style_widget(child)

        _style_widget(picker)
        try:
            hexa_entry = getattr(picker, "hexa", None)
            if hexa_entry is not None and hexa_entry.winfo_exists():
                parent = hexa_entry.master
                if parent is not None and not getattr(parent, "_hex_clip_buttons", None):
                    def _copy_hex() -> None:
                        try:
                            value = str(hexa_entry.get() or "").strip()
                            if not value:
                                return
                            picker.clipboard_clear()
                            picker.clipboard_append(value)
                        except Exception:
                            pass

                    def _paste_hex() -> None:
                        try:
                            value = str(picker.clipboard_get() or "").strip()
                            if not value:
                                return
                            hexa_entry.delete(0, "end")
                            hexa_entry.insert(0, value)
                            try:
                                picker._update_color_hexa()
                            except Exception:
                                pass
                        except Exception:
                            pass

                    copy_btn = ttk.Button(parent, text="Copy", width=5, command=_copy_hex)
                    paste_btn = ttk.Button(parent, text="Paste", width=5, command=_paste_hex)
                    copy_btn.pack(side="left", padx=(4, 2), pady=(4, 1))
                    paste_btn.pack(side="left", padx=(2, 0), pady=(4, 1))
                    parent._hex_clip_buttons = (copy_btn, paste_btn)
        except Exception:
            pass
        # Titlebar apply happens in _ask_colour_picker when the picker is shown.

    def _center_child_window(self, child: tk.Toplevel, parent: tk.Toplevel | None) -> None:
        try:
            child.update_idletasks()
            width = child.winfo_reqwidth()
            height = child.winfo_reqheight()
            if parent and tk.Toplevel.winfo_exists(parent):
                parent.update_idletasks()
                px = parent.winfo_rootx()
                py = parent.winfo_rooty()
                pw = parent.winfo_width()
                ph = parent.winfo_height()
                x = px + (pw - width) // 2
                y = py + (ph - height) // 2
            else:
                sw = child.winfo_screenwidth()
                sh = child.winfo_screenheight()
                x = (sw - width) // 2
                y = (sh - height) // 2
            x = max(0, x)
            y = max(0, y)
            child.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _ask_colour_picker(self, current: str, title: str, parent: tk.Toplevel | None) -> str | None:
        if TkColorPicker is None:
            return colorchooser.askcolor(color=current, title=title, parent=parent)[1]
        picker = TkColorPicker(parent, color=current, title=title)
        self._apply_picker_theme(picker)
        try:
            picker.attributes("-alpha", 0.0)
        except Exception:
            pass
        try:
            picker.withdraw()
        except Exception:
            pass
        self._center_child_window(picker, parent)
        try:
            top = picker.winfo_toplevel()
            picker.deiconify()
            picker.attributes("-alpha", 1.0)
            picker.update_idletasks()
            self._apply_picker_titlebar(top)
            picker.after_idle(lambda: self._apply_picker_titlebar(top))
            # DWM titlebar updates for tkcolorpicker are timing-sensitive on some systems.
            # Queue a few retries against the picker window handle (not parent) for reliability.
            self._queue_dark_titlebar(top, attempts=8, delay_ms=80, allow_parent=False)
        except Exception:
            try:
                picker.deiconify()
                picker.attributes("-alpha", 1.0)
            except Exception:
                pass
        picker.wait_window(picker)
        try:
            res = picker.get_color()
        except Exception:
            res = None
        try:
            if parent and tk.Toplevel.winfo_exists(parent):
                self._queue_settings_titlebar(parent)
        except Exception:
            pass
        if res:
            return res[2]
        return None

    def _choose_theme_color(self, mode: str, key: str) -> None:
        palette = self.theme_palette_dark if mode == "dark" else self.theme_palette_light
        current = palette.get(key, "#ffffff")
        settings_win = getattr(self, "settings_window", None)
        parent = None
        try:
            if settings_win and tk.Toplevel.winfo_exists(settings_win):
                parent = settings_win
        except Exception:
            parent = None
        picked = self._ask_colour_picker(current=current, title="Select colour", parent=parent)
        try:
            if settings_win and tk.Toplevel.winfo_exists(settings_win):
                self._queue_settings_titlebar(settings_win)
        except Exception:
            pass
        color = self._normalize_hex(picked or "")
        if not color:
            return
        self._set_palette_color(mode, key, color)

    def _reset_theme_palettes(self) -> None:
        default_dark, default_light = get_default_palettes()
        self.theme_palette_dark = dict(default_dark)
        self.theme_palette_light = dict(default_light)
        set_palette_overrides(self.theme_palette_dark, self.theme_palette_light)
        self.apply_theme(self.dark_var.get())
        self._update_theme_color_buttons()
        self._save_config()

    def _choose_threshold_color(self, key: str) -> None:
        current = getattr(self, key, None) or "#2ecc71"
        settings_win = getattr(self, "settings_window", None)
        parent = None
        try:
            if settings_win and tk.Toplevel.winfo_exists(settings_win):
                parent = settings_win
        except Exception:
            parent = None
        picked = self._ask_colour_picker(current=current, title="Select colour", parent=parent)
        try:
            if settings_win and tk.Toplevel.winfo_exists(settings_win):
                self._queue_settings_titlebar(settings_win)
        except Exception:
            pass
        color = self._normalize_hex(picked or "")
        if not color:
            return
        setattr(self, key, color)
        self._update_threshold_color_buttons()
        self._refresh_stock()
        self._refresh_log()
        if key.startswith("scraper_status_"):
            self._update_scraper_status_icon()
        self._save_config()

    def _bring_settings_to_front(self, settings_win: tk.Toplevel) -> None:
        try:
            settings_win.transient(self.root)
            settings_win.lift()
            settings_win.focus_force()
        except Exception:
            pass

    def _queue_settings_titlebar(self, settings_win: tk.Toplevel) -> None:
        try:
            if getattr(self, "_settings_titlebar_job", None) is not None:
                return
            def _apply():
                self._settings_titlebar_job = None
                try:
                    if settings_win and tk.Toplevel.winfo_exists(settings_win):
                        self._set_dark_title_bar(self.dark_var.get(), target=settings_win)
                except Exception:
                    pass
            self._settings_titlebar_job = self.root.after_idle(_apply)
        except Exception:
            try:
                self._set_dark_title_bar(self.dark_var.get(), target=settings_win)
            except Exception:
                pass

    def _resolve_hwnd(self, win: tk.Tk | tk.Toplevel, allow_parent: bool = True) -> int:
        hwnd = win.winfo_id()
        try:
            GA_ROOT = 2
            root_hwnd = ctypes.windll.user32.GetAncestor(hwnd, GA_ROOT)
            if root_hwnd:
                hwnd = root_hwnd
        except Exception:
            pass
        if not allow_parent:
            return hwnd
        get_parent = ctypes.windll.user32.GetParent
        parent = get_parent(hwnd)
        while parent:
            hwnd = parent
            parent = get_parent(hwnd)
        return hwnd

    def _refresh_window_frame(self, win: tk.Tk | tk.Toplevel, allow_parent: bool = True) -> None:
        if os.name != "nt":
            return
        try:
            hwnd = self._resolve_hwnd(win, allow_parent=allow_parent)
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_NOZORDER = 0x0004
            SWP_FRAMECHANGED = 0x0020
            flags = SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, flags)
        except Exception:
            pass

    def _apply_picker_titlebar(self, win: tk.Toplevel) -> None:
        try:
            if not win or not tk.Toplevel.winfo_exists(win):
                return
            self._set_dark_title_bar(self.dark_var.get(), target=win, allow_parent=False)
            self._refresh_window_frame(win, allow_parent=False)
        except Exception:
            pass

    def _queue_dark_titlebar(
        self, win: tk.Toplevel, attempts: int = 20, delay_ms: int = 100, allow_parent: bool = True
    ) -> None:
        def _apply(remaining: int) -> None:
            try:
                if not win or not tk.Toplevel.winfo_exists(win):
                    return
                self._set_dark_title_bar(self.dark_var.get(), target=win, allow_parent=allow_parent)
                self._refresh_window_frame(win, allow_parent=allow_parent)
            except Exception:
                pass
            if remaining > 1:
                try:
                    win.after(delay_ms, lambda: _apply(remaining - 1))
                except Exception:
                    pass
        _apply(attempts)

    def _toggle_theme(self) -> None:
        self.apply_theme(self.dark_var.get())
        self.save_data()
        self._save_config()
    def open_settings(self) -> None:
        open_tracker_settings(self)
    def open_tools(self) -> None:
        if self.tools_window and tk.Toplevel.winfo_exists(self.tools_window):
            try:
                self.tools_window.deiconify()
                self.tools_window.lift()
                self.tools_window.focus_force()
            except Exception:
                pass
            return
        win = tk.Toplevel(self.root)
        win._stats_period = period
        win.title("Tools")
        try:
            win.iconbitmap(self._resource_path('icon.ico'))
        except Exception:
            pass
        self.tools_window = win
        win.resizable(False, False)
        win.geometry("320x240")
        win.grid_columnconfigure(0, weight=1)
        win.grid_rowconfigure(0, weight=1)
        frame = ttk.Frame(win, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)
        frame.rowconfigure(3, weight=0)
        frame.rowconfigure(4, weight=0)
        ttk.Label(frame, text="Tools", font=self.font_bold_small).grid(row=0, column=0, sticky="w", pady=(0, 6))
        if self.network_mode != MODE_CLIENT:
            ttk.Button(frame, text="Medicann Scraper", command=lambda: self._open_scraper_from_tools()).grid(
                row=1, column=0, sticky="w", pady=(0, 6)
            )
        ttk.Button(frame, text="Flower Library", command=lambda: self.launch_flower_library(close_tools=True)).grid(
            row=2, column=0, sticky="w", pady=(0, 6)
        )
        ttk.Button(frame, text="Mix Calculator", command=lambda: self.launch_mix_calculator(close_tools=True)).grid(
            row=3, column=0, sticky="w", pady=(0, 6)
        )
        ttk.Button(frame, text="Close", command=win.destroy).grid(row=4, column=0, sticky="se", pady=(12, 0))
        self._prepare_toplevel(win)
    def _save_settings(self) -> None:
        _save_tracker_settings(self)
    def _mark_stock_form_dirty(self, event: tk.Event) -> None:
        _stock_mark_stock_form_dirty(self, event)
    def _bind_tree_resize(self, tree: ttk.Treeview, key: str) -> None:
        tree.bind("<ButtonRelease-1>", lambda e, t=tree, k=key: self._store_tree_widths(t, k))
        tree.bind("<ButtonRelease-2>", lambda e, t=tree, k=key: self._store_tree_widths(t, k))
        tree.bind("<ButtonRelease-3>", lambda e, t=tree, k=key: self._store_tree_widths(t, k))
        tree.bind("<Configure>", lambda e, t=tree, k=key: self._store_tree_widths(t, k))
        tree.bind("<B1-Motion>", lambda e, t=tree, k=key: self._schedule_tree_widths(t, k))
    def _schedule_tree_widths(self, tree: ttk.Treeview, key: str) -> None:
        try:
            if not hasattr(self, "_tree_width_jobs"):
                self._tree_width_jobs = {}
            job = self._tree_width_jobs.get(key)
            if job:
                try:
                    self.root.after_cancel(job)
                except Exception:
                    pass
            self._tree_width_jobs[key] = self.root.after(200, lambda t=tree, k=key: self._commit_tree_widths(t, k))
        except Exception:
            self._commit_tree_widths(tree, key)
    def _store_tree_widths(self, tree: ttk.Treeview, key: str) -> None:
        try:
            # Delay slightly so the final width is applied after the drag ends.
            self.root.after(50, lambda t=tree, k=key: self._commit_tree_widths(t, k))
        except Exception:
            self._commit_tree_widths(tree, key)
    def _commit_tree_widths(self, tree: ttk.Treeview, key: str) -> None:
        widths = {col: int(tree.column(col, option="width")) for col in tree["columns"]}
        if key == "stock_column_widths":
            if getattr(self, "_suspend_stock_width_save", False):
                return
            self.stock_column_widths = widths
        else:
            if getattr(self, "_suspend_log_width_save", False):
                return
            self.log_column_widths = widths
        self._save_config()
    def _persist_tree_widths(self) -> None:
        _persist_persist_tree_widths(self)
    def _on_root_configure(self, event: tk.Event) -> None:
        _persist_on_root_configure(self, event)
    def _persist_geometry(self) -> None:
        _persist_persist_geometry(self)

    def _schedule_settings_geometry(self, win: tk.Toplevel) -> None:
        _persist_schedule_settings_geometry(self, win)

    def _persist_settings_geometry(self, win: tk.Toplevel) -> None:
        _persist_persist_settings_geometry(self, win)

    def _current_screen_resolution(self) -> str:
        return _persist_current_screen_resolution(self)

    @staticmethod
    def _parse_resolution(value: str) -> tuple[int, int] | None:
        return _persist_parse_resolution(value)

    def _apply_resolution_safety(self) -> None:
        _persist_apply_resolution_safety(self)
    def apply_theme(self, dark: bool) -> None:
        colors = compute_colors(dark)
        base = colors["bg"]
        text_color = colors["fg"]
        panel = colors["ctrl_bg"]
        entry_bg = colors["ctrl_bg"]
        accent = colors["accent"]
        highlight = colors.get("highlight", colors["accent"])
        highlight_text = colors.get("highlight_text", "#ffffff")
        border = colors.get("border", colors["ctrl_bg"])
        scroll = "#2a2a2a" if dark else "#e6e6e6"
        cursor_color = text_color
        # Prefer dark title bar when dark mode is on
        self.root.after(0, lambda: self._set_dark_title_bar(dark))
        self.current_base_color = base
        self.current_ctrl_bg = panel
        self.current_border_color = border
        self.root.configure(bg=base)
        apply_style_theme(self.style, colors)
        self.style.configure(
            "TCheckbutton",
            background=base,
            foreground=text_color,
            indicatorcolor=panel,
            indicatorbackground=panel,
            indicatorforeground=text_color,
        )
        self.style.map(
            "TCheckbutton",
            background=[("active", accent)],
            foreground=[("active", "#ffffff")],
            indicatorcolor=[("selected", accent), ("!selected", panel)],
            indicatorbackground=[("selected", accent), ("!selected", panel)],
            indicatorforeground=[("selected", text_color), ("!selected", text_color)],
        )
        panel_border = border
        self.style.configure(
            "Panel.TLabelframe",
            background=base,
            foreground=text_color,
            bordercolor=panel_border,
            borderwidth=0,
            relief="flat",
        )
        self.style.configure("Panel.TLabelframe.Label", background=base, foreground=text_color)
        for wrap in (getattr(self, "stock_wrap", None), getattr(self, "dose_wrap", None), getattr(self, "log_wrap", None)):
            if wrap:
                try:
                    wrap.configure(bg=base, highlightbackground=panel_border, highlightcolor=panel_border)
                except Exception:
                    pass
        try:
            split = getattr(self, "main_split", None)
            if split:
                split.configure(bg=base, sashrelief="flat")
        except Exception:
            pass
        self.style.configure(
            "TEntry",
            fieldbackground=entry_bg,
            background=entry_bg,
            foreground=text_color,
            insertcolor=cursor_color,
            bordercolor=panel_border,
            lightcolor=panel_border,
            darkcolor=panel_border,
        )
        self.style.configure(
            self.combo_style,
            fieldbackground=entry_bg,
            background=entry_bg,
            foreground=text_color,
            arrowcolor=text_color,
            bordercolor=panel_border,
            lightcolor=panel_border,
            darkcolor=panel_border,
        )
        self.style.map(
            self.combo_style,
            fieldbackground=[("readonly", entry_bg), ("!readonly", entry_bg), ("active", entry_bg)],
            background=[("readonly", entry_bg), ("!readonly", entry_bg), ("active", entry_bg)],
            foreground=[("active", text_color)],
        )
        # Try to align dropdown list colors with the combobox button/field
        self.root.option_add("*TCombobox*Listbox*Background", entry_bg)
        self.root.option_add("*TCombobox*Listbox*Foreground", text_color)
        self.root.option_add("*TCombobox*Listbox*selectBackground", highlight)
        self.root.option_add("*TCombobox*Listbox*selectForeground", highlight_text)
        # Alias patterns improve reliability across Tk builds/themes.
        self.root.option_add("*TCombobox*Listbox.background", entry_bg)
        self.root.option_add("*TCombobox*Listbox.foreground", text_color)
        self.root.option_add("*TCombobox*Listbox.selectBackground", highlight)
        self.root.option_add("*TCombobox*Listbox.selectForeground", highlight_text)
        self.root.option_add("*TCombobox*Entry*selectBackground", highlight)
        self.root.option_add("*TCombobox*Entry*selectForeground", highlight_text)
        self.root.option_add("*TCombobox*Entry*inactiveselectBackground", highlight)
        self.root.option_add("*TCombobox*Entry*inactiveselectForeground", highlight_text)
        self.root.option_add("*Entry*selectBackground", highlight)
        self.root.option_add("*Entry*selectForeground", highlight_text)
        self.root.option_add("*Entry*inactiveselectBackground", highlight)
        self.root.option_add("*Entry*inactiveselectForeground", highlight_text)
        self.root.option_add("*TEntry*selectBackground", highlight)
        self.root.option_add("*TEntry*selectForeground", highlight_text)
        self.root.option_add("*TEntry*inactiveselectBackground", highlight)
        self.root.option_add("*TEntry*inactiveselectForeground", highlight_text)
        self.style.configure(
            "Treeview",
            background=panel,
            fieldbackground=panel,
            foreground=text_color,
            bordercolor=panel_border,
            lightcolor=panel_border,
            darkcolor=panel_border,
            font=self.font_body,
        )
        self.style.configure(
            "Treeview.Heading",
            background=colors["ctrl_bg"],
            foreground=text_color,
            bordercolor=panel_border,
            lightcolor=panel_border,
            darkcolor=panel_border,
            font=self.font_body,
        )
        self.style.map("Treeview.Heading", background=[("active", accent)], foreground=[("active", "#ffffff")])
        self.style.map("Treeview", background=[("selected", highlight)], foreground=[("selected", highlight_text)])
        self.style.configure(
            self.vscroll_style,
            troughcolor=panel,
            background=scroll,
            arrowcolor=text_color,
            bordercolor=border,
            lightcolor=border,
            darkcolor=border,
        )
        self.style.configure(
            self.hscroll_style,
            troughcolor=panel,
            background=scroll,
            arrowcolor=text_color,
            bordercolor=border,
            lightcolor=border,
            darkcolor=border,
        )
        self.style.map(
            self.vscroll_style,
            background=[("disabled", scroll), ("!disabled", scroll)],
            arrowcolor=[("disabled", text_color), ("!disabled", text_color)],
            troughcolor=[("disabled", panel), ("!disabled", panel)],
            bordercolor=[("disabled", border), ("!disabled", border)],
        )
        self.style.map(
            self.hscroll_style,
            background=[("disabled", scroll), ("!disabled", scroll)],
            arrowcolor=[("disabled", text_color), ("!disabled", text_color)],
            troughcolor=[("disabled", panel), ("!disabled", panel)],
            bordercolor=[("disabled", border), ("!disabled", border)],
        )
        # Update any open child windows to reflect title bar/background changes
        for win_name in ("settings_window", "tools_window", "library_window"):
            win = getattr(self, win_name, None)
            try:
                if win and tk.Toplevel.winfo_exists(win):
                    self._set_dark_title_bar(dark, target=win)
                    win.configure(bg=base)
            except Exception:
                pass
        self.text_color = text_color
        self.muted_color = "#777777" if dark else "#666666"
        if self.note_label:
            self.note_label.configure(foreground=colors["fg"], background=base)
        self.date_label.configure(background=base, foreground=text_color)
        self.total_label.configure(background=base)
        self.days_label.configure(background=base, foreground=text_color)
        self.remaining_today_label.configure(background=base, foreground=text_color)
        if hasattr(self, "remaining_today_cbd_label"):
            self.remaining_today_cbd_label.configure(background=base, foreground=text_color)
        if hasattr(self, "day_total_label"):
            self.day_total_label.configure(background=base, foreground=text_color)
        if hasattr(self, "day_total_cbd_label"):
            self.day_total_cbd_label.configure(background=base, foreground=text_color)
        if hasattr(self, "data_path_label") and self.data_path_label.winfo_exists():
            self.data_path_label.configure(background=base, foreground=text_color)
        self.clock_label.configure(background=base, foreground=text_color)
        self.top_date_label.configure(background=base, foreground=text_color)
        # Improve caret visibility
        try:
            self.root.option_add("*insertBackground", cursor_color)
            self.root.option_add("*Entry.insertBackground", cursor_color)
            self.root.option_add("*TEntry.insertBackground", cursor_color)
            self.root.option_add("*TCombobox*Entry*insertBackground", cursor_color)
            self.root.option_add("*Text.insertBackground", cursor_color)
        except Exception:
            pass
        self._apply_caret_color(cursor_color)
        self._refresh_combobox_popdowns(entry_bg, highlight, highlight_text)
        self._refresh_settings_notebook_style(dark)

    def _iter_comboboxes(self, root_widget: tk.Misc) -> list[ttk.Combobox]:
        combos: list[ttk.Combobox] = []
        try:
            stack: list[tk.Misc] = [root_widget]
            while stack:
                widget = stack.pop()
                try:
                    stack.extend(widget.winfo_children())
                except Exception:
                    pass
                if isinstance(widget, ttk.Combobox):
                    combos.append(widget)
        except Exception:
            pass
        return combos

    def _refresh_combobox_popdowns(self, list_bg: str, select_bg: str, select_fg: str) -> None:
        """Apply combobox dropdown list colours immediately without requiring app restart."""
        roots: list[tk.Misc] = [self.root]
        for win_name in ("settings_window", "tools_window"):
            win = getattr(self, win_name, None)
            try:
                if win and tk.Toplevel.winfo_exists(win):
                    roots.append(win)
            except Exception:
                pass
        for root_widget in roots:
            for combo in self._iter_comboboxes(root_widget):
                try:
                    popdown = str(combo.tk.call("ttk::combobox::PopdownWindow", combo))
                    listbox = f"{popdown}.f.l"
                    combo.tk.call(
                        listbox,
                        "configure",
                        "-background",
                        list_bg,
                        "-selectbackground",
                        select_bg,
                        "-selectforeground",
                        select_fg,
                    )
                except Exception:
                    pass

    def _refresh_settings_notebook_style(self, dark: bool) -> None:
        win = getattr(self, "settings_window", None)
        if not (win and tk.Toplevel.winfo_exists(win)):
            return
        notebook = getattr(self, "settings_notebook", None)
        style_name = getattr(self, "settings_tab_style", None)
        if notebook is None or not style_name:
            return
        tab_style = "SettingsLocal.TNotebook.Tab"
        sep_style = "SettingsLocal.TSeparator"
        colors = compute_colors(dark)
        bg = colors["bg"]
        fg = colors["fg"]
        ctrl_bg = colors["ctrl_bg"]
        border = colors.get("border", ctrl_bg)
        selected_bg = "#222222" if dark else "#e0e0e0"
        local_style = ttk.Style(win)
        local_style.theme_use("clam")
        local_style.configure(
            style_name,
            background=bg,
            bordercolor=border,
            lightcolor=border,
            darkcolor=border,
            relief="solid",
            borderwidth=1,
        )
        local_style.configure(
            tab_style,
            background=ctrl_bg,
            foreground=fg,
            lightcolor=border,
            bordercolor=border,
            focuscolor=border,
            padding=[10, 4],
        )
        local_style.map(
            tab_style,
            background=[("selected", selected_bg), ("!selected", ctrl_bg)],
            foreground=[("selected", fg), ("!selected", fg), ("disabled", fg)],
        )
        local_style.configure(sep_style, background=border)
        try:
            notebook.configure(style=style_name)
            tabs = notebook.tabs()
            labels = [
                "Tracker settings",
                "Window settings",
                "Colour settings",
                "Theme",
                "Data settings",
            ]
            for idx, tab_id in enumerate(tabs):
                if idx < len(labels):
                    notebook.tab(tab_id, text=labels[idx])
            current = notebook.index("current")
            notebook.select(current)
        except Exception:
            pass

    def _apply_caret_color(self, color: str) -> None:
        """Force insert cursor color on text/entry-like widgets."""
        try:
            widgets = self.root.winfo_children()
            while widgets:
                w = widgets.pop()
                widgets.extend(w.winfo_children())
                if isinstance(w, (tk.Entry, tk.Text)):
                    try:
                        w.configure(insertbackground=color)
                    except Exception:
                        pass
        except Exception:
            pass
        # Reapply stock colors after theme change
        self._refresh_stock()
    def _sort_stock(self, column: str, numeric: bool) -> None:
        _stock_sort_stock(self, column, numeric)

    def _apply_stock_sort(self) -> None:
        _stock_apply_stock_sort(self)
    def _grams_used_on_day(self, day: date) -> float:
        day_str = day.isoformat()
        return sum(
            log.get("grams_used", 0.0)
            for log in self.logs
            if log.get("date") == day_str and self._log_counts_for_totals(log)
        )
    def _grams_used_on_day_cbd(self, day: date) -> float:
        day_str = day.isoformat()
        return sum(
            log.get("grams_used", 0.0)
            for log in self.logs
            if log.get("date") == day_str and self._log_counts_for_cbd(log)
        )
    def _average_daily_usage(self) -> float | None:
        if not self.logs:
            return None
        cutoff = None
        try:
            days = int(self.avg_usage_days)
        except Exception:
            days = 0
        if days > 0:
            cutoff = date.today() - timedelta(days=days - 1)
        usage_by_day: dict[str, float] = {}
        for log in self.logs:
            if not self._log_counts_for_totals(log):
                continue
            day = log.get("date")
            if cutoff is not None:
                try:
                    log_date = datetime.fromisoformat(day).date()
                except Exception:
                    continue
                if log_date < cutoff:
                    continue
            usage_by_day[day] = usage_by_day.get(day, 0.0) + float(log.get("grams_used", 0.0))
        if not usage_by_day:
            return None
        return sum(usage_by_day.values()) / len(usage_by_day)
    def _average_daily_usage_cbd(self) -> float | None:
        if not self.logs:
            return None
        cutoff = None
        try:
            days = int(self.avg_usage_days)
        except Exception:
            days = 0
        if days > 0:
            cutoff = date.today() - timedelta(days=days - 1)
        usage_by_day: dict[str, float] = {}
        for log in self.logs:
            if not self._log_counts_for_cbd(log):
                continue
            day = log.get("date")
            if cutoff is not None:
                try:
                    log_date = datetime.fromisoformat(day).date()
                except Exception:
                    continue
                if log_date < cutoff:
                    continue
            usage_by_day[day] = usage_by_day.get(day, 0.0) + float(log.get("grams_used", 0.0))
        if not usage_by_day:
            return None
        return sum(usage_by_day.values()) / len(usage_by_day)
    def _update_clock(self) -> None:
        now = datetime.now()
        self.clock_label.config(text=now.strftime("%H:%M"))
        self.top_date_label.config(text=now.strftime("%a %b %d").upper())
        today = date.today()
        if today != self._last_seen_date:
            self._last_seen_date = today
            self.current_date = today
            # Recompute today-based metrics and refresh the displayed day
            self._refresh_stock()
            self._refresh_log()
        self._maybe_reload_external()
        self.root.after(1000, self._update_clock)
    def _compute_stats(self, logs_subset: list[dict[str, float]]) -> dict[str, str]:
        times = []
        doses = []
        for log in logs_subset:
            try:
                times.append(datetime.strptime(log["time"], "%Y-%m-%d %H:%M"))
            except Exception:
                continue
            doses.append(float(log.get("grams_used", 0.0)))
        stats = {
            "first_time": "N/A",
            "last_time": "N/A",
            "avg_interval": "N/A",
            "max_interval": "N/A",
            "max_dose": "N/A",
            "min_dose": "N/A",
            "avg_dose": "N/A",
        }
        if times:
            times_sorted = sorted(times)
            stats["first_time"] = times_sorted[0].strftime("%H:%M")
            stats["last_time"] = times_sorted[-1].strftime("%H:%M")
            if len(times_sorted) > 1:
                intervals = [
                    (t2 - t1).total_seconds() for t1, t2 in zip(times_sorted[:-1], times_sorted[1:])
                ]
                non_zero_intervals = [sec for sec in intervals if sec > 0]
                if non_zero_intervals:
                    stats["avg_interval"] = self._format_interval(sum(non_zero_intervals) / len(non_zero_intervals))
                stats["max_interval"] = self._format_interval(max(intervals))
        if doses:
            stats["max_dose"] = f"{max(doses):.3f} g"
            stats["min_dose"] = f"{min(doses):.3f} g"
            stats["avg_dose"] = f"{(sum(doses)/len(doses)):.3f} g"
        return stats
    @staticmethod
    def _format_interval(seconds: float) -> str:
        seconds = int(seconds)
        minutes, sec = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h {minutes}m"
        if minutes:
            return f"{minutes}m {sec}s"
        return f"{sec}s"
    def _render_stats_rows(self, rows: list[tuple[str, str]]) -> None:
        try:
            self.stats_frame.columnconfigure(0, weight=1)
            self.stats_frame.columnconfigure(1, weight=1)
        except Exception:
            pass
        for idx, (label, value) in enumerate(rows):
            ttk.Label(self.stats_frame, text=label, font=self.font_body, anchor="w").grid(
                row=idx, column=0, sticky="w", padx=(8, 12), pady=(0, 2)
            )
            ttk.Label(self.stats_frame, text=value, font=self.font_body, anchor="e").grid(
                row=idx, column=1, sticky="e", padx=(0, 12), pady=(0, 2)
            )
    def _logs_for_period(self, period: str) -> tuple[list[dict[str, float]], str, int]:
        end_date = self.current_date
        if period == "day":
            start_date = end_date
            label = f"Day ({end_date.isoformat()})"
        elif period == "week":
            start_date = end_date - timedelta(days=6)
            label = f"Week (last 7 days)"
        elif period == "month":
            start_date = end_date - timedelta(days=29)
            label = f"Month (last 30 days)"
        elif period == "year":
            start_date = end_date - timedelta(days=364)
            label = f"Year (last 365 days)"
        else:
            start_date = end_date
            label = f"Day ({end_date.isoformat()})"
        logs_subset = []
        for log in self.logs:
            try:
                log_date = datetime.fromisoformat(log["date"]).date()
            except Exception:
                continue
            if start_date <= log_date <= end_date:
                logs_subset.append(log)
        days_count = (end_date - start_date).days + 1
        return logs_subset, label, max(days_count, 1)
    def _stats_text(
        self,
        logs_subset: list[dict[str, float]],
        label: str,
        days_count: int,
        return_title: bool = False,
    ) -> str | tuple[str, list[tuple[str, str]]]:
        stats = self._compute_stats(logs_subset)
        thc_total = sum(
            float(log.get("grams_used", 0.0))
            for log in logs_subset
            if not self._log_counts_for_cbd(log)
        )
        avg_daily = thc_total / max(days_count, 1)
        rows = [
            ("Average interval", stats["avg_interval"]),
            ("Longest interval", stats["max_interval"]),
            ("Average dose", stats["avg_dose"]),
            ("Largest dose", stats["max_dose"]),
            ("Smallest dose", stats["min_dose"]),
            ("Average daily THC usage", f"{avg_daily:.3f} g"),
            ("Total THC usage", f"{thc_total:.3f} g"),
        ]
        if getattr(self, "track_cbd_flower", False):
            cbd_total = sum(
                float(log.get("grams_used", 0.0))
                for log in logs_subset
                if self._log_counts_for_cbd(log)
            )
            cbd_avg_daily = cbd_total / max(days_count, 1)
            rows.extend(
                [
                    ("Average daily CBD usage", f"{cbd_avg_daily:.3f} g"),
                    ("Total CBD usage", f"{cbd_total:.3f} g"),
                ]
            )
        body = "\n".join(f"{k}: {v}" for k, v in rows)
        if return_title:
            return label, rows
        return body
    def _copy_stats_to_clipboard(self, period: str) -> None:
        try:
            logs_for_period, label, days_count = self._logs_for_period(period)
            title, stats_list = self._stats_text(logs_for_period, label, days_count, return_title=True)
            lines = [title, ""]
            lines.extend(f"{label}: {value}" for label, value in stats_list)
            text = "\n".join(lines)
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update_idletasks()
            messagebox.showinfo("Copy stats", "Copied stats to clipboard.")
        except Exception as exc:
            messagebox.showerror("Copy stats", f"Could not copy stats:\n{exc}")
    def save_data(self) -> None:
        data = {
            "flowers": [
                {
                    "name": f.name,
                    "thc_pct": f.thc_pct,
                    "cbd_pct": f.cbd_pct,
                    "grams_remaining": f.grams_remaining,
                }
                for f in self.flowers.values()
            ],
            "logs": self.logs,
            "dark_mode": self.dark_var.get(),
            "total_green_threshold": self.total_green_threshold,
            "total_red_threshold": self.total_red_threshold,
            "cbd_total_green_threshold": getattr(self, "cbd_total_green_threshold", self.total_green_threshold),
            "cbd_total_red_threshold": getattr(self, "cbd_total_red_threshold", self.total_red_threshold),
            "single_green_threshold": self.single_green_threshold,
            "single_red_threshold": self.single_red_threshold,
            "cbd_single_green_threshold": getattr(self, "cbd_single_green_threshold", self.single_green_threshold),
            "cbd_single_red_threshold": getattr(self, "cbd_single_red_threshold", self.single_red_threshold),
            "total_thc_high_color": self.total_thc_high_color,
            "total_thc_low_color": self.total_thc_low_color,
            "total_cbd_high_color": self.total_cbd_high_color,
            "total_cbd_low_color": self.total_cbd_low_color,
            "single_thc_high_color": self.single_thc_high_color,
            "single_thc_low_color": self.single_thc_low_color,
            "single_cbd_high_color": self.single_cbd_high_color,
            "single_cbd_low_color": self.single_cbd_low_color,
            "remaining_thc_high_color": self.remaining_thc_high_color,
            "remaining_thc_low_color": self.remaining_thc_low_color,
            "remaining_cbd_high_color": self.remaining_cbd_high_color,
            "remaining_cbd_low_color": self.remaining_cbd_low_color,
            "days_thc_high_color": self.days_thc_high_color,
            "days_thc_low_color": self.days_thc_low_color,
            "days_cbd_high_color": self.days_cbd_high_color,
            "days_cbd_low_color": self.days_cbd_low_color,
            "target_daily_grams": self.target_daily_grams,
            "avg_usage_days": self.avg_usage_days,
            "target_daily_cbd_grams": getattr(self, "target_daily_cbd_grams", 0.0),
            "track_cbd_flower": getattr(self, "track_cbd_flower", False),
            "enable_stock_coloring": self.enable_stock_coloring,
            "enable_usage_coloring": self.enable_usage_coloring,
        }
        if self.network_mode == MODE_CLIENT:
            ok = self._push_network_tracker_data(data)
            if not ok:
                if not self._network_error_shown:
                    self._network_error_shown = True
                    messagebox.showerror(
                        "Network save failed",
                        f"Could not save tracker data to host {self.network_host}:{self.network_port}.",
                    )
            else:
                self._update_data_mtime(reset=True)
            self._save_config()
            return
        save_tracker_data(data, path=Path(self.data_path), logger=lambda m: print(m))
        self._update_data_mtime()
        self._save_config()
    def load_data(self) -> None:
        if self.network_mode == MODE_CLIENT:
            data = self._fetch_network_tracker_data()
            if not data:
                self.flowers = {}
                self.logs = []
                self._update_data_mtime(reset=True)
                if not self._network_error_shown:
                    self._network_error_shown = True
                    messagebox.showwarning(
                        "Network data unavailable",
                        f"Could not load tracker data from host {self.network_host}:{self.network_port}.",
                    )
                return
        else:
            data = load_tracker_data(path=Path(self.data_path), logger=lambda m: print(m))
        if not data:
            messagebox.showwarning("No data", f"No tracker data found at {self.data_path}")
            self._update_data_mtime(reset=True)
            return
        if self.network_mode != MODE_CLIENT:
            loaded = load_tracker_data(path=Path(self.data_path), logger=lambda m: print(m))
            if loaded:
                data = loaded
        self._apply_loaded_tracker_data(data)

    def _apply_loaded_tracker_data(self, data: dict, remote_mtime: float | None = None) -> None:
        self.flowers = {}
        for item in data.get("flowers", []):
            self.flowers[item["name"]] = Flower(
                name=item["name"],
                thc_pct=float(item.get("thc_pct", 0.0)),
                cbd_pct=float(item.get("cbd_pct", 0.0)),
                grams_remaining=float(item.get("grams_remaining", 0.0)),
            )
        self.logs = data.get("logs", [])
        self.dark_var.set(bool(data.get("dark_mode", True)))
        self.total_green_threshold = float(data.get("total_green_threshold", self.total_green_threshold))
        self.total_red_threshold = float(data.get("total_red_threshold", self.total_red_threshold))
        self.cbd_total_green_threshold = float(data.get("cbd_total_green_threshold", getattr(self, "cbd_total_green_threshold", self.total_green_threshold)))
        self.cbd_total_red_threshold = float(data.get("cbd_total_red_threshold", getattr(self, "cbd_total_red_threshold", self.total_red_threshold)))
        self.single_green_threshold = float(data.get("single_green_threshold", self.single_green_threshold))
        self.single_red_threshold = float(data.get("single_red_threshold", self.single_red_threshold))
        self.cbd_single_green_threshold = float(
            data.get("cbd_single_green_threshold", getattr(self, "cbd_single_green_threshold", self.single_green_threshold))
        )
        self.cbd_single_red_threshold = float(
            data.get("cbd_single_red_threshold", getattr(self, "cbd_single_red_threshold", self.single_red_threshold))
        )
        self.total_thc_high_color = str(data.get("total_thc_high_color", self.total_thc_high_color))
        self.total_thc_low_color = str(data.get("total_thc_low_color", self.total_thc_low_color))
        self.total_cbd_high_color = str(data.get("total_cbd_high_color", self.total_cbd_high_color))
        self.total_cbd_low_color = str(data.get("total_cbd_low_color", self.total_cbd_low_color))
        self.single_thc_high_color = str(data.get("single_thc_high_color", self.single_thc_high_color))
        self.single_thc_low_color = str(data.get("single_thc_low_color", self.single_thc_low_color))
        self.single_cbd_high_color = str(data.get("single_cbd_high_color", self.single_cbd_high_color))
        self.single_cbd_low_color = str(data.get("single_cbd_low_color", self.single_cbd_low_color))
        self.target_daily_grams = float(data.get("target_daily_grams", self.target_daily_grams))
        self.avg_usage_days = int(data.get("avg_usage_days", getattr(self, "avg_usage_days", 30)))
        self.target_daily_cbd_grams = float(data.get("target_daily_cbd_grams", getattr(self, "target_daily_cbd_grams", 0.0)))
        self.remaining_thc_high_color = str(data.get("remaining_thc_high_color", self.remaining_thc_high_color))
        self.remaining_thc_low_color = str(data.get("remaining_thc_low_color", self.remaining_thc_low_color))
        self.remaining_cbd_high_color = str(data.get("remaining_cbd_high_color", self.remaining_cbd_high_color))
        self.remaining_cbd_low_color = str(data.get("remaining_cbd_low_color", self.remaining_cbd_low_color))
        self.days_thc_high_color = str(data.get("days_thc_high_color", self.days_thc_high_color))
        self.days_thc_low_color = str(data.get("days_thc_low_color", self.days_thc_low_color))
        self.days_cbd_high_color = str(data.get("days_cbd_high_color", self.days_cbd_high_color))
        self.days_cbd_low_color = str(data.get("days_cbd_low_color", self.days_cbd_low_color))
        # Prefer config-driven CBD tracking; tracker data should not override it on startup.
        self.track_cbd_flower = bool(getattr(self, "track_cbd_flower", False))
        self.enable_stock_coloring = bool(data.get("enable_stock_coloring", self.enable_stock_coloring))
        self.enable_usage_coloring = bool(data.get("enable_usage_coloring", self.enable_usage_coloring))
        self.library_data_path = data.get("library_data_path", self.library_data_path) or self.library_data_path
        # Backfill time_display/roa/efficiency for legacy logs
        for log in self.logs:
            if "time_display" not in log and "time" in log:
                try:
                    log["time_display"] = log["time"].split(" ")[-1]
                except Exception:
                    log["time_display"] = log.get("time", "")
            if "roa" not in log:
                log["roa"] = "Unknown"
            if "efficiency" not in log:
                log["efficiency"] = 1.0
            if "is_cbd_dominant" not in log:
                flower = self.flowers.get(log.get("flower"))
                if flower:
                    log["is_cbd_dominant"] = self._is_cbd_dominant(flower)
                else:
                    try:
                        log["is_cbd_dominant"] = float(log.get("cbd_mg", 0.0)) >= float(log.get("thc_mg", 0.0))
                    except Exception:
                        log["is_cbd_dominant"] = False
        # Default to last logged day if available
        if self.logs:
            last_date = self.logs[-1].get("date")
            try:
                self.current_date = datetime.fromisoformat(last_date).date()
            except Exception:
                self.current_date = date.today()
        else:
            self.current_date = date.today()
        self._last_seen_date = self.current_date
        if self.network_mode == MODE_CLIENT:
            if remote_mtime is not None:
                self._network_tracker_mtime = float(remote_mtime or 0.0)
            else:
                meta = fetch_tracker_meta(
                    self.network_host,
                    int(self.network_port),
                    timeout=0.9,
                    access_key=str(getattr(self, "network_access_key", "") or ""),
                )
                if isinstance(meta, dict):
                    try:
                        self._network_tracker_mtime = float(meta.get("mtime") or 0.0)
                    except Exception:
                        self._network_tracker_mtime = 0.0
        self._update_data_mtime()
    def choose_data_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Load tracker data",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=os.path.dirname(self.data_path) or ".",
        )
        if not path:
            return
        if not os.path.exists(path):
            messagebox.showerror("Not found", "Selected file does not exist.")
            return
        self.data_path = path
        self.load_data()
        self.save_data()  # persist any defaults added
        self._save_config()
        self._refresh_stock()
        self._refresh_log()
        self._update_data_path_label()
    def export_data_file(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export tracker data",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=os.path.dirname(self.data_path) or ".",
        )
        if not path:
            return
        self.data_path = path
        self.save_data()
        self._save_config()
        self._update_data_path_label()
    def _load_config(self) -> None:
        cfg = load_tracker_config(Path(TRACKER_CONFIG_FILE))
        self.data_path = cfg.get("data_path", str(TRACKER_DATA_FILE)) or str(TRACKER_DATA_FILE)
        self.library_data_path = cfg.get("library_data_path", str(TRACKER_LIBRARY_FILE)) or str(TRACKER_LIBRARY_FILE)
        self.dark_var.set(bool(cfg.get("dark_mode", True)))
        track_cbd_raw = cfg.get("track_cbd_flower", cfg.get("track_cbd_usage", False))
        if isinstance(track_cbd_raw, bool):
            self.track_cbd_flower = track_cbd_raw
        else:
            self.track_cbd_flower = str(track_cbd_raw).strip().lower() in ("1", "true", "yes", "on")
        self.enable_stock_coloring = bool(cfg.get("enable_stock_coloring", True))
        self.enable_usage_coloring = bool(cfg.get("enable_usage_coloring", True))
        self.hide_roa_options = bool(cfg.get("hide_roa_options", False))
        self.hide_mixed_dose = bool(cfg.get("hide_mixed_dose", False))
        self.hide_mix_stock = bool(cfg.get("hide_mix_stock", False))
        self.show_stock_form = bool(cfg.get("show_stock_form", True))
        self.minimize_to_tray = bool(cfg.get("minimize_to_tray", self.minimize_to_tray))
        self.close_to_tray = bool(cfg.get("close_to_tray", self.close_to_tray))
        self.show_scraper_status_icon = bool(cfg.get("show_scraper_status_icon", self.show_scraper_status_icon))
        self.scraper_status_running_color = str(cfg.get("scraper_status_running_color", self.scraper_status_running_color))
        self.scraper_status_stopped_color = str(cfg.get("scraper_status_stopped_color", self.scraper_status_stopped_color))
        self.scraper_status_error_color = str(cfg.get("scraper_status_error_color", self.scraper_status_error_color))
        self.show_scraper_buttons = bool(cfg.get("show_scraper_buttons", self.show_scraper_buttons))
        self.network_host = str(cfg.get("network_host", self.network_host)).strip() or "127.0.0.1"
        self.network_bind_host = str(cfg.get("network_bind_host", self.network_bind_host)).strip() or "0.0.0.0"
        self.network_access_key = str(cfg.get("network_access_key", self.network_access_key)).strip()
        try:
            self.network_rate_limit_requests_per_minute = max(
                0,
                int(cfg.get("network_rate_limit_requests_per_minute", self.network_rate_limit_requests_per_minute)),
            )
        except Exception:
            self.network_rate_limit_requests_per_minute = 0
        try:
            self.network_port = max(1, min(65535, int(cfg.get("network_port", self.network_port))))
        except Exception:
            self.network_port = DEFAULT_NETWORK_PORT
        try:
            self.export_port = max(1, min(65535, int(cfg.get("network_export_port", self.export_port))))
        except Exception:
            self.export_port = DEFAULT_EXPORT_PORT
        try:
            cap_cfg = _load_capture_config()
            self.scraper_notify_windows = bool(cap_cfg.get("notify_windows", self.scraper_notify_windows))
            self.scraper_notifications_muted = bool(cap_cfg.get("notifications_muted", False))
            snap = cap_cfg.get("notification_restore_snapshot", {})
            self._scraper_notify_restore = snap if isinstance(snap, dict) else None
        except Exception:
            pass
        self.total_green_threshold = float(cfg.get("total_green_threshold", self.total_green_threshold))
        self.total_red_threshold = float(cfg.get("total_red_threshold", self.total_red_threshold))
        self.single_green_threshold = float(cfg.get("single_green_threshold", self.single_green_threshold))
        self.single_red_threshold = float(cfg.get("single_red_threshold", self.single_red_threshold))
        self.cbd_total_green_threshold = float(cfg.get("cbd_total_green_threshold", self.total_green_threshold))
        self.cbd_total_red_threshold = float(cfg.get("cbd_total_red_threshold", self.total_red_threshold))
        self.cbd_single_green_threshold = float(cfg.get("cbd_single_green_threshold", self.single_green_threshold))
        self.cbd_single_red_threshold = float(cfg.get("cbd_single_red_threshold", self.single_red_threshold))
        self.accent_green = str(cfg.get("accent_green", self.accent_green))
        self.accent_red = str(cfg.get("accent_red", self.accent_red))
        self.total_thc_high_color = str(cfg.get("total_thc_high_color", self.total_thc_high_color))
        self.total_thc_low_color = str(cfg.get("total_thc_low_color", self.total_thc_low_color))
        self.total_cbd_high_color = str(cfg.get("total_cbd_high_color", self.total_cbd_high_color))
        self.total_cbd_low_color = str(cfg.get("total_cbd_low_color", self.total_cbd_low_color))
        self.single_thc_high_color = str(cfg.get("single_thc_high_color", self.single_thc_high_color))
        self.single_thc_low_color = str(cfg.get("single_thc_low_color", self.single_thc_low_color))
        self.single_cbd_high_color = str(cfg.get("single_cbd_high_color", self.single_cbd_high_color))
        self.single_cbd_low_color = str(cfg.get("single_cbd_low_color", self.single_cbd_low_color))
        self.remaining_thc_high_color = str(cfg.get("remaining_thc_high_color", self.remaining_thc_high_color))
        self.remaining_thc_low_color = str(cfg.get("remaining_thc_low_color", self.remaining_thc_low_color))
        self.remaining_cbd_high_color = str(cfg.get("remaining_cbd_high_color", self.remaining_cbd_high_color))
        self.remaining_cbd_low_color = str(cfg.get("remaining_cbd_low_color", self.remaining_cbd_low_color))
        self.days_thc_high_color = str(cfg.get("days_thc_high_color", self.days_thc_high_color))
        self.days_thc_low_color = str(cfg.get("days_thc_low_color", self.days_thc_low_color))
        self.days_cbd_high_color = str(cfg.get("days_cbd_high_color", self.days_cbd_high_color))
        self.days_cbd_low_color = str(cfg.get("days_cbd_low_color", self.days_cbd_low_color))
        self.used_thc_under_color = str(cfg.get("used_thc_under_color", self.used_thc_under_color))
        self.used_thc_over_color = str(cfg.get("used_thc_over_color", self.used_thc_over_color))
        self.used_cbd_under_color = str(cfg.get("used_cbd_under_color", self.used_cbd_under_color))
        self.used_cbd_over_color = str(cfg.get("used_cbd_over_color", self.used_cbd_over_color))
        if isinstance(cfg.get("theme_palette_dark"), dict):
            self.theme_palette_dark.update(cfg.get("theme_palette_dark", {}))
        if isinstance(cfg.get("theme_palette_light"), dict):
            self.theme_palette_light.update(cfg.get("theme_palette_light", {}))
        set_palette_overrides(self.theme_palette_dark, self.theme_palette_light)
        self.target_daily_grams = float(cfg.get("target_daily_grams", self.target_daily_grams))
        self.avg_usage_days = int(cfg.get("avg_usage_days", getattr(self, "avg_usage_days", 30)))
        self.target_daily_cbd_grams = float(cfg.get("target_daily_cbd_grams", 0.0))
        if isinstance(cfg.get("roa_options"), dict):
            try:
                self.roa_options = {k: float(v) for k, v in cfg["roa_options"].items()}
            except Exception:
                pass
        # note_label removed; tooltip now handles THC/CBD estimate messaging
        self.window_geometry = cfg.get("window_geometry", "") or self.window_geometry
        self.settings_window_geometry = cfg.get("settings_window_geometry", "") or self.settings_window_geometry
        self.screen_resolution = str(cfg.get("screen_resolution", self.screen_resolution or "")).strip()
        try:
            self.main_split_ratio = float(cfg.get("main_split_ratio", self.main_split_ratio))
            if not (0.15 <= self.main_split_ratio <= 0.85):
                self.main_split_ratio = 0.48
        except Exception:
            self.main_split_ratio = 0.48
        self._apply_resolution_safety()
        if self._force_center_on_start:
            try:
                self._save_config()
            except Exception:
                pass
        if isinstance(cfg.get("stock_column_widths"), dict):
            self.stock_column_widths = {k: int(v) for k, v in cfg["stock_column_widths"].items()}
        if isinstance(cfg.get("log_column_widths"), dict):
            self.log_column_widths = {k: int(v) for k, v in cfg["log_column_widths"].items()}
        if self.window_geometry:
            try:
                self.root.geometry(self.window_geometry)
            except Exception:
                pass
        if hasattr(self, "stock_tree") and self.stock_column_widths:
            for col, width in self.stock_column_widths.items():
                if col in self.stock_tree["columns"]:
                    self.stock_tree.column(col, width=width)
        if hasattr(self, "log_tree") and self.log_column_widths:
            for col, width in self.log_column_widths.items():
                if col in self.log_tree["columns"]:
                    self.log_tree.column(col, width=width)
        self._apply_scraper_controls_visibility()
        self._apply_roa_visibility()
        self._apply_stock_form_visibility()
        try:
            self.root.after_idle(self._apply_split_ratio)
            self.root.after(240, self._apply_split_ratio)
        except Exception:
            pass
    def _save_config(self) -> None:
        self.screen_resolution = self._current_screen_resolution()
        cfg = {
            "data_path": self.data_path or str(TRACKER_DATA_FILE),
            "library_data_path": self.library_data_path or str(TRACKER_LIBRARY_FILE),
            "enable_stock_coloring": self.enable_stock_coloring,
            "enable_usage_coloring": self.enable_usage_coloring,
            "track_cbd_flower": getattr(self, "track_cbd_flower", False),
            "total_green_threshold": self.total_green_threshold,
            "total_red_threshold": self.total_red_threshold,
            "single_green_threshold": self.single_green_threshold,
            "single_red_threshold": self.single_red_threshold,
            "cbd_total_green_threshold": self.cbd_total_green_threshold,
            "cbd_total_red_threshold": self.cbd_total_red_threshold,
            "cbd_single_green_threshold": self.cbd_single_green_threshold,
            "cbd_single_red_threshold": self.cbd_single_red_threshold,
            "accent_green": self.accent_green,
            "accent_red": self.accent_red,
            "total_thc_high_color": self.total_thc_high_color,
            "total_thc_low_color": self.total_thc_low_color,
            "total_cbd_high_color": self.total_cbd_high_color,
            "total_cbd_low_color": self.total_cbd_low_color,
            "single_thc_high_color": self.single_thc_high_color,
            "single_thc_low_color": self.single_thc_low_color,
            "single_cbd_high_color": self.single_cbd_high_color,
            "single_cbd_low_color": self.single_cbd_low_color,
            "remaining_thc_high_color": self.remaining_thc_high_color,
            "remaining_thc_low_color": self.remaining_thc_low_color,
            "remaining_cbd_high_color": self.remaining_cbd_high_color,
            "remaining_cbd_low_color": self.remaining_cbd_low_color,
            "days_thc_high_color": self.days_thc_high_color,
            "days_thc_low_color": self.days_thc_low_color,
            "days_cbd_high_color": self.days_cbd_high_color,
            "days_cbd_low_color": self.days_cbd_low_color,
            "used_thc_under_color": self.used_thc_under_color,
            "used_thc_over_color": self.used_thc_over_color,
            "used_cbd_under_color": self.used_cbd_under_color,
            "used_cbd_over_color": self.used_cbd_over_color,
            "theme_palette_dark": self.theme_palette_dark,
            "theme_palette_light": self.theme_palette_light,
            "target_daily_grams": self.target_daily_grams,
            "avg_usage_days": self.avg_usage_days,
            "target_daily_cbd_grams": self.target_daily_cbd_grams,
            "dark_mode": self.dark_var.get(),
            "roa_options": self.roa_options,
            "hide_roa_options": self.hide_roa_options,
            "hide_mixed_dose": getattr(self, "hide_mixed_dose", False),
            "hide_mix_stock": getattr(self, "hide_mix_stock", False),
            "show_stock_form": getattr(self, "show_stock_form", True),
            "window_geometry": self.window_geometry,
            "settings_window_geometry": self.settings_window_geometry,
            "screen_resolution": self.screen_resolution,
            "stock_column_widths": self.stock_column_widths,
            "log_column_widths": self.log_column_widths,
            "main_split_ratio": getattr(self, "main_split_ratio", 0.48),
            "minimize_to_tray": self.minimize_to_tray,
            "close_to_tray": self.close_to_tray,
            "show_scraper_status_icon": self.show_scraper_status_icon,
            "scraper_status_running_color": self.scraper_status_running_color,
            "scraper_status_stopped_color": self.scraper_status_stopped_color,
            "scraper_status_error_color": self.scraper_status_error_color,
            "show_scraper_buttons": self.show_scraper_buttons,
            "network_host": self.network_host,
            "network_bind_host": self.network_bind_host,
            "network_access_key": self.network_access_key,
            "network_rate_limit_requests_per_minute": int(
                max(0, int(getattr(self, "network_rate_limit_requests_per_minute", 0) or 0))
            ),
            "network_port": int(self.network_port),
            "network_export_port": int(self.export_port),
        }
        save_tracker_config(Path(TRACKER_CONFIG_FILE), cfg)
    def _settings_choose_data(self) -> None:
        self.choose_data_file()
    def _settings_export_data(self) -> None:
        self.export_data_file()
    def _settings_choose_library(self) -> None:
        path = filedialog.askopenfilename(
            title="Load library data",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=os.path.dirname(self.library_data_path) or ".",
        )
        if not path:
            return
        if not os.path.exists(path):
            messagebox.showerror("Not found", "Selected library file does not exist.")
            return
        self.library_data_path = path
        self._save_config()
        self._update_library_path_label()
    def _settings_export_library(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export library data",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=os.path.dirname(self.library_data_path) or ".",
        )
        if not path:
            return
        try:
            # Copy from current library data if it exists; otherwise write empty structure
            if os.path.exists(self.library_data_path):
                shutil.copy2(self.library_data_path, path)
            else:
                Path(path).write_text(json.dumps({"entries": []}, indent=2), encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("Export failed", f"Could not export library data:\n{exc}")
            return
        self.library_data_path = path
        self._save_config()
        self._update_library_path_label()
    def _settings_export_backup(self) -> None:
        backups_dir = Path(APP_DIR) / "backups"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        default_name = f"flowertrack-backup-{stamp}.zip"
        zip_path = filedialog.asksaveasfilename(
            title="Export FlowerTrack backup",
            defaultextension=".zip",
            initialdir=str(backups_dir) if backups_dir.exists() else ".",
            initialfile=default_name,
            filetypes=[("Zip files", "*.zip"), ("All files", "*.*")],
        )
        if not zip_path:
            return
        zip_path = Path(zip_path)
        try:
            zip_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            messagebox.showerror("Backup failed", f"Could not create backup folder:\n{exc}")
            return
        try:
            count = self._write_backup_zip(zip_path)
        except Exception as exc:
            messagebox.showerror("Backup failed", f"Could not create backup:\n{exc}")
            return
        try:
            json_count, json_backup_dir = self._snapshot_data_json_backups(stamp)
        except Exception:
            json_count, json_backup_dir = 0, None
        details = [f"Saved {count} files to:\n{zip_path}"]
        if json_backup_dir:
            details.append(
                f"\nJSON snapshots saved: {json_count}\n{json_backup_dir}"
            )
        messagebox.showinfo("Backup created", "".join(details))
    def _settings_import_backup(self) -> None:
        backups_dir = Path(APP_DIR) / "backups"
        path = filedialog.askopenfilename(
            title="Import FlowerTrack backup",
            filetypes=[("Zip files", "*.zip"), ("All files", "*.*")],
            initialdir=str(backups_dir) if backups_dir.exists() else ".",
        )
        if not path:
            return
        if not os.path.exists(path):
            messagebox.showerror("Not found", "Selected backup file does not exist.")
            return
        summary = self._backup_import_summary(Path(path))
        if summary:
            if not messagebox.askokcancel("Import summary", summary):
                return
        if not messagebox.askyesno(
            "Import backup",
            "Importing will overwrite existing settings and data.\n\nContinue?",
        ):
            return
        confirmation = simpledialog.askstring(
            "Type CONFIRM",
            "Type CONFIRM to overwrite existing data:",
        )
        if confirmation != "CONFIRM":
            messagebox.showinfo("Import cancelled", "Backup import cancelled.")
            return
        try:
            self._restore_backup_zip(Path(path))
        except Exception as exc:
            messagebox.showerror("Import failed", f"Could not import backup:\n{exc}")
            return
        self._reload_after_backup()
        messagebox.showinfo("Import complete", "Backup imported successfully.")

    def _backup_import_summary(self, zip_path: Path) -> str:
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
        except Exception as exc:
            return f"Could not read backup:\n{exc}"
        external_hits = [name for name in names if name.startswith("external/")]
        if external_hits:
            preview = "\n".join(f"  - {name}" for name in external_hits[:5])
            more = "" if len(external_hits) <= 5 else f"\n  ...and {len(external_hits) - 5} more"
            return (
                "Warning: Backup contains files stored outside the default AppData paths.\n"
                "These will be imported into your AppData data/logs paths if present.\n\n"
                "External files detected:\n"
                f"{preview}{more}\n\nContinue?"
            )
        def _has(prefix: str, suffix: str | None = None) -> bool:
            for name in names:
                if not name.startswith(prefix):
                    continue
                if suffix is None or name.endswith(suffix):
                    return True
            return False
        lines = ["This backup will overwrite the following:"]
        if _has("data/"):
            lines.append("- Tracker data (data/)")
        if _has("logs/"):
            lines.append("- Logs (logs/)")
        if _has("dumps/"):
            lines.append("- Dumps (dumps/)")
        if _has("Exports/") or _has("exports/"):
            lines.append("- Flower Browser exports (Exports/)")
        if any(name.endswith(Path(TRACKER_CONFIG_FILE).name) for name in names):
            lines.append("- Tracker config (flowertrack_config.json)")
        if len(lines) == 1:
            lines.append("- (No recognized data files found)")
        return "\n".join(lines)
    def _reload_after_backup(self) -> None:
        self._load_config()
        try:
            cfg = load_tracker_config(Path(TRACKER_CONFIG_FILE))
            if isinstance(cfg, dict) and "dark_mode" in cfg:
                self.dark_var.set(bool(cfg.get("dark_mode", True)))
        except Exception:
            pass
        try:
            if not self.data_path or not os.path.exists(self.data_path):
                self.data_path = str(TRACKER_DATA_FILE)
            if not self.library_data_path or not os.path.exists(self.library_data_path):
                self.library_data_path = str(TRACKER_LIBRARY_FILE)
        except Exception:
            pass
        try:
            self.load_data()
        except Exception:
            pass
        try:
            self.apply_theme(self.dark_var.get())
        except Exception:
            pass
        try:
            self._apply_scraper_controls_visibility()
            self._apply_roa_visibility()
        except Exception:
            pass
        try:
            self._refresh_stock()
            self._refresh_log()
        except Exception:
            pass
        self._update_data_path_label()
        self._update_library_path_label()
    def _write_backup_zip(self, zip_path: Path) -> int:
        app_dir = Path(APP_DIR)
        data_dir = app_dir / "data"
        logs_dir = app_dir / "logs"
        dumps_dir = app_dir / "dumps"
        exports_dir = Path(EXPORTS_DIR_DEFAULT)
        backups_dir = app_dir / "backups"
        config_path = Path(TRACKER_CONFIG_FILE)
        paths: set[Path] = set()

        def _is_auth_token_file(path: Path) -> bool:
            try:
                name = path.name.lower()
            except Exception:
                return False
            if name in {"api_auth.json", "api_auth.json.bak", "api_auth.json.tmp"}:
                return True
            return False

        def _collect_tree(root: Path) -> None:
            if not root.exists():
                return
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if backups_dir in path.parents:
                    continue
                if _is_auth_token_file(path):
                    continue
                paths.add(path)

        _collect_tree(data_dir)
        _collect_tree(logs_dir)
        _collect_tree(dumps_dir)
        _collect_tree(exports_dir)
        if config_path.exists():
            paths.add(config_path)
        # Include current tracker/library files if they live outside the app data dir.
        for extra in (Path(self.data_path), Path(self.library_data_path)):
            try:
                if extra.exists() and app_dir not in extra.parents and not _is_auth_token_file(extra):
                    paths.add(extra)
            except Exception:
                pass

        def _backup_arcname(path: Path) -> str:
            if path == config_path:
                return config_path.name
            try:
                if app_dir in path.parents:
                    return path.relative_to(app_dir).as_posix()
            except Exception:
                pass
            return (Path("external") / path.name).as_posix()

        def _sanitized_config_bytes() -> bytes:
            try:
                raw = _read_json_file(config_path)
                if not isinstance(raw, dict):
                    raise ValueError("invalid config")
                scraper = raw.get("scraper")
                if isinstance(scraper, dict):
                    # Keep credentials/settings, but strip token fields from backup.
                    for key in ("ha_token", "api_token", "access_token", "refresh_token", "auth_token", "authorization"):
                        if key in scraper:
                            scraper[key] = ""
                return json.dumps(raw, ensure_ascii=False, indent=2).encode("utf-8")
            except Exception:
                try:
                    return config_path.read_bytes()
                except Exception:
                    return b"{}"

        def _read_json_file(path: Path):
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {}

        written = 0
        used_names: set[str] = set()
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(paths):
                try:
                    arcname = _backup_arcname(path)
                    if arcname in used_names:
                        base = Path(arcname)
                        idx = 2
                        while True:
                            alt = (base.parent / f"{base.stem}-{idx}{base.suffix}").as_posix()
                            if alt not in used_names:
                                arcname = alt
                                break
                            idx += 1
                    used_names.add(arcname)
                    if path == config_path:
                        zf.writestr(arcname, _sanitized_config_bytes())
                    else:
                        zf.write(path, arcname)
                    written += 1
                except Exception:
                    pass
        return written

    def _snapshot_data_json_backups(self, stamp: str) -> tuple[int, Path]:
        app_dir = Path(APP_DIR)
        data_dir = app_dir / "data"
        backup_dir = app_dir / "backups" / "data-json" / stamp
        count = 0
        if not data_dir.exists():
            backup_dir.mkdir(parents=True, exist_ok=True)
            return 0, backup_dir
        for pattern in ("*.json", "*.json.bak"):
            for src in data_dir.rglob(pattern):
                if not src.is_file():
                    continue
                rel = src.relative_to(data_dir)
                dst = backup_dir / rel
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    count += 1
                except Exception:
                    pass
        return count, backup_dir
    def _restore_backup_zip(self, zip_path: Path) -> None:
        app_dir = Path(APP_DIR)
        data_dir = app_dir / "data"
        logs_dir = app_dir / "logs"
        dumps_dir = app_dir / "dumps"
        exports_dir = Path(EXPORTS_DIR_DEFAULT)
        tmp_dir = Path(tempfile.mkdtemp(prefix="ft-backup-"))
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmp_dir)
            src_data = tmp_dir / "data"
            src_logs = tmp_dir / "logs"
            src_dumps = tmp_dir / "dumps"
            src_exports = tmp_dir / "Exports"
            src_exports_lower = tmp_dir / "exports"
            src_config = tmp_dir / Path(TRACKER_CONFIG_FILE).name
            src_external = tmp_dir / "external"
            if src_data.exists() and src_data.is_dir():
                if data_dir.exists():
                    shutil.rmtree(data_dir, ignore_errors=True)
                shutil.copytree(src_data, data_dir)
                # Never restore API auth tokens from backup archives.
                for token_file in ("api_auth.json", "api_auth.json.bak", "api_auth.json.tmp"):
                    try:
                        (data_dir / token_file).unlink(missing_ok=True)
                    except Exception:
                        pass
            if src_logs.exists() and src_logs.is_dir():
                if logs_dir.exists():
                    shutil.rmtree(logs_dir, ignore_errors=True)
                shutil.copytree(src_logs, logs_dir)
            if src_dumps.exists() and src_dumps.is_dir():
                if dumps_dir.exists():
                    shutil.rmtree(dumps_dir, ignore_errors=True)
                shutil.copytree(src_dumps, dumps_dir)
            restore_exports_src = src_exports if src_exports.exists() else src_exports_lower
            if restore_exports_src.exists() and restore_exports_src.is_dir():
                if exports_dir.exists():
                    shutil.rmtree(exports_dir, ignore_errors=True)
                shutil.copytree(restore_exports_src, exports_dir)
            if src_config.exists():
                shutil.copy2(src_config, Path(TRACKER_CONFIG_FILE))
            if src_external.exists() and src_external.is_dir():
                try:
                    data_target = Path(self.data_path) if self.data_path else None
                    library_target = Path(self.library_data_path) if self.library_data_path else None
                    for ext_file in src_external.rglob("*"):
                        if not ext_file.is_file():
                            continue
                        if data_target and ext_file.name == data_target.name:
                            data_target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(ext_file, data_target)
                        elif library_target and ext_file.name == library_target.name:
                            library_target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(ext_file, library_target)
                except Exception:
                    pass
        finally:
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass
    def _settings_open_data_folder(self) -> None:
        data_dir = Path(self.data_path).parent if self.data_path else Path(APP_DIR) / "data"
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            os.startfile(str(data_dir))
        except Exception as exc:
            messagebox.showerror("Open folder", f"Could not open data folder:\n{exc}")

    def _update_data_path_label(self) -> None:
        if hasattr(self, "data_path_label"):
            self.data_path_label.config(text=self._format_path_display(self.data_path))
    def _update_library_path_label(self) -> None:
        if hasattr(self, "library_path_label"):
            self.library_path_label.config(text=self._format_path_display(self.library_data_path))
    def _update_data_mtime(self, reset: bool = False) -> None:
        """Track last modified time for external reloads."""
        if reset:
            self._data_mtime = None
            return
        try:
            self._data_mtime = os.path.getmtime(self.data_path)
        except OSError:
            self._data_mtime = None
    def _maybe_reload_external(self) -> None:
        """Reload data if tracker file changed externally (e.g., mix calculator)."""
        if self.network_mode == MODE_CLIENT:
            if not bool(getattr(self, "_network_bootstrap_ready", False)):
                return
            self._request_client_network_poll(initial=False)
            return
        try:
            current = os.path.getmtime(self.data_path)
        except OSError:
            return
        prev = getattr(self, "_data_mtime", None)
        if prev is None or current > prev:
            self.load_data()
            self._refresh_stock()
            self._refresh_log()
            self._data_mtime = current
    def _place_window_at_pointer(self, win: tk.Toplevel) -> None:
        try:
            x = self.root.winfo_pointerx()
            y = self.root.winfo_pointery()
            win.update_idletasks()
            width = win.winfo_reqwidth()
            height = win.winfo_reqheight()
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            # Center near the pointer, keeping inside the screen with a slight offset
            x_pos = min(max(0, x - width // 2), max(sw - width, 0))
            y_pos = min(max(0, y - height // 2), max(sh - height, 0))
            win.geometry(f"+{x_pos}+{y_pos}")
        except Exception:
            pass

    def _center_window_on_screen(self, win: tk.Toplevel) -> None:
        try:
            win.update_idletasks()
            width = win.winfo_reqwidth()
            height = win.winfo_reqheight()
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x_pos = max(0, (sw - width) // 2)
            y_pos = max(0, (sh - height) // 2)
            win.geometry(f"+{x_pos}+{y_pos}")
        except Exception:
            pass
    def _prepare_toplevel(self, win: tk.Toplevel, keep_geometry: bool = False, placement: str = "pointer") -> None:
        """Prevent white flash when opening toplevels by styling before showing."""
        try:
            try:
                win.attributes("-alpha", 0.0)
            except Exception:
                pass
            win.withdraw()
            win.configure(bg=self.current_base_color)
            win.update_idletasks()
            if not keep_geometry:
                if placement == "center":
                    self._center_window_on_screen(win)
                else:
                    self._place_window_at_pointer(win)
            # Apply dark title bar before showing to avoid white flash
            self._set_dark_title_bar(self.dark_var.get(), target=win)
            win.deiconify()
            try:
                win.attributes("-alpha", 1.0)
            except Exception:
                pass
            win.lift()
        except Exception:
            # Fallback to basic placement
            if not keep_geometry:
                if placement == "center":
                    self._center_window_on_screen(win)
                else:
                    self._place_window_at_pointer(win)
            self._set_dark_title_bar(self.dark_var.get(), target=win)
    def _export_stats_csv(self, period: str) -> None:
        logs_subset, label, _ = self._logs_for_period(period)
        if not logs_subset:
            messagebox.showinfo("Export CSV", "No logs available for this period.")
            return
        filename = f"usage-{period}-{self.current_date.isoformat()}.csv"
        path = filedialog.asksaveasfilename(
            title="Export usage CSV",
            defaultextension=".csv",
            initialfile=filename,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["date", "time", "flower", "roa", "grams_used", "thc_mg", "cbd_mg", "is_cbd_dominant"])
                for log in logs_subset:
                    writer.writerow([
                        log.get("date", ""),
                        log.get("time", ""),
                        log.get("flower", ""),
                        log.get("roa", ""),
                        log.get("grams_used", log.get("grams", "")),
                        log.get("thc_mg", ""),
                        log.get("cbd_mg", ""),
                        log.get("is_cbd_dominant", ""),
                    ])
            messagebox.showinfo("Export CSV", f"Exported {len(logs_subset)} rows.")
        except Exception as exc:
            messagebox.showerror("Export CSV", f"Could not export CSV:\n{exc}")
    def _show_stats_window(self, period: str = "day") -> None:
        logs_for_period, label, days_count = self._logs_for_period(period)
        title, stats_list = self._stats_text(logs_for_period, label, days_count, return_title=True)
        win = tk.Toplevel(self.root)
        win._stats_period = period
        win.title("Usage stats")
        try:
            win.iconbitmap(self._resource_path('icon.ico'))
        except Exception:
            pass
        win.resizable(False, False)
        frame = ttk.Frame(win, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        btns = ttk.Frame(frame)
        btns.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        btns.columnconfigure(5, weight=1)
        for idx, (p, text) in enumerate(
            [("day", "Day"), ("week", "Week"), ("month", "Month"), ("year", "Year")]
        ):
            ttk.Button(btns, text=text, width=7, command=lambda per=p: self._update_stats_display(per, win)).grid(
                row=0, column=idx, padx=(0 if idx == 0 else 6, 0)
            )
        ttk.Button(btns, text="Export CSV", command=lambda: self._export_stats_csv(getattr(win, "_stats_period", period))).grid(row=0, column=4, padx=(12, 0), sticky="e")
        # Title line for period label
        self.stats_title = ttk.Label(frame, text=title, justify="left", font=self.font_bold_small, foreground="#555555")
        self.stats_title.grid(row=1, column=0, sticky="w", pady=(4, 2))
        self.stats_frame = ttk.Frame(frame)
        self.stats_frame.grid(row=2, column=0, sticky="ew", padx=(6, 0))
        self._render_stats_rows(stats_list)
        actions = ttk.Frame(frame)
        actions.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        actions.columnconfigure(0, weight=1)
        actions_right = ttk.Frame(actions)
        actions_right.grid(row=0, column=1, sticky="e")
        ttk.Button(
            actions_right,
            text="Copy stats",
            command=lambda: self._copy_stats_to_clipboard(getattr(win, "_stats_period", period)),
        ).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(actions_right, text="Close", command=win.destroy).grid(row=0, column=1)
        win.update_idletasks()
        try:
            width = max(340, frame.winfo_reqwidth() + 12)
            height = frame.winfo_reqheight() + 18
            height = max(230, min(420, height))
            win.geometry(f"{width}x{height}")
        except Exception:
            pass
        self._prepare_toplevel(win)
    def _update_stats_display(self, period: str, win: tk.Toplevel) -> None:
        win._stats_period = period
        logs_for_period, label, days_count = self._logs_for_period(period)
        title, stats_list = self._stats_text(logs_for_period, label, days_count, return_title=True)
        if hasattr(self, "stats_title"):
            self.stats_title.config(text=title)
        if hasattr(self, "stats_frame"):
            for child in self.stats_frame.winfo_children():
                child.destroy()
            self._render_stats_rows(stats_list)
    def _format_path_display(self, path: str, max_len: int = 28) -> str:
        if len(path) <= max_len:
            return path
        return path[: max_len // 2] + "..." + path[-(max_len // 2) :]
    def _ensure_storage_dirs(self) -> None:
        try:
            os.makedirs(os.path.dirname(TRACKER_DATA_FILE), exist_ok=True)
            os.makedirs(os.path.dirname(TRACKER_CONFIG_FILE), exist_ok=True)
            if self.data_path:
                os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        except OSError:
            pass
    @staticmethod
    def _ensure_dir_for_path(path: str) -> None:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except OSError:
            pass
    def _is_cbd_dominant(self, flower: Flower | None) -> bool:
        return is_cbd_dominant(flower)
    def _log_is_cbd_dominant(self, log: dict) -> bool:
        if log is None:
            return False
        if "is_cbd_dominant" in log:
            return bool(log.get("is_cbd_dominant"))
        mix_cbd = log.get("mix_cbd_pct")
        if mix_cbd is not None:
            try:
                return float(mix_cbd) >= 5.0
            except Exception:
                pass
        # Fall back to deriving CBD% from the log values if available.
        try:
            grams_used = float(log.get("grams_used", 0.0))
            eff = float(log.get("efficiency", 1.0)) or 1.0
            if grams_used > 0 and eff > 0:
                cbd_mg = float(log.get("cbd_mg", 0.0))
                cbd_pct = (cbd_mg / eff) / (grams_used * 1000) * 100
                return cbd_pct >= 5.0
        except Exception:
            pass
        name = str(log.get("flower", "")).strip()
        flower = self.flowers.get(name)
        if flower is None:
            for f in self.flowers.values():
                if f.name.strip().lower() == name.lower():
                    flower = f
                    break
        if flower is None:
            return False
        return self._is_cbd_dominant(flower)
    def _should_count_flower(self, flower: Flower | None) -> bool:
        if flower is None:
            return True
        return not self._is_cbd_dominant(flower)
    def _log_counts_for_totals(self, log: dict) -> bool:
        if self._log_is_cbd_dominant(log):
            return False
        name = str(log.get('flower', '')).strip()
        flower = self.flowers.get(name)
        if flower is None:
            for f in self.flowers.values():
                if f.name.strip().lower() == name.lower():
                    flower = f
                    break
        if flower is None:
            return True
        return self._should_count_flower(flower)
    def _log_counts_for_cbd(self, log: dict) -> bool:
        return self._log_is_cbd_dominant(log)
    def _set_window_icon(self) -> None:
        ico_path = self._resource_path('icon.ico')
        png_path = self._resource_path('icon.png')
        try:
            if os.path.exists(ico_path):
                self.root.iconbitmap(ico_path)
        except Exception:
            pass
        try:
            if os.path.exists(png_path):
                self.root.iconphoto(True, tk.PhotoImage(file=png_path))
        except Exception:
            pass
    def _show_tooltip(self, text: str, event: tk.Event | None = None) -> None:
        _status_show_tooltip(self, text, event)
    def _hide_tooltip(self) -> None:
        _status_hide_tooltip(self)
    def _bind_tooltip(self, widget: tk.Widget, text: str, delay_ms: int = 400) -> None:
        _status_bind_tooltip(self, widget, text, delay_ms)
    def _bind_log_thc_cbd_tooltip(self) -> None:
        _status_bind_log_thc_cbd_tooltip(self)
    def _clear_combo_selection(self, event: tk.Event | None = None) -> None:
        widget = getattr(event, "widget", None)
        if widget is None:
            return
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
    # --- Tray helpers ---
    def _stop_tray_icon(self) -> None:
        try:
            stop_tray_icon(getattr(self, "tray_icon", None))
        except Exception:
            pass
        try:
            if getattr(self, "tray_thread", None):
                self.tray_thread.join(timeout=1.0)
        except Exception:
            pass
        self.tray_icon = None
        self.tray_thread = None
    def _on_main_close(self) -> None:
        try:
            self.window_geometry = self.root.geometry()
            self._persist_split_ratio()
            self._persist_tree_widths()
            self._save_config()
        except Exception:
            pass
        self._shutdown_children()
        self._destroy_child_windows()
        self._stop_network_server()
        self._stop_export_server()
        self._stop_tray_icon()
        self.root.destroy()
    def _on_close_to_tray(self) -> None:
        if self.close_to_tray:
            self._hide_to_tray()
        else:
            self._on_main_close()
    def _on_unmap(self, event: tk.Event) -> None:
        # On minimize, hide to tray; ignore when already hidden
        if self.minimize_to_tray and self.root.state() == "iconic" and not self.is_hidden_to_tray:
            self._hide_to_tray()
    def _shutdown_children(self) -> None:
        procs = getattr(self, 'child_procs', [])
        alive = []
        for proc in procs:
            try:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
            except Exception:
                continue
        self.child_procs = alive
        self._update_scraper_status_icon()
    def _prune_child_procs(self) -> None:
        """Remove exited child processes to avoid stale scraper status."""
        procs = getattr(self, "child_procs", [])
        alive = []
        for proc in procs:
            try:
                if proc.poll() is None:
                    alive.append(proc)
            except Exception:
                continue
        self.child_procs = alive
    def _destroy_child_windows(self) -> None:
        for win_name in ('tools_window', 'settings_window', 'library_window'):
            win = getattr(self, win_name, None)
            try:
                if win and tk.Toplevel.winfo_exists(win):
                    win.destroy()
            except Exception:
                pass
    def _hide_to_tray(self) -> None:
        if self.is_hidden_to_tray:
            return
        # Close any open tool/settings/library windows before hiding
        self._destroy_child_windows()
        if not tray_supported():
            messagebox.showwarning(
                "Tray unavailable",
                "pystray/Pillow not installed; cannot hide to tray. Close will exit instead.",
            )
            self.root.destroy()
            return
        self.is_hidden_to_tray = True
        self.root.withdraw()
        def on_open() -> None:
            self.root.after(0, self._restore_from_tray)
        def on_quit() -> None:
            self.root.after(0, self._quit_from_tray)
        running, warn = resolve_scraper_status(getattr(self, "child_procs", []))
        icon_image = self._build_tray_image()
        self.tray_icon = create_tray_icon(
            "FlowerTrack",
            "FlowerTrack",
            running,
            warn,
            on_open,
            on_quit,
            image=icon_image,
        )
        self.tray_thread = None
    def _open_scraper_from_tools(self) -> None:
        self.open_parser()
        if self.tools_window and tk.Toplevel.winfo_exists(self.tools_window):
            self.tools_window.destroy()
    def launch_mix_calculator(self, close_tools: bool = False, mode: str = "dose") -> None:
        try:
            if self._focus_existing_mix_window(mode):
                if close_tools and self.tools_window and tk.Toplevel.winfo_exists(self.tools_window):
                    self.tools_window.destroy()
                return
            if getattr(sys, "frozen", False):
                args = [sys.executable, "--run-mixcalc"]
                cwd = os.path.dirname(sys.executable) or os.getcwd()
            else:
                exe = sys.executable
                target = os.path.join(os.getcwd(), 'mixcalc.py')
                args = [exe, target]
                cwd = os.getcwd()
            # Hint to child to place near pointer (best-effort)
            env = os.environ.copy()
            env["FT_MIX_MODE"] = mode
            env["FT_MOUSE_LAUNCH"] = "1"
            proc = subprocess.Popen(args, cwd=cwd, env=env)
            self._watch_mixcalc_process(proc)
            if close_tools and self.tools_window and tk.Toplevel.winfo_exists(self.tools_window):
                self.tools_window.destroy()
            try:
                self.child_procs.append(proc)
            except Exception:
                pass
        except Exception as exc:
            messagebox.showerror('Mix Calculator', f'Could not launch mix calculator.\n{exc}')

    def _focus_existing_mix_window(self, mode: str) -> bool:
        """Focus an existing mix-calculator window for the requested mode."""
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            HWND = wintypes.HWND
            LPARAM = wintypes.LPARAM
            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, LPARAM)
            mode_normalized = str(mode or "").strip().lower()
            want_stock = mode_normalized in {"stock", "blend", "stockblend"}
            target_titles = (
                ("Blend Calculator (stock)",)
                if want_stock
                else ("Mix Calculator",)
            )

            found = []

            def enum_proc(hwnd, _lparam):
                buf = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(hwnd, buf, 512)
                title = (buf.value or "").strip()
                if title and any(token in title for token in target_titles):
                    found.append(hwnd)
                return True

            user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
            if not found:
                return False
            hwnd = found[0]
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            return True
        except Exception:
            return False
    def _watch_mixcalc_process(self, proc: subprocess.Popen) -> None:
        def poll() -> None:
            try:
                if proc.poll() is None:
                    self.root.after(500, poll)
                    return
            except Exception:
                return
            try:
                self.load_data()
                self._refresh_stock()
                self._refresh_log()
            except Exception:
                pass
        try:
            self.root.after(500, poll)
        except Exception:
            pass
    def launch_flower_library(self, close_tools: bool = False) -> None:
        # Launch a new process of the same executable in library mode, so no external Python is needed.
        try:
            # Prefer focusing an existing library window to avoid duplicates.
            try:
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.WinDLL("user32", use_last_error=True)
                HWND = wintypes.HWND
                LPARAM = wintypes.LPARAM
                WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, LPARAM)
                found = []
                def enum_proc(hwnd, lParam):
                    buf = ctypes.create_unicode_buffer(512)
                    user32.GetWindowTextW(hwnd, buf, 512)
                    title = buf.value
                    if "Medical Cannabis Flower Library" in title or "Flower Library" in title:
                        found.append(hwnd)
                    return True
                user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
                if found:
                    hwnd = found[0]
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    user32.SetForegroundWindow(hwnd)
                    if close_tools and self.tools_window and tk.Toplevel.winfo_exists(self.tools_window):
                        self.tools_window.destroy()
                    return
            except Exception:
                pass
            if self.network_mode == MODE_CLIENT:
                # Client mode ignores stale local library data; refresh from host before opening.
                try:
                    remote_entries = self._fetch_network_library_data()
                    if isinstance(remote_entries, list):
                        lib_path = Path(self.library_data_path or TRACKER_LIBRARY_FILE)
                        lib_path.parent.mkdir(parents=True, exist_ok=True)
                        lib_path.write_text(
                            json.dumps(remote_entries, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                except Exception:
                    pass
            if getattr(sys, "frozen", False):
                args = [sys.executable, "--run-library"]
                cwd = os.path.dirname(sys.executable) or os.getcwd()
            else:
                entry = Path(__file__).resolve().parent / "flowertracker.py"
                if not entry.exists():
                    entry = Path(__file__).resolve()
                args = [sys.executable, str(entry), "--run-library"]
                cwd = os.path.dirname(str(entry)) or os.getcwd()
            proc = subprocess.Popen(args, cwd=cwd)
            if self.network_mode == MODE_CLIENT:
                self._watch_library_process(proc)
            if close_tools and self.tools_window and tk.Toplevel.winfo_exists(self.tools_window):
                self.tools_window.destroy()
        except Exception as exc:
            messagebox.showerror("Cannot launch", f"Failed to launch flower library:\n{exc}")

    def _watch_library_process(self, proc: subprocess.Popen) -> None:
        def poll() -> None:
            try:
                if proc.poll() is None:
                    self.root.after(700, poll)
                    return
            except Exception:
                return
            try:
                if self.network_mode != MODE_CLIENT:
                    return
                lib_path = Path(self.library_data_path or TRACKER_LIBRARY_FILE)
                if not lib_path.exists():
                    return
                payload = json.loads(lib_path.read_text(encoding="utf-8"))
                if isinstance(payload, list):
                    self._push_network_library_data(payload)
            except Exception:
                pass
        try:
            self.root.after(700, poll)
        except Exception:
            pass
    def _restore_from_tray(self) -> None:
        self.is_hidden_to_tray = False
        self._stop_tray_icon()
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.root.focus_force()
    def _quit_from_tray(self) -> None:
        self.is_hidden_to_tray = False
        self._on_main_close()
    def _build_tray_image(self) -> "Image.Image":
        """Use colored status dot based on scraper running state; fallback to icon."""
        icon_path = self._resource_path('icon.png')
        if not getattr(self, "show_scraper_buttons", True):
            if Image is not None and os.path.exists(icon_path):
                try:
                    img = Image.open(icon_path).convert("RGBA")
                    img.thumbnail((64, 64), Image.LANCZOS)
                    return img
                except Exception:
                    pass
        try:
            running, warn = resolve_scraper_status(getattr(self, "child_procs", []))
            # Tray icons need a normal icon size; tiny images can fail on some Win32 paths.
            target_size = 64
            img = self._build_status_image(running, warn, size=target_size)
            # Ensure a tray-friendly size even if fallback paths return larger images.
            try:
                if img is not None and Image is not None and hasattr(img, "size") and tuple(img.size) != (target_size, target_size):
                    img = img.copy()
                    img.thumbnail((target_size, target_size), Image.LANCZOS)
            except Exception:
                pass
            if img is not None:
                return img
        except Exception:
            pass
        icon_path = self._resource_path('icon.png')
        if Image is not None and os.path.exists(icon_path):
            try:
                img = Image.open(icon_path).convert("RGBA")
                # Resize to a tray-friendly size
                img.thumbnail((64, 64), Image.LANCZOS)
                return img
            except Exception:
                pass
        # Fallback simple colored dot
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((8, 8, size - 8, size - 8), fill=(0, 200, 0, 255))
        return img
    def _apply_scraper_controls_visibility(self) -> None:
        self._apply_scraper_status_visibility()
        btn = getattr(self, 'scraper_button', None)
        if btn:
            try:
                show_scraper_btn = self.show_scraper_buttons and self.network_mode != MODE_CLIENT
                (btn.grid if show_scraper_btn else btn.grid_remove)()
            except Exception:
                pass
        btn = getattr(self, 'flower_browser_button', None)
        if btn:
            try:
                (btn.grid if self.show_scraper_buttons else btn.grid_remove)()
            except Exception:
                pass

    def _apply_roa_visibility(self) -> None:
        _visibility_apply_roa_visibility(self)

    def _toggle_stock_form(self) -> None:
        _layout_toggle_stock_form(self)

    def _persist_split_ratio(self) -> None:
        _layout_persist_split_ratio(self)

    def _finalize_split_restore(self) -> None:
        _layout_finalize_split_restore(self)

    def _schedule_split_persist(self) -> None:
        _layout_schedule_split_persist(self)

    def _on_split_release(self) -> None:
        _layout_on_split_release(self)

    def _schedule_split_apply(self) -> None:
        _layout_schedule_split_apply(self)

    def _apply_split_ratio(self) -> None:
        _layout_apply_split_ratio(self)

    def _apply_stock_form_visibility(self) -> None:
        _layout_apply_stock_form_visibility(self)

    def _apply_mix_button_visibility(self) -> None:
        _visibility_apply_mix_button_visibility(self)

    def _apply_scraper_status_visibility(self) -> None:
        _visibility_apply_scraper_status_visibility(self)

    def _bind_scraper_status_actions(self) -> None:
        _visibility_bind_scraper_status_actions(self)

    def _status_tooltip_text(self) -> str:
        return _status_tooltip_text_helper(self, resolve_scraper_status)

    def _on_status_enter(self, event: tk.Event | None = None) -> None:
        _status_on_enter(self, delay_ms=400)

    def _on_status_leave(self, _event: tk.Event | None = None) -> None:
        _status_on_leave(self)

    def _on_status_double_click(self, _event: tk.Event | None = None) -> None:
        if self.network_mode == MODE_CLIENT:
            return
        try:
            running, _warn = resolve_scraper_status(getattr(self, "child_procs", []))
            if running:
                self._send_scraper_command("stop")
            else:
                self._send_scraper_command("start")
                # Ensure a background scraper process exists, but never force-show its window.
                if not self._scraper_process_alive_from_state():
                    self.open_parser(show_window=False)
            self._update_scraper_status_icon()
        except Exception:
            pass

    def _send_scraper_command(self, cmd: str) -> None:
        command = str(cmd or "").strip().lower()
        if command not in ("start", "stop", "show"):
            return
        try:
            command_path = Path(APP_DIR) / "data" / "scraper_command.json"
            command_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"cmd": command, "ts": time.time()}
            tmp = command_path.with_suffix(command_path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            tmp.replace(command_path)
        except Exception:
            pass

    def _stop_scraper_instances(self) -> None:
        try:
            for proc in list(getattr(self, "child_procs", [])):
                try:
                    if proc and proc.poll() is None:
                        proc.terminate()
                except Exception:
                    pass
            self._prune_child_procs()
        except Exception:
            pass
        # Try to close any scraper window not launched as a tracked child process.
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            HWND = wintypes.HWND
            LPARAM = wintypes.LPARAM
            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, LPARAM)
            WM_CLOSE = 0x0010
            targets = []

            def enum_proc(hwnd, _lparam):
                buf = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(hwnd, buf, 512)
                title = buf.value or ""
                if "Medicann Scraper" in title or ("FlowerTrack" in title and "Scraper" in title):
                    targets.append(hwnd)
                return True

            user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
            for hwnd in targets:
                try:
                    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                except Exception:
                    pass
        except Exception:
            pass

    def _on_status_right_click(self, _event: tk.Event | None = None) -> None:
        if self.network_mode == MODE_CLIENT:
            return
        self._toggle_scraper_notifications_mute()

    def _toggle_scraper_notifications_mute(self) -> None:
        cfg = _load_capture_config() or {}
        keys = (
            "auto_notify_ha",
            "notify_windows",
            "notify_price_changes",
            "notify_stock_changes",
            "notify_out_of_stock",
            "notify_restock",
            "notify_new_items",
            "notify_removed_items",
        )
        try:
            if not self.scraper_notifications_muted:
                snapshot = {k: bool(cfg.get(k, False)) for k in keys}
                self._scraper_notify_restore = dict(snapshot)
                for key in keys:
                    cfg[key] = False
                cfg["notification_restore_snapshot"] = dict(snapshot)
                cfg["notifications_muted"] = True
                self.scraper_notifications_muted = True
            else:
                restore = cfg.get("notification_restore_snapshot")
                if not isinstance(restore, dict) or not restore:
                    restore = self._scraper_notify_restore or {}
                for key in keys:
                    cfg[key] = bool(restore.get(key, cfg.get(key, False)))
                cfg["notification_restore_snapshot"] = {}
                cfg["notifications_muted"] = False
                self.scraper_notifications_muted = False
                self._scraper_notify_restore = None
            self.scraper_notify_windows = bool(cfg.get("notify_windows", self.scraper_notify_windows))
            _save_capture_config(cfg)
        except Exception:
            pass
        self._update_scraper_status_icon()
        try:
            self._show_tooltip(self._status_tooltip_text())
        except Exception:
            pass
        else:
            try:
                label.grid_remove()
            except Exception:
                pass
    def _resource_path(self, filename: str) -> str:
        return _resource_path(filename)
    def _set_dark_title_bar(
        self, enable: bool, target: tk.Tk | tk.Toplevel | None = None, allow_parent: bool = True
    ) -> None:
        widget = target or self.root
        apply_dark_titlebar(widget, enable, allow_parent=allow_parent)
    def run(self) -> None:
        self.root.mainloop()
    def _update_scraper_status_icon(self) -> None:
        """Update small status dot near the clock to reflect scraper running state."""
        try:
            self._prune_child_procs()
            running, warn = resolve_scraper_status(getattr(self, "child_procs", []))
            client_state = None
            host_clients = 0
            if self.network_mode == MODE_CLIENT:
                client_state, _missed = self._client_connection_state()
            elif self.network_mode == MODE_HOST:
                host_clients = self._host_active_connections_count()
            if getattr(self, "tray_icon", None):
                if not getattr(self, "show_scraper_buttons", True):
                    icon_path = self._resource_path('icon.png')
                    if Image is not None and os.path.exists(icon_path):
                        try:
                            img_icon = Image.open(icon_path).convert("RGBA")
                            img_icon.thumbnail((64, 64), Image.LANCZOS)
                            self.tray_icon.icon = img_icon
                        except Exception:
                            pass
                else:
                    update_tray_icon(self.tray_icon, running, warn)
            if not self.show_scraper_status_icon or not self.show_scraper_buttons:
                try:
                    self.host_clients_label.configure(text="")
                except Exception:
                    pass
                self._apply_scraper_controls_visibility()
                return
            target_size = 32
            img = self._build_status_image(running, warn, size=target_size, client_state=client_state)
            try:
                if img is not None and Image is not None and hasattr(img, "size") and tuple(img.size) != (target_size, target_size):
                    img = img.copy()
                    img.thumbnail((target_size, target_size), Image.LANCZOS)
            except Exception:
                pass
            if img is not None and self.scraper_notifications_muted:
                img = _overlay_mute_icon(img)
            if img and ImageTk is not None:
                tk_img = ImageTk.PhotoImage(img)
                self.scraper_status_img = tk_img
                self.scraper_status_label.configure(image=tk_img, text="")
            else:
                self.scraper_status_label.configure(image="", text="")
            try:
                if self.network_mode == MODE_HOST:
                    self.host_clients_label.configure(
                        text=f"Clients: {host_clients}",
                        foreground=getattr(self, "muted_color", "#999"),
                    )
                else:
                    self.host_clients_label.configure(text="")
            except Exception:
                pass
        except Exception:
            self.scraper_status_label.configure(image="", text="")
        finally:
            try:
                self.root.after(1500, self._update_scraper_status_icon)
            except Exception:
                pass

    def _build_status_image(
        self,
        running: bool,
        warn: bool,
        size: int = 64,
        client_state: str | None = None,
    ):
        if Image is None or ImageDraw is None:
            return _build_scraper_status_image(getattr(self, "child_procs", []))
        try:
            if client_state == "good":
                color_hex = self.scraper_status_running_color
            elif client_state == "interrupted":
                color_hex = self.scraper_status_error_color
            elif client_state == "down":
                color_hex = self.scraper_status_stopped_color
            elif warn:
                color_hex = self.scraper_status_error_color
            elif running:
                color_hex = self.scraper_status_running_color
            else:
                color_hex = self.scraper_status_stopped_color
            rgb = self._hex_to_rgb(color_hex, fallback=(46, 204, 113) if running else (231, 76, 60))
            border_hex = str(getattr(self, "current_border_color", "#2a2a2a") or "#2a2a2a")
            border_rgb = self._hex_to_rgb(border_hex, fallback=(42, 42, 42))
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            pad = max(1, size // 8)
            draw.ellipse(
                (pad, pad, size - pad, size - pad),
                fill=(rgb[0], rgb[1], rgb[2], 255),
                outline=(border_rgb[0], border_rgb[1], border_rgb[2], 220),
                width=1,
            )
            return img
        except Exception:
            return _build_scraper_status_image(getattr(self, "child_procs", []))

    def _client_connection_state(self) -> tuple[str, int]:
        missed = int(getattr(self, "_client_missed_pings", 0) or 0)
        ever = bool(getattr(self, "_client_ever_connected", False))
        if not ever:
            return ("down" if missed >= 3 else "interrupted", missed)
        if missed <= 0:
            return ("good", 0)
        if missed >= 3:
            return ("down", missed)
        return ("interrupted", missed)

    def _host_active_connections_count(self) -> int:
        if self.network_mode != MODE_HOST:
            return 0
        server = getattr(self, "network_server", None)
        if not server:
            return 0
        try:
            lock = getattr(server, "_ft_clients_lock", None)
            clients = getattr(server, "_ft_clients", None)
            ttl = float(getattr(server, "_ft_client_ttl", 20.0) or 20.0)
            if lock is None or clients is None:
                return 0
            now = time.monotonic()
            with lock:
                stale = [ip for ip, ts in clients.items() if (now - float(ts)) > ttl]
                for ip in stale:
                    clients.pop(ip, None)
                return len(clients)
        except Exception:
            return 0
