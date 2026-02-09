from __future__ import annotations
import json
import csv
import os
import sys
import webbrowser
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
from scraper_state import resolve_scraper_status as resolve_scraper_status_core
from theme import apply_style_theme, compute_colors, set_titlebar_dark
from ui_tracker_settings import open_tracker_settings
from resources import resource_path as _resource_path
from inventory import (
    TRACKER_DATA_FILE,
    TRACKER_LIBRARY_FILE,
    TRACKER_CONFIG_FILE,
    load_tracker_data,
    save_tracker_data,
)
from storage import load_last_parse
from inventory import add_stock_entry, log_dose_entry, is_cbd_dominant
from exports import export_html_auto, export_size_warning
from export_server import start_export_server as srv_start_export_server, stop_export_server as srv_stop_export_server
from config import load_tracker_config, save_tracker_config
from inventory import Flower
try:
    from PIL import Image, ImageDraw, ImageTk
except ImportError:  # Pillow may not be installed; tray icon will be disabled
    Image = None
    ImageDraw = None
    ImageTk = None
def resolve_scraper_status(child_procs) -> tuple[bool, bool]:
    return resolve_scraper_status_core(child_procs, SCRAPER_STATE_FILE)
def _build_scraper_status_image(child_procs):
    try:
        running, warn = resolve_scraper_status_core(child_procs, SCRAPER_STATE_FILE)
        return make_tray_image(running=running, warn=warn)
    except Exception:
        return None
 
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
        self._threshold_color_buttons: dict[str, list[tk.Button]] = {}
        self.stock_form_source: str | None = None
        self.stock_form_dirty = False
        self.current_base_color = "#f5f5f5"
        self.data_path = TRACKER_DATA_FILE
        self.library_data_path = TRACKER_LIBRARY_FILE
        self.minimize_to_tray = False
        self.close_to_tray = False
        self.show_scraper_status_icon = True
        self.show_scraper_buttons = True
        self.scraper_notify_windows = True
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
        self.export_port = 8765
        self.tray_thread: threading.Thread | None = None
        self.is_hidden_to_tray = False
        self.tools_window: tk.Toplevel | None = None
        self.flowers: dict[str, Flower] = {}
        self.logs: list[dict[str, str | float]] = []
        self.window_geometry = ""
        self.stock_column_widths: dict[str, int] = {}
        self.log_column_widths: dict[str, int] = {}
        self._geometry_save_job = None
        self.current_date: date = date.today()
        self._last_seen_date: date = date.today()
        self._data_mtime: float | None = None
        self._build_ui()
        self._ensure_storage_dirs()
        self._load_config()
        self.load_data()
        self.root.after(50, lambda: self._set_dark_title_bar(self.dark_var.get()))
        self.apply_theme(self.dark_var.get())
        self._refresh_stock()
        self._refresh_log()
        self._update_scraper_status_icon()
    def open_parser(self) -> None:
        """Launch the scraper UI in a separate process."""
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
            # First try to focus an existing scraper window
            if focus_existing():
                return
            if getattr(sys, "frozen", False):
                proc = subprocess.Popen([sys.executable, "--scraper"])
            else:
                exe = sys.executable
                target = Path(__file__).resolve().parent / "flowertracker.py"
                proc = subprocess.Popen([exe, str(target), "--scraper"])
            try:
                self.child_procs.append(proc)
                self._update_scraper_status_icon()
            except Exception:
                pass
        except Exception as exc:
            messagebox.showerror("Open Scraper", f"Could not launch parser:\n{exc}")
    def open_flower_browser(self) -> None:
        exports_dir = Path(EXPORTS_DIR_DEFAULT)
        exports_dir.mkdir(parents=True, exist_ok=True)
        html_files = sorted(exports_dir.glob("export-*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
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
        url = latest.as_uri()
        if self._ensure_export_server() and self.export_port:
            url = f"http://127.0.0.1:{self.export_port}/flowerbrowser"
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
    def _ensure_export_server(self) -> bool:
        try:
            if self.export_server and self.export_port:
                return True
            exports_dir = Path(EXPORTS_DIR_DEFAULT)
            httpd, thread, port = srv_start_export_server(self.export_port, exports_dir, self._log_export)
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
        self.scraper_status_img = None
        self.scraper_status_label = ttk.Label(top_bar, text="")
        self.scraper_status_label.grid(row=0, column=6, sticky="e", padx=(6, 0))
        self._apply_scraper_controls_visibility()
        top_bar.columnconfigure(4, weight=1)
        # Stock list
        self.stock_wrap = tk.Frame(main, highlightthickness=2)
        self.stock_wrap.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
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
        main.columnconfigure(0, weight=3)
        main.rowconfigure(1, weight=1)
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
        right = ttk.Frame(main)
        right.grid(row=1, column=1, sticky="nsew")
        main.columnconfigure(1, weight=4)
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
        nav = ttk.Frame(log_frame)
        nav.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        prev_btn = ttk.Button(nav, text="< Prev", width=8, command=lambda: self._change_day(-1))
        prev_btn.grid(row=0, column=0, padx=(0, 6))
        self.date_label = ttk.Label(nav, text="", font=("", 10, "bold"))
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
        selection = self.stock_tree.selection()
        if not selection:
            return
        name = self.stock_tree.set(selection[0], "name")
        if not name:
            return
        flower = self.flowers.get(name)
        if flower:
            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, flower.name)
            self.thc_entry.delete(0, tk.END)
            self.thc_entry.insert(0, f"{flower.thc_pct:.1f}")
            self.cbd_entry.delete(0, tk.END)
            self.cbd_entry.insert(0, f"{flower.cbd_pct:.1f}")
            self.grams_entry.delete(0, tk.END)
            self.grams_entry.insert(0, f"{flower.grams_remaining:.3f}")
            self.stock_form_source = flower.name
            self.stock_form_dirty = False
        if name in self.flower_choice["values"]:
            self.flower_choice.set(name)
    def _maybe_clear_stock_selection(self, event: tk.Event) -> None:
        # If click is on empty space, clear selection
        if not self.stock_tree.identify_row(event.y):
            self.stock_tree.selection_remove(self.stock_tree.selection())
            if self.stock_form_source and not self.stock_form_dirty:
                self._clear_stock_inputs()
        else:
            # user clicked a row; keep selection and do nothing else
            pass
    def _maybe_clear_log_selection(self, event: tk.Event) -> None:
        if not self.log_tree.identify_row(event.y):
            self.log_tree.selection_remove(self.log_tree.selection())
    def add_stock(self) -> None:
        name = self.name_entry.get().strip()
        thc_text = self.thc_entry.get().strip()
        cbd_text = self.cbd_entry.get().strip()
        grams_text = self.grams_entry.get().strip()
        if not name or not thc_text or not grams_text:
            messagebox.showwarning("Missing info", "Enter name, THC %, and grams. CBD % can be 0.")
            return
        try:
            thc_pct = float(thc_text)
            cbd_pct = float(cbd_text) if cbd_text else 0.0
            grams = float(grams_text)
        except ValueError:
            messagebox.showerror("Invalid input", "Potency and grams must be numbers.")
            return
        if thc_pct < 0 or cbd_pct < 0 or grams <= 0:
            messagebox.showerror("Invalid input", "Potency must be non-negative and grams must be positive.")
            return
        try:
            add_stock_entry(self.flowers, name=name, grams=grams, thc_pct=thc_pct, cbd_pct=cbd_pct)
        except ValueError as exc:
            messagebox.showerror("Cannot add stock", str(exc))
            return
        self._refresh_stock()
        self._clear_stock_inputs()
        self.save_data()
        self._save_config()
    def delete_stock(self) -> None:
        selection = self.stock_tree.selection()
        if not selection:
            messagebox.showwarning("Select flower", "Select a flower row to delete.")
            return
        # Get the name from the selected row explicitly by column id
        name = self.stock_tree.set(selection[0], "name")
        if not name:
            messagebox.showerror("Not found", "Could not determine selected flower name.")
            return
        has_logs = any(log.get("flower") == name for log in self.logs)
        msg = f"Delete '{name}' from stock?"
        if has_logs:
            msg += "\nLogs exist for this flower; they will remain but stock will be removed."
        if not messagebox.askokcancel("Confirm delete", msg):
            return
        self.flowers.pop(name, None)
        self._refresh_stock()
        self._refresh_log()
        self.save_data()
        self._save_config()
        self._clear_stock_inputs()
        self.stock_tree.selection_remove(selection)
    def _clear_stock_inputs(self) -> None:
        self.name_entry.delete(0, tk.END)
        self.thc_entry.delete(0, tk.END)
        self.cbd_entry.delete(0, tk.END)
        self.grams_entry.delete(0, tk.END)
        self.stock_form_source = None
        self.stock_form_dirty = False
    def log_dose(self) -> None:
        name = self.flower_choice.get().strip()
        grams_text = self.dose_entry.get().strip()
        if not name:
            messagebox.showwarning("Select flower", "Choose a saved flower to log a dose.")
            return
        if name not in self.flowers:
            messagebox.showerror("Unknown flower", "Selected flower is not in stock.")
            return
        if not grams_text:
            messagebox.showwarning("Missing dose", "Enter a dose in grams of flower.")
            return
        try:
            grams_used = float(grams_text)
        except ValueError:
            messagebox.showerror("Invalid dose", "Dose must be numeric.")
            return
        if grams_used <= 0:
            messagebox.showerror("Invalid dose", "Dose must be positive.")
            return
        roa = self._resolve_roa()
        try:
            remaining, log_entry = log_dose_entry(
                self.flowers,
                self.logs,
                name=name,
                grams_used=grams_used,
                roa=roa,
                roa_options=self.roa_options,
            )
        except ValueError as exc:
            messagebox.showerror("Cannot log dose", str(exc))
            return
        self._refresh_stock()
        self._refresh_log()
        self._update_scraper_status_icon()
        self.dose_entry.delete(0, tk.END)
        self.save_data()

    def _resolve_roa(self) -> str:
        if getattr(self, "hide_roa_options", False):
            return "Unknown"
        try:
            return self.roa_choice.get().strip() or "Vaped"
        except Exception:
            return "Vaped"
    def edit_log_entry(self) -> None:
        selection = self.log_tree.selection()
        if not selection:
            messagebox.showwarning("Select log", "Select a log entry to edit.")
            return
        idx = int(selection[0])
        if idx >= len(self.logs):
            messagebox.showerror("Not found", "Selected log entry is missing.")
            return
        log = self.logs[idx]
        current_flower = log["flower"]
        current_roa = log.get("roa", "Smoking")
        current_eff = float(log.get("efficiency", 1.0))
        current_grams = float(log.get("grams_used", 0.0))
        current_time = log.get("time_display") or log.get("time", "").split(" ")[-1]
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit log entry")
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        ttk.Label(frame, text="Flower").grid(row=0, column=0, sticky="w")
        flower_var = tk.StringVar(value=current_flower)
        flower_combo = ttk.Combobox(
            frame,
            state="readonly",
            values=[f.name for f in sorted(self.flowers.values(), key=lambda f: f.name.lower())],
            textvariable=flower_var,
            width=22,
            style=self.combo_style,
        )
        flower_combo.grid(row=1, column=0, sticky="w", padx=(0, 8))
        flower_combo.bind("<FocusOut>", self._clear_combo_selection)
        flower_combo.bind("<<ComboboxSelected>>", self._clear_combo_selection)
        ttk.Label(frame, text="Route").grid(row=0, column=1, sticky="w")
        roa_var = tk.StringVar(value=current_roa if current_roa in self.roa_options else "Vaped")
        roa_combo = ttk.Combobox(
            frame, state="readonly", values=list(self.roa_options.keys()), textvariable=roa_var, width=12, style=self.combo_style
        )
        roa_combo.grid(row=1, column=1, sticky="w", padx=(0, 8))
        roa_combo.bind("<FocusOut>", self._clear_combo_selection)
        roa_combo.bind("<<ComboboxSelected>>", self._clear_combo_selection)
        ttk.Label(frame, text="Dose (g)").grid(row=0, column=2, sticky="w")
        grams_var = tk.StringVar(value=f"{current_grams:.3f}")
        grams_entry = ttk.Entry(frame, textvariable=grams_var, width=12)
        grams_entry.grid(row=1, column=2, sticky="w")
        ttk.Label(frame, text="Time (HH:MM)").grid(row=0, column=3, sticky="w")
        time_var = tk.StringVar(value=current_time)
        time_entry = ttk.Entry(frame, textvariable=time_var, width=10)
        time_entry.grid(row=1, column=3, sticky="w", padx=(0, 8))
        buttons = ttk.Frame(dialog, padding=(12, 8, 12, 12))
        buttons.grid(row=1, column=0, sticky="ew")
        buttons.columnconfigure(0, weight=1)
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).grid(row=0, column=0, sticky="w")
        def save_edit() -> None:
            new_flower_name = flower_var.get().strip()
            new_roa = roa_var.get().strip() or "Smoking"
            try:
                new_grams = float(grams_var.get().strip())
            except ValueError:
                messagebox.showerror("Invalid dose", "Dose must be numeric.")
                return
            if new_grams <= 0:
                messagebox.showerror("Invalid dose", "Dose must be positive.")
                return
            if not new_flower_name or new_flower_name not in self.flowers:
                messagebox.showerror("Missing flower", "Select a valid flower.")
                return
            time_text = time_var.get().strip()
            try:
                # Build timestamp with the existing date to keep day context
                dt_obj = datetime.strptime(f"{log.get('date')} {time_text}", "%Y-%m-%d %H:%M")
            except Exception:
                messagebox.showerror("Invalid time", "Enter time as HH:MM in 24-hour format.")
                return
            efficiency = self.roa_options.get(new_roa, 1.0)
            old_flower = self.flowers.get(current_flower)
            new_flower = self.flowers[new_flower_name]
            # Roll back previous consumption on old flower
            if log.get("mix_sources") or log.get("mix_thc_pct") is not None:
                self._restore_mix_stock(log)
            elif old_flower:
                old_flower.grams_remaining += current_grams
            # Apply new consumption to selected flower
            try:
                new_flower.remove_by_grams(new_grams)
            except ValueError as exc:
                # Revert rollback if needed
                if old_flower:
                    try:
                        old_flower.remove_by_grams(current_grams)
                    except Exception:
                        pass
                messagebox.showerror("Not enough stock", str(exc))
                return
            log["flower"] = new_flower_name
            log["roa"] = new_roa
            log["efficiency"] = efficiency
            log["grams_used"] = new_grams
            log["thc_mg"] = new_grams * 1000 * (new_flower.thc_pct / 100.0) * efficiency
            log["cbd_mg"] = new_grams * 1000 * (new_flower.cbd_pct / 100.0) * efficiency
            log["remaining"] = new_flower.grams_remaining
            log["time"] = dt_obj.strftime("%Y-%m-%d %H:%M")
            log["time_display"] = dt_obj.strftime("%H:%M")
            log["is_cbd_dominant"] = self._is_cbd_dominant(new_flower)
            self._refresh_stock()
            self._refresh_log()
            self.save_data()
            dialog.destroy()
        ttk.Button(buttons, text="Save", command=save_edit).grid(row=0, column=1, sticky="e")
        self._prepare_toplevel(dialog)
    def _restore_mix_stock(self, log: dict) -> None:
        name = str(log.get("flower", "")).strip()
        if not name:
            return
        grams_used = float(log.get("grams_used", 0.0))
        if grams_used <= 0:
            return
        thc_pct = log.get("mix_thc_pct")
        cbd_pct = log.get("mix_cbd_pct")
        if thc_pct is None or cbd_pct is None:
            try:
                eff = float(log.get("efficiency", 1.0)) or 1.0
                thc_mg = float(log.get("thc_mg", 0.0))
                cbd_mg = float(log.get("cbd_mg", 0.0))
                if grams_used > 0 and eff > 0:
                    thc_pct = (thc_mg / eff) / (grams_used * 1000) * 100
                    cbd_pct = (cbd_mg / eff) / (grams_used * 1000) * 100
            except Exception:
                pass
        flower = self.flowers.get(name)
        if flower is None:
            for f in self.flowers.values():
                if f.name.strip().lower() == name.lower():
                    flower = f
                    break
        if flower is None:
            if thc_pct is None or cbd_pct is None:
                return
            flower = Flower(name=name, thc_pct=float(thc_pct), cbd_pct=float(cbd_pct), grams_remaining=0.0)
            self.flowers[name] = flower
        flower.grams_remaining += grams_used
    def delete_log_entry(self) -> None:
        selection = self.log_tree.selection()
        if not selection:
            messagebox.showwarning("Select log", "Select a log entry to delete.")
            return
        idx = int(selection[0])
        if idx >= len(self.logs):
            messagebox.showerror("Not found", "Selected log entry is missing.")
            return
        log = self.logs[idx]
        if not messagebox.askokcancel("Confirm delete", "Delete this log entry and restore its grams to stock?"):
            return
        grams_used = float(log.get("grams_used", 0.0))
        flower_name = str(log.get("flower", "")).strip()
        if log.get("mix_sources") or log.get("mix_thc_pct") is not None:
            self._restore_mix_stock(log)
        else:
            flower = self.flowers.get(flower_name)
            if flower is None:
                # Fallback to case-insensitive match in case the name casing changed
                for f in self.flowers.values():
                    if f.name.strip().lower() == flower_name.lower():
                        flower = f
                        break
            if flower:
                flower.grams_remaining += grams_used
        del self.logs[idx]
        self._refresh_stock()
        self._refresh_log()
        self.save_data()
    def _refresh_stock(self) -> None:
        for item in self.stock_tree.get_children():
            self.stock_tree.delete(item)
        total_all = 0.0
        total_counted = 0.0
        cbd_total = 0.0
        for flower in sorted(self.flowers.values(), key=lambda f: f.name.lower()):
            total_all += flower.grams_remaining
            if self._should_count_flower(flower):
                total_counted += flower.grams_remaining
            if self._is_cbd_dominant(flower):
                cbd_total += flower.grams_remaining
            if self.enable_stock_coloring:
                if self._is_cbd_dominant(flower):
                    green_thr = getattr(self, "cbd_single_green_threshold", self.single_green_threshold)
                    red_thr = getattr(self, "cbd_single_red_threshold", self.single_red_threshold)
                    high_color = self.single_cbd_high_color
                    low_color = self.single_cbd_low_color
                else:
                    green_thr = self.single_green_threshold
                    red_thr = self.single_red_threshold
                    high_color = self.single_thc_high_color
                    low_color = self.single_thc_low_color
                row_color = self._color_for_value(flower.grams_remaining, green_thr, red_thr, high_color, low_color)
            else:
                row_color = self.text_color
            if flower.grams_remaining <= 1e-6:
                row_color = self.muted_color
            tag = f"stock_{flower.name}"
            self.stock_tree.tag_configure(tag, foreground=row_color)
            self.stock_tree.insert(
                "",
                tk.END,
                tags=(tag,),
                values=(
                    flower.name,
                    f"{flower.thc_pct:.1f}",
                    f"{flower.cbd_pct:.1f}",
                    f"{flower.grams_remaining:.3f}",
                ),
            )
        track_cbd = getattr(self, "track_cbd_flower", False)
        combined_total = total_counted
        if track_cbd:
            self.total_label.config(text=f"Total THC stock: {total_counted:.2f} g")
            self.total_cbd_label.config(text=f"Total CBD stock: {cbd_total:.2f} g")
            if not self.total_cbd_label.winfo_ismapped():
                self.total_cbd_label.pack(side="left")
        else:
            self.total_label.config(text=f"Total flower stock: {combined_total:.2f} g")
            try:
                self.total_cbd_label.pack_forget()
            except Exception:
                pass
        total_color = (
            self._color_for_value(
                combined_total,
                self.total_green_threshold,
                self.total_red_threshold,
                self.total_thc_high_color,
                self.total_thc_low_color,
            )
            if self.enable_stock_coloring
            else self.text_color
        )
        self.total_label.configure(foreground=total_color)
        if track_cbd:
            cbd_total_color = (
                self._color_for_value(
                    cbd_total,
                    getattr(self, "cbd_total_green_threshold", self.total_green_threshold),
                    getattr(self, "cbd_total_red_threshold", self.total_red_threshold),
                    self.total_cbd_high_color,
                    self.total_cbd_low_color,
                )
                if self.enable_stock_coloring
                else self.text_color
            )
            self.total_cbd_label.configure(foreground=cbd_total_color)
        used_today = self._grams_used_on_day(self.current_date)
        used_today_cbd = self._grams_used_on_day_cbd(self.current_date) if getattr(self, "track_cbd_flower", False) else 0.0
        if self.target_daily_grams > 0:
            remaining_today = self.target_daily_grams - used_today
            self.remaining_today_label.config(
                text=f"Remaining today (THC): {remaining_today:.2f} g / {self.target_daily_grams:.2f} g",
                foreground=(
                    self.remaining_thc_high_color
                    if (self.target_daily_grams - used_today) >= 0
                    else self.remaining_thc_low_color
                )
                if self.enable_usage_coloring
                else self.text_color,
            )
        else:
            self.remaining_today_label.config(text="Remaining today (THC): N/A", foreground=self.text_color)
        if getattr(self, "track_cbd_flower", False):
            target_cbd = getattr(self, "target_daily_cbd_grams", 0.0)
            if target_cbd > 0:
                remaining_cbd = target_cbd - used_today_cbd
                self.remaining_today_cbd_label.config(
                    text=f"Remaining today (CBD): {remaining_cbd:.2f} g / {target_cbd:.2f} g",
                    foreground=(
                        self.remaining_cbd_high_color if remaining_cbd >= 0 else self.remaining_cbd_low_color
                    )
                    if self.enable_usage_coloring
                    else self.text_color,
                )
            else:
                self.remaining_today_cbd_label.config(text="Remaining today (CBD): N/A", foreground=self.text_color)
            self.remaining_today_cbd_label.grid()
        else:
            self.remaining_today_cbd_label.grid_remove()
        remaining_stock = max(combined_total, 0.0)
        days_target = "N/A"
        days_target_val: float | None = None
        if self.target_daily_grams > 0:
            days_target_val = remaining_stock / self.target_daily_grams
            days_target = f"{days_target_val:.1f}"
        avg_daily = self._average_daily_usage()
        days_actual_val = None if avg_daily is None or avg_daily <= 0 else remaining_stock / avg_daily
        days_actual = "N/A" if days_actual_val is None else f"{days_actual_val:.1f}"
        actual_color = self.text_color
        if self.enable_usage_coloring and days_actual_val is not None and days_target_val is not None:
            actual_color = self.days_thc_high_color if days_actual_val >= days_target_val else self.days_thc_low_color
        if track_cbd:
            self.days_label.config(text=f"Days of THC flower left - target: {days_target} | actual: {days_actual}", foreground=actual_color)
        else:
            self.days_label.config(text=f"Days of flower left - target: {days_target} | actual: {days_actual}", foreground=actual_color)
        if not track_cbd:
            self.days_label_cbd.grid_remove()
        elif getattr(self, "track_cbd_flower", False):
            days_target_cbd = "N/A"
            days_target_val_cbd: float | None = None
            if getattr(self, "target_daily_cbd_grams", 0.0) > 0:
                days_target_val_cbd = cbd_total / max(self.target_daily_cbd_grams, 1e-9)
                days_target_cbd = f"{days_target_val_cbd:.1f}"
            avg_daily_cbd = self._average_daily_usage_cbd()
            days_actual_val_cbd = None if avg_daily_cbd is None or avg_daily_cbd <= 0 else cbd_total / avg_daily_cbd
            days_actual_cbd = "N/A" if days_actual_val_cbd is None else f"{days_actual_val_cbd:.1f}"
            color_cbd = self.text_color
            if self.enable_usage_coloring and days_actual_val_cbd is not None and days_target_val_cbd is not None:
                color_cbd = self.days_cbd_high_color if days_actual_val_cbd >= days_target_val_cbd else self.days_cbd_low_color
            self.days_label_cbd.config(
                text=f"Days of CBD flower left - target: {days_target_cbd} | actual: {days_actual_cbd}", foreground=color_cbd
            )
            self.days_label_cbd.grid()
        else:
            self.days_label_cbd.grid_remove()
        self.flower_choice["values"] = [f.name for f in sorted(self.flowers.values(), key=lambda f: f.name.lower())]
        self._apply_stock_sort()
    def _refresh_log(self) -> None:
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)
        day_str = self.current_date.isoformat()
        day_logs = [log for log in self.logs if log.get("date") == day_str]
        day_total = sum(float(log.get("grams_used", 0.0)) for log in day_logs if self._log_counts_for_totals(log))
        day_total_cbd = sum(float(log.get("grams_used", 0.0)) for log in day_logs if self._log_counts_for_cbd(log))
        if hasattr(self, "day_total_label"):
            if self.current_date < date.today():
                remaining = self.target_daily_grams - day_total if self.target_daily_grams > 0 else None
                color = self.text_color
                if self.enable_usage_coloring:
                    color = self.accent_green
                    if remaining is not None and remaining < 0:
                        color = self.accent_red
                self.day_total_label.config(
                    text=f"Total used this day (THC): {day_total:.3f} g", foreground=color
                )
                self.day_total_label.grid()
                if getattr(self, "track_cbd_flower", False):
                    color_cbd = self.text_color
                    target_cbd = getattr(self, "target_daily_cbd_grams", 0.0)
                    if self.enable_usage_coloring and target_cbd > 0:
                        color_cbd = self.accent_green if (target_cbd - day_total_cbd) >= 0 else self.accent_red
                    self.day_total_cbd_label.config(
                        text=f"Total used this day (CBD): {day_total_cbd:.3f} g", foreground=color_cbd
                    )
                    self.day_total_cbd_label.grid()
                else:
                    self.day_total_cbd_label.grid_remove()
            else:
                self.day_total_label.grid_remove()
                self.day_total_cbd_label.grid_remove()
        for idx, log in enumerate(self.logs):
            if log.get("date") != day_str:
                continue
            roa = log.get("roa", "Unknown")
            self.log_tree.insert(
                "",
                tk.END,
                iid=str(idx),
                values=(
                    log.get("time_display") or log["time"].split(" ")[-1],
                    log["flower"],
                    roa,
                    f"{log['grams_used']:.3f}",
                    f"{log['thc_mg']:.1f}",
                    f"{log['cbd_mg']:.1f}",
                ),
            )
        # If there are logs for this day, scroll to the bottom to show the latest
        children = self.log_tree.get_children()
        if children:
            try:
                self.log_tree.yview_moveto(1.0)
            except Exception:
                pass
        self.date_label.config(text=self.current_date.strftime("%Y-%m-%d"))
    def _change_day(self, delta_days: int) -> None:
        self.current_date += timedelta(days=delta_days)
        self._refresh_log()
        self._refresh_stock()
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
                    btn.configure(bg=color, activebackground=color, highlightbackground=color)
                except Exception:
                    pass

    def _choose_threshold_color(self, key: str) -> None:
        current = getattr(self, key, None) or "#2ecc71"
        settings_win = getattr(self, "settings_window", None)
        try:
            if settings_win and tk.Toplevel.winfo_exists(settings_win):
                settings_win.transient(self.root)
                settings_win.lift()
                settings_win.focus_force()
        except Exception:
            pass
        picked = colorchooser.askcolor(color=current, title="Select color")[1]
        try:
            if settings_win and tk.Toplevel.winfo_exists(settings_win):
                settings_win.lift()
                settings_win.focus_force()
        except Exception:
            pass
        color = self._normalize_hex(picked or "")
        if not color:
            return
        setattr(self, key, color)
        self._update_threshold_color_buttons()
        self._refresh_stock()
        self._refresh_log()
        self._save_config()
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
        try:
            def _parse_float(label: str, raw: str, allow_empty: bool = False, default: float = 0.0) -> float:
                text = (raw or "").strip()
                if not text:
                    if allow_empty:
                        return float(default)
                    raise ValueError(f"{label} is required.")
                try:
                    value = float(text)
                except Exception:
                    raise ValueError(f"{label} must be a number.")
                if value != value or value in (float("inf"), float("-inf")):
                    raise ValueError(f"{label} must be a finite number.")
                return value

            def _parse_int(label: str, raw: str, allow_empty: bool = False, default: int = 0) -> int:
                text = (raw or "").strip()
                if not text:
                    if allow_empty:
                        return int(default)
                    raise ValueError(f"{label} is required.")
                try:
                    value = int(float(text))
                except Exception:
                    raise ValueError(f"{label} must be an integer.")
                return value

            green = _parse_float("Total THC green threshold", self.total_green_entry.get())
            red = _parse_float("Total THC red threshold", self.total_red_entry.get())
            single_green = _parse_float("Single THC green threshold", self.single_green_entry.get())
            single_red = _parse_float("Single THC red threshold", self.single_red_entry.get())
            cbd_total_green = _parse_float("Total CBD green threshold", self.cbd_total_green_entry.get())
            cbd_total_red = _parse_float("Total CBD red threshold", self.cbd_total_red_entry.get())
            cbd_single_green = _parse_float("Single CBD green threshold", self.cbd_single_green_entry.get())
            cbd_single_red = _parse_float("Single CBD red threshold", self.cbd_single_red_entry.get())
            target_daily = _parse_float("Daily THC target", self.daily_target_entry.get())
            target_daily_cbd = _parse_float(
                "Daily CBD target",
                self.daily_target_cbd_entry.get(),
                allow_empty=True,
                default=0.0,
            )
            avg_usage_days = _parse_int(
                "Average usage days",
                self.avg_usage_days_entry.get(),
                allow_empty=True,
                default=0,
            )
            track_cbd_flower = bool(self.track_cbd_flower_var.get())
            enable_stock_coloring = bool(self.enable_stock_color_var.get())
            enable_usage_coloring = bool(self.enable_usage_color_var.get())
            roa_opts = {}
            for name, var in self.roa_vars.items():
                val = _parse_float(f"{name} efficiency (%)", var.get())
                if val < 0 or val > 100:
                    raise ValueError(f"{name} efficiency must be 0-100%.")
                roa_opts[name] = val / 100.0
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            return
        if (
            green <= 0
            or red < 0
            or single_green <= 0
            or single_red < 0
            or red >= green
            or single_red >= single_green
            or cbd_total_green <= 0
            or cbd_total_red < 0
            or cbd_single_green <= 0
            or cbd_single_red < 0
            or cbd_total_red >= cbd_total_green
            or cbd_single_red >= cbd_single_green
            or target_daily < 0
            or target_daily_cbd < 0
            or avg_usage_days < 0
            or (track_cbd_flower and target_daily_cbd <= 0)
        ):
            messagebox.showerror(
                "Invalid thresholds", "Use positive numbers with red thresholds below green thresholds."
            )
            return
        if not roa_opts:
            messagebox.showerror("Invalid efficiencies", "Provide at least one route efficiency value.")
            return
        self.total_green_threshold = green
        self.total_red_threshold = red
        self.single_green_threshold = single_green
        self.single_red_threshold = single_red
        self.cbd_total_green_threshold = cbd_total_green
        self.cbd_total_red_threshold = cbd_total_red
        self.cbd_single_green_threshold = cbd_single_green
        self.cbd_single_red_threshold = cbd_single_red
        self.target_daily_grams = target_daily
        self.target_daily_cbd_grams = target_daily_cbd
        self.avg_usage_days = avg_usage_days
        self.track_cbd_flower = track_cbd_flower
        self.enable_stock_coloring = enable_stock_coloring
        self.enable_usage_coloring = enable_usage_coloring
        if hasattr(self, "hide_roa_var"):
            self.hide_roa_options = bool(self.hide_roa_var.get())
        if hasattr(self, "hide_mixed_dose_var"):
            self.hide_mixed_dose = bool(self.hide_mixed_dose_var.get())
        if hasattr(self, "hide_mix_stock_var"):
            self.hide_mix_stock = bool(self.hide_mix_stock_var.get())
        self.roa_options = roa_opts
        self.minimize_to_tray = self.minimize_var.get()
        self.close_to_tray = self.close_var.get()
        if hasattr(self, 'scraper_status_icon_var'):
            self.show_scraper_status_icon = bool(self.scraper_status_icon_var.get())
        if hasattr(self, 'scraper_controls_var'):
            self.show_scraper_buttons = bool(self.scraper_controls_var.get())
        self._apply_scraper_controls_visibility()
        if hasattr(self, 'scraper_notify_windows_var'):
            self.scraper_notify_windows = bool(self.scraper_notify_windows_var.get())
            try:
                cap_cfg = _load_capture_config()
                cap_cfg["notify_windows"] = self.scraper_notify_windows
                _save_capture_config(cap_cfg)
            except Exception:
                pass
        # Refresh ROA dropdowns
        values = list(self.roa_options.keys())
        self.roa_choice["values"] = values
        if self.roa_choice.get() not in values and values:
            self.roa_choice.set(values[0])
        self._apply_roa_visibility()
        self._apply_stock_form_visibility()
        self._refresh_stock()
        self._refresh_log()
        try:
            self.root.update_idletasks()
            self.root.after(0, self._apply_roa_visibility)
            self.root.after(0, self._refresh_stock)
        except Exception:
            pass
        self.save_data()
        if self.settings_window:
            self.settings_window.destroy()
            self.settings_window = None
    def _mark_stock_form_dirty(self, event: tk.Event) -> None:
        # Any user typing marks the form dirty
        self.stock_form_dirty = True
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
            self.stock_column_widths = widths
        else:
            if getattr(self, "_suspend_log_width_save", False):
                return
            self.log_column_widths = widths
        self._save_config()
    def _persist_tree_widths(self) -> None:
        try:
            if hasattr(self, "stock_tree"):
                self.stock_column_widths = {
                    col: int(self.stock_tree.column(col, option="width")) for col in self.stock_tree["columns"]
                }
            if hasattr(self, "log_tree"):
                self.log_column_widths = {
                    col: int(self.log_tree.column(col, option="width")) for col in self.log_tree["columns"]
                }
        except Exception:
            pass
    def _on_root_configure(self, event: tk.Event) -> None:
        if event.widget is not self.root:
            return
        if self._geometry_save_job is not None:
            try:
                self.root.after_cancel(self._geometry_save_job)
            except Exception:
                pass
        self._geometry_save_job = self.root.after(500, self._persist_geometry)
    def _persist_geometry(self) -> None:
        try:
            self.window_geometry = self.root.geometry()
            self._persist_tree_widths()
            self._save_config()
        except Exception:
            pass
    def apply_theme(self, dark: bool) -> None:
        colors = compute_colors(dark)
        base = colors["bg"]
        text_color = colors["fg"]
        panel = colors["ctrl_bg"]
        entry_bg = colors["ctrl_bg"]
        accent = colors["accent"]
        border = colors.get("border", colors["ctrl_bg"])
        scroll = "#2a2a2a" if dark else "#e6e6e6"
        cursor_color = text_color
        # Prefer dark title bar when dark mode is on
        self.root.after(0, lambda: self._set_dark_title_bar(dark))
        self.current_base_color = base
        self.root.configure(bg=base)
        apply_style_theme(self.style, colors)
        self.style.configure("TCheckbutton", background=base, foreground=text_color)
        self.style.map("TCheckbutton", background=[("active", accent)], foreground=[("active", "#ffffff")])
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
        self.root.option_add("*TCombobox*Listbox*selectBackground", accent)
        self.root.option_add("*TCombobox*Listbox*selectForeground", "#ffffff")
        self.root.option_add("*TCombobox*Entry*selectBackground", entry_bg)
        self.root.option_add("*TCombobox*Entry*selectForeground", text_color)
        self.root.option_add("*TCombobox*Entry*inactiveselectBackground", entry_bg)
        self.root.option_add("*TCombobox*Entry*inactiveselectForeground", text_color)
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
        self.style.map("Treeview", background=[("selected", accent)], foreground=[("selected", "#ffffff")])
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
        if self.stock_sort_column == column:
            self.stock_sort_reverse = not self.stock_sort_reverse
        else:
            self.stock_sort_column = column
            self.stock_sort_reverse = False
        self._apply_stock_sort()
    def _apply_stock_sort(self) -> None:
        # Update heading text with arrow
        arrows = {"asc": " ^", "desc": " v"}
        for col in ("name", "thc", "cbd", "grams"):
            base = {
                "name": "Name",
                "thc": "THC (%)",
                "cbd": "CBD (%)",
                "grams": "Remaining (g)",
            }[col]
            if col == self.stock_sort_column:
                suffix = arrows["desc"] if self.stock_sort_reverse else arrows["asc"]
            else:
                suffix = ""
            self.stock_tree.heading(col, text=base + suffix)
        children = list(self.stock_tree.get_children())
        if not children:
            return
        def sort_key(item: str) -> tuple:
            value = self.stock_tree.set(item, self.stock_sort_column)
            if self.stock_sort_column in {"thc", "cbd", "grams"}:
                try:
                    return (float(value), value)
                except ValueError:
                    return (0.0, value)
            return (value.lower(), value)
        for index, iid in enumerate(sorted(children, key=sort_key, reverse=self.stock_sort_reverse)):
            self.stock_tree.move(iid, "", index)
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
            "min_interval": "N/A",
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
                stats["avg_interval"] = self._format_interval(sum(intervals) / len(intervals))
                stats["min_interval"] = self._format_interval(min(intervals))
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
            ("First dose", stats["first_time"]),
            ("Last dose", stats["last_time"]),
            ("Average interval", stats["avg_interval"]),
            ("Shortest interval", stats["min_interval"]),
            ("Longest interval", stats["max_interval"]),
            ("Largest dose", stats["max_dose"]),
            ("Smallest dose", stats["min_dose"]),
            ("Average dose", stats["avg_dose"]),
            ("Total THC usage", f"{thc_total:.3f} g"),
            ("Average daily THC usage", f"{avg_daily:.3f} g"),
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
                    ("Total CBD usage", f"{cbd_total:.3f} g"),
                    ("Average daily CBD usage", f"{cbd_avg_daily:.3f} g"),
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
        save_tracker_data(data, path=Path(self.data_path), logger=lambda m: print(m))
        self._update_data_mtime()
        self._save_config()
    def load_data(self) -> None:
        data = load_tracker_data(path=Path(self.data_path), logger=lambda m: print(m))
        if not data:
            messagebox.showwarning("No data", f"No tracker data found at {self.data_path}")
            self._update_data_mtime(reset=True)
            return
        self.flowers = {}
        loaded = load_tracker_data(path=Path(self.data_path), logger=lambda m: print(m))
        if loaded:
            data = loaded
        self.flowers = {}
        for item in data.get("flowers", []):
            self.flowers[item["name"]] = Flower(
                name=item["name"],
                thc_pct=float(item.get("thc_pct", 0.0)),
                cbd_pct=float(item.get("cbd_pct", 0.0)),
                grams_remaining=float(item.get("grams_remaining", 0.0)),
            )
        self.logs = data.get("logs", [])
        self.dark_var.set(bool(data.get("dark_mode", False)))
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
        self.show_scraper_buttons = bool(cfg.get("show_scraper_buttons", self.show_scraper_buttons))
        try:
            cap_cfg = _load_capture_config()
            self.scraper_notify_windows = bool(cap_cfg.get("notify_windows", self.scraper_notify_windows))
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
    def _save_config(self) -> None:
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
            "stock_column_widths": self.stock_column_widths,
            "log_column_widths": self.log_column_widths,
            "minimize_to_tray": self.minimize_to_tray,
            "close_to_tray": self.close_to_tray,
            "show_scraper_status_icon": self.show_scraper_status_icon,
            "show_scraper_buttons": self.show_scraper_buttons,
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
        messagebox.showinfo("Backup created", f"Saved {count} files to:\n{zip_path}")
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
        if _has("logs/", "changes.ndjson"):
            lines.append("- Change history log (logs/changes.ndjson)")
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
        config_path = Path(TRACKER_CONFIG_FILE)
        changes_path = logs_dir / "changes.ndjson"
        paths = set()
        if data_dir.exists():
            for path in data_dir.rglob("*"):
                if path.is_file():
                    paths.add(path)
        if config_path.exists():
            paths.add(config_path)
        if changes_path.exists():
            paths.add(changes_path)
        # Include current tracker/library files if they live outside the app data dir.
        for extra in (Path(self.data_path), Path(self.library_data_path)):
            try:
                if extra.exists() and app_dir not in extra.parents:
                    paths.add(extra)
            except Exception:
                pass
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(paths):
                try:
                    if app_dir in path.parents:
                        arcname = path.relative_to(app_dir)
                    else:
                        arcname = Path("external") / path.name
                    zf.write(path, arcname.as_posix())
                except Exception:
                    pass
        return len(paths)
    def _restore_backup_zip(self, zip_path: Path) -> None:
        app_dir = Path(APP_DIR)
        data_dir = app_dir / "data"
        logs_dir = app_dir / "logs"
        tmp_dir = Path(tempfile.mkdtemp(prefix="ft-backup-"))
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmp_dir)
            src_data = tmp_dir / "data"
            src_config = tmp_dir / Path(TRACKER_CONFIG_FILE).name
            src_changes = tmp_dir / "logs" / "changes.ndjson"
            if src_data.exists():
                if data_dir.exists():
                    shutil.rmtree(data_dir, ignore_errors=True)
                shutil.copytree(src_data, data_dir)
            if src_config.exists():
                shutil.copy2(src_config, Path(TRACKER_CONFIG_FILE))
            if src_changes.exists():
                logs_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_changes, logs_dir / "changes.ndjson")
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
    def _prepare_toplevel(self, win: tk.Toplevel) -> None:
        """Prevent white flash when opening toplevels by styling before showing."""
        try:
            win.withdraw()
            win.configure(bg=self.current_base_color)
            win.update_idletasks()
            self._place_window_at_pointer(win)
            # Apply dark title bar before showing to avoid white flash
            self._set_dark_title_bar(self.dark_var.get(), target=win)
            win.deiconify()
            win.lift()
        except Exception:
            # Fallback to basic placement
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
        self._hide_tooltip()
        try:
            self._tooltip_win = tk.Toplevel(self.root)
            self._tooltip_win.wm_overrideredirect(True)
            x = event.x_root + 10 if event else self.root.winfo_pointerx() + 10
            y = event.y_root + 10 if event else self.root.winfo_pointery() + 10
            self._tooltip_win.wm_geometry(f"+{x}+{y}")
            label = ttk.Label(self._tooltip_win, text=text, relief="solid", padding=4)
            label.pack()
        except Exception:
            self._tooltip_win = None
    def _hide_tooltip(self) -> None:
        if self._tooltip_win and tk.Toplevel.winfo_exists(self._tooltip_win):
            self._tooltip_win.destroy()
        self._tooltip_win = None
    def _bind_tooltip(self, widget: tk.Widget, text: str) -> None:
        widget.bind("<Enter>", lambda e: self._show_tooltip(text, e))
        widget.bind("<Leave>", lambda e: self._hide_tooltip())
    def _bind_log_thc_cbd_tooltip(self) -> None:
        if not hasattr(self, "log_tree"):
            return
        message = (
            "THC/CBD values are estimates based on flower potency and selected RoA efficiency."
        )
        def on_motion(event):
            try:
                region = self.log_tree.identify_region(event.x, event.y)
                if region != "heading":
                    self._hide_tooltip()
                    return
                col = self.log_tree.identify_column(event.x)
                if col in ("#5", "#6"):
                    self._show_tooltip(message, event)
                else:
                    self._hide_tooltip()
            except Exception:
                pass
        self.log_tree.bind("<Motion>", on_motion)
        self.log_tree.bind("<Leave>", lambda e: self._hide_tooltip())
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
            self._persist_tree_widths()
            self._save_config()
        except Exception:
            pass
        self._shutdown_children()
        self._destroy_child_windows()
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
            if getattr(sys, "frozen", False):
                args = [sys.executable, "--run-library"]
                cwd = os.path.dirname(sys.executable) or os.getcwd()
            else:
                entry = Path(__file__).resolve().parent / "flowertracker.py"
                if not entry.exists():
                    entry = Path(__file__).resolve()
                args = [sys.executable, str(entry), "--run-library"]
                cwd = os.path.dirname(str(entry)) or os.getcwd()
            subprocess.Popen(args, cwd=cwd)
            if close_tools and self.tools_window and tk.Toplevel.winfo_exists(self.tools_window):
                self.tools_window.destroy()
        except Exception as exc:
            messagebox.showerror("Cannot launch", f"Failed to launch flower library:\n{exc}")
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
            img = _build_scraper_status_image(getattr(self, "child_procs", []))
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
                (btn.grid if self.show_scraper_buttons else btn.grid_remove)()
            except Exception:
                pass
        btn = getattr(self, 'flower_browser_button', None)
        if btn:
            try:
                (btn.grid if self.show_scraper_buttons else btn.grid_remove)()
            except Exception:
                pass

    def _apply_roa_visibility(self) -> None:
        hide = bool(getattr(self, "hide_roa_options", False))
        try:
            if hasattr(self, "log_tree"):
                cols = list(self.log_tree["columns"])
                display = tuple(c for c in cols if c not in ("roa", "thc_mg", "cbd_mg")) if hide else cols
                self.log_tree["displaycolumns"] = display
        except Exception:
            pass
        try:
            if hide:
                if hasattr(self, "roa_label"):
                    self.roa_label.grid_remove()
                if hasattr(self, "roa_choice"):
                    self.roa_choice.grid_remove()
            else:
                if hasattr(self, "roa_label"):
                    self.roa_label.grid()
                if hasattr(self, "roa_choice"):
                    self.roa_choice.grid()
        except Exception:
            pass
        self._apply_mix_button_visibility()

    def _toggle_stock_form(self) -> None:
        self.show_stock_form = not bool(getattr(self, "show_stock_form", True))
        self._apply_stock_form_visibility()
        try:
            self._save_config()
        except Exception:
            pass

    def _apply_stock_form_visibility(self) -> None:
        frame = getattr(self, "stock_form_frame", None)
        btn = getattr(self, "stock_form_toggle", None)
        if frame:
            try:
                (frame.grid if self.show_stock_form else frame.grid_remove)()
            except Exception:
                pass
        if btn:
            try:
                btn.configure(text="˅" if self.show_stock_form else "˄")
            except Exception:
                pass
        self._apply_mix_button_visibility()

    def _apply_mix_button_visibility(self) -> None:
        try:
            btn = getattr(self, "mixed_dose_button", None)
            if btn:
                if getattr(self, "hide_mixed_dose", False):
                    btn.grid_remove()
                else:
                    info = getattr(self, "_mixed_dose_grid", None)
                    btn.grid(**info) if isinstance(info, dict) else btn.grid()
        except Exception:
            pass
        try:
            btn = getattr(self, "mix_stock_button", None)
            if btn:
                if getattr(self, "hide_mix_stock", False):
                    btn.grid_remove()
                else:
                    info = getattr(self, "_mix_stock_grid", None)
                    btn.grid(**info) if isinstance(info, dict) else btn.grid()
        except Exception:
            pass
        try:
            if hasattr(self, "log_tree"):
                cols = list(self.log_tree["columns"])
                widths = self.log_column_widths or {
                    col: int(self.log_tree.column(col, option="width")) for col in cols
                }
                has_prefs = bool(self.log_column_widths)
                display = cols
                if hide:
                    display = tuple(c for c in cols if c not in ("roa", "thc_mg", "cbd_mg"))
                try:
                    self.log_tree["displaycolumns"] = display
                    self.log_tree.configure(displaycolumns=display)
                except Exception:
                    pass
                if hide:
                    if has_prefs:
                        adjusted = dict(widths)
                    if not has_prefs:
                        if not hasattr(self, "_log_widths_before_hide"):
                            self._log_widths_before_hide = dict(widths)
                        hidden_total = sum(
                            widths.get(col, int(self.log_tree.column(col, option="width")))
                            for col in cols
                            if col not in display
                        )
                        adjusted = dict(widths)
                        visible = [c for c in display]
                        base_total = sum(adjusted.get(c, 0) for c in visible) or 1
                        min_widths = {
                            "time": 70,
                            "flower": 160,
                            "grams": 80,
                        }
                        for col in visible:
                            share = adjusted.get(col, 0) / base_total
                            adjusted[col] = max(min_widths.get(col, 50), adjusted.get(col, 0) + int(hidden_total * share))
                else:
                    display = cols
                    restore = getattr(self, "_log_widths_before_hide", None)
                    adjusted = dict(restore or widths)
                    if hasattr(self, "_log_widths_before_hide"):
                        delattr(self, "_log_widths_before_hide")
                self._suspend_log_width_save = True
                for col, width in adjusted.items():
                    try:
                        self.log_tree.column(col, width=width)
                    except Exception:
                        continue
                try:
                    self.log_tree.update_idletasks()
                    self.log_tree["displaycolumns"] = display
                except Exception:
                    pass
                try:
                    self.root.after(300, lambda: setattr(self, "_suspend_log_width_save", False))
                except Exception:
                    self._suspend_log_width_save = False
        except Exception:
            pass

        # Final fallback to ensure ROA/THC/CBD columns are hidden when requested.
        try:
            if hasattr(self, "log_tree"):
                cols = list(self.log_tree["columns"])
                if hide:
                    display = tuple(c for c in cols if c not in ("roa", "thc_mg", "cbd_mg"))
                else:
                    display = cols
                self.log_tree["displaycolumns"] = display
        except Exception:
            pass

    def _apply_scraper_status_visibility(self) -> None:
        label = getattr(self, 'scraper_status_label', None)
        if not label:
            return
        if self.show_scraper_status_icon and self.show_scraper_buttons:
            try:
                label.grid()
            except Exception:
                pass
        else:
            try:
                label.grid_remove()
            except Exception:
                pass
    def _resource_path(self, filename: str) -> str:
        return _resource_path(filename)
    def _set_dark_title_bar(self, enable: bool, target: tk.Tk | tk.Toplevel | None = None) -> None:
        """On Windows 10/11, ask DWM for a dark title bar to match the theme."""
        if os.name != "nt":
            return
        try:
            widget = target or self.root
            hwnd = widget.winfo_id()
            # Walk up to the top-level window; Tk can hand back a child handle
            get_parent = ctypes.windll.user32.GetParent
            parent = get_parent(hwnd)
            while parent:
                hwnd = parent
                parent = get_parent(hwnd)
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19
            BOOL = ctypes.c_int
            value = BOOL(1 if enable else 0)
            # Try newer attribute, fall back to older if needed
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)
            ) != 0:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1, ctypes.byref(value), ctypes.sizeof(value)
                )
        except Exception:
            pass
    def run(self) -> None:
        self.root.mainloop()
    def _update_scraper_status_icon(self) -> None:
        """Update small status dot near the clock to reflect scraper running state."""
        try:
            self._prune_child_procs()
            running, warn = resolve_scraper_status(getattr(self, "child_procs", []))
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
                self._apply_scraper_controls_visibility()
                return
            img = _build_scraper_status_image(getattr(self, "child_procs", []))
            if img and ImageTk is not None:
                tk_img = ImageTk.PhotoImage(img)
                self.scraper_status_img = tk_img
                self.scraper_status_label.configure(image=tk_img, text="")
            else:
                self.scraper_status_label.configure(image="", text="")
        except Exception:
            self.scraper_status_label.configure(image="", text="")
        finally:
            try:
                self.root.after(1500, self._update_scraper_status_icon)
            except Exception:
                pass
