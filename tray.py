from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

try:
    import pystray  # type: ignore
    from PIL import Image, ImageDraw  # type: ignore
except Exception:
    pystray = None
    Image = None
    ImageDraw = None


def tray_supported() -> bool:
    return pystray is not None and Image is not None


def make_tray_image(running: bool, warn: bool = False):
    if Image is None or ImageDraw is None:
        return None
    size = 32
    if warn:
        color = (220, 180, 0, 255)
    else:
        color = (0, 200, 0, 255) if running else (200, 0, 0, 255)
    bg = (0, 0, 0, 0)
    img = Image.new("RGBA", (size, size), bg)  # type: ignore
    draw = ImageDraw.Draw(img)
    pad = 4
    draw.ellipse((pad, pad, size - pad, size - pad), fill=color)
    return img


def compute_tray_state(is_running: bool, status: str | None = None, error_count: int = 0, empty_retry: bool = False):
    warn = bool(empty_retry) or (error_count > 0)
    if status and str(status).lower() in {"retrying", "faulted", "error"}:
        warn = True
    return bool(is_running), warn


def create_tray_icon(
    name: str, title: str, running: bool, warn: bool, on_open: Callable[[], None], on_quit: Callable[[], None]
):
    if not tray_supported():
        return None
    try:
        img = make_tray_image(running, warn)
        menu = pystray.Menu(
            pystray.MenuItem("Open", lambda icon, item: on_open(), default=True),
            pystray.MenuItem("Quit", lambda icon, item: on_quit()),
        )
        icon = pystray.Icon(name, img, title, menu)
        icon.title = title
        icon.run_detached()
        if hasattr(icon, "visible"):
            icon.visible = True
        return icon
    except Exception:
        return None


def update_tray_icon(icon, running: bool, warn: bool = False):
    """Update tray icon state safely."""
    if not icon or not tray_supported():
        return
    try:
        img = make_tray_image(running, warn)
        if img is not None:
            icon.icon = img
    except Exception:
        pass


def stop_tray_icon(icon) -> None:
    try:
        if icon:
            icon.stop()
    except Exception:
        pass
