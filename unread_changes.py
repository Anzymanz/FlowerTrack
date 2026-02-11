from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from parser import make_identity_key

_STATE_LOCK = threading.Lock()


def unread_changes_path() -> Path:
    appdata = Path(os.getenv("APPDATA", os.path.expanduser("~")))
    return appdata / "FlowerTrack" / "data" / "unread_changes.json"


def _default_state() -> dict[str, Any]:
    return {
        "version": 1,
        "epoch": 0,
        "updated_at": "",
        "items": {},
        "removed_items": {},
    }


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _normalize_item_flags(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    for key in ("new", "price", "stock", "out_of_stock", "restock", "removed"):
        out[key] = _to_bool(raw.get(key))
    price_delta = raw.get("price_delta")
    stock_delta = raw.get("stock_delta")
    if isinstance(price_delta, (int, float)):
        out["price_delta"] = float(price_delta)
    if isinstance(stock_delta, (int, float)):
        out["stock_delta"] = float(stock_delta)
    return out


def _normalize_state(raw: Any) -> dict[str, Any]:
    state = _default_state()
    if not isinstance(raw, dict):
        return state
    try:
        state["epoch"] = max(0, int(raw.get("epoch", 0)))
    except Exception:
        state["epoch"] = 0
    updated_at = raw.get("updated_at")
    state["updated_at"] = str(updated_at or "")
    items = raw.get("items")
    if isinstance(items, dict):
        normalized_items: dict[str, dict[str, Any]] = {}
        for key, val in items.items():
            if not key:
                continue
            normalized_items[str(key)] = _normalize_item_flags(val)
        state["items"] = normalized_items
    removed_items = raw.get("removed_items")
    if isinstance(removed_items, dict):
        normalized_removed: dict[str, dict[str, Any]] = {}
        for key, val in removed_items.items():
            if key and isinstance(val, dict):
                normalized_removed[str(key)] = dict(val)
        state["removed_items"] = normalized_removed
    return state


def load_unread_changes(path: Path | None = None) -> dict[str, Any]:
    target = Path(path or unread_changes_path())
    with _STATE_LOCK:
        if not target.exists():
            return _default_state()
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            return _default_state()
        return _normalize_state(raw)


def save_unread_changes(state: dict[str, Any], path: Path | None = None) -> None:
    target = Path(path or unread_changes_path())
    target.parent.mkdir(parents=True, exist_ok=True)
    clean = _normalize_state(state)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with _STATE_LOCK:
        tmp.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(target)


def _touch(state: dict[str, Any]) -> None:
    state["epoch"] = int(state.get("epoch", 0)) + 1
    state["updated_at"] = datetime.now(timezone.utc).isoformat()


def _entry_has_any_flag(entry: dict[str, Any]) -> bool:
    return any(
        _to_bool(entry.get(k))
        for k in ("new", "price", "stock", "out_of_stock", "restock", "removed")
    )


def _ensure_entry(items: dict[str, Any], key: str) -> dict[str, Any]:
    entry = items.get(key)
    if not isinstance(entry, dict):
        entry = {}
        items[key] = entry
    return entry


def merge_unread_changes(diff: dict[str, Any], current_items: list[dict], path: Path | None = None) -> bool:
    if not isinstance(diff, dict):
        return False
    state = load_unread_changes(path)
    items_map: dict[str, dict[str, Any]] = state.get("items", {})
    removed_map: dict[str, dict[str, Any]] = state.get("removed_items", {})
    changed = False

    def set_flag(item: dict[str, Any], flag: str, *, price_delta: Any = None, stock_delta: Any = None) -> None:
        nonlocal changed
        key = make_identity_key(item)
        if not key:
            return
        entry = _ensure_entry(items_map, key)
        if not _to_bool(entry.get(flag)):
            entry[flag] = True
            changed = True
        if flag == "removed":
            if not isinstance(removed_map.get(key), dict):
                changed = True
            removed_map[key] = dict(item, is_removed=True, is_new=False)
        if isinstance(price_delta, (int, float)):
            pd = float(price_delta)
            if entry.get("price_delta") != pd:
                entry["price_delta"] = pd
                changed = True
        if isinstance(stock_delta, (int, float)):
            sd = float(stock_delta)
            if entry.get("stock_delta") != sd:
                entry["stock_delta"] = sd
                changed = True

    for it in diff.get("new_items", []) or []:
        if isinstance(it, dict):
            set_flag(it, "new")
    for it in diff.get("price_changes", []) or []:
        if isinstance(it, dict):
            set_flag(it, "price", price_delta=it.get("price_delta"))
    for it in diff.get("stock_changes", []) or []:
        if isinstance(it, dict):
            set_flag(it, "stock", stock_delta=it.get("stock_delta"))
    for it in diff.get("out_of_stock_changes", []) or []:
        if isinstance(it, dict):
            set_flag(it, "out_of_stock", stock_delta=it.get("stock_delta"))
    for it in diff.get("restock_changes", []) or []:
        if isinstance(it, dict):
            set_flag(it, "restock", stock_delta=it.get("stock_delta"))
    for it in diff.get("removed_items", []) or []:
        if isinstance(it, dict):
            set_flag(it, "removed")

    current_keys = {make_identity_key(it) for it in current_items if isinstance(it, dict)}
    current_keys.discard("")
    for key in list(current_keys):
        if key in removed_map:
            removed_map.pop(key, None)
            changed = True
        entry = items_map.get(key)
        if isinstance(entry, dict) and _to_bool(entry.get("removed")):
            entry["removed"] = False
            changed = True

    for key in list(items_map.keys()):
        entry = items_map.get(key)
        if not isinstance(entry, dict):
            items_map.pop(key, None)
            changed = True
            continue
        if not _entry_has_any_flag(entry):
            items_map.pop(key, None)
            changed = True

    state["items"] = items_map
    state["removed_items"] = removed_map
    if changed:
        _touch(state)
        save_unread_changes(state, path)
    return changed


def clear_unread_changes(path: Path | None = None) -> bool:
    state = load_unread_changes(path)
    had_changes = bool(state.get("items")) or bool(state.get("removed_items"))
    state["items"] = {}
    state["removed_items"] = {}
    _touch(state)
    save_unread_changes(state, path)
    return had_changes


def unread_removed_items_for_export(current_items: list[dict], path: Path | None = None) -> list[dict]:
    state = load_unread_changes(path)
    removed_map: dict[str, dict[str, Any]] = state.get("removed_items", {})
    if not removed_map:
        return []
    current_keys = {make_identity_key(it) for it in current_items if isinstance(it, dict)}
    current_keys.discard("")
    out: list[dict] = []
    changed = False
    for key in list(removed_map.keys()):
        snap = removed_map.get(key)
        if not isinstance(snap, dict):
            removed_map.pop(key, None)
            changed = True
            continue
        if key in current_keys:
            removed_map.pop(key, None)
            entry = state.get("items", {}).get(key)
            if isinstance(entry, dict) and _to_bool(entry.get("removed")):
                entry["removed"] = False
            changed = True
            continue
        out.append(dict(snap, is_removed=True, is_new=False))
    if changed:
        state["removed_items"] = removed_map
        # Drop now-empty entries.
        items_map = state.get("items", {})
        if isinstance(items_map, dict):
            for key in list(items_map.keys()):
                entry = items_map.get(key)
                if isinstance(entry, dict) and not _entry_has_any_flag(entry):
                    items_map.pop(key, None)
            state["items"] = items_map
        _touch(state)
        save_unread_changes(state, path)
    return out


def unread_payload(path: Path | None = None) -> dict[str, Any]:
    state = load_unread_changes(path)
    items = state.get("items", {})
    if not isinstance(items, dict):
        items = {}
    return {
        "epoch": int(state.get("epoch", 0)),
        "updated_at": str(state.get("updated_at") or ""),
        "items": items,
    }

