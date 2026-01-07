from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Tuple

from models_inventory import Flower


def is_cbd_dominant(flower: Flower | None) -> bool:
    if flower is None:
        return False
    try:
        return float(flower.cbd_pct) >= float(flower.thc_pct)
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
