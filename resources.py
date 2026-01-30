from __future__ import annotations

import os
import sys
from pathlib import Path


def resource_path(relative: str) -> str:
    """Resolve resource paths for dev and PyInstaller builds."""
    if not relative:
        return relative
    path = Path(relative)
    if path.is_absolute():
        return str(path)
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    candidates = [
        base / relative,
        base / "assets" / relative,
        Path(os.getcwd()) / relative,
        Path(os.getcwd()) / "assets" / relative,
    ]
    for cand in candidates:
        if cand.exists():
            return str(cand)
    return str(candidates[0])
