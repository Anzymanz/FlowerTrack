from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from typing import Any

# Default schema for capture config (centralized)
SCHEMA_VERSION = 1
DEFAULT_CAPTURE_CONFIG = {
    "version": SCHEMA_VERSION,
    "url": "",
    "username": "",
    "password": "",
    "username_selector": "",
    "password_selector": "",
    "login_button_selector": "",
    "interval_seconds": 60.0,
    "login_wait_seconds": 3.0,
    "post_nav_wait_seconds": 30.0,
    "retry_attempts": 3,
    "timeout_ms": 45000,
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


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _dpapi_protect(data: bytes) -> bytes | None:
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
    except Exception:
        pass
    return None


def _dpapi_unprotect(data: bytes) -> bytes | None:
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
    except Exception:
        pass
    return None


def encrypt_secret(value: str) -> str:
    if not value:
        return value
    data = value.encode("utf-8")
    protected = _dpapi_protect(data)
    if protected:
        return "enc:" + base64.b64encode(protected).decode("ascii")
    return "enc:" + base64.b64encode(data).decode("ascii")


def decrypt_secret(value: str) -> str:
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


def _coerce_bool(val: Any, default: bool) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(val, (int, float)):
        return bool(val)
    return default


def _coerce_float(val: Any, default: float, min_value: float | None = None) -> float:
    try:
        f = float(val)
        if min_value is not None and f < min_value:
            return min_value
        return f
    except Exception:
        return default


def _validate_capture_config(raw: dict) -> dict:
    cfg = dict(DEFAULT_CAPTURE_CONFIG)
    cfg["version"] = int(raw.get("version") or SCHEMA_VERSION)
    cfg["url"] = str(raw.get("url") or "").strip()
    cfg["username"] = str(raw.get("username") or "")
    cfg["password"] = str(raw.get("password") or "")
    cfg["username_selector"] = str(raw.get("username_selector") or "")
    cfg["password_selector"] = str(raw.get("password_selector") or "")
    cfg["login_button_selector"] = str(raw.get("login_button_selector") or "")
    cfg["interval_seconds"] = _coerce_float(raw.get("interval_seconds"), DEFAULT_CAPTURE_CONFIG["interval_seconds"], 1.0)
    cfg["login_wait_seconds"] = _coerce_float(raw.get("login_wait_seconds"), DEFAULT_CAPTURE_CONFIG["login_wait_seconds"], 0.0)
    cfg["post_nav_wait_seconds"] = _coerce_float(
        raw.get("post_nav_wait_seconds"),
        DEFAULT_CAPTURE_CONFIG["post_nav_wait_seconds"],
        5.0,
    )
    cfg["retry_attempts"] = int(_coerce_float(raw.get("retry_attempts"), DEFAULT_CAPTURE_CONFIG["retry_attempts"], 0))
    cfg["timeout_ms"] = int(_coerce_float(raw.get("timeout_ms"), DEFAULT_CAPTURE_CONFIG["timeout_ms"], 0))
    cfg["headless"] = _coerce_bool(raw.get("headless"), DEFAULT_CAPTURE_CONFIG["headless"])
    cfg["auto_notify_ha"] = _coerce_bool(raw.get("auto_notify_ha"), DEFAULT_CAPTURE_CONFIG["auto_notify_ha"])
    cfg["ha_webhook_url"] = str(raw.get("ha_webhook_url") or "")
    cfg["ha_token"] = str(raw.get("ha_token") or "")
    cfg["notify_price_changes"] = _coerce_bool(raw.get("notify_price_changes"), DEFAULT_CAPTURE_CONFIG["notify_price_changes"])
    cfg["notify_stock_changes"] = _coerce_bool(raw.get("notify_stock_changes"), DEFAULT_CAPTURE_CONFIG["notify_stock_changes"])
    cfg["notify_windows"] = _coerce_bool(raw.get("notify_windows"), DEFAULT_CAPTURE_CONFIG["notify_windows"])
    cfg["minimize_to_tray"] = _coerce_bool(raw.get("minimize_to_tray"), DEFAULT_CAPTURE_CONFIG["minimize_to_tray"])
    cfg["close_to_tray"] = _coerce_bool(raw.get("close_to_tray"), DEFAULT_CAPTURE_CONFIG["close_to_tray"])
    return cfg


def _migrate_capture_config(raw: dict) -> dict:
    """
    Apply schema migrations. Currently bumps missing version to current schema.
    """
    if not isinstance(raw, dict):
        return {}
    if "version" not in raw:
        raw["version"] = SCHEMA_VERSION
    return raw


def load_capture_config(path: Path, legacy_paths: list[Path], decrypt_keys: list[str], logger=None) -> dict:
    cfg = dict(DEFAULT_CAPTURE_CONFIG)
    try:
        source = None
        if path.exists():
            source = path
        else:
            for lp in legacy_paths:
                if lp.exists():
                    source = lp
                    break
        raw = {}
        if source:
            raw = json.loads(source.read_text(encoding="utf-8"))
        raw = _migrate_capture_config(raw)
        for key in decrypt_keys:
            if key in raw:
                raw[key] = decrypt_secret(raw.get(key, ""))
        cfg = _validate_capture_config(raw)
    except Exception as exc:
        if logger:
            try:
                logger(f"Config load failed: {exc}")
            except Exception:
                pass
    return cfg


def save_capture_config(path: Path, data: dict, encrypt_keys: list[str]):
    try:
        cfg = _validate_capture_config(_migrate_capture_config(data or {}))
        for key in encrypt_keys:
            cfg[key] = encrypt_secret(cfg.get(key, ""))
        ensure_dir(path.parent)
        path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception:
        pass
