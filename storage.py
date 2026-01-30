from __future__ import annotations



def _atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding=encoding)
    tmp.replace(path)


def _atomic_write_json(path: Path, data) -> None:
    _atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))
import json
from pathlib import Path


def load_last_parse(path: Path) -> list[dict]:
    """Load last parsed items from disk."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def save_last_parse(path: Path, items: list[dict]) -> None:
    """Persist the latest parsed items to disk."""
    try:
        _atomic_write_json(path, items)
    except Exception:
        pass


def append_change_log(path: Path, record: dict) -> None:
    """Append a single change record to the ndjson log."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def load_last_change(path: Path) -> str | None:
    """Load the last change summary line."""
    try:
        if path.exists():
            text = path.read_text(encoding="utf-8").strip()
            return text or None
    except Exception:
        pass
    return None


def save_last_change(path: Path, summary: str) -> None:
    """Persist the last change summary line."""
    try:
        _atomic_write_text(path, summary)
    except Exception:
        pass

def load_last_scrape(path: Path) -> str | None:
    """Load the last successful scrape timestamp."""
    try:
        if path.exists():
            text = path.read_text(encoding="utf-8").strip()
            return text or None
    except Exception:
        pass
    return None


def save_last_scrape(path: Path, summary: str) -> None:
    """Persist the last successful scrape timestamp."""
    try:
        _atomic_write_text(path, summary)
    except Exception:
        pass

