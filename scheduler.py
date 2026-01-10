from __future__ import annotations

from datetime import datetime
from threading import Event
from typing import Callable


class IntervalScheduler:
    """Handles wait intervals with optional overnight backoff and stop checks."""

    def __init__(self, stop_event: Event, wait_fn: Callable[[float, str], bool]) -> None:
        self.stop_event: Event = stop_event
        self.wait_fn: Callable[[float, str], bool] = wait_fn

    def next_interval(self, base_interval: float, cfg: dict) -> float:
        """Return the next interval, honoring quiet-hours override when enabled."""
        interval = base_interval
        try:
            if not cfg.get("quiet_hours_enabled"):
                return interval
            quiet_interval = float(cfg.get("quiet_hours_interval_seconds", interval) or interval)
            if quiet_interval <= 0:
                quiet_interval = interval
            start = _parse_time(cfg.get("quiet_hours_start"))
            end = _parse_time(cfg.get("quiet_hours_end"))
            now = datetime.now().time()
            if _in_window(now, start, end):
                interval = quiet_interval
        except Exception:
            pass
        return interval

    def wait(self, seconds: float, label: str) -> bool:
        """Wait using the provided wait_fn (returns True if stop requested)."""
        return self.wait_fn(seconds, label=label)


def _parse_time(value: str | None):
    if not value:
        return None
    try:
        parts = [int(p) for p in str(value).strip().split(":")[:2]]
        if len(parts) != 2:
            return None
        hour, minute = parts
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            return None
        return datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0).time()
    except Exception:
        return None


def _in_window(now, start, end) -> bool:
    if start is None or end is None:
        return False
    if start <= end:
        return start <= now < end
    # Overnight window (e.g. 22:00 -> 07:00)
    return now >= start or now < end
