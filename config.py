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


def ensure_dir(path: Path) -> None:
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        _log_config_error(f"ensure_dir failed: {exc}")


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _dpapi_encrypt(raw: bytes) -> bytes | None:
    if raw is None:
        return None
    if raw == b"":
        return b""
    data_in = _DATA_BLOB(len(raw), ctypes.cast(ctypes.create_string_buffer(raw), ctypes.POINTER(ctypes.c_byte)))
    data_out = _DATA_BLOB()
    crypt_protect = ctypes.windll.crypt32.CryptProtectData
    if crypt_protect(ctypes.byref(data_in), None, None, None, None, 0, ctypes.byref(data_out)):
        try:
            return ctypes.string_at(data_out.pbData, data_out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(data_out.pbData)
    return None


def _dpapi_decrypt(raw: bytes) -> bytes | None:
    if raw is None:
        return None
    if raw == b"":
        return b""
    data_in = _DATA_BLOB(len(raw), ctypes.cast(ctypes.create_string_buffer(raw), ctypes.POINTER(ctypes.c_byte)))
    data_out = _DATA_BLOB()
    crypt_unprotect = ctypes.windll.crypt32.CryptUnprotectData
    if crypt_unprotect(ctypes.byref(data_in), None, None, None, None, 0, ctypes.byref(data_out)):
        try:
            return ctypes.string_at(data_out.pbData, data_out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(data_out.pbData)
    return None


def encrypt_secret(value: str) -> str:
    try:
        if value is None:
            return ""
        raw = str(value).encode("utf-8")
        enc = _dpapi_encrypt(raw)
        if enc is not None:
            return base64.b64encode(enc).decode("utf-8")
    except Exception:
        pass
    return str(value)


def _is_encrypted_secret(value: str) -> bool:
    if not value:
        return False
    try:
        raw = base64.b64decode(str(value).encode("utf-8"), validate=True)
    except Exception:
        return False
    try:
        dec = _dpapi_decrypt(raw)
    except Exception:
        return False
    return dec is not None


def _secret_needs_encryption(value: str) -> bool:
    if not value:
        return False
    return not _is_encrypted_secret(value)

def decrypt_secret(value: str) -> str:
    try:
        if not value:
            return ""
        raw = base64.b64decode(str(value).encode("utf-8"), validate=True)
        dec = _dpapi_decrypt(raw)
        if dec is not None:
            return dec.decode("utf-8", errors="ignore")
    except Exception:
        pass
    return str(value)


def _maybe_encrypt_secret(value: str) -> str:
    if not value:
        return ""
    try:
        decrypted = decrypt_secret(value)
    except Exception:
        decrypted = value
    if decrypted != str(value):
        return str(value)
    return encrypt_secret(str(value))

# Default schema for capture config (centralized)
SCHEMA_VERSION = 2
DEFAULT_CAPTURE_CONFIG = {
    "version": SCHEMA_VERSION,
    "url": "https://medicann-patient.scriptassist.co.uk/products",
    "username": "",
    "password": "",
    "username_selector": "input[name=\"email\"]",
    "password_selector": "input[name=\"password\"]",
    "login_button_selector": "button[type=\"submit\"]",
    "organization": "",
    "organization_selector": "label:has-text(\"Organization\") + *",
    "window_geometry": "769x420+1125+346",
    "settings_geometry": "560x1127+1582+83",
    "interval_seconds": 60.0,
    "login_wait_seconds": 2.0,
    "post_nav_wait_seconds": 10.0,
    "retry_attempts": 3,
    "retry_wait_seconds": 30.0,
    "retry_backoff_max": 2.0,
    "dump_capture_html": False,
    "dump_api_json": False,
    "dump_api_full": False,
    "timeout_ms": 45000,
    "headless": True,
    "api_only": True,
    "show_log_window": False,
    "auto_notify_ha": False,
    "ha_webhook_url": "",
    "ha_token": "",
    "notify_price_changes": True,
    "notify_stock_changes": False,
    "notify_out_of_stock": True,
    "notify_restock": True,
    "notify_new_items": True,
    "notify_removed_items": True,
    "notify_windows": True,
    "notifications_muted": False,
    "notification_restore_snapshot": {},
    "log_window_hidden_height": 200.0,
    "quiet_hours_enabled": False,
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "07:00",
    "quiet_hours_interval_seconds": 1200.0,
    "notification_detail": "full",
    "include_inactive": True,
    "requestable_only": False,
    "in_stock_only": False,
    "filter_flower": False,
    "filter_oil": False,
    "filter_vape": False,
    "filter_pastille": False,
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
    "show_scraper_buttons": True,
    "enable_stock_coloring": True,
    "enable_usage_coloring": True,
    "track_cbd_flower": False,
    "total_green_threshold": 30.0,
    "total_red_threshold": 5.0,
    "single_green_threshold": 10.0,
    "single_red_threshold": 2.0,
    "cbd_total_green_threshold": 30.0,
    "cbd_total_red_threshold": 5.0,
    "cbd_single_green_threshold": 10.0,
    "cbd_single_red_threshold": 2.0,
    "accent_green": "#2ecc71",
    "accent_red": "#e74c3c",
    "total_thc_high_color": "#2ecc71",
    "total_thc_low_color": "#e74c3c",
    "total_cbd_high_color": "#2ecc71",
    "total_cbd_low_color": "#e74c3c",
    "single_thc_high_color": "#2ecc71",
    "single_thc_low_color": "#e74c3c",
    "single_cbd_high_color": "#2ecc71",
    "single_cbd_low_color": "#e74c3c",
    "remaining_thc_high_color": "#2ecc71",
    "remaining_thc_low_color": "#e74c3c",
    "remaining_cbd_high_color": "#2ecc71",
    "remaining_cbd_low_color": "#e74c3c",
    "days_thc_high_color": "#2ecc71",
    "days_thc_low_color": "#e74c3c",
    "days_cbd_high_color": "#2ecc71",
    "days_cbd_low_color": "#e74c3c",
    "used_thc_under_color": "#2ecc71",
    "used_thc_over_color": "#e74c3c",
    "used_cbd_under_color": "#2ecc71",
    "used_cbd_over_color": "#e74c3c",
    "theme_palette_dark": {},
    "theme_palette_light": {},
    "target_daily_grams": 1.0,
    "target_daily_cbd_grams": 0.0,
    "roa_options": {"Vaped": 0.60, "Eaten": 0.10, "Smoked": 0.30},
    "hide_roa_options": False,
    "hide_mixed_dose": False,
    "hide_mix_stock": False,
    "show_stock_form": True,
    "window_geometry": "",
    "settings_window_geometry": "",
    "screen_resolution": "",
    "main_split_ratio": 0.48,
    "mixcalc_geometry": "",
    "mixcalc_stock_geometry": "",
    "stock_column_widths": {},
    "log_column_widths": {},
}


DEFAULT_UI_CONFIG = {
    "dark_mode": True,
    "minimize_to_tray": False,
    "close_to_tray": False,
}

DEFAULT_LIBRARY_CONFIG = {
    "dark_mode": True,
    "column_widths": {},
    "window_geometry": "",
}


def _default_unified_config() -> dict:
    return {
        "version": SCHEMA_VERSION,
        "tracker": copy.deepcopy(DEFAULT_TRACKER_CONFIG),
        "scraper": copy.deepcopy(DEFAULT_CAPTURE_CONFIG),
        "ui": copy.deepcopy(DEFAULT_UI_CONFIG),
        "library": copy.deepcopy(DEFAULT_LIBRARY_CONFIG),
    }


def _read_json(path: Path) -> dict:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception as exc:
        _log_config_error(f"read_json failed for {path}: {exc}")
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
            "track_cbd_flower",
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


def _coerce_color(val: Any, default: str) -> str:
    try:
        text = str(val or "").strip()
    except Exception:
        return default
    if not text:
        return default
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return default
    try:
        int(text, 16)
    except Exception:
        return default
    return f"#{text.lower()}"



def _validate_tracker_config(raw: dict) -> dict:
    cfg = dict(DEFAULT_TRACKER_CONFIG)
    if not isinstance(raw, dict):
        return cfg
    if "track_cbd_flower" not in raw and "track_cbd_usage" in raw:
        cfg["track_cbd_flower"] = _coerce_bool(raw.get("track_cbd_usage"), cfg["track_cbd_flower"])
    bool_keys = {
        "dark_mode",
        "enable_stock_coloring",
        "enable_usage_coloring",
        "track_cbd_flower",
        "hide_roa_options",
        "hide_mixed_dose",
        "hide_mix_stock",
        "show_stock_form",
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
        "main_split_ratio",
    }
    palette_keys = {
        "bg",
        "fg",
        "ctrl_bg",
        "border",
        "accent",
        "list_bg",
        "muted",
    }
    for key, value in raw.items():
        if key not in cfg:
            continue
        if key in bool_keys:
            cfg[key] = _coerce_bool(value, cfg[key])
        elif key in float_keys:
            cfg[key] = _coerce_float(value, cfg[key], 0.0)
        elif key in (
            "accent_green",
            "accent_red",
            "total_thc_high_color",
            "total_thc_low_color",
            "total_cbd_high_color",
            "total_cbd_low_color",
            "single_thc_high_color",
            "single_thc_low_color",
            "single_cbd_high_color",
            "single_cbd_low_color",
            "remaining_thc_high_color",
            "remaining_thc_low_color",
            "remaining_cbd_high_color",
            "remaining_cbd_low_color",
            "days_thc_high_color",
            "days_thc_low_color",
            "days_cbd_high_color",
            "days_cbd_low_color",
            "used_thc_under_color",
            "used_thc_over_color",
            "used_cbd_under_color",
            "used_cbd_over_color",
        ):
            cfg[key] = _coerce_color(value, cfg[key])
        elif key == "roa_options" and isinstance(value, dict):
            cfg[key] = {str(k): float(v) for k, v in value.items() if v is not None}
        elif key in ("theme_palette_dark", "theme_palette_light") and isinstance(value, dict):
            cleaned = {}
            for palette_key, palette_val in value.items():
                if palette_key in palette_keys:
                    cleaned[palette_key] = _coerce_color(palette_val, cfg[key].get(palette_key, ""))
            cfg[key] = cleaned
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
    if not isinstance(raw, dict):
        return cfg
    cfg["version"] = int(raw.get("version") or SCHEMA_VERSION)
    cfg["url"] = str(raw.get("url") or DEFAULT_CAPTURE_CONFIG["url"]).strip()
    cfg["username"] = str(raw.get("username") or "")
    cfg["password"] = str(raw.get("password") or "")
    cfg["username_selector"] = str(raw.get("username_selector") or DEFAULT_CAPTURE_CONFIG["username_selector"])
    cfg["password_selector"] = str(raw.get("password_selector") or DEFAULT_CAPTURE_CONFIG["password_selector"])
    cfg["login_button_selector"] = str(raw.get("login_button_selector") or DEFAULT_CAPTURE_CONFIG["login_button_selector"])
    cfg["organization"] = str(raw.get("organization") or "")
    cfg["organization_selector"] = str(raw.get("organization_selector") or DEFAULT_CAPTURE_CONFIG["organization_selector"]).strip()
    cfg["dump_capture_html"] = _coerce_bool(raw.get("dump_capture_html"), DEFAULT_CAPTURE_CONFIG["dump_capture_html"])
    cfg["dump_api_json"] = _coerce_bool(raw.get("dump_api_json"), DEFAULT_CAPTURE_CONFIG["dump_api_json"])
    cfg["dump_api_full"] = _coerce_bool(raw.get("dump_api_full"), DEFAULT_CAPTURE_CONFIG["dump_api_full"])
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
    cfg["api_only"] = _coerce_bool(raw.get("api_only"), DEFAULT_CAPTURE_CONFIG["api_only"])
    cfg["auto_notify_ha"] = _coerce_bool(raw.get("auto_notify_ha"), DEFAULT_CAPTURE_CONFIG["auto_notify_ha"])
    cfg["show_log_window"] = _coerce_bool(raw.get("show_log_window"), DEFAULT_CAPTURE_CONFIG["show_log_window"])
    cfg["ha_webhook_url"] = str(raw.get("ha_webhook_url") or "")
    cfg["ha_token"] = str(raw.get("ha_token") or "")
    cfg["notify_price_changes"] = _coerce_bool(raw.get("notify_price_changes"), DEFAULT_CAPTURE_CONFIG["notify_price_changes"])
    cfg["notify_stock_changes"] = _coerce_bool(raw.get("notify_stock_changes"), DEFAULT_CAPTURE_CONFIG["notify_stock_changes"])
    cfg["notify_out_of_stock"] = _coerce_bool(raw.get("notify_out_of_stock"), DEFAULT_CAPTURE_CONFIG["notify_out_of_stock"])
    cfg["notify_restock"] = _coerce_bool(raw.get("notify_restock"), DEFAULT_CAPTURE_CONFIG["notify_restock"])
    cfg["notify_new_items"] = _coerce_bool(raw.get("notify_new_items"), DEFAULT_CAPTURE_CONFIG["notify_new_items"])
    cfg["notify_removed_items"] = _coerce_bool(raw.get("notify_removed_items"), DEFAULT_CAPTURE_CONFIG["notify_removed_items"])
    cfg["notify_windows"] = _coerce_bool(raw.get("notify_windows"), DEFAULT_CAPTURE_CONFIG["notify_windows"])
    cfg["notifications_muted"] = _coerce_bool(raw.get("notifications_muted"), DEFAULT_CAPTURE_CONFIG["notifications_muted"])
    snapshot = raw.get("notification_restore_snapshot", DEFAULT_CAPTURE_CONFIG["notification_restore_snapshot"])
    if isinstance(snapshot, dict):
        cfg["notification_restore_snapshot"] = {
            str(k): _coerce_bool(v, False)
            for k, v in snapshot.items()
        }
    else:
        cfg["notification_restore_snapshot"] = {}
    cfg["log_window_hidden_height"] = _coerce_float(
        raw.get("log_window_hidden_height"),
        DEFAULT_CAPTURE_CONFIG["log_window_hidden_height"],
        100.0,
    )
    cfg["quiet_hours_enabled"] = _coerce_bool(raw.get("quiet_hours_enabled"), DEFAULT_CAPTURE_CONFIG["quiet_hours_enabled"])
    cfg["quiet_hours_start"] = str(raw.get("quiet_hours_start") or DEFAULT_CAPTURE_CONFIG["quiet_hours_start"]).strip()
    cfg["quiet_hours_end"] = str(raw.get("quiet_hours_end") or DEFAULT_CAPTURE_CONFIG["quiet_hours_end"]).strip()
    cfg["quiet_hours_interval_seconds"] = _coerce_float(raw.get("quiet_hours_interval_seconds"), DEFAULT_CAPTURE_CONFIG["quiet_hours_interval_seconds"], 1.0)
    cfg["notification_detail"] = str(raw.get("notification_detail") or DEFAULT_CAPTURE_CONFIG["notification_detail"]).strip() or "full"
    cfg["include_inactive"] = _coerce_bool(raw.get("include_inactive"), DEFAULT_CAPTURE_CONFIG["include_inactive"])
    cfg["requestable_only"] = _coerce_bool(raw.get("requestable_only"), DEFAULT_CAPTURE_CONFIG["requestable_only"])
    cfg["in_stock_only"] = _coerce_bool(raw.get("in_stock_only"), DEFAULT_CAPTURE_CONFIG["in_stock_only"])
    cfg["filter_flower"] = _coerce_bool(raw.get("filter_flower"), DEFAULT_CAPTURE_CONFIG["filter_flower"])
    cfg["filter_oil"] = _coerce_bool(raw.get("filter_oil"), DEFAULT_CAPTURE_CONFIG["filter_oil"])
    cfg["filter_vape"] = _coerce_bool(raw.get("filter_vape"), DEFAULT_CAPTURE_CONFIG["filter_vape"])
    cfg["filter_pastille"] = _coerce_bool(raw.get("filter_pastille"), DEFAULT_CAPTURE_CONFIG["filter_pastille"])
    cfg["minimize_to_tray"] = _coerce_bool(raw.get("minimize_to_tray"), DEFAULT_CAPTURE_CONFIG["minimize_to_tray"])
    cfg["close_to_tray"] = _coerce_bool(raw.get("close_to_tray"), DEFAULT_CAPTURE_CONFIG["close_to_tray"])
    return cfg

def _validate_library_config(raw: dict) -> dict:
    cfg = dict(DEFAULT_LIBRARY_CONFIG)
    if not isinstance(raw, dict):
        return cfg
    if "dark_mode" in raw:
        cfg["dark_mode"] = _coerce_bool(raw.get("dark_mode"), cfg["dark_mode"])
    if isinstance(raw.get("column_widths"), dict):
        cfg["column_widths"] = raw.get("column_widths")
    if raw.get("window_geometry"):
        cfg["window_geometry"] = str(raw.get("window_geometry")).strip()
    return cfg


def _normalize_unified_config(raw: dict) -> dict:
    tracker_raw = raw.get("tracker", {}) if isinstance(raw, dict) else {}
    scraper_raw = raw.get("scraper", {}) if isinstance(raw, dict) else {}
    ui_raw = raw.get("ui", {}) if isinstance(raw, dict) else {}
    library_raw = raw.get("library", {}) if isinstance(raw, dict) else {}
    tracker_cfg = _validate_tracker_config(tracker_raw)
    scraper_cfg = _validate_capture_config(scraper_raw)
    ui_cfg = _validate_ui_config(ui_raw, tracker_cfg)
    library_cfg = _validate_library_config(library_raw)
    tracker_cfg["dark_mode"] = ui_cfg["dark_mode"]
    return {
        "version": SCHEMA_VERSION,
        "tracker": tracker_cfg,
        "scraper": scraper_cfg,
        "ui": ui_cfg,
        "library": library_cfg,
    }


def load_unified_config(
    path: Path,
    decrypt_scraper_keys: list[str] | None = None,
    logger=None,
    write_back: bool = True,
) -> dict:
    decrypt_scraper_keys = decrypt_scraper_keys or []

    raw = _read_json(path)
    legacy_tracker = {}
    legacy_scraper = {}
    legacy_library = {}
    legacy_sources = []
    legacy_map = {
        "tracker": [path.with_name("tracker_config.json"), path.parent / "data" / "tracker_config.json"],
        "scraper": [path.with_name("scraper_config.json"), path.parent / "data" / "scraper_config.json"],
        "library": [path.with_name("library_config.json"), path.parent / "data" / "library_config.json"],
        "tracker_settings": [path.with_name("tracker_settings.json"), path.parent / "data" / "tracker_settings.json"],
    }
    for legacy_path in legacy_map["tracker"]:
        if legacy_path.exists():
            legacy_raw = _read_json(legacy_path)
            if _looks_like_tracker(legacy_raw):
                legacy_tracker.update(legacy_raw)
                legacy_sources.append(legacy_path)
    for legacy_path in legacy_map["scraper"]:
        if legacy_path.exists():
            legacy_raw = _read_json(legacy_path)
            if _looks_like_scraper(legacy_raw):
                legacy_scraper.update(legacy_raw)
                legacy_sources.append(legacy_path)
    for legacy_path in legacy_map["library"]:
        if legacy_path.exists():
            legacy_raw = _read_json(legacy_path)
            if isinstance(legacy_raw, dict):
                legacy_library.update(legacy_raw)
                legacy_sources.append(legacy_path)
    for legacy_path in legacy_map["tracker_settings"]:
        if legacy_path.exists():
            legacy_raw = _read_json(legacy_path)
            if _looks_like_tracker(legacy_raw):
                legacy_tracker.update(legacy_raw)
                legacy_sources.append(legacy_path)
    is_unified = any(k in raw for k in ("tracker", "scraper", "ui", "library"))
    unified_raw: dict = {}
    if is_unified:
        unified_raw = raw
    else:
        if raw:
            if _looks_like_scraper(raw):
                unified_raw["scraper"] = raw
            elif _looks_like_tracker(raw):
                unified_raw["tracker"] = raw

    if legacy_scraper:
        unified_raw.setdefault("scraper", {})
        for key, value in legacy_scraper.items():
            unified_raw["scraper"].setdefault(key, value)

    if legacy_library:
        unified_raw.setdefault("library", {})
        for key, value in legacy_library.items():
            unified_raw["library"].setdefault(key, value)

    if legacy_tracker:
        unified_raw.setdefault("tracker", {})
        for key, value in legacy_tracker.items():
            unified_raw["tracker"].setdefault(key, value)

    secrets_need_migration = False
    if "scraper" in unified_raw and decrypt_scraper_keys:
        for key in decrypt_scraper_keys:
            if _secret_needs_encryption(unified_raw["scraper"].get(key, "")):
                secrets_need_migration = True
                break

    if "scraper" in unified_raw:
        for key in decrypt_scraper_keys:
            if key in unified_raw["scraper"]:
                unified_raw["scraper"][key] = decrypt_secret(unified_raw["scraper"].get(key, ""))

    prev_version = raw.get("version") if is_unified else None
    unified = _normalize_unified_config(unified_raw)
    needs_migration = (not is_unified) or (prev_version != SCHEMA_VERSION)
    if secrets_need_migration:
        needs_migration = True
    if legacy_tracker or legacy_scraper or legacy_library:
        needs_migration = True
    if write_back and (not path.exists() or needs_migration):
        try:
            save_unified_config(path, unified, encrypt_scraper_keys=decrypt_scraper_keys)
            if legacy_sources:
                for legacy_path in legacy_sources:
                    try:
                        legacy_path.rename(legacy_path.with_suffix(legacy_path.suffix + ".migrated"))
                    except Exception:
                        pass
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
    # Always protect sensitive scraper fields, even if caller doesn't pass explicit keys.
    for key in ("username", "password", "ha_token"):
        if key not in encrypt_scraper_keys:
            encrypt_scraper_keys.append(key)
    cfg = _normalize_unified_config(data or {})
    for key in encrypt_scraper_keys:
        cfg["scraper"][key] = _maybe_encrypt_secret(cfg["scraper"].get(key, ""))
    _atomic_write_json(path, cfg)


def load_tracker_config(path: Path) -> dict:
    try:
        unified = load_unified_config(
            path,
            decrypt_scraper_keys=["username", "password", "ha_token"],
            write_back=True,
        )
        return _validate_tracker_config(unified.get("tracker", {}))
    except Exception:
        raw = _read_json(path)
        return _validate_tracker_config(raw if isinstance(raw, dict) else {})


def save_tracker_config(path: Path, cfg: dict) -> None:
    try:
        raw = _read_json(path)
        if any(k in raw for k in ("tracker", "scraper", "ui")):
            existing_tracker = raw.get("tracker", {})
        else:
            existing_tracker = raw if isinstance(raw, dict) else {}
        merged_tracker = dict(existing_tracker) if isinstance(existing_tracker, dict) else {}
        merged_tracker.update(cfg or {})
        tracker_cfg = _validate_tracker_config(merged_tracker)
        if any(k in raw for k in ("tracker", "scraper", "ui")):
            raw["tracker"] = tracker_cfg
            raw.setdefault("ui", {})["dark_mode"] = tracker_cfg["dark_mode"]
            save_unified_config(path, raw)
        else:
            unified = _default_unified_config()
            unified["tracker"] = tracker_cfg
            unified["ui"]["dark_mode"] = tracker_cfg["dark_mode"]
            save_unified_config(path, unified)
    except Exception as exc:
        _log_config_error(f"save_tracker_config failed: {exc}")


def _migrate_capture_config(raw: dict) -> dict:
    return _validate_capture_config(raw or {})


def load_capture_config(path: Path, decrypt_keys: list[str], logger=None) -> dict:
    try:
        unified = load_unified_config(
            path,
            decrypt_scraper_keys=decrypt_keys,
            logger=logger,
            write_back=True,
        )
        cfg = _validate_capture_config(unified.get("scraper", {}))
        return cfg
    except Exception as exc:
        if logger:
            try:
                logger(f"Config load failed: {exc}")
            except Exception:
                pass
        return _validate_capture_config({})


def save_capture_config(path: Path, data: dict, encrypt_keys: list[str]):
    try:
        unified = load_unified_config(
            path,
            decrypt_scraper_keys=encrypt_keys,
            write_back=False,
        )
        unified["scraper"] = _migrate_capture_config(data or {})
        save_unified_config(path, unified, encrypt_scraper_keys=encrypt_keys)
    except Exception as exc:
        _log_config_error(f"save_capture_config failed: {exc}")

def load_library_config(path: Path) -> dict:
    try:
        unified = load_unified_config(path, decrypt_scraper_keys=["username", "password", "ha_token"], write_back=True)
        return _validate_library_config(unified.get("library", {}))
    except Exception:
        return _validate_library_config({})


def save_library_config(path: Path, cfg: dict) -> None:
    try:
        unified = load_unified_config(path, decrypt_scraper_keys=["username", "password", "ha_token"], write_back=False)
        unified["library"] = _validate_library_config(cfg or {})
        save_unified_config(path, unified, encrypt_scraper_keys=["username", "password", "ha_token"])
    except Exception as exc:
        _log_config_error(f"save_library_config failed: {exc}")


def _migration_log_path() -> Path:
    appdata = Path(os.getenv("APPDATA", os.path.expanduser("~")))
    return appdata / "FlowerTrack" / "logs" / "config_migrations.log"


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
        old_path = Path(os.getenv("APPDATA", os.path.expanduser("~"))) / "FlowerTrack" / "data" / "config_migrations.log"
        if old_path.exists() and old_path != path and not path.exists():
            try:
                old_path.replace(path)
            except Exception:
                pass
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def _config_error_log_path() -> Path:
    appdata = Path(os.getenv("APPDATA", os.path.expanduser("~")))
    return appdata / "FlowerTrack" / "logs" / "config_errors.log"


def _log_config_error(message: str, logger=None) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {message}"
    if logger:
        try:
            logger(line)
        except Exception:
            pass
    try:
        path = _config_error_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass
