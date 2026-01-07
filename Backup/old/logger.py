from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional


class UILogger:
    """
    Simple UI-aware logger that fans out to console widget and optional tray updater.
    Severity: info, warn, error.
    """

    def __init__(
        self,
        console_fn: Optional[Callable[[str], None]] = None,
        tray_fn: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.console_fn: Optional[Callable[[str], None]] = console_fn
        self.tray_fn: Optional[Callable[[str], None]] = tray_fn

    def _emit(self, level: str, msg: str) -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{stamp}] [{level}] {msg}"
        if self.console_fn:
            try:
                self.console_fn(line)
            except Exception:
                pass
        if self.tray_fn:
            try:
                self.tray_fn(line)
            except Exception:
                pass

    def info(self, msg: str) -> None:
        self._emit("INFO", msg)

    def warn(self, msg: str) -> None:
        self._emit("WARN", msg)

    def error(self, msg: str) -> None:
        self._emit("ERROR", msg)
