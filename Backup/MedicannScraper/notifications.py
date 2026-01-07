from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

try:
    from win10toast import ToastNotifier as Win10ToastNotifier  # type: ignore
except Exception:
    Win10ToastNotifier = None


def _log_debug(msg: str) -> None:
    """Lightweight stdout logger with timestamp."""
    try:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{stamp}] {msg}")
    except Exception:
        pass


def _maybe_send_windows_notification(
    title: str,
    body: str,
    icon: Optional[Path] = None,
    launch_url: Optional[str] = None,
    ui_logger: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Send a Windows toast using win10toast.
    launch_url is accepted for API compatibility but ignored (win10toast limitation).
    """
    icon_path = str(icon.resolve()) if icon and icon.exists() else None
    if Win10ToastNotifier is None:
        _log_debug("[toast] win10toast not installed.")
        if ui_logger:
            try:
                ui_logger("[toast] win10toast not installed.")
            except Exception:
                pass
        return
    try:
        notifier = Win10ToastNotifier()
        # Use threaded=True to keep Tk event loop responsive; avoid callbacks to reduce WNDPROC issues.
        notifier.show_toast(title, body, icon_path=icon_path, duration=8, threaded=True)
        _log_debug(f"[toast] sent via win10toast: {title} | {body} (icon={icon_path})")
        if ui_logger:
            try:
                ui_logger(f"[toast] sent via win10toast: {title}")
            except Exception:
                pass
    except Exception as exc:
        _log_debug(f"[toast] win10toast failed: {exc}")
        if ui_logger:
            try:
                ui_logger(f"[toast] win10toast failed: {exc}")
            except Exception:
                pass
