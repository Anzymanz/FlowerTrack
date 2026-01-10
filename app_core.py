from __future__ import annotations

import base64
import ctypes
import functools
import html
import http.server
import json
import math
import os
import re
import socketserver
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from capture import ensure_browser_available, ensure_playwright_installed, install_playwright_browsers, start_capture_worker
from config import (
    DEFAULT_CAPTURE_CONFIG,
    load_capture_config,
    load_unified_config,
    save_capture_config,
    save_unified_config,
)
from exports import cleanup_html_exports, export_html, export_html_auto, init_exports, set_exports_dir
from notifications import _maybe_send_windows_notification
from parser import (
    format_brand,
    get_google_medicann_link,
    infer_brand,
    init_parser_paths,
    make_identity_key,
    make_item_key,
    parse_clinic_text,
    seed_brand_db_if_needed,
)
from storage import append_change_log, load_last_change, load_last_parse, save_last_change, save_last_parse, load_last_scrape, save_last_scrape
from tray import create_tray_icon, make_tray_image, stop_tray_icon, tray_supported
from ui_settings import open_settings_window
from export_server import start_export_server as srv_start_export_server, stop_export_server as srv_stop_export_server

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(Path(os.getenv("APPDATA", os.path.expanduser("~"))) / "FlowerTrack" / "pw-browsers"))
try:
    import pystray  # type: ignore
    from PIL import Image, ImageDraw  # type: ignore
except Exception:
    pystray = None
    Image = None
    ImageDraw = None
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
ASSETS_DIR = BASE_DIR / "assets"
APP_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "FlowerTrack")
DATA_DIR = Path(APP_DIR) / "data"
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(APP_DIR, exist_ok=True)
# Unified config path
UNIFIED_CONFIG_FILE = os.path.join(APP_DIR, "flowertrack_config.json")
CONFIG_FILE = UNIFIED_CONFIG_FILE
EXPORTS_DIR_DEFAULT = Path(os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "FlowerTrack", "Exports"))
BRAND_HINTS_FILE = DATA_DIR / "parser_database.json"
init_parser_paths(BRAND_HINTS_FILE)
LAST_PARSE_FILE = DATA_DIR / "last_parse.json"
SERVER_LOG = DATA_DIR / "parser_server.log"
CHANGES_LOG_FILE = DATA_DIR / "changes.ndjson"
LAST_CHANGE_FILE = DATA_DIR / "last_change.txt"
LAST_SCRAPE_FILE = DATA_DIR / "last_scrape.txt"
SCRAPER_STATE_FILE = Path(APP_DIR) / "scraper_state.json"

def _log_debug(msg: str) -> None:

    """Print and persist lightweight debug info for server/startup issues."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {msg}"
    try:
        print(line)
    except Exception:
        pass
    try:
        SERVER_LOG.parent.mkdir(parents=True, exist_ok=True)
        with SERVER_LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass

def _port_ready(host: str, port: int, timeout: float = 0.5) -> bool:

    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False

def _load_tracker_dark_mode(default: bool = True) -> bool:

    try:
        unified = load_unified_config(
            Path(UNIFIED_CONFIG_FILE),
            decrypt_scraper_keys=["username", "password", "ha_token"],
            logger=lambda m: _log_debug(f"[config] {m}"),
        )
        ui_cfg = unified.get("ui", {}) if isinstance(unified, dict) else {}
        if "dark_mode" in ui_cfg:
            return bool(ui_cfg["dark_mode"])
    except Exception:
        pass
    return default

def _save_tracker_dark_mode(enabled: bool) -> None:

    try:
        unified = load_unified_config(
            Path(UNIFIED_CONFIG_FILE),
            decrypt_scraper_keys=["username", "password", "ha_token"],
            write_back=False,
        )
        unified.setdefault("ui", {})["dark_mode"] = bool(enabled)
        unified.setdefault("tracker", {})["dark_mode"] = bool(enabled)
        save_unified_config(Path(UNIFIED_CONFIG_FILE), unified, encrypt_scraper_keys=["username", "password", "ha_token"])
    except Exception:
        pass


def _load_capture_config() -> dict:
    return load_capture_config(
        Path(UNIFIED_CONFIG_FILE),
        ["username", "password", "ha_token"],
        logger=lambda m: _log_debug(f"[config] {m}"),
    )


def _save_capture_config(data: dict) -> None:
    save_capture_config(
        Path(UNIFIED_CONFIG_FILE),
        data,
        ["username", "password", "ha_token"],
    )


def _cleanup_and_record_export(path: Path, max_files: int = 20):
    """Track latest export path and keep exports tidy."""
    try:
        cleanup_html_exports(path.parent, max_files=max_files)
    except Exception:
        pass

def _seed_brand_db_if_needed():
    """On first run, seed the parser database from the bundled copy if none exists."""
    try:
        bundled = Path(BASE_DIR) / "parser_database.json"
        seed_brand_db_if_needed(BRAND_HINTS_FILE, bundled, logger=_log_debug)
    except Exception as exc:
        _log_debug(f"Failed to seed parser database: {exc}")
