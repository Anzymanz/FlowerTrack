from __future__ import annotations

from datetime import datetime
from threading import Event
from typing import Callable


class IntervalScheduler:
    """Handles wait intervals with optional overnight backoff and stop checks."""

    def __init__(self, stop_event: Event, wait_fn: Callable[[float, str], bool]) -> None:
        self.stop_event: Event = stop_event
        self.wait_fn: Callable[[float, str], bool] = wait_fn

    def next_interval(self, base_interval: float) -> float:
        """Apply overnight rule: between 00:00-07:00, ensure at least 3600s."""
        interval = base_interval
        try:
            now = datetime.now().time()
            if 0 <= now.hour < 7:
                interval = max(interval, 3600.0)
        except Exception:
            pass
        return interval

    def wait(self, seconds: float, label: str) -> bool:
        """Wait using the provided wait_fn (returns True if stop requested)."""
        return self.wait_fn(seconds, label=label)
