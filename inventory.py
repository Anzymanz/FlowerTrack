from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
import json
import shutil
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from app_core import APP_DIR

SCHEMA_VERSION = 1

@dataclass
class Flower:
    name: str
    thc_pct: float
    cbd_pct: float
    grams_remaining: float = 0.0

    def remove_by_grams(self, grams: float) -> None:
        epsilon = 1e-6
        if grams > self.grams_remaining + epsilon:
            raise ValueError("Not enough stock for this dose.")
        self.grams_remaining = max(0.0, self.grams_remaining - grams)

    def add_stock(self, grams: float, thc_pct: float, cbd_pct: float) -> None:
        if abs(thc_pct - self.thc_pct) > 1e-6 or abs(cbd_pct - self.cbd_pct) > 1e-6:
            raise ValueError("Potency for this flower does not match existing record.")
        # Set to the new absolute value rather than incrementing
        self.grams_remaining = grams

# New storage locations under FlowerTrack AppData
TRACKER_DATA_FILE = Path(APP_DIR) / "data" / "tracker_data.json"
TRACKER_CONFIG_FILE = Path(APP_DIR) / "flowertrack_config.json"
TRACKER_LIBRARY_FILE = Path(APP_DIR) / "data" / "library_data.json"

def ensure_dirs() -> None:
    TRACKER_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRACKER_LIBRARY_FILE.parent.mkdir(parents=True, exist_ok=True)

def _normalize_log_entry(log: dict) -> dict:
    if not isinstance(log, dict):
        return log
    if 'grams_used' not in log and 'grams' in log:
        log['grams_used'] = log.get('grams')
    if 'grams' not in log and 'grams_used' in log:
        log['grams'] = log.get('grams_used')
    if 'efficiency' not in log:
        log['efficiency'] = 1.0
    if 'time_display' not in log:
        try:
            if isinstance(log.get('time'), str) and ' ' in log['time']:
                log['time_display'] = log['time'].split(' ')[-1]
        except Exception:
            pass
    if 'date' not in log:
        try:
            if isinstance(log.get('time'), str) and ' ' in log['time']:
                log['date'] = log['time'].split(' ')[0]
        except Exception:
            pass
    if 'thc_mg' not in log:
        log['thc_mg'] = 0.0
    if 'cbd_mg' not in log:
        log['cbd_mg'] = 0.0
    return log


def _migrate_tracker_data(data: dict) -> dict:
    if not isinstance(data, dict):
        return {"schema_version": SCHEMA_VERSION, "logs": data if isinstance(data, list) else []}
    schema_version = int(data.get("schema_version", 0) or 0)
    if schema_version < SCHEMA_VERSION:
        data["schema_version"] = SCHEMA_VERSION
    return data


def load_tracker_data(path: Path | None = None, logger: Optional[Callable[[str], None]] = None) -> dict:
    target = Path(path) if path else TRACKER_DATA_FILE
    if not target.exists():
        if logger:
            logger(f"Tracker data not found at {target}")
        return {}
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            raw = {"logs": raw}
        data = _migrate_tracker_data(raw)
        if isinstance(data, dict) and isinstance(data.get('logs'), list):
            data['logs'] = [_normalize_log_entry(log) for log in data['logs']]
        return data
    except Exception as exc:
        if logger:
            logger(f"Failed to load tracker data from {target}: {exc}")
        return {}

def _backup_tracker_data(target: Path, max_backups: int = 5) -> None:
    try:
        if not target.exists():
            return
        backup_dir = target.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = backup_dir / f"tracker_data-{stamp}.json"
        backup_path.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
        backups = sorted(backup_dir.glob("tracker_data-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in backups[max_backups:]:
            try:
                old.unlink()
            except Exception:
                pass
    except Exception:
        pass


def save_tracker_data(data: dict, path: Path | None = None, logger: Optional[Callable[[str], None]] = None) -> None:
    target = Path(path) if path else TRACKER_DATA_FILE
    try:
        payload = data
        if isinstance(data, dict):
            payload = dict(data)
            payload.setdefault("schema_version", SCHEMA_VERSION)
        target.parent.mkdir(parents=True, exist_ok=True)
        _backup_tracker_data(target)
        tmp = target.with_suffix(target.suffix + ".tmp")
        if target.exists():
            try:
                shutil.copy2(target, target.with_suffix(target.suffix + ".bak"))
            except Exception:
                pass
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(target)
    except Exception as exc:
        if logger:
            logger(f"Failed to save tracker data: {exc}")

def is_cbd_dominant(flower: Flower | None) -> bool:
    if flower is None:
        return False
    try:
        return float(flower.cbd_pct) >= 5.0
    except Exception:
        return False

def add_stock_entry(
    flowers: Dict[str, Flower],
    name: str,
    grams: float,
    thc_pct: float,
    cbd_pct: float,
) -> None:
    """Add or update stock for a flower."""
    if name in flowers:
        existing = flowers[name]
        # Allow potency updates when the old stock is effectively empty.
        if existing.grams_remaining <= 1e-6:
            existing.thc_pct = thc_pct
            existing.cbd_pct = cbd_pct
            existing.grams_remaining = grams
            return
        existing.add_stock(grams, thc_pct, cbd_pct)
    else:
        flowers[name] = Flower(name=name, thc_pct=thc_pct, cbd_pct=cbd_pct, grams_remaining=grams)

def log_dose_entry(
    flowers: Dict[str, Flower],
    logs: List[dict],
    name: str,
    grams_used: float,
    roa: str,
    roa_options: Dict[str, float],
) -> Tuple[float, dict]:
    """
    Log a dose for a flower; updates flower remaining and returns (remaining, log_entry).
    roa_options maps ROA to efficiency (0-1).
    """
    if name not in flowers:
        raise ValueError("Selected flower is not in stock.")
    flower = flowers[name]
    flower.remove_by_grams(grams_used)
    efficiency = roa_options.get(roa, 1.0)
    raw_thc_mg = grams_used * 1000 * (flower.thc_pct / 100.0)
    raw_cbd_mg = grams_used * 1000 * (flower.cbd_pct / 100.0)
    thc_mg = raw_thc_mg * efficiency
    cbd_mg = raw_cbd_mg * efficiency
    remaining = flower.grams_remaining
    now = datetime.now()
    log_entry = {
        "date": now.date().isoformat(),
        "time": now.strftime("%Y-%m-%d %H:%M"),
        "time_display": now.strftime("%H:%M"),
        "flower": name,
        "roa": roa,
        "grams": grams_used,
        "grams_used": grams_used,
        "efficiency": efficiency,
        "thc_mg": thc_mg,
        "cbd_mg": cbd_mg,
        "remaining": remaining,
        "is_cbd_dominant": is_cbd_dominant(flower),
    }
    logs.append(log_entry)
    return remaining, log_entry
