from __future__ import annotations

import json
import os
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
    tmp.write_text(text, encoding=encoding)
    tmp.replace(path)


def _atomic_write_json(path: Path, data) -> None:
    _atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def load_last_parse(path: Path) -> list[dict]:
    """Load last parsed items from disk."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
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
        if path.exists():
            text = path.read_text(encoding="utf-8").strip()
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
        if path.exists():
            text = path.read_text(encoding="utf-8").strip()
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

