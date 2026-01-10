from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

from app_core import APP_DIR

# New storage locations under FlowerTrack AppData
TRACKER_DATA_FILE = Path(APP_DIR) / "data" / "tracker_data.json"
TRACKER_CONFIG_FILE = Path(APP_DIR) / "flowertrack_config.json"
TRACKER_LIBRARY_FILE = Path(APP_DIR) / "data" / "library_data.json"



def ensure_dirs() -> None:
    TRACKER_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRACKER_LIBRARY_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_tracker_data(logger: Optional[Callable[[str], None]] = None) -> dict:
    ensure_dirs()
    if not TRACKER_DATA_FILE.exists():
        if logger:
            logger(f"Tracker data not found at {TRACKER_DATA_FILE}")
        return {}
    try:
        return json.loads(TRACKER_DATA_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        if logger:
            logger(f"Failed to load tracker data from {TRACKER_DATA_FILE}: {exc}")
        return {}


def save_tracker_data(data: dict, logger: Optional[Callable[[str], None]] = None) -> None:
    ensure_dirs()
    try:
        TRACKER_DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as exc:
        if logger:
            logger(f"Failed to save tracker data: {exc}")
