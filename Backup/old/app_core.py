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
from config import DEFAULT_CAPTURE_CONFIG, decrypt_secret, encrypt_secret, load_capture_config, save_capture_config
from exports import cleanup_html_exports, export_html, export_html_auto, export_json_auto, init_exports, set_exports_dir
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
    _load_brand_hints,
    _save_brand_hints,
)
from storage import append_change_log, load_last_change, load_last_parse, save_last_change, save_last_parse
from tray import create_tray_icon, make_tray_image, stop_tray_icon, tray_supported
from ui_settings import open_settings_window
from export_server import start_export_server as srv_start_export_server, stop_export_server as srv_stop_export_server

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(Path(os.getenv("APPDATA", os.path.expanduser("~"))) / "MedicannScraper" / "pw-browsers"))
try:
    import pystray  # type: ignore
    from PIL import Image, ImageDraw  # type: ignore
except Exception:
    pystray = None
    Image = None
    ImageDraw = None
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
ASSETS_DIR = BASE_DIR / "assets"
APP_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "MedicannScraper")
LEGACY_APP_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "FlowerTrack")
DATA_DIR = Path(APP_DIR) / "data"
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(APP_DIR, exist_ok=True)
LOCAL_CONFIG_FILE = Path(__file__).parent / "config.json"
CONFIG_FILE = os.path.join(APP_DIR, "tracker_config.json")
LEGACY_CONFIG_FILE = os.path.join(LEGACY_APP_DIR, "tracker_config.json")
EXPORTS_DIR_DEFAULT = Path(os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "MedicannScraper", "Exports"))
BRAND_HINTS_FILE = DATA_DIR / "parser_database.json"
LEGACY_BRAND_HINTS_FILE_APP = Path(APP_DIR) / "parser_database.json"
LEGACY_BRAND_HINTS_FILE = Path(__file__).parent / "parser_database.json"
LEGACY_BRAND_HINTS_FILE_OLD_APP = Path(LEGACY_APP_DIR) / "parser_database.json"
_BRAND_HINTS_CACHE: list[dict] | None = None
_BADGE_CACHE: dict | None = None
init_parser_paths(BRAND_HINTS_FILE, [LEGACY_BRAND_HINTS_FILE_APP, LEGACY_BRAND_HINTS_FILE_OLD_APP, LEGACY_BRAND_HINTS_FILE])
LAST_PARSE_FILE = DATA_DIR / "last_parse.json"
SERVER_LOG = DATA_DIR / "parser_server.log"
CHANGES_LOG_FILE = DATA_DIR / "changes.ndjson"
LAST_CHANGE_FILE = DATA_DIR / "last_change.txt"

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
        source = CONFIG_FILE if os.path.exists(CONFIG_FILE) else (LEGACY_CONFIG_FILE if os.path.exists(LEGACY_CONFIG_FILE) else None)
        if source:
            with open(source, "r", encoding="utf-8") as fh:
                cfg = json.load(fh)
            if "dark_mode" in cfg:
                return bool(cfg["dark_mode"])
    except Exception:
        pass
    return default

def _save_tracker_dark_mode(enabled: bool) -> None:

    try:
        cfg = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
                cfg = json.load(fh) or {}
        cfg["dark_mode"] = bool(enabled)
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
    except Exception:
        pass


def _load_capture_config() -> dict:
    return load_capture_config(
        Path(CONFIG_FILE),
        [Path(LEGACY_CONFIG_FILE), Path(LOCAL_CONFIG_FILE)],
        ["username", "password", "ha_token"],
        logger=lambda m: _log_debug(f"[config] {m}"),
    )


def _save_capture_config(data: dict) -> None:
    save_capture_config(
        Path(CONFIG_FILE),
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
