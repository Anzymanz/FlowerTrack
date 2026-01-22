from __future__ import annotations

import base64
import copy
import ctypes
import json
import os
import shutil
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from typing import Any

# Default schema for capture config (centralized)
SCHEMA_VERSION = 2
DEFAULT_CAPTURE_CONFIG = {
    "version": SCHEMA_VERSION,
    "url": "",
    "username": "",
    "password": "",
    "username_selector": "",
    "password_selector": "",
    "login_button_selector": "",
    "organization": "",
    "organization_selector": "label:has-text(\"Organization\") + *",
    "window_geometry": "900x720",
    "settings_geometry": "560x960",
    "interval_seconds": 60.0,
    "login_wait_seconds": 3.0,
    "post_nav_wait_seconds": 30.0,
    "retry_attempts": 3,
    "retry_wait_seconds": 30.0,
    "retry_backoff_max": 4.0,
    "scroll_times": 0,
    "scroll_pause_seconds": 0.5,
    "dump_capture_html": False,
    "dump_api_json": False,
    "timeout_ms": 45000,
    "headless": True,
    "auto_notify_ha": False,
    "ha_webhook_url": "",
    "ha_token": "",
    "notify_price_changes": True,
    "notify_stock_changes": True,
    "notify_windows": True,
    "quiet_hours_enabled": False,
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "07:00",
    "quiet_hours_interval_seconds": 3600.0,
    "notification_detail": "full",
    "include_inactive": False,
    "requestable_only": True,
    "in_stock_only": False,
    "minimize_to_tray": False,
    "close_to_tray": False,
}


def _default_tracker_data_path() -> str:
    appdata = Path(os.getenv("APPDATA", os.path.expanduser("~")))
    return str(appdata / "FlowerTrack" / "data" / "tracker_data.json")


def _default_library_data_path() -> str:
    appdata = Path(os.getenv("APPDATA", os.path.expanduser("~")))
    return str(appdata / "FlowerTrack" / "data" / "library_data.json")


# Default schema for tracker config (centralized)
DEFAULT_TRACKER_CONFIG = {
    "data_path": _default_tracker_data_path(),
    "library_data_path": _default_library_data_path(),
    "dark_mode": True,
    "minimize_to_tray": False,
    "close_to_tray": False,
    "show_scraper_status_icon": True,
    "enable_stock_coloring": True,
    "enable_usage_coloring": True,
    "track_cbd_usage": False,
    "total_green_threshold": 30.0,
    "total_red_threshold": 5.0,
    "single_green_threshold": 10.0,
    "single_red_threshold": 2.0,
    "cbd_total_green_threshold": 30.0,
    "cbd_total_red_threshold": 5.0,
    "cbd_single_green_threshold": 10.0,
    "cbd_single_red_threshold": 2.0,
    "target_daily_grams": 1.0,
    "target_daily_cbd_grams": 0.0,
    "roa_options": {"Vaped": 0.60, "Eaten": 0.10, "Smoked": 0.30},
    "window_geometry": "",
    "stock_column_widths": {},
    "log_column_widths": {},
}


DEFAULT_UI_CONFIG = {
    "dark_mode": True,
    "minimize_to_tray": False,
    "close_to_tray": False,
}


def _default_unified_config() -> dict:
    return {
        "version": SCHEMA_VERSION,
        "tracker": copy.deepcopy(DEFAULT_TRACKER_CONFIG),
        "scraper": copy.deepcopy(DEFAULT_CAPTURE_CONFIG),
        "ui": copy.deepcopy(DEFAULT_UI_CONFIG),
    }


def _read_json(path: Path) -> dict:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _looks_like_scraper(raw: dict) -> bool:
    return any(
        key in raw
        for key in (
            "url",
            "username_selector",
            "password_selector",
            "login_button_selector",
            "interval_seconds",
            "post_nav_wait_seconds",
        )
    )


def _looks_like_tracker(raw: dict) -> bool:
    return any(
        key in raw
        for key in (
            "dark_mode",
            "roa_options",
            "target_daily_grams",
            "track_cbd_usage",
        "minimize_to_tray",
        "close_to_tray",
        )
    )


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


def _coerce_int(val: Any, default: int, min_value: int | None = None) -> int:
    try:
        i = int(float(val))
        if min_value is not None and i < min_value:
            return min_value
        return i
    except Exception:
        return default



def _validate_tracker_config(raw: dict) -> dict:
    cfg = dict(DEFAULT_TRACKER_CONFIG)
    if not isinstance(raw, dict):
        return cfg
    bool_keys = {
        "dark_mode",
        "enable_stock_coloring",
        "enable_usage_coloring",
        "track_cbd_usage",
        "minimize_to_tray",
        "close_to_tray",
        "show_scraper_status_icon",
}
    float_keys = {
        "total_green_threshold",
        "total_red_threshold",
        "single_green_threshold",
        "single_red_threshold",
        "cbd_total_green_threshold",
        "cbd_total_red_threshold",
        "cbd_single_green_threshold",
        "cbd_single_red_threshold",
        "target_daily_grams",
        "target_daily_cbd_grams",
    }
    for key, value in raw.items():
        if key not in cfg:
            continue
        if key in bool_keys:
            cfg[key] = _coerce_bool(value, cfg[key])
        elif key in float_keys:
            cfg[key] = _coerce_float(value, cfg[key], 0.0)
        elif key == "roa_options" and isinstance(value, dict):
            cfg[key] = {str(k): float(v) for k, v in value.items() if v is not None}
        else:
            cfg[key] = value
    if not cfg.get("data_path"):
        cfg["data_path"] = _default_tracker_data_path()
    if not cfg.get("library_data_path"):
        cfg["library_data_path"] = _default_library_data_path()
    return cfg


def _validate_ui_config(raw: dict, tracker_fallback: dict) -> dict:
    cfg = dict(DEFAULT_UI_CONFIG)
    if isinstance(raw, dict) and "dark_mode" in raw:
        cfg["dark_mode"] = _coerce_bool(raw.get("dark_mode"), cfg["dark_mode"])
    if isinstance(tracker_fallback, dict) and "dark_mode" in tracker_fallback:
        cfg["dark_mode"] = _coerce_bool(tracker_fallback.get("dark_mode"), cfg["dark_mode"])
    return cfg


def _validate_capture_config(raw: dict) -> dict:
    cfg = dict(DEFAULT_CAPTURE_CONFIG)
    cfg["version"] = int(raw.get("version") or SCHEMA_VERSION)
    cfg["url"] = str(raw.get("url") or "").strip()
    cfg["username"] = str(raw.get("username") or "")
    cfg["password"] = str(raw.get("password") or "")
    cfg["username_selector"] = str(raw.get("username_selector") or "")
    cfg["password_selector"] = str(raw.get("password_selector") or "")
    cfg["login_button_selector"] = str(raw.get("login_button_selector") or "")
    cfg["organization"] = str(raw.get("organization") or "")
    cfg["organization_selector"] = str(raw.get("organization_selector") or "").strip()
    cfg["scroll_times"] = int(_coerce_float(raw.get("scroll_times"), DEFAULT_CAPTURE_CONFIG["scroll_times"], 0))
    cfg["scroll_pause_seconds"] = _coerce_float(raw.get("scroll_pause_seconds"), DEFAULT_CAPTURE_CONFIG["scroll_pause_seconds"], 0.0)
    cfg["dump_capture_html"] = _coerce_bool(raw.get("dump_capture_html"), DEFAULT_CAPTURE_CONFIG["dump_capture_html"])
    cfg["dump_api_json"] = _coerce_bool(raw.get("dump_api_json"), DEFAULT_CAPTURE_CONFIG["dump_api_json"])
    cfg["window_geometry"] = str(raw.get("window_geometry") or DEFAULT_CAPTURE_CONFIG["window_geometry"]).strip() or DEFAULT_CAPTURE_CONFIG["window_geometry"]
    cfg["settings_geometry"] = str(raw.get("settings_geometry") or DEFAULT_CAPTURE_CONFIG["settings_geometry"]).strip() or DEFAULT_CAPTURE_CONFIG["settings_geometry"]
    cfg["interval_seconds"] = _coerce_float(raw.get("interval_seconds"), DEFAULT_CAPTURE_CONFIG["interval_seconds"], 1.0)
    cfg["login_wait_seconds"] = _coerce_float(raw.get("login_wait_seconds"), DEFAULT_CAPTURE_CONFIG["login_wait_seconds"], 0.0)
    cfg["post_nav_wait_seconds"] = _coerce_float(
        raw.get("post_nav_wait_seconds"),
        DEFAULT_CAPTURE_CONFIG["post_nav_wait_seconds"],
        5.0,
    )
    cfg["retry_attempts"] = int(_coerce_float(raw.get("retry_attempts"), DEFAULT_CAPTURE_CONFIG["retry_attempts"], 0))
    cfg["retry_wait_seconds"] = _coerce_float(raw.get("retry_wait_seconds"), DEFAULT_CAPTURE_CONFIG["retry_wait_seconds"], 0.0)
    cfg["retry_backoff_max"] = _coerce_float(raw.get("retry_backoff_max"), DEFAULT_CAPTURE_CONFIG["retry_backoff_max"], 1.0)
    cfg["timeout_ms"] = int(_coerce_float(raw.get("timeout_ms"), DEFAULT_CAPTURE_CONFIG["timeout_ms"], 0))
    cfg["headless"] = _coerce_bool(raw.get("headless"), DEFAULT_CAPTURE_CONFIG["headless"])
    cfg["auto_notify_ha"] = _coerce_bool(raw.get("auto_notify_ha"), DEFAULT_CAPTURE_CONFIG["auto_notify_ha"])
    cfg["ha_webhook_url"] = str(raw.get("ha_webhook_url") or "")
    cfg["ha_token"] = str(raw.get("ha_token") or "")
    cfg["notify_price_changes"] = _coerce_bool(raw.get("notify_price_changes"), DEFAULT_CAPTURE_CONFIG["notify_price_changes"])
    cfg["notify_stock_changes"] = _coerce_bool(raw.get("notify_stock_changes"), DEFAULT_CAPTURE_CONFIG["notify_stock_changes"])
    cfg["notify_windows"] = _coerce_bool(raw.get("notify_windows"), DEFAULT_CAPTURE_CONFIG["notify_windows"])
    cfg["quiet_hours_enabled"] = _coerce_bool(raw.get("quiet_hours_enabled"), DEFAULT_CAPTURE_CONFIG["quiet_hours_enabled"])
    cfg["quiet_hours_start"] = str(raw.get("quiet_hours_start") or DEFAULT_CAPTURE_CONFIG["quiet_hours_start"]).strip()
    cfg["quiet_hours_end"] = str(raw.get("quiet_hours_end") or DEFAULT_CAPTURE_CONFIG["quiet_hours_end"]).strip()
    cfg["quiet_hours_interval_seconds"] = _coerce_float(raw.get("quiet_hours_interval_seconds"), DEFAULT_CAPTURE_CONFIG["quiet_hours_interval_seconds"], 1.0)
    cfg["notification_detail"] = str(raw.get("notification_detail") or DEFAULT_CAPTURE_CONFIG["notification_detail"]).strip() or "full"
    cfg["minimize_to_tray"] = _coerce_bool(raw.get("minimize_to_tray"), DEFAULT_CAPTURE_CONFIG["minimize_to_tray"])
    cfg["close_to_tray"] = _coerce_bool(raw.get("close_to_tray"), DEFAULT_CAPTURE_CONFIG["close_to_tray"])
    return cfg


def _normalize_unified_config(raw: dict) -> dict:
    tracker_raw = raw.get("tracker", {}) if isinstance(raw, dict) else {}
    scraper_raw = raw.get("scraper", {}) if isinstance(raw, dict) else {}
    ui_raw = raw.get("ui", {}) if isinstance(raw, dict) else {}
    tracker_cfg = _validate_tracker_config(tracker_raw)
    scraper_cfg = _validate_capture_config(scraper_raw)
    ui_cfg = _validate_ui_config(ui_raw, tracker_cfg)
    tracker_cfg["dark_mode"] = ui_cfg["dark_mode"]
    return {
        "version": SCHEMA_VERSION,
        "tracker": tracker_cfg,
        "scraper": scraper_cfg,
        "ui": ui_cfg,
    }


def load_unified_config(
    path: Path,
    decrypt_scraper_keys: list[str] | None = None,
    logger=None,
    write_back: bool = True,
) -> dict:
    decrypt_scraper_keys = decrypt_scraper_keys or []

    raw = _read_json(path)
    is_unified = any(k in raw for k in ("tracker", "scraper", "ui"))
    unified_raw: dict = {}
    if is_unified:
        unified_raw = raw
    else:
        if raw:
            if _looks_like_scraper(raw):
                unified_raw["scraper"] = raw
            elif _looks_like_tracker(raw):
                unified_raw["tracker"] = raw

    if "scraper" in unified_raw:
        for key in decrypt_scraper_keys:
            if key in unified_raw["scraper"]:
                unified_raw["scraper"][key] = decrypt_secret(unified_raw["scraper"].get(key, ""))

    prev_version = raw.get("version") if is_unified else None
    unified = _normalize_unified_config(unified_raw)
    needs_migration = (not is_unified) or (prev_version != SCHEMA_VERSION)
    if write_back and (not path.exists() or needs_migration):
        try:
            save_unified_config(path, unified, encrypt_scraper_keys=decrypt_scraper_keys)
            if needs_migration:
                _log_migration(
                    f"Config migrated v{prev_version or 'none'} -> v{SCHEMA_VERSION}",
                    logger=logger,
                )
        except Exception as exc:
            if logger:
                try:
                    logger(f"Config migration failed: {exc}")
                except Exception:
                    pass
    return unified


def _atomic_write_json(path: Path, data: dict) -> None:
    ensure_dir(path.parent)
    tmp = path.with_suffix(path.suffix + ".tmp")
    backup = path.with_suffix(path.suffix + ".bak")
    try:
        if path.exists():
            try:
                shutil.copy2(path, backup)
            except Exception:
                pass
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass


def save_unified_config(path: Path, data: dict, encrypt_scraper_keys: list[str] | None = None) -> None:
    encrypt_scraper_keys = encrypt_scraper_keys or []
    cfg = _normalize_unified_config(data or {})
    for key in encrypt_scraper_keys:
        cfg["scraper"][key] = encrypt_secret(cfg["scraper"].get(key, ""))
    _atomic_write_json(path, cfg)


def load_tracker_config(path: Path) -> dict:
    raw = _read_json(path)
    if not raw or not any(k in raw for k in ("tracker", "scraper", "ui")):
        unified = load_unified_config(
            path,
            decrypt_scraper_keys=["username", "password", "ha_token"],
        )
        return _validate_tracker_config(unified.get("tracker", {}))
    if any(k in raw for k in ("tracker", "scraper", "ui")):
        raw = raw.get("tracker", {})
    merged = _validate_tracker_config(raw)
    return merged


def save_tracker_config(path: Path, cfg: dict) -> None:
    try:
        raw = _read_json(path)
        tracker_cfg = _validate_tracker_config(cfg or {})
        if any(k in raw for k in ("tracker", "scraper", "ui")):
            raw["tracker"] = tracker_cfg
            raw.setdefault("ui", {})["dark_mode"] = tracker_cfg["dark_mode"]
            save_unified_config(path, raw)
        else:
            unified = _default_unified_config()
            unified["tracker"] = tracker_cfg
            unified["ui"]["dark_mode"] = tracker_cfg["dark_mode"]
            save_unified_config(path, unified)
    except Exception:
        pass



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




def _migration_log_path() -> Path:
    appdata = Path(os.getenv("APPDATA", os.path.expanduser("~")))
    return appdata / "FlowerTrack" / "data" / "config_migrations.log"


def _log_migration(message: str, logger=None) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {message}"
    if logger:
        try:
            logger(line)
        except Exception:
            pass
    try:
        path = _migration_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass

def _migrate_capture_config(raw: dict) -> dict:
    """
    Apply schema migrations. Currently bumps missing version to current schema.
    """
    if not isinstance(raw, dict):
        return {}
    ver = int(raw.get("version") or 0)
    if ver < SCHEMA_VERSION:
        raw["version"] = SCHEMA_VERSION
    return raw


def load_capture_config(path: Path, decrypt_keys: list[str], logger=None) -> dict:
    cfg = dict(DEFAULT_CAPTURE_CONFIG)
    try:
        unified = load_unified_config(
            path,
            decrypt_scraper_keys=decrypt_keys,
            logger=logger,
        )
        cfg = _validate_capture_config(unified.get("scraper", {}))
    except Exception as exc:
        if logger:
            try:
                logger(f"Config load failed: {exc}")
            except Exception:
                pass
    return cfg


def save_capture_config(path: Path, data: dict, encrypt_keys: list[str]):
    try:
        unified = load_unified_config(
            path,
            decrypt_scraper_keys=encrypt_keys,
            write_back=False,
        )
        unified["scraper"] = _validate_capture_config(_migrate_capture_config(data or {}))
        save_unified_config(path, unified, encrypt_scraper_keys=encrypt_keys)
    except Exception:
        pass
