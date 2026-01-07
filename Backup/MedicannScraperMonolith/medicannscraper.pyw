import json
import threading
import time
import urllib.parse
import urllib.request
import urllib.error
import re
import html
import base64
import math
import http.server
import socketserver
import functools
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from queue import Queue, Empty
import os
import webbrowser
from datetime import datetime, timezone
import ctypes
from ctypes import wintypes
import sys
import json
from dataclasses import dataclass
import threading as _threading
import time
import subprocess
import os
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(Path(os.getenv("APPDATA", os.path.expanduser("~"))) / "MedicannScraper" / "pw-browsers"))
try:
    from win10toast import ToastNotifier as Win10ToastNotifier  # type: ignore
except Exception:
    Win10ToastNotifier = None
# winotify removed; keep placeholder for guards
WinNotification = None
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
_ASSET_CACHE: dict[str, str] | None = None
LAST_PARSE_FILE = DATA_DIR / "last_parse.json"
SERVER_LOG = DATA_DIR / "parser_server.log"
CHANGES_LOG_FILE = DATA_DIR / "changes.ndjson"
LAST_CHANGE_FILE = DATA_DIR / "last_change.txt"
DEFAULT_CAPTURE_CONFIG = {
    "url": "",
    "username": "",
    "password": "",
    "username_selector": "",
    "password_selector": "",
    "login_button_selector": "",
    "interval_seconds": 60.0,
    "login_wait_seconds": 3.0,
    "post_nav_wait_seconds": 30.0,
    "headless": True,
    "auto_notify_ha": False,
    "ha_webhook_url": "",
    "ha_token": "",
    "notify_price_changes": True,
    "notify_stock_changes": True,
    "notify_windows": True,
    "minimize_to_tray": False,
    "close_to_tray": False,
}

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

class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _dpapi_protect(data: bytes) -> bytes | None:
    """Protect data with Windows DPAPI; returns None on failure."""
    if os.name != "nt":
        return None
    try:
        blob_in = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
        blob_out = DATA_BLOB()
        if ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        ):
            buf = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return buf
    except Exception as exc:
        _log_debug(f"[dpapi] protect failed: {exc}")
    return None


def _dpapi_unprotect(data: bytes) -> bytes | None:
    """Unprotect data with Windows DPAPI; returns None on failure."""
    if os.name != "nt":
        return None
    try:
        blob_in = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
        blob_out = DATA_BLOB()
        if ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        ):
            buf = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return buf
    except Exception as exc:
        _log_debug(f"[dpapi] unprotect failed: {exc}")
    return None


def _encrypt_secret(value: str) -> str:
    if not value:
        return value
    data = value.encode("utf-8")
    protected = _dpapi_protect(data)
    if protected:
        return "enc:" + base64.b64encode(protected).decode("ascii")
    # fallback to base64 obfuscation (still prefixed to avoid plain text)
    return "enc:" + base64.b64encode(data).decode("ascii")


def _decrypt_secret(value: str) -> str:
    if not value:
        return value
    if not isinstance(value, str):
        return str(value)
    if value.startswith("enc:"):
        b = base64.b64decode(value[4:].encode("ascii"))
        unprotected = _dpapi_unprotect(b)
        if unprotected is None:
            try:
                return b.decode("utf-8")
            except Exception:
                return value
        try:
            return unprotected.decode("utf-8")
        except Exception:
            return value
    return value

def _maybe_send_windows_notification(title: str, body: str, icon: Path | None = None, launch_url: str | None = None) -> None:
    """Send a Windows toast using win10toast (blocking until queued)."""
    icon_path = str(icon.resolve()) if icon and icon.exists() else None
    if Win10ToastNotifier is None:
        _log_debug("[toast] win10toast not installed.")
        try:
            App.instance()._log_console("[toast] win10toast not installed.")
        except Exception:
            pass
        return
    try:
        notifier = Win10ToastNotifier()
        notifier.show_toast(title, body, icon_path=icon_path, duration=8, threaded=True)
        _log_debug(f"[toast] sent via win10toast: {title} | {body} (icon={icon_path})")
        try:
            App.instance()._log_console(f"[toast] sent via win10toast: {title}")
        except Exception:
            pass
    except Exception as exc:
        _log_debug(f"[toast] win10toast failed: {exc}")
        try:
            App.instance()._log_console(f"[toast] win10toast failed: {exc}")
        except Exception:
            pass

def _port_ready(host: str, port: int, timeout: float = 0.5) -> bool:

    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False

def _normalize_val(val):

    if val is None:
        return ""
    if isinstance(val, float):
        return f"{val:.4f}"
    return str(val).strip().lower()

def make_item_key(item: dict) -> str:

    """Stable key to identify a product across parses."""
    parts = [
        _normalize_val(item.get("product_id")),
        _normalize_val(item.get("producer")),
        _normalize_val(item.get("brand")),
        _normalize_val(item.get("strain")),
        _normalize_val(item.get("grams")),
        _normalize_val(item.get("ml")),
        _normalize_val(item.get("price")),
        _normalize_val(item.get("product_type")),
        _normalize_val(item.get("strain_type")),
    ]
    return "|".join(parts)

def make_identity_key(item: dict) -> str:

    """Identity key that ignores price so price changes don't look like new items."""
    parts = [
        _normalize_val(item.get("product_id")),
        _normalize_val(item.get("producer")),
        _normalize_val(item.get("brand")),
        _normalize_val(item.get("strain")),
        _normalize_val(item.get("grams")),
        _normalize_val(item.get("ml")),
        _normalize_val(item.get("product_type")),
        _normalize_val(item.get("strain_type")),
        _normalize_val(item.get("is_smalls")),
        _normalize_val(item.get("thc")),
        _normalize_val(item.get("thc_unit")),
        _normalize_val(item.get("cbd")),
        _normalize_val(item.get("cbd_unit")),
    ]
    return "|".join(parts)

def load_last_parse() -> list[dict]:

    try:
        if LAST_PARSE_FILE.exists():
            return json.loads(LAST_PARSE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []

def save_last_parse(items: list[dict]) -> None:

    try:
        LAST_PARSE_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
# ---------------- SEARCH ----------------

def get_google_medicann_link(producer, strain):

    parts = [producer.strip() if producer else '', strain.strip() if strain else '']
    q = " ".join([p for p in parts if p]) + " medbud.wiki"
    return "https://www.google.com/search?q=" + urllib.parse.quote(q)
# ---------------- PARSER ----------------

def _load_brand_hints() -> list[dict]:

    global _BRAND_HINTS_CACHE
    if _BRAND_HINTS_CACHE is not None:
        return _BRAND_HINTS_CACHE
    hints: list[dict] = []
    try:
        if not BRAND_HINTS_FILE.exists():
            for legacy in (LEGACY_BRAND_HINTS_FILE_APP, LEGACY_BRAND_HINTS_FILE_OLD_APP, LEGACY_BRAND_HINTS_FILE):
                if legacy.exists():
                    try:
                        BRAND_HINTS_FILE.write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")
                        break
                    except Exception:
                        pass
        if BRAND_HINTS_FILE.exists():
            text = BRAND_HINTS_FILE.read_text(encoding="utf-8")
            data = json.loads(text)
            if isinstance(data, list):
                hints = [entry for entry in data if isinstance(entry, dict)]
    except Exception:
        pass
    _BRAND_HINTS_CACHE = hints
    return hints

def _save_brand_hints(hints: list[dict]) -> None:

    global _BRAND_HINTS_CACHE
    try:
        BRAND_HINTS_FILE.write_text(json.dumps(hints, indent=2), encoding="utf-8")
        _BRAND_HINTS_CACHE = hints
    except Exception:
        pass

def _match_token(text: str, token: str) -> bool:

    # Use loose boundaries: token separated by non-alphanumerics or full word.
    pattern = rf"(?<![A-Z0-9]){re.escape(token.strip())}(?![A-Z0-9])"
    return re.search(pattern, text, flags=re.I) is not None

def _strip_trailing_code(value: str) -> str:

    """
    Remove trailing short codes (1-3 uppercase letters/numbers) often appended to brands (e.g., strain initials).
    """
    parts = value.strip().split()
    if len(parts) >= 2 and re.fullmatch(r"[A-Z0-9]{1,3}", parts[-1]):
        parts = parts[:-1]
    return " ".join(parts).strip()

def _normalize_brand_key(value: str | None) -> str | None:

    if not value:
        return None
    # Strip trailing strain/lot codes, uppercase, and remove non-alphanumerics for consistent matching.
    stripped = _strip_trailing_code(str(value))
    cleaned = re.sub(r"[^A-Z0-9]", "", stripped.upper())
    return cleaned or None

def _heuristic_trim_brand(value: str) -> str:

    """
    Best-effort removal of trailing product/strain codes when no canonical match is found.
    Stops at the first token that contains a digit or is an uppercase short code (<=4 chars) after the first token.
    """
    tokens = value.strip().split()
    kept = []
    for idx, tok in enumerate(tokens):
        clean_tok = re.sub(r"[^A-Za-z0-9-]", "", tok)
        if idx > 0 and (re.search(r"\d", clean_tok) or (clean_tok.isupper() and len(clean_tok) <= 4)):
            break
        kept.append(tok)
    if kept:
        return " ".join(kept).strip()
    return value.strip()

def canonical_brand(value: str | None) -> str | None:

    """Return canonical brand display name if the value matches known brands."""
    if not value:
        return None
    raw_upper = str(value).upper()
    if re.search(r"\bT2\.0\b|\bT2\b", raw_upper):
        return "Tyson 2.0"
    norm = _normalize_brand_key(value)
    for entry in _load_brand_hints():
        brand_name = entry.get("brand")
        display = entry.get("display") or brand_name
        if not brand_name:
            continue
        if norm and norm == _normalize_brand_key(brand_name):
            return display
        if norm and entry.get("display") and norm == _normalize_brand_key(entry.get("display")):
            return display
    return None

def format_brand(value: str | None) -> str | None:

    """Return a nicely formatted brand for display."""
    if not value:
        return None
    stripped = _strip_trailing_code(str(value))
    # If value starts with a known brand token, keep that portion.
    for entry in _load_brand_hints():
        brand_name = entry.get("brand")
        if not brand_name:
            continue
        tokens = entry.get("patterns") or entry.get("phrases") or []
        tokens = list(tokens) + [brand_name]
        for tok in tokens:
            if not tok:
                continue
            # If the stripped value begins with this token, prefer the canonical display.
            if stripped.upper().startswith(str(tok).upper()):
                display = entry.get("display") or brand_name
                return str(display)
    canonical = canonical_brand(stripped)
    if canonical:
        return canonical
    # Fallback: trim obvious trailing codes and title-case.
    trimmed = _heuristic_trim_brand(stripped)
    return trimmed.title()

def infer_brand(producer: str | None, product_id: str | None, strain: str | None, source_text: str | None = None) -> str | None:

    combined = " ".join([p for p in (producer, product_id, strain, source_text) if p])
    if not combined:
        return None
    upper_text = f" {combined.upper()} "
    # First, see if the raw combined text directly matches a known brand name.
    direct = canonical_brand(combined)
    if direct:
        return direct
    best_match = None
    for entry in _load_brand_hints():
        brand = entry.get("brand")
        tokens = entry.get("patterns") or entry.get("phrases") or []
        if brand:
            tokens = list(tokens) + [brand]
        if not brand or not isinstance(tokens, list):
            continue
        for tok in tokens:
            if not tok:
                continue
            tok_str = str(tok)
            if _match_token(upper_text, tok_str.upper()):
                score = len(tok_str)
                # Prefer longer, more specific tokens; tie-break on brand length.
                if not best_match or score > best_match[0] or (score == best_match[0] and len(str(brand)) > best_match[1]):
                    best_match = (score, len(str(brand)), entry)
    if best_match:
        entry = best_match[2]
        display = entry.get("display") or entry.get("brand")
        if display:
            return str(display)
    return None

def parse_clinic_text(text):

    items = []
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    pending_stock = None
    PRODUCT_KEYWORDS = (
        "CANNABIS FLOWER",
        "CANNABIS OIL",
        "VAPE CARTRIDGE",
        "MEDICAL INHALATION DEVICE",
        "SUBLINGUAL OIL",
    )
    STOCK_KEYWORDS = (
        'IN STOCK',
        'LOW STOCK',
        'OUT OF STOCK',
        'NOT PRESCRIBABLE',
    )
    i = 0
    while i < len(lines):
        line = lines[i]
        if any(sk in line.upper() for sk in STOCK_KEYWORDS) and not any(k in line.upper() for k in PRODUCT_KEYWORDS):
            # Stock marks the start of a block; remember it for the upcoming product line.
            pending_stock = line.strip()
            i += 1
            continue
        if any(k in line.upper() for k in PRODUCT_KEYWORDS):
            m = re.match(r'^(?P<header>[^\(]+)\s*(?:\((?P<product_id>[^)]+)\))?\s*(?P<producer>.*)?$', line)
            header = m.group('header').strip() if m and m.group('header') else line
            product_id = (m.group('product_id').strip() if m and m.group('product_id') else None)
            producer = header
            is_smalls = bool(re.search(r"\b(SMALLS?|SMLS?|SML|SMALL BUDS?|BUDS?)\b", line, re.I))
            if product_id and re.search(r"\b(SMALLS?|SMLS?|SML|BUDS?)\b", product_id, re.I):
                product_id = None
            ut = line.upper()
            if "OIL" in ut:
                product_type = "oil"
            elif "VAPE" in ut:
                product_type = "vape"
            elif "DEVICE" in ut:
                product_type = "device"
            else:
                product_type = "flower"
            strain = None
            strain_type = None
            stock = pending_stock
            next_pending_stock = None
            grams = ml = price = None
            thc = cbd = None
            thc_unit = cbd_unit = None
            stop_index = None
            # Track smalls flag across the block
            smalls_flag = is_smalls
            for j in range(i + 1, min(i + 12, len(lines))):
                l = lines[j]
                if any(k in l.upper() for k in PRODUCT_KEYWORDS):
                    break
                if any(sk in l.upper() for sk in STOCK_KEYWORDS):
                    next_pending_stock = l.strip()
                    stop_index = j
                    break
                if re.search(r"\b(SMALLS?|SMLS?|SML)\b", l, re.I):
                    smalls_flag = True
                if "|" in l and strain is None:
                    left, right = [p.strip() for p in l.split("|", 1)]
                    if not re.search(r"\b(IN STOCK|LOW STOCK|OUT OF STOCK|NOT PRESCRIBABLE|FORMULATION ONLY)\b", left, re.I):
                        strain = left
                        st_meta = right.lower()
                        if 'hybrid' in st_meta:
                            strain_type = 'Hybrid'
                        elif 'indica' in st_meta:
                            strain_type = 'Indica'
                        elif 'sativa' in st_meta:
                            strain_type = 'Sativa'
                        else:
                            whole = l.lower()
                            if 'hybrid' in whole:
                                strain_type = 'Hybrid'
                            elif 'indica' in whole:
                                strain_type = 'Indica'
                            elif 'sativa' in whole:
                                strain_type = 'Sativa'
                            else:
                                strain_type = None
                num = r"(\d+(?:\.\d+)?|\.\d+)"
                gm = re.search(rf"{num}\s*(?:g|grams?)\b", l, re.I)
                mlm = re.search(rf"{num}\s*(?:ml|mL)\b", l, re.I)
                if gm and grams is None:
                    try:
                        grams = float(gm.group(1))
                    except Exception:
                        grams = None
                if mlm and ml is None:
                    try:
                        ml = float(mlm.group(1))
                    except Exception:
                        ml = None
                pm = re.search(rf"(?:£|\$|€|GBP|USD|EUR)\s*{num}", l, re.I)
                if pm and price is None:
                    try:
                        price = float(pm.group(1))
                    except Exception:
                        price = None
                tm = re.search(rf"THC:\s*{num}\s*([a-z/%]+)", l, re.I)
                if tm and thc is None:
                    try:
                        thc = float(tm.group(1))
                    except Exception:
                        thc = None
                    u = tm.group(2).strip().lower().replace(' ', '')
                    if 'mg/ml' in u or '/ml' in u:
                        thc_unit = 'mg/ml'
                    elif 'mg/g' in u or '/g' in u:
                        thc_unit = 'mg/g'
                    elif '%' in u:
                        thc_unit = '%'
                    else:
                        thc_unit = u
                cm = re.search(rf"CBD:\s*{num}\s*([a-z/%]+)", l, re.I)
                if cm and cbd is None:
                    try:
                        cbd = float(cm.group(1))
                    except Exception:
                        cbd = None
                    u2 = cm.group(2).strip().lower().replace(' ', '')
                    if 'mg/ml' in u2 or '/ml' in u2:
                        cbd_unit = 'mg/ml'
                    elif 'mg/g' in u2 or '/g' in u2:
                        cbd_unit = 'mg/g'
                    elif '%' in u2:
                        cbd_unit = '%'
                    else:
                        cbd_unit = u2
            items.append({
                "product_id": product_id,
                "producer": producer,
                "brand": None,
                "strain": strain,
                "strain_type": strain_type,
                "stock": stock,
                "product_type": product_type,
                "is_smalls": smalls_flag,
                "grams": grams,
                "ml": ml,
                "price": price,
                "thc": thc,
                "thc_unit": thc_unit,
                "cbd": cbd,
                "cbd_unit": cbd_unit,
            })
            if stop_index is not None:
                i = stop_index
            pending_stock = next_pending_stock

            def _clean_name(s):
                if not s:
                    return s
                out = str(s)
                out = re.sub(r"\b(IN STOCK|LOW STOCK|OUT OF STOCK|NOT PRESCRIBABLE|NOT PRESCRIBABLE DO NOT SELECT|FORMULATION ONLY|FULL SPECTRUM)\b", "", out, flags=re.I)
                out = re.sub(r"\b(SMALLS?|SMLS?|SML)\b", "", out, flags=re.I)
                out = re.sub(r"\bBUDS?\b", "", out, flags=re.I)
                out = re.sub(r"\bT\d+(?::C?\d+)?\b", "", out, flags=re.I)
                out = re.sub(r"THC[:~\s]*[\d./%]+.*$", "", out, flags=re.I)
                out = re.sub(r"CBD[:~\s]*[\d./%]+.*$", "", out, flags=re.I)
                out = re.sub(r"[\s\\-_/]+", " ", out).strip()
                return out
            raw_producer = items[-1].get("producer")
            raw_strain = items[-1].get("strain")
            raw_product_id = items[-1].get("product_id")
            items[-1]["producer"] = _clean_name(raw_producer)
            items[-1]["strain"] = _clean_name(raw_strain)
            cleaned_pid = _clean_name(raw_product_id)
            if cleaned_pid and re.search(r"\b(SMALLS?|SMLS?|SML|BUDS?)\b", cleaned_pid, re.I):
                cleaned_pid = None
            items[-1]["product_id"] = cleaned_pid
            inferred = infer_brand(raw_producer, raw_product_id, raw_strain, line)
            items[-1]["brand"] = format_brand(inferred or items[-1].get("brand"))
        i += 1
    return items
# ---------------- EXPORT HTML ----------------

def export_html(data, path, fetch_images=False):

    parts = []
    out_path = Path(path)

    def normalize_pct(value, unit):
        if value is None:
            return None
        if not unit:
            return value
        u = unit.lower()
        try:
            if "mg" in u:
                return float(value) / 10.0
            if "%" in u:
                return float(value)
        except Exception:
            return None
        return float(value)
    price_values = [float(it.get("price")) for it in data if isinstance(it.get("price"), (int, float))]
    price_min_bound = math.floor(min(price_values)) if price_values else 0
    price_max_bound = math.ceil(max(price_values)) if price_values else 0
    thc_values: list[float] = []
    for it in data:
        val = normalize_pct(it.get("thc"), it.get("thc_unit"))
        if isinstance(val, (int, float)):
            thc_values.append(float(val))
    thc_min_bound = math.floor(min(thc_values)) if thc_values else 0
    thc_max_bound = math.ceil(max(thc_values)) if thc_values else 0

    def _load_asset(name: str) -> str | None:
        """Return data URI for a given asset name (filename)."""
        global _ASSET_CACHE
        if _ASSET_CACHE is None:
            _ASSET_CACHE = {}
        if name in _ASSET_CACHE:
            return _ASSET_CACHE[name]
        img_path = ASSETS_DIR / name
        try:
            raw = img_path.read_bytes()
            encoded = base64.b64encode(raw).decode("ascii")
            uri = f"data:image/png;base64,{encoded}"
            _ASSET_CACHE[name] = uri
            return uri
        except Exception:
            return None

    def get_badge_src(strain_type: str | None) -> str | None:
        """Return a data URI for the strain badge image if available."""
        if not strain_type:
            return None
        return _load_asset(f"{strain_type.title()}.png")

    def get_type_icon(pt: str | None, theme: str) -> str | None:
        """Return a data URI for product-type icon respecting theme (dark/light)."""
        if not pt:
            return None
        if pt.lower() == "vape":
            return _load_asset("VapeLight.png" if theme == "light" else "VapeDark.png")
        if pt.lower() == "oil":
            return _load_asset("OilLight.png" if theme == "light" else "OilDark.png")
        return None

    def esc(value):
        return html.escape("" if value is None else str(value))

    def esc_attr(value):
        return html.escape("" if value is None else str(value), quote=True)
    parts.append("""
<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Available Medical Cannabis</title>
<style>
:root {
  --bg: #0f1115;
  --fg: #e8e8e8;
  --panel: #1c1f26;
  --border: #2b3040;
  --accent: #7cc7ff;
  --pill: #242a35;
  --hover: #2f3542;
  --muted: #aab2c0;
}
.light {
  --bg: #f6f7fb;
  --fg: #111;
  --panel: #ffffff;
  --border: #d5d8e0;
  --accent: #2f6fed;
  --pill: #e9ecf3;
  --hover: #dde3ef;
  --muted: #555;
}
body{background:var(--bg);color:var(--fg);font-family:Arial;padding:16px;margin:0;transition:background .2s ease,color .2s ease}
.controls{display:flex;gap:8px;align-items:center;margin-bottom:16px;flex-wrap:wrap}
.controls-inner{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.controls-right{margin-left:auto;display:flex;gap:8px;align-items:center}
.basket-summary{padding:6px 10px;border-radius:10px;border:1px solid var(--border);background:var(--panel);color:var(--fg);font-weight:700;min-width:180px;text-align:center}
.btn-basket{padding:6px 10px;border-radius:8px;border:1px solid var(--border);background:var(--panel);color:var(--accent);font-weight:700;cursor:pointer}
.btn-basket:hover{background:var(--hover)}
.btn-basket.added{background:var(--accent);color:var(--bg);border-color:var(--accent)}
.btn-basket.added:hover{background:var(--accent);color:var(--bg)}
.basket-button{padding:8px 12px;border-radius:10px;border:1px solid var(--border);background:var(--panel);color:var(--accent);font-weight:700;cursor:pointer;display:flex;gap:6px;align-items:center}
.basket-button:hover{background:var(--hover)}
.basket-button.active{background:var(--accent);color:var(--bg);border-color:var(--accent)}
.basket-modal{position:fixed;inset:0;background:rgba(0,0,0,0.6);display:none;align-items:center;justify-content:center;z-index:9999}
.basket-panel{background:var(--panel);color:var(--fg);border:1px solid var(--border);border-radius:12px;min-width:320px;max-width:520px;max-height:70vh;overflow:auto;padding:16px;box-shadow:0 10px 30px rgba(0,0,0,0.3)}
.basket-row{display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--border)}
.basket-row:last-child{border-bottom:none}
.basket-title{font-weight:700;font-size:16px;margin-bottom:8px}
.basket-empty{padding:8px 0;color:var(--muted)}
.basket-qty{width:64px}
.type-badge{position:absolute;top:40px;right:8px;width:40px;height:40px;object-fit:contain;opacity:0.9}
.badge-new{position:absolute;top:6px;right:6px;left:auto;display:inline-block;padding:2px 8px;border-radius:999px;background:var(--accent);color:var(--bg);font-size:11px;font-weight:700;white-space:nowrap;max-width:120px;overflow:hidden;text-overflow:ellipsis}
.badge-removed{position:absolute;top:6px;right:6px;left:auto;display:inline-block;padding:2px 8px;border-radius:999px;background:#c0392b;color:#fff;font-size:11px;font-weight:700;white-space:nowrap;max-width:120px;overflow:hidden;text-overflow:ellipsis}
.range-group{display:flex;flex-direction:column;gap:4px;margin:4px 0}
.range-line{display:flex;align-items:center;gap:3px;min-width:140px;position:relative;padding-top:14px;padding-bottom:6px}
.range-slider{position:relative;flex:1;min-width:120px;height:36px}
.range-slider::before{content:"";position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);height:6px;background:var(--border);border-radius:999px;z-index:1}
.range-slider input[type=range]{position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);height:36px;width:100%;margin:0;background:transparent;pointer-events:none;-webkit-appearance:none;appearance:none;z-index:5}
.range-slider input.range-max{z-index:6}
.range-slider input.range-min{z-index:7}
.range-slider input[type=range]::-webkit-slider-thumb{pointer-events:auto;position:relative;z-index:10}
.range-slider input[type=range]::-moz-range-thumb{pointer-events:auto;position:relative;z-index:10}
.range-slider input[type=range]::-webkit-slider-runnable-track{height:6px;background:transparent;border-radius:999px}
.range-slider input[type=range]::-moz-range-track{height:6px;background:transparent;border-radius:999px}
.range-label{font-size:12px;color:var(--muted)}
.range-values{font-size:14px;font-weight:700;color:var(--fg);text-align:center}
.range-tag{font-size:12px;color:var(--muted);min-width:28px;text-align:center}
.range-val{font-size:12px;color:var(--fg);min-width:48px;text-align:center}
.range-title{position:absolute;left:50%;top:6px;transform:translate(-50%,-50%);font-size:12px;color:var(--muted);pointer-events:none}
input.search-box{padding:8px 10px;border-radius:10px;border:1px solid var(--border);background:var(--panel);color:var(--fg);min-width:200px}
button{padding:8px 10px;border-radius:8px;border:1px solid var(--border);background:var(--panel);color:var(--accent);font-weight:600;cursor:pointer;transition:background .2s ease,color .2s ease}
button.btn-filter{background:var(--panel);color:var(--accent)}
button.btn-filter.active{background:var(--accent);color:var(--bg);background-image:none}
button:hover{background:var(--hover)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}
.card{background:var(--panel);padding:12px;border-radius:12px;border:1px solid var(--border);position:relative;display:flex;flex-direction:column;min-height:320px}
.card-new{background:#0f2616;border-color:#1f5d35}
.card-removed{background:#2b1313;border-color:#6a1f1f}
.card-fav{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent) inset}
.light .card-removed{background:#ffe6e6;border-color:#e0b3b3}
.light .card-new{background:#e6ffef;border-color:#b3e0c5}
.pill{display:inline-block;padding:2px 8px;border-radius:999px;background:var(--pill);margin:4px 6px 0 0;font-size:13px;color:var(--fg)}
.price-up{background:#3a1a1a;color:#f6c6c6}
.price-down{background:#15331e;color:#b7f0c8}
.light .price-up{background:#ffdede;color:#b20000}
.light .price-down{background:#dff5e6;color:#116a2b}
.card-price-up{border-color:#a13535;box-shadow:0 0 0 1px #a13535 inset}
.card-price-down{border-color:#2f7a46;box-shadow:0 0 0 1px #2f7a46 inset}
.card-content{display:flex;flex-direction:column;gap:6px;margin-top:auto}
.card-title{display:block;margin:4px 0 6px 0;padding-right:32px;overflow-wrap:break-word;word-wrap:break-word}
.brand-line{display:block;margin:2px 0;padding-right:32px;overflow-wrap:break-word;word-wrap:break-word}
.badge-price-up{display:inline-block;position:relative;top:0;left:0;padding:2px 8px;border-radius:999px;background:#3a1a1a;color:#f6c6c6;font-size:11px;font-weight:700;margin-right:6px}
.badge-price-down{display:inline-block;position:relative;top:0;left:0;padding:2px 8px;border-radius:999px;background:#15331e;color:#b7f0c8;font-size:11px;font-weight:700;margin-right:6px}
.light .badge-price-up{background:#ffdede;color:#b20000}
.light .badge-price-down{background:#dff5e6;color:#116a2b}
.card-actions{margin-top:auto;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.search{display:inline-flex;align-items:center;justify-content:center;padding:8px 12px;border-radius:8px;border:1px solid var(--border);background:var(--panel);color:var(--accent);text-decoration:none;font-weight:700;min-width:140px}
.search:hover{background:var(--panel);color:var(--accent)}
.small{font-size:13px;opacity:.85;color:var(--muted)}
.stock-indicator{display:inline-block;width:14px;height:14px;min-width:14px;flex:0 0 14px;border-radius:50%;margin-right:10px;vertical-align:middle}
.stock-in{background:#2ecc71}
.stock-low{background:#f5a623}
.stock-out{background:#e74c3c}
.stock-not-prescribable{background:#999}
.strain-badge{position:absolute;top:40px;right:8px;width:40px;height:40px;object-fit:contain;opacity:0.9}
.fav-btn{position:absolute;bottom:10px;right:10px;border:none;background:transparent;color:var(--muted);font-size:30px;cursor:pointer;line-height:1}
.fav-btn.fav-on{color:var(--accent)}
.fav-btn:hover{background:transparent;color:inherit}
.badge-new{position:absolute;top:6px;right:6px;padding:2px 8px;border-radius:999px;background:var(--accent);color:var(--bg);font-size:11px;font-weight:700}
.badge-removed{position:absolute;top:6px;right:6px;padding:2px 8px;border-radius:999px;background:#c0392b;color:#fff;font-size:11px;font-weight:700}
h3.card-title{margin-right:48px;}
</style>
<script>
const state = { key: 'price', asc: false };
function updateSortButtons() {
    document.querySelectorAll('.sort-btn').forEach(btn => {
        const k = btn.dataset.sort;
        if (k === state.key) {
            const arrow = state.asc ? "↑" : "↓";
            btn.textContent = `Sort by ${k.toUpperCase()} ${arrow}`;
            btn.classList.add('active');
        } else {
            btn.textContent = `Sort by ${k.toUpperCase()}`;
            btn.classList.remove('active');
        }
    });
}
function sortCards(key, btn) {
    if (key === undefined || key === null) key = state.key || 'price';
    const grid = document.getElementById("grid");
    const cards = Array.from(grid.children);
    if (state.key === key) {
        state.asc = !state.asc;
    } else {
        state.key = key;
        state.asc = true;
    }
    const dir = state.asc ? 1 : -1;
    cards.sort((a, b) => {
        const avRaw = parseFloat(a.dataset[key]);
        const bvRaw = parseFloat(b.dataset[key]);
        const av = Number.isFinite(avRaw) ? avRaw : (key === 'price' ? Number.POSITIVE_INFINITY : 0);
        const bv = Number.isFinite(bvRaw) ? bvRaw : (key === 'price' ? Number.POSITIVE_INFINITY : 0);
        return (av - bv) * dir;
    });
    cards.forEach(c => grid.appendChild(c));
    updateSortButtons();
}
let activeTypes = new Set(['flower','oil','vape']);
let activeStrains = new Set(['Indica','Sativa','Hybrid']);
let favoritesOnly = false;
let showSmalls = true;
let searchTerm = "";
const priceMinBound = {price_min_bound};
const priceMaxBound = {price_max_bound};
let priceMinSel = priceMinBound;
let priceMaxSel = priceMaxBound;
const thcMinBound = {thc_min_bound};
const thcMaxBound = {thc_max_bound};
let thcMinSel = thcMinBound;
let thcMaxSel = thcMaxBound;
function applyFilters() {
    const grid = document.getElementById('grid');
    const cards = Array.from(grid.children);
    const term = searchTerm.trim().toLowerCase();
    cards.forEach(c => {
        const pt = (c.dataset.pt || '').toLowerCase();
        const isRemoved = c.dataset.removed === '1';
        const st = c.dataset.strainType || '';
        const favKey = c.dataset.favkey || '';
        const isSmalls = c.dataset.smalls === '1';
        const priceVal = parseFloat(c.dataset.price);
        const thcVal = parseFloat(c.dataset.thc);
        const priceOk = Number.isFinite(priceVal) ? (priceVal >= priceMinSel && priceVal <= priceMaxSel) : true;
        const thcOk = Number.isFinite(thcVal) ? (thcVal >= thcMinSel && thcVal <= thcMaxSel) : true;
        const showType = isRemoved ? true : activeTypes.has(pt);
        const showStrain = (!st) ? true : activeStrains.has(st);
        const text = (c.dataset.strain || '') + ' ' + (c.dataset.brand || '') + ' ' + (c.dataset.producer || '') + ' ' + (c.dataset.productId || '');
        const matchesSearch = term ? text.toLowerCase().includes(term) : true;
        const favOk = favoritesOnly ? favorites.has(favKey) : true;
        const smallsOk = showSmalls || !isSmalls;
        c.style.display = (showType && showStrain && matchesSearch && priceOk && thcOk && favOk && smallsOk) ? '' : 'none';
    });
}
function handleSearch(el) {
    searchTerm = el.value || "";
    applyFilters();
}
function toggleType(type, btn) {
    if (activeTypes.has(type)) {
        activeTypes.delete(type);
        btn.classList.remove('active');
    } else {
        activeTypes.add(type);
        btn.classList.add('active');
    }
    applyFilters();
}
function toggleStrain(kind, btn) {
    if (activeStrains.has(kind)) {
        activeStrains.delete(kind);
        btn.classList.remove('active');
    } else {
        activeStrains.add(kind);
        btn.classList.add('active');
    }
    applyFilters();
}
function toggleFavorites(btn) {
    favoritesOnly = !favoritesOnly;
    btn.classList.toggle('active', favoritesOnly);
    applyFilters();
}
function toggleSmalls(btn) {
    showSmalls = !showSmalls;
    btn.classList.toggle('active', showSmalls);
    applyFilters();
}
let favorites = new Set();
let basketTotal = 0;
let basketCount = 0;
let basket = new Map();
function refreshBasketButtons() {
    document.querySelectorAll('.card').forEach(card => {
        const key = card.dataset.key || card.dataset.favkey || card.dataset.productId || card.dataset.strain;
        const btn = card.querySelector('.btn-basket');
        if (!btn) return;
        const qty = (key && basket.has(key)) ? (basket.get(key).qty || 0) : 0;
        if (qty > 0) {
            btn.classList.add('added');
            btn.textContent = `${qty} in basket`;
        } else {
            btn.classList.remove('added');
            btn.textContent = 'Add to basket';
        }
    });
}
function updateBasketUI() {
    const c = document.getElementById('basketCount');
    const t = document.getElementById('basketTotal');
    basketCount = 0;
    basketTotal = 0;
    basket.forEach((item) => {
        basketCount += item.qty;
        basketTotal += item.price * item.qty;
    });
    if (c) c.textContent = basketCount;
    if (t) t.textContent = basketTotal.toFixed(2);
}
function addToBasket(btn) {
    const card = btn.closest('.card');
    if (!card) return;
    const price = parseFloat(card.dataset.price);
    if (!Number.isFinite(price)) return;
    const key = card.dataset.key || card.dataset.favkey || card.dataset.productId || card.dataset.strain || String(Math.random());
    const name = (card.dataset.strain || "").trim();
    const brand = (card.dataset.brand || "").trim();
    const existing = basket.get(key);
    if (existing) {
        existing.qty += 1;
        basket.set(key, existing);
    } else {
        basket.set(key, { key, name, brand, price, qty: 1 });
    }
    updateBasketUI();
    renderBasketModal(false);
    refreshBasketButtons();
}
function toggleBasket() {
    renderBasketModal(true);
    const btn = document.getElementById('basketButton');
    if (btn) btn.classList.add('active');
}
function renderBasketModal(show) {
    let modal = document.getElementById('basketModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'basketModal';
        modal.className = 'basket-modal';
        document.body.appendChild(modal);
    }
    const rows = [];
    if (basket.size === 0) {
        rows.push("<div class='basket-empty'>Basket is empty.</div>");
    } else {
        basket.forEach((item) => {
            rows.push(`
            <div class='basket-row' data-key='${item.key}'>
              <div style='flex:1;'>
                <div><strong>${item.name || 'Item'}</strong></div>
                <div class='small'>${item.brand || ''}</div>
                <div class='small'>£${item.price.toFixed(2)}</div>
              </div>
              <input class='basket-qty' type='number' min='0' value='${item.qty}' onchange='updateBasketQty("${item.key}", this.value)' />
              <button class='btn-basket' onclick='removeFromBasket("${item.key}")'>Remove</button>
            </div>
            `);
        });
    }
    modal.innerHTML = `
      <div class='basket-panel'>
        <div class='basket-title'>Basket</div>
        ${rows.join("\\n")}
        <div style='margin-top:12px;display:flex;justify-content:space-between;align-items:center;'>
          <div><strong>Total:</strong> £${basketTotal.toFixed(2)} (${basketCount} item${basketCount===1?"":"s"})</div>
          <button class='btn-basket' onclick='closeBasket()'>Close</button>
        </div>
      </div>
    `;
    if (show) {
        modal.style.display = 'flex';
    }
}
function closeBasket() {
    const modal = document.getElementById('basketModal');
    if (modal) modal.style.display = 'none';
    const btn = document.getElementById('basketButton');
    if (btn) btn.classList.remove('active');
}
function updateBasketQty(key, val) {
    const qty = parseInt(val, 10);
    if (!basket.has(key)) return;
    if (!Number.isFinite(qty) || qty <= 0) {
        basket.delete(key);
    } else {
        const item = basket.get(key);
        item.qty = qty;
        basket.set(key, item);
    }
    updateBasketUI();
    renderBasketModal(false);
    refreshBasketButtons();
}
function removeFromBasket(key) {
    if (basket.has(key)) basket.delete(key);
    updateBasketUI();
    renderBasketModal(false);
    refreshBasketButtons();
}
function loadFavorites() {
    try {
        const rawNew = localStorage.getItem('ft_favs_global');
        const rawOld = localStorage.getItem('ft_favs');
        const cookie = (document.cookie || '').split(';').map(s=>s.trim()).find(s=>s.startsWith('ft_favs_global='));
        const cookieVal = cookie ? decodeURIComponent(cookie.split('=').slice(1).join('=')) : null;
        const arrNew = rawNew ? JSON.parse(rawNew) : [];
        const arrOld = rawOld ? JSON.parse(rawOld) : [];
        const arrCookie = cookieVal ? JSON.parse(cookieVal) : [];
        const merged = Array.from(new Set([...(Array.isArray(arrOld)?arrOld:[]), ...(Array.isArray(arrNew)?arrNew:[]), ...(Array.isArray(arrCookie)?arrCookie:[])]));
        favorites = new Set(merged);
    } catch (e) {}
}
function saveFavorites() {
    try {
        localStorage.setItem('ft_favs_global', JSON.stringify(Array.from(favorites)));
        document.cookie = `ft_favs_global=${encodeURIComponent(JSON.stringify(Array.from(favorites)))}; path=/; max-age=${60*60*24*365}`;
    } catch (e) {}
}
function applyFavState(card) {
    if (!card) return;
    const key = card.dataset.favkey;
    const btn = card.querySelector('.fav-btn');
    const isFav = key && favorites.has(key);
    card.classList.toggle('card-fav', isFav);
    if (btn) {
        btn.textContent = isFav ? '★' : '☆';
        btn.classList.toggle('fav-on', isFav);
    }
}
function toggleFavorite(btn) {
    const card = btn.closest('.card');
    if (!card) return;
    const key = card.dataset.favkey;
    if (!key) return;
    if (favorites.has(key)) {
        favorites.delete(key);
    } else {
        favorites.add(key);
    }
    saveFavorites();
    applyFavState(card);
    // Immediately persist and reflect without needing refresh
    document.cookie = `ft_favs_global=${encodeURIComponent(JSON.stringify(Array.from(favorites)))}; path=/; max-age=${60*60*24*365}`;
}
function resetFilters() {
    activeTypes = new Set(['flower','oil','vape']);
    activeStrains = new Set(['Indica','Sativa','Hybrid']);
    document.querySelectorAll('.btn-filter').forEach(b => b.classList.add('active'));
    favoritesOnly = false;
    showSmalls = true;
    // Reset sliders
    const priceMinEl = document.getElementById('priceMinRange');
    const priceMaxEl = document.getElementById('priceMaxRange');
    const thcMinEl = document.getElementById('thcMinRange');
    const thcMaxEl = document.getElementById('thcMaxRange');
    if (priceMinEl && priceMaxEl) {
        priceMinSel = priceMinBound;
        priceMaxSel = priceMaxBound;
        priceMinEl.value = priceMinBound;
        priceMaxEl.value = priceMaxBound;
        priceMinEl.dispatchEvent(new Event('input'));
        priceMaxEl.dispatchEvent(new Event('input'));
    }
    if (thcMinEl && thcMaxEl) {
        thcMinSel = thcMinBound;
        thcMaxSel = thcMaxBound;
        thcMinEl.value = thcMinBound;
        thcMaxEl.value = thcMaxBound;
        thcMinEl.dispatchEvent(new Event('input'));
        thcMaxEl.dispatchEvent(new Event('input'));
    }
    applyFilters();
}
function applyTheme(saved) {
    const body = document.body;
    const useLight = saved === true || saved === 'light';
    body.classList.toggle('light', useLight);
    localStorage.setItem('ft_theme', useLight ? 'light' : 'dark');
    const btn = document.getElementById('themeToggle');
    if (btn) btn.textContent = useLight ? 'Use dark theme' : 'Use light theme';
    // Swap type icons to match theme
    document.querySelectorAll('[data-theme-icon]').forEach(img => {
        const theme = img.getAttribute('data-theme-icon');
        img.style.display = theme === (useLight ? 'light' : 'dark') ? '' : 'none';
    });
}
function toggleTheme() {
    const current = localStorage.getItem('ft_theme') || 'dark';
    applyTheme(current !== 'light');
}
document.addEventListener('DOMContentLoaded', () => {
    const saved = localStorage.getItem('ft_theme');
applyTheme(saved === 'light');
    loadFavorites();
    document.querySelectorAll('.card').forEach(applyFavState);
    updateBasketUI();
    updateSortButtons();
    sortCards(state.key);
    // Init ranges
    const priceMinEl = document.getElementById('priceMinRange');
    const priceMaxEl = document.getElementById('priceMaxRange');
    const thcMinEl = document.getElementById('thcMinRange');
    const thcMaxEl = document.getElementById('thcMaxRange');
    const clamp = (val, min, max) => {
        const n = parseFloat(val);
        if (!Number.isFinite(n)) return min;
        return Math.min(Math.max(n, min), max);
    };
    const updatePriceLabel = () => {
        const label = document.getElementById('priceLabel');
        const minVal = document.getElementById('priceMinVal');
        const maxVal = document.getElementById('priceMaxVal');
        if (label) label.textContent = `£${priceMinSel.toFixed(0)} – £${priceMaxSel.toFixed(0)}`;
        if (minVal) minVal.textContent = `£${priceMinSel.toFixed(0)}`;
        if (maxVal) maxVal.textContent = `£${priceMaxSel.toFixed(0)}`;
    };
    const updateThcLabel = () => {
        const label = document.getElementById('thcLabel');
        const minVal = document.getElementById('thcMinVal');
        const maxVal = document.getElementById('thcMaxVal');
        if (label) label.textContent = `${thcMinSel.toFixed(0)}% – ${thcMaxSel.toFixed(0)}%`;
        if (minVal) minVal.textContent = `${thcMinSel.toFixed(0)}%`;
        if (maxVal) maxVal.textContent = `${thcMaxSel.toFixed(0)}%`;
    };
    if (priceMinEl && priceMaxEl) {
        priceMinEl.min = priceMinBound; priceMinEl.max = priceMaxBound; priceMinEl.value = priceMinBound;
        priceMaxEl.min = priceMinBound; priceMaxEl.max = priceMaxBound; priceMaxEl.value = priceMaxBound;
        const syncPrice = () => {
            priceMinSel = clamp(parseFloat(priceMinEl.value), priceMinBound, priceMaxBound);
            priceMaxSel = clamp(parseFloat(priceMaxEl.value), priceMinSel, priceMaxBound);
            if (parseFloat(priceMinEl.value) > priceMaxSel) priceMinEl.value = priceMaxSel;
            priceMaxEl.value = priceMaxSel;
            priceMinEl.value = priceMinSel;
            updatePriceLabel();
            applyFilters();
        };
        priceMinEl.addEventListener('input', syncPrice);
        priceMaxEl.addEventListener('input', syncPrice);
        updatePriceLabel();
    }
    if (thcMinEl && thcMaxEl) {
        thcMinEl.min = thcMinBound; thcMinEl.max = thcMaxBound; thcMinEl.value = thcMinBound;
        thcMaxEl.min = thcMinBound; thcMaxEl.max = thcMaxBound; thcMaxEl.value = thcMaxBound;
        const syncThc = () => {
            thcMinSel = clamp(parseFloat(thcMinEl.value), thcMinBound, thcMaxBound);
            thcMaxSel = clamp(parseFloat(thcMaxEl.value), thcMinSel, thcMaxBound);
            if (parseFloat(thcMinEl.value) > thcMaxSel) thcMinEl.value = thcMaxSel;
            thcMaxEl.value = thcMaxSel;
            thcMinEl.value = thcMinSel;
            updateThcLabel();
            applyFilters();
        };
        thcMinEl.addEventListener('input', syncThc);
        thcMaxEl.addEventListener('input', syncThc);
        updateThcLabel();
    }
    applyFilters();
});
</script>
</head><body>
<h1>Available Medical Cannabis</h1>
<div class='controls'>
  <div class='controls-inner'>
    <button class='sort-btn' data-sort="price" onclick="sortCards('price', this)">Sort by PRICE</button>
    <button class='sort-btn' data-sort="thc" onclick="sortCards('thc', this)">Sort by THC</button>
    <button class='sort-btn' data-sort="cbd" onclick="sortCards('cbd', this)">Sort by CBD</button>
    <input class="search-box" type="text" placeholder="Search strain or producer" oninput="handleSearch(this)" />
    <button class='btn-filter active' onclick="toggleType('flower', this)">Flower</button>
    <button class='btn-filter active' onclick="toggleType('oil', this)">Oil</button>
    <button class='btn-filter active' onclick="toggleType('vape', this)">Vape</button>
    <button class='btn-filter active' onclick="toggleStrain('Indica', this)">Indica</button>
    <button class='btn-filter active' onclick="toggleStrain('Sativa', this)">Sativa</button>
    <button class='btn-filter active' onclick="toggleStrain('Hybrid', this)">Hybrid</button>
    <button class='btn-filter' onclick="toggleFavorites(this)">Favorites</button>
    <button class='btn-filter active' onclick="toggleSmalls(this)">Smalls</button>
    <button onclick="resetFilters()">Reset</button>
    <div class="range-group">
      <div class="range-line">
        <span class="range-val" id="priceMinVal"></span>
        <span class="range-tag">Min</span>
        <div class="range-slider">
          <input class="range-min" type="range" id="priceMinRange" step="1">
          <input class="range-max" type="range" id="priceMaxRange" step="1">
        </div>
        <span class="range-tag">Max</span>
        <span class="range-val" id="priceMaxVal"></span>
        <div class="range-title">Price</div>
      </div>
      <div class="range-values" id="priceLabel"></div>
    </div>
    <div class="range-group">
      <div class="range-line">
        <span class="range-val" id="thcMinVal"></span>
        <span class="range-tag">Min</span>
        <div class="range-slider">
          <input class="range-min" type="range" id="thcMinRange" step="1">
          <input class="range-max" type="range" id="thcMaxRange" step="1">
        </div>
        <span class="range-tag">Max</span>
        <span class="range-val" id="thcMaxVal"></span>
        <div class="range-title">THC %</div>
      </div>
      <div class="range-values" id="thcLabel"></div>
    </div>
  </div>
<div class='controls-right'>
    <button class="basket-button" id="basketButton" onclick="toggleBasket()">Basket: <span id="basketCount">0</span> | £<span id="basketTotal">0.00</span></button>
    <button id="themeToggle" onclick="toggleTheme()">Use light theme</button>
  </div>
</div>
<div class='grid' id='grid'>
""")

    def fav_key_for(item: dict) -> str:
        """Stable favorite key based on brand + strain (fallback to producer/product_id)."""

        def norm(s: str | None) -> str:
            if not s:
                return ""
            return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")
        brand_norm = norm(format_brand(item.get("brand") or item.get("producer") or ""))
        strain_norm = norm(item.get("strain") or "")
        if brand_norm or strain_norm:
            combo = f"{brand_norm}-{strain_norm}".strip("-")
        else:
            prod_norm = norm(item.get("producer"))
            pid_norm = norm(item.get("product_id"))
            combo = f"{prod_norm}-{pid_norm}".strip("-")
        if not combo:
            combo = f"item-{abs(hash(str(item)))%10_000_000}"
        return combo
    for it in data:
        price = it.get("price")
        if it.get("is_removed") and not isinstance(price, (int, float)):
            price = 0
        grams = it.get("grams")
        ppg = (price / grams) if isinstance(price, (int, float)) and isinstance(grams, (int, float)) and grams else None
        qty = ""
        if it.get("grams") is not None:
            qty = f"{it['grams']}g"
        elif it.get("ml") is not None:
            qty = f"{it['ml']}ml"

        def normalize_pct(value, unit):
            if value is None:
                return None
            if not unit:
                return value
            u = unit.lower()
            try:
                if 'mg' in u:
                    return float(value) / 10.0
                if '%' in u:
                    return float(value)
            except Exception:
                return None
            return float(value)
        thc_raw = it.get('thc')
        thc_unit = it.get('thc_unit')
        cbd_raw = it.get('cbd')
        cbd_unit = it.get('cbd_unit')
        thc_pct = normalize_pct(thc_raw, thc_unit)
        cbd_pct = normalize_pct(cbd_raw, cbd_unit)

        def clean_name(s):
            if not s:
                return s
            out = str(s)
            out = re.sub(r"\b(IN STOCK|LOW STOCK|OUT OF STOCK|NOT PRESCRIBABLE|NOT PRESCRIBABLE DO NOT SELECT|FORMULATION ONLY|FULL SPECTRUM)\b", "", out, flags=re.I)
            out = re.sub(r"\b(SMALLS?|SMLS?|SML)\b", "", out, flags=re.I)
            out = re.sub(r"\bT\d+(?::C?\d+)?\b", "", out, flags=re.I)
            out = re.sub(r"THC[:~\s]*[\d./%]+.*$", "", out, flags=re.I)
            out = re.sub(r"CBD[:~\s]*[\d./%]+.*$", "", out, flags=re.I)
            out = re.sub(r"[\s\\-_/]+", " ", out).strip()
            return out
        strain_name = clean_name(it.get('strain') or '')
        if it.get("brand"):
            b = format_brand(it.get("brand"))
            if b and strain_name:
                pat = re.compile(re.escape(str(b)), re.I)
                strain_name = pat.sub("", strain_name).strip()
                first_tok = b.split()[0]
                strain_name = re.sub(rf"\b{re.escape(first_tok)}\b", "", strain_name, flags=re.I).strip()
                strain_name = re.sub(r"\s{2,}", " ", strain_name).strip()
        heading = strain_name or clean_name(it.get('product_id') or it.get('producer') or it.get('product_type') or '-')
        if it.get("is_smalls") and heading:
            heading = f"{heading} (Smalls)"
        brand = format_brand(it.get('brand') or it.get('producer') or '')

        def display_strength(raw, unit, pct):
            if raw is None:
                return '?'
            base = f"{raw} {unit or ''}".strip()
            if pct is not None and (unit and '%' not in unit):
                return f"{base} ({pct:.1f}%)"
            return base
        disp_thc = display_strength(thc_raw, thc_unit, thc_pct)
        disp_cbd = display_strength(cbd_raw, cbd_unit, cbd_pct)
        data_price_attr = '' if price is None else str(price)
        data_thc_attr = '' if thc_pct is None else f"{thc_pct}"
        data_cbd_attr = '' if cbd_pct is None else f"{cbd_pct}"
        card_key = make_identity_key(it)
        fav_key = fav_key_for(it)
        smalls_tag = "<span class='pill'>Smalls</span>" if it.get("is_smalls") else ""
        price_delta = it.get("price_delta")
        price_class = "pill"
        delta_text = ""
        if isinstance(price_delta, (int, float)) and price is not None:
            if price_delta > 0:
                price_class += " price-up"
                delta_text = f" (+£{abs(price_delta):.2f})"
            elif price_delta < 0:
                price_class += " price-down"
                delta_text = f" (-£{abs(price_delta):.2f})"
        price_label = "£?" if price is None else f"£{price:.2f}"
        price_pill = f"<span class='{price_class}' data-pricedelta='{esc_attr(price_delta if price_delta is not None else '')}'>{esc(price_label + delta_text)}</span>"
        price_badge = ""
        price_border_class = ""
        if isinstance(price_delta, (int, float)) and price_delta:
            badge_cls = "badge-price-up" if price_delta > 0 else "badge-price-down"
            badge_text = f"New price {'+' if price_delta>0 else '-'}£{abs(price_delta):.2f}"
            price_badge = f"<span class='{badge_cls}'>{esc(badge_text)}</span>"
            price_border_class = " card-price-up" if price_delta > 0 else " card-price-down"
        stock_indicator = (
            f"<span class='stock-indicator "
            f"{('stock-not-prescribable' if (it.get('stock') and 'NOT' in (it.get('stock') or '').upper()) else ('stock-in' if (it.get('stock') and 'IN STOCK' in (it.get('stock') or '').upper()) else ('stock-low' if (it.get('stock') and 'LOW' in (it.get('stock') or '').upper()) else ('stock-out' if (it.get('stock') and 'OUT' in (it.get('stock') or '').upper()) else ''))))}"
            f"' title='{esc(it.get('stock') or '')}'></span>"
        )
        heading_html = f"{stock_indicator}{esc(heading)}"
        card_classes = "card card-removed" if it.get("is_removed") else ("card card-new" if it.get("is_new") else "card")
        parts.append(f"""
    <div class='{card_classes}{price_border_class}' style='position:relative;'
          data-price='{esc_attr(data_price_attr)}'
      data-thc='{esc_attr(data_thc_attr)}'
      data-cbd='{esc_attr(data_cbd_attr)}'
      data-pt='{esc_attr((it.get("product_type") or "").lower())}'
      data-strain-type='{esc_attr(it.get("strain_type") or "")}'
      data-strain='{esc_attr(it.get("strain") or "")}'
      data-brand='{esc_attr(brand or "")}'
      data-producer='{esc_attr(it.get("producer") or "")}'
      data-product-id='{esc_attr(it.get("product_id") or "")}'
      data-stock='{esc_attr((it.get("stock") or "").strip())}'
      data-key='{esc_attr(card_key)}'
      data-favkey='{esc_attr(fav_key)}'
      data-smalls='{1 if it.get("is_smalls") else 0}'
      data-removed='{1 if it.get("is_removed") else 0}'>
    <button class='fav-btn' onclick='toggleFavorite(this)' title='Favorite this item'>☆</button>
    {("<img class='type-badge' data-theme-icon='dark' src='" + esc_attr(get_type_icon(it.get('product_type'), 'dark')) + "' alt='" + esc_attr(it.get('product_type') or '') + "' />") if get_type_icon(it.get('product_type'), 'dark') else ""}
    {("<img class='type-badge' data-theme-icon='light' src='" + esc_attr(get_type_icon(it.get('product_type'), 'light')) + "' alt='" + esc_attr(it.get('product_type') or '') + "' style='display:none;' />") if get_type_icon(it.get('product_type'), 'light') else ""}
    {("<img class='strain-badge' src='" + esc_attr(get_badge_src(it.get('strain_type'))) + "' alt='" + esc_attr(it.get('strain_type') or '') + "' />") if get_badge_src(it.get("strain_type")) else ""}
    {("<span class='badge-new'>New</span>") if it.get("is_new") else ("<span class='badge-removed'>Removed</span>" if it.get("is_removed") else "")}
    <div style='display:flex;flex-direction:column;align-items:flex-start;gap:4px;'>
      {price_badge}
      <h3 class='card-title'>{heading_html}</h3>
    </div>
<a class='search' style='position:absolute;bottom:12px;right:44px;font-size:18px;padding:6px 8px;border-radius:6px;min-width:auto;width:28px;height:28px;display:flex;align-items:center;justify-content:center;border:none' href='{esc_attr(get_google_medicann_link(it.get('producer') or '', it.get('strain')))}' target='_blank' title='Search Medbud.wiki'>🔎</a>
      <p class="brand-line"><strong>{esc(brand)}</strong></p>
      {("<p class='small'>Removed since last parse</p>") if it.get("is_removed") else ""}
        <p class='small'>
        {(esc(it.get('product_id') or '') + (' - ' + esc((it.get('product_type') or '').title()) if it.get('product_type') and it.get('product_id') else esc((it.get('product_type') or '').title()))) if (it.get('product_id') or it.get('product_type')) else ''}
        </p>
  <div class='card-content'>
    <div>
      {price_pill}
      <span class='pill'>{qty or '?'}</span>
        {f"<span class='pill'>£/g {ppg:.2f}</span>" if ppg is not None else ''}
        {f"<span class='pill'>{esc(it.get('strain_type'))}</span>" if it.get('strain_type') else ''}
    </div>
    <div class='small'>🍿 THC: {esc(disp_thc)}</div>
    <div class='small'>🌱 CBD: {esc(disp_cbd)}</div>
    <div class='card-actions'>
      <button class='btn-basket' onclick='addToBasket(this)' onmouseenter='basketHover(this,true)' onmouseleave='basketHover(this,false)'>Add to basket</button>
    </div>
  </div>
</div>
""")
    parts.append("</div></body></html>")
    html_text = "\n".join(parts)
    # Inject computed bounds for sliders
    html_text = html_text.replace("{price_min_bound}", str(price_min_bound))
    html_text = html_text.replace("{price_max_bound}", str(price_max_bound))
    html_text = html_text.replace("{thc_min_bound}", str(thc_min_bound))
    html_text = html_text.replace("{thc_max_bound}", str(thc_max_bound))
    out_path.write_text(html_text, encoding="utf-8")

def export_html_auto(data, exports_dir=EXPORTS_DIR_DEFAULT, open_file=False, fetch_images=False):

    d = Path(exports_dir)
    d.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().astimezone().strftime('%Y-%m-%d_%H-%M-%S%z')
    fname = f"export-{ts}.html"
    path = d / fname
    export_html(data, path, fetch_images=fetch_images)
    if open_file:
        try:
            if os.name == 'nt':
                os.startfile(path)
            else:
                webbrowser.open(path.as_uri())
        except Exception:
            pass
    return path

def export_json_auto(data, exports_dir=EXPORTS_DIR_DEFAULT, open_file=False):

    d = Path(exports_dir)
    d.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().astimezone().strftime('%Y-%m-%d_%H-%M-%S%z')
    fname = f"export-{ts}.json"
    path = d / fname
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
    if open_file:
        try:
            if os.name == 'nt':
                os.startfile(path)
            else:
                webbrowser.open(path.as_uri())
        except Exception:
            pass
    return path

def cleanup_html_exports(exports_dir=EXPORTS_DIR_DEFAULT, max_files: int = 20) -> None:
    """Keep only the newest `max_files` HTML exports."""
    try:
        d = Path(exports_dir)
        files = sorted(d.glob("export-*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[max_files:]:
            try:
                old.unlink()
            except Exception:
                pass
    except Exception:
        pass

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
    cfg = dict(DEFAULT_CAPTURE_CONFIG)
    try:
        source = None
        # Prefer AppData config; fall back to legacy
        if os.path.exists(CONFIG_FILE):
            source = CONFIG_FILE
        elif os.path.exists(LEGACY_CONFIG_FILE):
            source = LEGACY_CONFIG_FILE
        if source:
            with open(source, "r", encoding="utf-8") as fh:
                raw = json.load(fh) or {}
            cfg.update({k: raw.get(k, v) for k, v in DEFAULT_CAPTURE_CONFIG.items()})
            changed = False
            # Decrypt/migrate secrets
            for key in ("username", "password", "ha_token"):
                val = raw.get(key, "")
                if isinstance(val, str) and val.startswith("enc:"):
                    dec = _decrypt_secret(val)
                else:
                    dec = val or ""
                    if dec:
                        raw[key] = _encrypt_secret(str(dec))
                        changed = True
                cfg[key] = dec
            # Optional notification toggles
            cfg["notify_price_changes"] = raw.get("notify_price_changes", True)
            cfg["notify_stock_changes"] = raw.get("notify_stock_changes", True)
            cfg["notify_windows"] = raw.get("notify_windows", True)
            cfg["minimize_to_tray"] = raw.get("minimize_to_tray", False)
            cfg["close_to_tray"] = raw.get("close_to_tray", False)
            if changed:
                try:
                    Path(source).write_text(json.dumps(raw, indent=2), encoding="utf-8")
                except Exception:
                    pass
    except Exception:
        pass
    return cfg


def _save_capture_config(data: dict) -> None:
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
                cfg = json.load(fh) or {}
        else:
            cfg = {}
        cfg.update({k: data.get(k, v) for k, v in DEFAULT_CAPTURE_CONFIG.items()})
        # Encrypt secrets before writing
        cfg["username"] = _encrypt_secret(data.get("username", ""))
        cfg["password"] = _encrypt_secret(data.get("password", ""))
        cfg["ha_token"] = _encrypt_secret(data.get("ha_token", ""))
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
    except Exception:
        pass


def _append_change_log(record: dict) -> None:
    try:
        CHANGES_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CHANGES_LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass

def _cleanup_and_record_export(path: Path, max_files: int = 20):
    """Track latest export path and keep exports tidy."""
    try:
        cleanup_html_exports(path.parent, max_files=max_files)
    except Exception:
        pass

def _seed_brand_db_if_needed():
    """On first run, seed the parser database from the bundled copy if none exists."""
    try:
        if BRAND_HINTS_FILE.exists():
            return
        # Look for bundled copy (works for frozen exe via BASE_DIR)
        bundled = Path(BASE_DIR) / "parser_database.json"
        if bundled.exists():
            BRAND_HINTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            BRAND_HINTS_FILE.write_text(bundled.read_text(encoding="utf-8"), encoding="utf-8")
            _log_debug(f"Seeded parser database from bundled copy to {BRAND_HINTS_FILE}")
    except Exception as exc:
        _log_debug(f"Failed to seed parser database: {exc}")
# ---------------- GUI ----------------
class App(tk.Tk):
    _instance = None

    @classmethod
    def instance(cls):
        return cls._instance

    def __init__(self):
        super().__init__()
        App._instance = self
        self.title("Medicann Scraper")
        self.geometry("900x720")
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
        self.tray_icon = None
        self.error_count = 0
        self.error_threshold = 3
        self._last_parse_empty = False
        self._empty_retry = False
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
        # Console log at bottom
        console_frame = ttk.Frame(self)
        console_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        ttk.Label(console_frame, text="Console Log").pack(anchor="w")
        self.console = scrolledtext.ScrolledText(console_frame, height=10, wrap="word", state="disabled")
        self.console.pack(fill="both", expand=True)
        self.last_change_label = ttk.Label(self, text="Last change detected: none")
        self.last_change_label.pack(pady=(0, 8))
        self.data = []
        self.price_up_count = 0
        self.price_down_count = 0
        self.q = Queue()
        self._polling = False
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
        self.last_change_summary = "none"
        self._build_capture_controls()
        # Tray behavior
        self.bind("<Unmap>", self._on_unmap)
        self.bind("<Map>", self._on_map)
        self.apply_theme()

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
        self.capture_config_path = Path(CONFIG_FILE)
        # Notification toggles from config
        self.notify_price_changes = tk.BooleanVar(value=cfg.get("notify_price_changes", True))
        self.notify_stock_changes = tk.BooleanVar(value=cfg.get("notify_stock_changes", True))
        self.notify_windows = tk.BooleanVar(value=cfg.get("notify_windows", True))
        self.cap_url = tk.StringVar(value=cfg.get("url", ""))
        self.cap_interval = tk.StringVar(value=str(cfg.get("interval_seconds", 60)))
        self.cap_headless = tk.BooleanVar(value=bool(cfg.get("headless", True)))
        self.cap_login_wait = tk.StringVar(value=str(cfg.get("login_wait_seconds", 3)))
        self.cap_post_wait = tk.StringVar(value=str(cfg.get("post_nav_wait_seconds", 30)))
        self.cap_user = tk.StringVar(value=_decrypt_secret(cfg.get("username", "")))
        self.cap_pass = tk.StringVar(value=_decrypt_secret(cfg.get("password", "")))
        self.cap_user_sel = tk.StringVar(value=cfg.get("username_selector", ""))
        self.cap_pass_sel = tk.StringVar(value=cfg.get("password_selector", ""))
        self.cap_btn_sel = tk.StringVar(value=cfg.get("login_button_selector", ""))
        self.cap_auto_notify_ha.set(bool(cfg.get("auto_notify_ha", False)))
        self.cap_ha_webhook.set(cfg.get("ha_webhook_url", ""))
        self.cap_ha_token.set(_decrypt_secret(cfg.get("ha_token", "")))
        self.minimize_to_tray = tk.BooleanVar(value=cfg.get("minimize_to_tray", False))
        self.close_to_tray = tk.BooleanVar(value=cfg.get("close_to_tray", False))

    def _open_settings_window(self):
        if self.settings_window and tk.Toplevel.winfo_exists(self.settings_window):
            try:
                self.settings_window.lift()
                self.settings_window.focus_force()
            except Exception:
                pass
            return
        win = tk.Toplevel(self)
        self.settings_window = win
        win.title("Settings")
        win.geometry("650x820")
        try:
            # Set icon for settings window
            icon_path = ASSETS_DIR / "icon.ico"
            if icon_path.exists():
                win.iconbitmap(str(icon_path))
            else:
                win.iconbitmap(self._resource_path('assets/icon2.ico'))
            self._set_window_titlebar_dark(win, self.dark_mode_var.get())
        except Exception:
            pass
        self.after(50, lambda: self._set_window_titlebar_dark(win, self.dark_mode_var.get()))

        # Notebook for scraper/parser settings
        notebook = ttk.Notebook(win, style="Settings.TNotebook")
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        # Scraper tab
        scraper_tab = ttk.Frame(notebook, padding=8)
        notebook.add(scraper_tab, text="Scraper")
        ttk.Label(
            scraper_tab,
            text="Configure how the scraper logs in, waits, and captures the page. "
            "Notifications fire only on new/removed items or price/stock changes.",
            wraplength=820,
            anchor="w",
            justify="left",
        ).pack(fill="x", pady=(0, 10))

        form = ttk.Frame(scraper_tab)
        form.pack(fill="x", expand=True)
        form.columnconfigure(1, weight=1)

        row_idx = 0
        ttk.Label(form, text="Target URL").grid(row=row_idx, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(form, textvariable=self.cap_url, width=50).grid(row=row_idx, column=1, sticky="ew", padx=4, pady=3)
        row_idx += 1

        ttk.Label(form, text="Interval (seconds)").grid(row=row_idx, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(form, textvariable=self.cap_interval, width=10).grid(row=row_idx, column=1, sticky="w", padx=4, pady=3)
        row_idx += 1

        ttk.Label(form, text="Headless").grid(row=row_idx, column=0, sticky="w", padx=4, pady=3)
        ttk.Checkbutton(form, variable=self.cap_headless).grid(row=row_idx, column=1, sticky="w", padx=4, pady=3)
        row_idx += 1

        ttk.Label(form, text="Wait after login (s)").grid(row=row_idx, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(form, textvariable=self.cap_login_wait, width=10).grid(row=row_idx, column=1, sticky="w", padx=4, pady=3)
        row_idx += 1

        ttk.Label(form, text="Wait after navigation (s, min 5)").grid(row=row_idx, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(form, textvariable=self.cap_post_wait, width=10).grid(row=row_idx, column=1, sticky="w", padx=4, pady=3)
        row_idx += 1

        ttk.Separator(form, orient="horizontal").grid(row=row_idx, column=0, columnspan=2, sticky="ew", pady=6)
        row_idx += 1

        ttk.Label(form, text="Username").grid(row=row_idx, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(form, textvariable=self.cap_user, width=40).grid(row=row_idx, column=1, sticky="ew", padx=4, pady=3)
        row_idx += 1

        ttk.Label(form, text="Password").grid(row=row_idx, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(form, textvariable=self.cap_pass, show="*", width=40).grid(row=row_idx, column=1, sticky="ew", padx=4, pady=3)
        row_idx += 1

        ttk.Label(form, text="Username selector").grid(row=row_idx, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(form, textvariable=self.cap_user_sel, width=40).grid(row=row_idx, column=1, sticky="ew", padx=4, pady=3)
        row_idx += 1

        ttk.Label(form, text="Password selector").grid(row=row_idx, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(form, textvariable=self.cap_pass_sel, width=40).grid(row=row_idx, column=1, sticky="ew", padx=4, pady=3)
        row_idx += 1

        ttk.Label(form, text="Login button selector").grid(row=row_idx, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(form, textvariable=self.cap_btn_sel, width=40).grid(row=row_idx, column=1, sticky="ew", padx=4, pady=3)
        row_idx += 1

        ttk.Separator(form, orient="horizontal").grid(row=row_idx, column=0, columnspan=2, sticky="ew", pady=6)
        row_idx += 1

        ttk.Label(form, text="Home Assistant notify").grid(row=row_idx, column=0, sticky="w", padx=4, pady=3)
        notify_frame = ttk.Labelframe(scraper_tab, text="Notification Settings", padding=8)
        notify_frame.pack(fill="x", padx=4, pady=(0, 10))
        ttk.Checkbutton(notify_frame, text="Send notifications for price changes", variable=self.notify_price_changes).pack(anchor="w", pady=2)
        ttk.Checkbutton(notify_frame, text="Send notifications for stock changes", variable=self.notify_stock_changes).pack(anchor="w", pady=2)
        ttk.Checkbutton(notify_frame, text="Send Windows desktop notifications", variable=self.notify_windows).pack(anchor="w", pady=2)
        ttk.Checkbutton(notify_frame, text="Send Home Assistant notifications", variable=self.cap_auto_notify_ha).pack(anchor="w", pady=2)

        window_frame = ttk.Labelframe(scraper_tab, text="Window behavior", padding=8)
        window_frame.pack(fill="x", padx=4, pady=(0, 10))
        ttk.Checkbutton(window_frame, text="Minimize to tray", variable=self.minimize_to_tray).pack(anchor="w", pady=2)
        ttk.Checkbutton(window_frame, text="Close to tray", variable=self.close_to_tray).pack(anchor="w", pady=2)

        ttk.Label(form, text="HA webhook URL").grid(row=row_idx, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(form, textvariable=self.cap_ha_webhook, width=50).grid(row=row_idx, column=1, sticky="ew", padx=4, pady=3)
        row_idx += 1

        ttk.Label(form, text="HA token (optional)").grid(row=row_idx, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(form, textvariable=self.cap_ha_token, show="*", width=50).grid(row=row_idx, column=1, sticky="ew", padx=4, pady=3)
        row_idx += 1

        # Parser tab (brands/patterns)
        parser_tab = ttk.Frame(notebook, padding=8)
        notebook.add(parser_tab, text="Parser / Brands")
        hints = [dict(brand=h.get("brand"), patterns=list(h.get("patterns") or h.get("phrases") or []), display=h.get("display")) for h in _load_brand_hints()]
        dark = self.dark_mode_var.get()
        bg = "#111" if dark else "#f4f4f4"
        fg = "#eee" if dark else "#111"
        accent = "#4a90e2" if dark else "#666666"
        list_bg = "#1e1e1e" if dark else "#ffffff"
        list_fg = fg
        entry_bg = list_bg
        parser_tab.configure()
        brand_var = tk.StringVar()
        pattern_var = tk.StringVar()
        entry_style = "ParserEntry.TEntry"
        try:
            self.style.configure(entry_style, fieldbackground=entry_bg, background=entry_bg, foreground=fg, insertcolor=fg)
        except Exception:
            pass
        # Styles for parser tab frames to increase contrast
        try:
            self.style.configure("Parser.TLabelframe", borderwidth=2, relief="groove")
            self.style.configure("Parser.TLabelframe.Label", padding=(6, 0))
        except Exception:
            pass

        container = ttk.Frame(parser_tab, padding=8)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1, uniform="parser")
        container.columnconfigure(1, weight=1, uniform="parser")
        container.rowconfigure(0, weight=1)

        left = ttk.Labelframe(container, text="Brands", padding=8, style="Parser.TLabelframe")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        right = ttk.Labelframe(container, text="Patterns", padding=8, style="Parser.TLabelframe")
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        brand_list = tk.Listbox(left, width=32, height=18, bg=list_bg, fg=list_fg, selectbackground=accent, selectforeground=bg, highlightbackground=bg, relief="flat")
        brand_list.pack(fill="both", expand=True, pady=(0, 6))
        brand_entry = ttk.Entry(left, textvariable=brand_var, style=entry_style)
        brand_entry.pack(fill="x", pady=(0, 6))

        pattern_list = tk.Listbox(right, width=32, height=18, bg=list_bg, fg=list_fg, selectbackground=accent, selectforeground=bg, highlightbackground=bg, relief="flat")
        pattern_list.pack(fill="both", expand=True, pady=(0, 6))
        pattern_entry = ttk.Entry(right, textvariable=pattern_var, style=entry_style)
        pattern_entry.pack(fill="x", pady=(0, 6))

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
            sel_brand = brand_list.curselection()
            sel_pat = pattern_list.curselection()
            if not sel_brand or not sel_pat:
                messagebox.showinfo("Pattern", "Select a brand and pattern to replace.")
                return
            pat = pattern_var.get().strip()
            if not pat:
                messagebox.showinfo("Pattern", "Enter a pattern.")
                return
            pats = hints[sel_brand[0]].setdefault("patterns", [])
            pats[sel_pat[0]] = pat
            refresh_patterns()

        def delete_pattern():
            sel_brand = brand_list.curselection()
            sel_pat = pattern_list.curselection()
            if not sel_brand or not sel_pat:
                return
            pats = hints[sel_brand[0]].setdefault("patterns", [])
            del pats[sel_pat[0]]
            refresh_patterns()

        # Brand actions under brand column
        brand_btns = ttk.Frame(left)
        brand_btns.pack(fill="x")
        ttk.Button(brand_btns, text="Add Brand", command=add_brand).pack(fill="x", pady=2)
        ttk.Button(brand_btns, text="Rename Brand", command=update_brand).pack(fill="x", pady=2)
        ttk.Button(brand_btns, text="Delete Brand", command=delete_brand).pack(fill="x", pady=2)

        # Pattern actions under pattern column
        pattern_btns = ttk.Frame(right)
        pattern_btns.pack(fill="x")
        ttk.Button(pattern_btns, text="Add Pattern", command=add_pattern).pack(fill="x", pady=2)
        ttk.Button(pattern_btns, text="Replace Pattern", command=replace_pattern).pack(fill="x", pady=2)
        ttk.Button(pattern_btns, text="Delete Pattern", command=delete_pattern).pack(fill="x", pady=2)

        ttk.Button(parser_tab, text="Export parser database", command=lambda: _save_brand_hints(hints)).pack(anchor="e", padx=8, pady=8)

        def save_and_close():
            self._save_capture_window()
            _save_brand_hints(hints)
            try:
                if self.settings_window and tk.Toplevel.winfo_exists(self.settings_window):
                    self.settings_window.destroy()
                    self.settings_window = None
            except Exception:
                pass

        # Scraper tab footer buttons
        scraper_btns = ttk.Frame(scraper_tab)
        scraper_btns.pack(fill="x", pady=10)
        ttk.Button(scraper_btns, text="Load config", command=self.load_capture_config).pack(side="left", padx=4)
        ttk.Button(scraper_btns, text="Save config", command=self.save_capture_config).pack(side="left", padx=4)
        ttk.Button(scraper_btns, text="Clear cache", command=self.clear_cache).pack(side="right", padx=4)
        ttk.Button(scraper_btns, text="Send test notification", command=self.send_test_notification).pack(side="right", padx=4)

        # Window footer
        btn_row = ttk.Frame(win)
        btn_row.pack(fill="x", pady=10, padx=10)
        ttk.Button(btn_row, text="Save & Close", command=save_and_close).pack(side="right", padx=4)
        refresh_brands()
        self._apply_theme_to_window(win)


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

    def start_auto_capture(self):
        if self.capture_thread and self.capture_thread.is_alive():
            self._log_console("Auto-capture already running.")
            return
        req = self._require_playwright()
        if not req:
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
        cfg = {
            "url": url,
            "interval_seconds": interval,
            "login_wait_seconds": login_wait,
            "post_nav_wait_seconds": post_wait,
            "username": self.cap_user.get(),
            "password": self.cap_pass.get(),
            "username_selector": self.cap_user_sel.get(),
            "password_selector": self.cap_pass_sel.get(),
            "login_button_selector": self.cap_btn_sel.get(),
            "headless": self.cap_headless.get(),
            "auto_notify_ha": self.cap_auto_notify_ha.get(),
            "ha_webhook_url": self.cap_ha_webhook.get(),
            "ha_token": self.cap_ha_token.get(),
            "minimize_to_tray": self.minimize_to_tray.get(),
            "close_to_tray": self.close_to_tray.get(),
            "notify_price_changes": self.notify_price_changes.get(),
            "notify_stock_changes": self.notify_stock_changes.get(),
            "notify_windows": self.notify_windows.get(),
        }
        _save_capture_config(cfg)
        self.capture_stop.clear()

        def worker():
            try:
                with sync_playwright() as p:
                    try:
                        browser = p.chromium.launch(headless=cfg["headless"])
                    except Exception as exc:
                        # Try installing browsers once if missing in packaged exe
                        if not getattr(self, "_playwright_install_attempted", False):
                            self._playwright_install_attempted = True
                            self._capture_log("Playwright browser missing; attempting download...")
                            if self._install_playwright_browsers():
                                browser = p.chromium.launch(headless=cfg["headless"])
                            else:
                                raise exc
                        else:
                            raise exc
                    context = browser.new_context()
                    page = context.new_page()
                    self._capture_log(f"Navigating to {cfg['url']}")
                    self._goto_with_log(page, cfg["url"], PlaywrightTimeoutError)
                    if cfg["username"] or cfg["password"]:
                        self._attempt_login(page, cfg, PlaywrightTimeoutError)
                        if cfg["login_wait_seconds"]:
                            self._capture_log(f"Waiting {cfg['login_wait_seconds']}s after login")
                            self._responsive_wait(cfg["login_wait_seconds"], label="Waiting after login")
                            self._capture_log(f"Revisiting {cfg['url']} after login")
                            self._goto_with_log(page, cfg["url"], PlaywrightTimeoutError)
                    while not self.capture_stop.is_set():
                        try:
                            if getattr(self, "_empty_retry_pending", False):
                                self._empty_retry_pending = False
                                self._capture_log("Retrying capture after empty parse (no reload)...")
                                self._wait_after_navigation(cfg["post_nav_wait_seconds"])
                                text = page.locator("body").inner_text()
                            else:
                                # Always refresh before capturing to avoid stale content
                                self._goto_with_log(page, cfg["url"], PlaywrightTimeoutError)
                                self._wait_after_navigation(cfg["post_nav_wait_seconds"])
                                text = page.locator("body").inner_text()
                            self._apply_captured_text(text)
                        except Exception as e:
                            self._capture_log(f"Capture error: {e}")
                        # Slow down overnight: between 00:00-07:00 run at most once per hour
                        interval = cfg["interval_seconds"]
                        try:
                            now = datetime.now().time()
                            if 0 <= now.hour < 7:
                                interval = max(interval, 3600)
                        except Exception:
                            pass
                        if self._responsive_wait(interval, label="Waiting for next capture"):
                            break
                    browser.close()
            except Exception as exc:
                self._capture_log(f"Auto-capture error: {exc}")
            finally:
                self.capture_stop.set()
                self._log_console("Auto-capture stopped.")

        self.capture_thread = _threading.Thread(target=worker, daemon=True)
        self.capture_thread.start()
        self._log_console("Auto-capture running...")
        self._update_tray_status()

    def stop_auto_capture(self):
        self.capture_stop.set()
        if self.capture_thread and not self.capture_thread.is_alive():
            self._log_console("Auto-capture stopped.")
        self._update_tray_status()

    def open_latest_export(self):
        """Open the most recent HTML export in the browser (served from the local server if available)."""
        exports_dir = Path(EXPORTS_DIR_DEFAULT)
        exports_dir.mkdir(parents=True, exist_ok=True)
        html_files = sorted(exports_dir.glob("export-*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not html_files:
            messagebox.showinfo("Exports", "No HTML exports found yet.")
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

    def _capture_log(self, msg: str):
        _log_debug(f"[capture] {msg}")
        self._log_console(msg)

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
        return pystray is not None and Image is not None

    def _minimize_to_tray(self):
        if not self._tray_supported():
            self.iconify()
            return
        try:
            self._hide_settings_window()
            self.withdraw()
            self._show_tray_icon()
            self._capture_log("Minimized to tray.")
        except Exception:
            self.iconify()

    def _restore_from_tray(self):
        try:
            self._hide_tray_icon()
            self.deiconify()
            self.state("normal")
            self.lift()
            self.focus_force()
            self._restore_settings_window()
            self._update_tray_status()
        except Exception:
            pass

    def _exit_from_tray(self, icon=None, item=None):
        self.after(0, self._exit_app)

    def _show_tray_icon(self):
        if getattr(self, "tray_icon", None):
            return
        if not self._tray_supported():
            return
        try:
            img = self._tray_image(self._is_capture_running())
            menu = pystray.Menu(
                pystray.MenuItem("Open", lambda icon, item: self._restore_from_tray(), default=True),
                pystray.MenuItem("Quit", lambda icon, item: self._exit_from_tray()),
            )
            self.tray_icon = pystray.Icon("MedicannScraper", img, "Medicann Scraper", menu)
            self.tray_icon.title = "Medicann Scraper"
            # run_detached avoids blocking Tk mainloop
            self.tray_icon.run_detached()
            # Ensure left-click restores too (Windows often uses default menu item on double-click)
            if hasattr(self.tray_icon, "visible"):
                self.tray_icon.visible = True
        except Exception as exc:
            self.tray_icon = None
            _log_debug(f"[tray] failed to show tray icon: {exc}")

    def _hide_tray_icon(self):
        try:
            if getattr(self, "tray_icon", None):
                self.tray_icon.stop()
                self.tray_icon = None
        except Exception:
            self.tray_icon = None

    def _on_unmap(self, event):
        try:
            if event.widget is self and self.state() == "iconic":
                if getattr(self, "minimize_to_tray", tk.BooleanVar(value=False)).get():
                    self._minimize_to_tray()
        except Exception:
            pass

    def _on_map(self, event):
        try:
            if event.widget is self:
                self._hide_tray_icon()
        except Exception:
            pass

    def _is_capture_running(self) -> bool:
        return bool(self.capture_thread and self.capture_thread.is_alive())

    def _tray_image(self, running: bool):
        """Return a small colored circle image (green running, red stopped)."""
        if Image is None or ImageDraw is None:
            return None
        size = 32
        if getattr(self, "_empty_retry_pending", False) or self.error_count > 0:
            color = (220, 180, 0, 255)  # yellow for warning
        else:
            color = (0, 200, 0, 255) if running else (200, 0, 0, 255)
        bg = (0, 0, 0, 0)
        img = Image.new("RGBA", (size, size), bg)  # type: ignore
        draw = ImageDraw.Draw(img)
        pad = 4
        draw.ellipse((pad, pad, size - pad, size - pad), fill=color)
        return img

    def _update_tray_status(self):
        """Update tray icon color based on capture running state."""
        try:
            if self.tray_icon and self._tray_supported():
                img = self._tray_image(self._is_capture_running())
                if img:
                    self.tray_icon.icon = img
        except Exception:
            pass

    def _hide_settings_window(self):
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
        try:
            LAST_CHANGE_FILE.parent.mkdir(parents=True, exist_ok=True)
            LAST_CHANGE_FILE.write_text(ts_line, encoding="utf-8")
            self.last_change_label.config(text=f"Last change detected: {ts_line}")
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
            time.sleep(min(0.2, remaining))
        if label:
            try:
                self.after(0, lambda: self.status.config(text="Auto-capture running..."))
            except Exception:
                pass
        return self.capture_stop.is_set()

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
            cfg = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as exc:
            messagebox.showerror("Capture Config", f"Could not load config:\n{exc}")
            return
        self.capture_config_path = Path(path)
        self.cap_url.set(cfg.get("url", ""))
        self.cap_interval.set(str(cfg.get("interval_seconds", 60)))
        self.cap_login_wait.set(str(cfg.get("login_wait_seconds", 3)))
        self.cap_post_wait.set(str(cfg.get("post_nav_wait_seconds", 30)))
        self.cap_user.set(_decrypt_secret(cfg.get("username", "")))
        self.cap_pass.set(_decrypt_secret(cfg.get("password", "")))
        self.cap_user_sel.set(cfg.get("username_selector", ""))
        self.cap_pass_sel.set(cfg.get("password_selector", ""))
        self.cap_btn_sel.set(cfg.get("login_button_selector", ""))
        self.cap_headless.set(bool(cfg.get("headless", True)))
        self.cap_auto_notify_ha.set(bool(cfg.get("auto_notify_ha", False)))
        self.cap_ha_webhook.set(cfg.get("ha_webhook_url", ""))
        self.cap_ha_token.set(_decrypt_secret(cfg.get("ha_token", "")))
        self.notify_price_changes.set(cfg.get("notify_price_changes", True))
        self.notify_stock_changes.set(cfg.get("notify_stock_changes", True))
        self.notify_windows.set(cfg.get("notify_windows", True))
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
            "username": _encrypt_secret(self.cap_user.get()),
            "password": _encrypt_secret(self.cap_pass.get()),
            "username_selector": self.cap_user_sel.get(),
            "password_selector": self.cap_pass_sel.get(),
            "login_button_selector": self.cap_btn_sel.get(),
            "headless": self.cap_headless.get(),
            "ha_webhook_url": self.cap_ha_webhook.get(),
            "ha_token": _encrypt_secret(self.cap_ha_token.get()),
            "notify_price_changes": self.notify_price_changes.get(),
            "notify_stock_changes": self.notify_stock_changes.get(),
            "notify_windows": self.notify_windows.get(),
            "minimize_to_tray": self.minimize_to_tray.get(),
            "close_to_tray": self.close_to_tray.get(),
        }
        try:
            Path(path).write_text(json.dumps(cfg, indent=2), encoding="utf-8")
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
            "username": _encrypt_secret(self.cap_user.get()),
            "password": _encrypt_secret(self.cap_pass.get()),
            "username_selector": self.cap_user_sel.get(),
            "password_selector": self.cap_pass_sel.get(),
            "login_button_selector": self.cap_btn_sel.get(),
            "headless": self.cap_headless.get(),
            "auto_notify_ha": self.cap_auto_notify_ha.get(),
            "ha_webhook_url": self.cap_ha_webhook.get(),
            "ha_token": _encrypt_secret(self.cap_ha_token.get()),
            "notify_price_changes": self.notify_price_changes.get(),
            "notify_stock_changes": self.notify_stock_changes.get(),
            "notify_windows": self.notify_windows.get(),
            "minimize_to_tray": self.minimize_to_tray.get(),
            "close_to_tray": self.close_to_tray.get(),
        }
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
            self.capture_config_path = target
        except Exception as exc:
            messagebox.showerror("Capture Config", f"Could not save config:\n{exc}")
            return
        try:
            if self.settings_window and tk.Toplevel.winfo_exists(self.settings_window):
                self.settings_window.destroy()
                self.settings_window = None
        except Exception:
            pass

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

    def send_home_assistant(self, log_only: bool = False):
        url = self.cap_ha_webhook.get().strip()
        if not url and not log_only:
            messagebox.showerror("Home Assistant", "Webhook URL is required.")
            return
        items = getattr(self, "data", [])
        prev_items = getattr(self, "prev_items", [])
        prev_keys = getattr(self, "prev_keys", set())
        # Fallback to persisted last parse if in-memory cache is empty
        if (not prev_items or not prev_keys) and LAST_PARSE_FILE.exists():
            try:
                prev_items = load_last_parse()
                prev_keys = {make_identity_key(it) for it in prev_items}
            except Exception:
                pass
        current_keys = {make_identity_key(it) for it in items}
        new_items = [it for it in items if make_identity_key(it) not in prev_keys]
        removed_keys = prev_keys - current_keys
        removed_items = [it for it in prev_items if make_identity_key(it) in removed_keys]
        price_changes = []
        stock_changes = []
        prev_price_map = {}
        prev_stock_map = {}
        for pit in prev_items:
            try:
                prev_price_map[make_identity_key(pit)] = float(pit.get("price")) if pit.get("price") is not None else None
            except Exception:
                prev_price_map[make_identity_key(pit)] = None
            prev_stock_map[make_identity_key(pit)] = pit.get("stock")
        for it in items:
            ident = make_identity_key(it)
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
            _append_change_log(log_record)
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
        # Build detailed desktop notification text and launch target
        def _join(lst, max_len=240):
            txt = "; ".join(lst)
            return txt if len(txt) <= max_len else (txt[: max_len - 3] + "...")
        body_parts = []
        if new_item_summaries:
            body_parts.append("New: " + _join(new_item_summaries))
        if removed_item_summaries:
            body_parts.append("Removed: " + _join(removed_item_summaries))
        if price_change_summaries:
            body_parts.append("Price: " + _join(price_change_summaries))
        if stock_change_summaries:
            body_parts.append("Stock: " + _join(stock_change_summaries))
        windows_body = " | ".join(body_parts) or summary
        launch_url = self.cap_url.get().strip() or self._latest_export_url()
        icon_path = ASSETS_DIR / "icon.ico"
        # Windows toast (always allowed when enabled)
        if self.notify_windows.get():
            self._capture_log(f"Sending Windows notification: {windows_body}")
            _maybe_send_windows_notification("Medicann update", windows_body, icon_path, launch_url=launch_url)
        # If log-only, skip HA network send but still append change log
        if log_only:
            return
        if not url:
            self._capture_log("HA webhook URL missing.")
            messagebox.showerror("Home Assistant", "Webhook URL is required.")
            try:
                if items:
                    self._generate_change_export(self._get_export_items())
            except Exception as exc:
                self._capture_log(f"Export generation error: {exc}")
            return
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        status = None
        body = ""
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                body = resp.read().decode("utf-8", errors="ignore")
                if 200 <= status < 300:
                    self._capture_log(f"Sent data to Home Assistant (status {status}).")
                    self._update_last_change(summary)
                else:
                    self._capture_log(f"HA response status: {status} body: {body[:200]}")
        except Exception as exc:
            self._capture_log(f"Home Assistant error: {exc}")
        finally:
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
        headers = {"Content-Type": "application/json"}
        token = self.cap_ha_token.get().strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        payload = {
            "test": True,
            "message": "Medicann Scraper test notification",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
            self._log_console(f"Test notification sent (status {status}).")
            messagebox.showinfo("Home Assistant", f"Test notification sent (status {status}).")
        except Exception as exc:
            self._log_console(f"Test notification error: {exc}")
            messagebox.showerror("Home Assistant", f"Test notification failed:\n{exc}")
            status = None
        # Also send a Windows test notification if enabled
        if self.notify_windows.get():
            icon_path = ASSETS_DIR / "icon.ico"
            self._log_console("Sending Windows test notification.")
            test_body = (
                f"HA test status: {status or 'error'} | "
                "New: Alpha Kush, Beta OG | Removed: None | Price: Gamma Glue ↑2.50; Delta Dream ↓1.00 | "
                "Stock: Zeta Zen: 10 → 8"
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
        exports_dir.mkdir(parents=True, exist_ok=True)
        class QuietHandler(http.server.SimpleHTTPRequestHandler):

            def log_message(self, fmt, *args):
                _log_debug("[server] " + fmt % args)

            def log_error(self, fmt, *args):
                _log_debug("[server] " + fmt % args)

            def handle(self):
                try:
                    super().handle()
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
                    _log_debug(f"[server] client disconnected early: {e}")
                except Exception as e:
                    _log_debug(f"[server] handler exception: {e}")

            def copyfile(self, source, outputfile):
                try:
                    return super().copyfile(source, outputfile)
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
                    _log_debug(f"[server] copy aborted: {e}")
                    return
        handler = functools.partial(QuietHandler, directory=str(exports_dir))
        # Find an available port starting at preferred
        port = self.server_port
        _log_debug(f"[server] attempting to start on port {port} serving {exports_dir}")
        for _ in range(10):
            try:
                self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
                self.httpd.allow_reuse_address = True
                self.server_port = port
                break
            except OSError as e:
                _log_debug(f"[server] port {port} unavailable ({e}), trying next")
                port += 1
        if not self.httpd:
            if not self._server_failed:
                self._server_failed = True
                messagebox.showerror("Export Server", "Could not start export server on localhost. Exports will open from file:// instead.")
            _log_debug("[server] failed to start export server after attempting 10 ports")
            return False
        self.http_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.http_thread.start()
        # Wait briefly for socket to be ready
        ready = False
        for _ in range(10):
            if _port_ready("127.0.0.1", self.server_port, timeout=0.2):
                ready = True
                break
            time.sleep(0.1)
        if not ready:
            _log_debug(f"[server] started but not reachable on port {self.server_port}")
        else:
            _log_debug(f"[server] serving exports at http://127.0.0.1:{self.server_port}")
        return ready

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
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
            self.httpd = None
            self.http_thread = None
            _log_debug("[server] shutdown complete")

    def _on_close(self):
        # Close-to-tray behavior
        if getattr(self, "close_to_tray", tk.BooleanVar(value=False)).get() and self._tray_supported():
            self._minimize_to_tray()
            return
        self._exit_app()

    def _exit_app(self):
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
        prev_items = load_last_parse()
        prev_keys = {make_identity_key(it) for it in prev_items}
        prev_price_map = {}
        for pit in prev_items:
            try:
                prev_price_map[make_identity_key(pit)] = float(pit.get("price")) if pit.get("price") is not None else None
            except Exception:
                prev_price_map[make_identity_key(pit)] = None
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
                    new_count = len({make_identity_key(it) for it in self.data} - prev_keys)
                    removed_keys = prev_keys - {make_identity_key(it) for it in self.data}
                    removed_items = [dict(it, is_removed=True, is_new=False) for it in prev_items if make_identity_key(it) in removed_keys]
                    removed_count = len(removed_items)
                    self.removed_data = removed_items
                    if not self.data:
                        self.error_count += 1
                        self._empty_retry_pending = True
                        self._update_tray_status()
                        self.status.config(text="No products parsed; retrying shortly.")
                        self._log_console("No products parsed; retrying shortly.")
                        if self.error_count >= self.error_threshold:
                            msg = "Repeated empty captures; auto-scraper stopped."
                            self._log_console(msg)
                            _maybe_send_windows_notification("Medicann error", msg, ASSETS_DIR / "icon.ico")
                            if self.cap_auto_notify_ha.get():
                                self._send_ha_error(msg)
                            self.stop_auto_capture()
                        self._polling = False
                        return
                    self.error_count = 0
                    self._empty_retry_pending = False
                    self._update_tray_status()
                    save_last_parse(self.data)
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
                    # Update prev cache for next run after notifications are sent
                    self.prev_items = list(self.data)
                    self.prev_keys = {make_identity_key(it) for it in self.data}
                    self._polling = False
                    return
        except Empty:
            pass
        if self._polling:
            self.after(50, self.poll)
        # Update last change label periodically
        try:
            if LAST_CHANGE_FILE.exists():
                ts = LAST_CHANGE_FILE.read_text(encoding="utf-8").strip()
                if ts:
                    self.last_change_label.config(text=f"Last change detected: {ts}")
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
        if dark:
            bg = "#111"
            fg = "#eee"
            ctrl_bg = "#222"
            accent = "#7cc7ff"
        else:
            bg = "#f7f7f7"
            fg = "#111"
            ctrl_bg = "#e6e6e6"
            accent = "#0b79d0"
        # Use a theme that respects our color overrides
        try:
            self.style.theme_use("clam")
        except Exception:
            pass
        self.configure(bg=bg)
        self.text.configure(bg=bg, fg=fg, insertbackground=fg)
        self.status.configure(background=bg, foreground=fg)
        self.style.configure("TFrame", background=bg)
        self.style.configure("TLabel", background=bg, foreground=fg)
        self.style.configure("TLabelframe", background=bg, foreground=fg, bordercolor=ctrl_bg)
        self.style.configure("TLabelframe.Label", background=bg, foreground=fg)
        self.style.configure(
            "TButton",
            background=ctrl_bg,
            foreground=fg,
            bordercolor=ctrl_bg,
            focusthickness=1,
            focuscolor=accent,
            padding=6,
        )
        self.style.map(
            "TButton",
            background=[("active", accent), ("pressed", accent)],
            foreground=[("active", bg if dark else "#fff"), ("pressed", bg if dark else "#fff")],
        )
        self.style.configure("TCheckbutton", background=bg, foreground=fg, focuscolor=accent)
        self.style.configure("TEntry", fieldbackground=ctrl_bg, foreground=fg, insertcolor=fg)
        self.style.map("TEntry", fieldbackground=[("readonly", ctrl_bg)], foreground=[("readonly", fg)])
        self.style.configure("TNotebook", background=bg, bordercolor=ctrl_bg)
        self.style.configure(
            "TNotebook.Tab",
            background=ctrl_bg,
            foreground=fg,
            padding=(10, 6),
            lightcolor=ctrl_bg,
            bordercolor=ctrl_bg,
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", accent), ("active", accent)],
            foreground=[("selected", bg if dark else "#fff"), ("active", bg if dark else "#fff")],
        )
        self.style.configure("TProgressbar", background=accent, troughcolor=ctrl_bg)
        # Option database tweaks for menus/listboxes if used by ttk popups
        self.option_add("*Menu*Background", ctrl_bg)
        self.option_add("*Menu*Foreground", fg)
        self.option_add("*Menu*ActiveBackground", accent)
        self.option_add("*Menu*ActiveForeground", bg)
        self.option_add("*TCombobox*Listbox*Background", ctrl_bg)
        self.option_add("*TCombobox*Listbox*Foreground", fg)
        for child in self.winfo_children():
            if isinstance(child, tk.Text):
                child.configure(bg=bg, fg=fg, insertbackground=fg)
            if isinstance(child, ttk.Frame):
                child.configure(style="TFrame")
        if hasattr(self, "console"):
            try:
                self.console.configure(bg=ctrl_bg, fg=fg, insertbackground=fg)
            except Exception:
                pass
        # Update last change label from stored file
        try:
            if LAST_CHANGE_FILE.exists():
                ts = LAST_CHANGE_FILE.read_text(encoding="utf-8").strip()
                if ts:
                    self.last_change_label.config(text=f"Last change detected: {ts}")
        except Exception:
            pass
        # Apply title bar color after the window is realized; schedule ensures hwnd exists
        self.after(50, lambda: self._set_win_titlebar_dark(dark))
        if self.capture_window and tk.Toplevel.winfo_exists(self.capture_window):
            self._apply_theme_to_window(self.capture_window)

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
        bg = "#111" if dark else "#f7f7f7"
        fg = "#eee" if dark else "#111"
        ctrl_bg = "#222" if dark else "#e6e6e6"
        accent = "#7cc7ff" if dark else "#0b79d0"
        try:
            window.configure(bg=bg)
            for widget in window.winfo_children():
                self._apply_theme_recursive(widget, bg, fg, ctrl_bg, accent, dark)
            self._set_window_titlebar_dark(window, dark)
        except Exception:
            pass
if __name__ == "__main__":
    App().mainloop()
