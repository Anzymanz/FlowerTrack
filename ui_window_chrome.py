from __future__ import annotations

import ctypes
import os
from typing import Callable


def apply_dark_titlebar(
    window,
    enable: bool,
    *,
    allow_parent: bool = True,
    log_fn: Callable[[str], None] | None = None,
) -> bool:
    """Apply Windows immersive dark title bar style to a Tk window."""
    if os.name != "nt":
        return False
    try:
        hwnd = int(window.winfo_id())
        if allow_parent:
            get_parent = ctypes.windll.user32.GetParent
            parent = get_parent(hwnd)
            while parent:
                hwnd = parent
                parent = get_parent(hwnd)
        value = ctypes.c_int(1 if enable else 0)
        dwm_set = ctypes.windll.dwmapi.DwmSetWindowAttribute
        # 20 is current, 19 is fallback for older Windows builds.
        if dwm_set(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value)) != 0:
            dwm_set(hwnd, 19, ctypes.byref(value), ctypes.sizeof(value))
        return True
    except Exception as exc:
        if log_fn is not None:
            try:
                log_fn(f"Suppressed exception: {exc}")
            except Exception:
                pass
        return False
