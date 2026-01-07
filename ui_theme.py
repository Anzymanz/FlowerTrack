from __future__ import annotations

from typing import Dict
from tkinter import ttk

from theme import apply_style_theme, compute_colors, set_titlebar_dark


def apply_window_theme(style: ttk.Style, root, dark: bool) -> Dict[str, str]:
    colors = compute_colors(dark)
    apply_style_theme(style, colors)
    try:
        root.configure(bg=colors["bg"])
    except Exception:
        pass
    return colors
