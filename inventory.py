from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from app_core import APP_DIR

@dataclass
class Flower:
    name: str
    thc_pct: float
    cbd_pct: float
    grams_remaining: float = 0.0

    def remove_by_grams(self, grams: float) -> None:
        if grams > self.grams_remaining:
            raise ValueError("Not enough stock for this dose.")
        self.grams_remaining -= grams

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
        flowers[name].add_stock(grams, thc_pct, cbd_pct)
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
