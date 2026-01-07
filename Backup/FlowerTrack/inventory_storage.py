from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Callable, Optional

from app_core import APP_DIR

# New storage locations under FlowerTrack AppData
TRACKER_DATA_FILE = Path(APP_DIR) / "data" / "tracker_data.json"
TRACKER_CONFIG_FILE = Path(APP_DIR) / "flowertrack_config.json"
TRACKER_LIBRARY_FILE = Path(APP_DIR) / "data" / "library_data.json"

# Legacy MedicannScraper locations (for migration)
LEGACY_APP_DIR = Path(os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "MedicannScraper"))
LEGACY_DATA_FILE = LEGACY_APP_DIR / "data" / "tracker_data.json"
LEGACY_LIBRARY_FILE = LEGACY_APP_DIR / "data" / "library_data.json"


def ensure_dirs() -> None:
    TRACKER_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRACKER_LIBRARY_FILE.parent.mkdir(parents=True, exist_ok=True)


def _is_empty_tracker(path: Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return not data.get("flowers") and not data.get("logs")
    except Exception:
        return True


def migrate_legacy(logger: Optional[Callable[[str], None]] = None) -> None:
    """Copy legacy MedicannScraper files into new location if none exist or if current is empty."""
    ensure_dirs()
    try:
        # Tracker data
        if LEGACY_DATA_FILE.exists():
            if (not TRACKER_DATA_FILE.exists()) or _is_empty_tracker(TRACKER_DATA_FILE):
                shutil.copy2(LEGACY_DATA_FILE, TRACKER_DATA_FILE)
                if logger:
                    logger(f"Migrated legacy tracker data from {LEGACY_DATA_FILE}")
        # Library data
        if LEGACY_LIBRARY_FILE.exists() and not TRACKER_LIBRARY_FILE.exists():
            shutil.copy2(LEGACY_LIBRARY_FILE, TRACKER_LIBRARY_FILE)
            if logger:
                logger(f"Migrated legacy library data from {LEGACY_LIBRARY_FILE}")
        # Also migrate data/library from current working dir if present (portable runs)
        cwd_data = Path("data") / "tracker_data.json"
        cwd_lib = Path("data") / "library_data.json"
        if cwd_data.exists() and ((not TRACKER_DATA_FILE.exists()) or _is_empty_tracker(TRACKER_DATA_FILE)):
            shutil.copy2(cwd_data, TRACKER_DATA_FILE)
            if logger:
                logger(f"Migrated tracker data from {cwd_data}")
        if cwd_lib.exists() and not TRACKER_LIBRARY_FILE.exists():
            shutil.copy2(cwd_lib, TRACKER_LIBRARY_FILE)
            if logger:
                logger(f"Migrated library data from {cwd_lib}")
    except Exception:
        if logger:
            logger("Legacy migration failed.")


def load_tracker_data(logger: Optional[Callable[[str], None]] = None) -> dict:
    ensure_dirs()
    migrate_legacy(logger=logger)
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
