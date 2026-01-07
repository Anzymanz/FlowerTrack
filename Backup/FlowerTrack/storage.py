from __future__ import annotations

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
        path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
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
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(summary, encoding="utf-8")
    except Exception:
        pass
