from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path


def _log_storage_error(message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {message}"
    try:
        print(line)
    except Exception:
        pass
    try:
        appdata = Path(os.getenv("APPDATA", os.path.expanduser("~")))
        path = appdata / "FlowerTrack" / "logs" / "storage_errors.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def _atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    if path.exists():
        try:
            shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        except Exception as exc:
            _log_storage_error(f"backup failed for {path}: {exc}")
    tmp.write_text(text, encoding=encoding)
    tmp.replace(path)


def _atomic_write_json(path: Path, data) -> None:
    _atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def _read_text_with_backup(path: Path) -> str | None:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception as exc:
        _log_storage_error(f"read failed for {path}: {exc}")
    backup = path.with_suffix(path.suffix + ".bak")
    if backup.exists():
        try:
            text = backup.read_text(encoding="utf-8")
            _log_storage_error(f"restored from backup for {path}")
            return text
        except Exception as exc:
            _log_storage_error(f"backup read failed for {backup}: {exc}")
    return None


def _read_json_with_backup(path: Path) -> object | None:
    raw = _read_text_with_backup(path)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception as exc:
        _log_storage_error(f"json decode failed for {path}: {exc}")
    backup = path.with_suffix(path.suffix + ".bak")
    if backup.exists():
        try:
            data = json.loads(backup.read_text(encoding="utf-8"))
            _log_storage_error(f"restored json from backup for {path}")
            return data
        except Exception as exc:
            _log_storage_error(f"backup json decode failed for {backup}: {exc}")
    return None


def load_last_parse(path: Path) -> list[dict]:
    """Load last parsed items from disk."""
    try:
        data = _read_json_with_backup(path)
        if isinstance(data, list):
            return data
    except Exception as exc:
        _log_storage_error(f"load_last_parse failed: {exc}")
    return []


def save_last_parse(path: Path, items: list[dict]) -> None:
    """Persist the latest parsed items to disk."""
    try:
        _atomic_write_json(path, items)
    except Exception as exc:
        _log_storage_error(f"save_last_parse failed: {exc}")


def append_change_log(path: Path, record: dict) -> None:
    """Append a single change record to the ndjson log."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        _log_storage_error(f"append_change_log failed: {exc}")


def load_last_change(path: Path) -> str | None:
    """Load the last change summary line."""
    try:
        text = _read_text_with_backup(path)
        if text is not None:
            text = text.strip()
            return text or None
    except Exception as exc:
        _log_storage_error(f"load_last_change failed: {exc}")
    return None


def save_last_change(path: Path, summary: str) -> None:
    """Persist the last change summary line."""
    try:
        _atomic_write_text(path, summary)
    except Exception as exc:
        _log_storage_error(f"save_last_change failed: {exc}")

def load_last_scrape(path: Path) -> str | None:
    """Load the last successful scrape timestamp."""
    try:
        text = _read_text_with_backup(path)
        if text is not None:
            text = text.strip()
            return text or None
    except Exception as exc:
        _log_storage_error(f"load_last_scrape failed: {exc}")
    return None


def save_last_scrape(path: Path, summary: str) -> None:
    """Persist the last successful scrape timestamp."""
    try:
        _atomic_write_text(path, summary)
    except Exception as exc:
        _log_storage_error(f"save_last_scrape failed: {exc}")

