from __future__ import annotations

import ctypes
from pathlib import Path
from tkinter import ttk
from logger import log_event


def compute_colors(dark: bool) -> dict:
    bg = "#111" if dark else "#f4f4f4"
    fg = "#eee" if dark else "#111"
    ctrl_bg = "#222" if dark else "#e6e6e6"
    # Dark accent toned to a neutral gray to keep hover/selection subtle in dark mode.
    accent = "#3c3c3c" if dark else "#666666"
    list_bg = "#1e1e1e" if dark else "#ffffff"
    return {
        "bg": bg,
        "fg": fg,
        "ctrl_bg": ctrl_bg,
        "accent": accent,
        "list_bg": list_bg,
    }


def apply_style_theme(style: ttk.Style, colors: dict) -> None:
    bg = colors["bg"]
    fg = colors["fg"]
    ctrl_bg = colors["ctrl_bg"]
    accent = colors["accent"]
    style.theme_use("clam")
    style.configure("TFrame", background=bg)
    style.configure("TLabel", background=bg, foreground=fg)
    hint_fg = "#c77" if bg == "#111" else "#a33"
    style.configure("Hint.TLabel", background=bg, foreground=hint_fg)
    style.configure("TLabelframe", background=bg, foreground=fg, bordercolor=ctrl_bg)
    style.configure("TLabelframe.Label", background=bg, foreground=fg)
    style.configure(
        "TButton",
        background=ctrl_bg,
        foreground=fg,
        bordercolor=ctrl_bg,
        focusthickness=3,
        focuscolor=ctrl_bg,
    )
    # Subtle hover/active colors for buttons
    style.map(
        "TButton",
        background=[("active", accent), ("pressed", accent)],
        foreground=[("active", fg), ("pressed", fg)],
    )
    style.map(
        "TCheckbutton",
        background=[("active", accent)],
        foreground=[("active", fg)],
    )
    style.configure("TCheckbutton", background=bg, foreground=fg)
    scrollbar_bg = "#1a1a1a" if colors["bg"] == "#111" else "#dcdcdc"
    scrollbar_trough = "#0d0d0d" if colors["bg"] == "#111" else "#cfcfcf"
    style.configure(
        "Dark.Vertical.TScrollbar",
        background=scrollbar_bg,
        troughcolor=scrollbar_trough,
        arrowcolor=fg,
        bordercolor=scrollbar_bg,
        lightcolor=scrollbar_bg,
        darkcolor=scrollbar_bg,
    )
    style.map(
        "Dark.Vertical.TScrollbar",
        background=[("active", accent)],
        arrowcolor=[("active", fg)],
    )
    style.configure("TEntry", fieldbackground=ctrl_bg, foreground=fg, insertcolor=fg)
    style.map("TEntry", fieldbackground=[("readonly", ctrl_bg)], foreground=[("readonly", fg)])
    style.configure("TNotebook", background=bg, bordercolor=ctrl_bg)
    style.configure(
        "TNotebook.Tab",
        background=ctrl_bg,
        foreground=fg,
        lightcolor=ctrl_bg,
        bordercolor=ctrl_bg,
        focuscolor=ctrl_bg,
    )
    style.configure("Settings.TNotebook.Tab", padding=[10, 4])
    style.map(
        "Settings.TNotebook.Tab",
        background=[("selected", accent), ("!selected", ctrl_bg)],
        foreground=[("selected", bg), ("!selected", fg)],
    )
    style.configure("TProgressbar", background=accent, troughcolor=ctrl_bg)
    style.configure("Parser.TLabelframe", borderwidth=2, relief="groove")
    style.configure("Parser.TLabelframe.Label", padding=(6, 0))


def set_titlebar_dark(window, enable: bool) -> None:
    """Attempt to set a window's titlebar to dark mode on Windows."""
    try:
        hwnd = window.winfo_id()
        # Walk up to the top-level window handle (Tk can return a child handle)
        get_parent = ctypes.windll.user32.GetParent
        parent = get_parent(hwnd)
        while parent:
            hwnd = parent
            parent = get_parent(hwnd)
        value = ctypes.c_int(1 if enable else 0)
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19
        if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)) != 0:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1, ctypes.byref(value), ctypes.sizeof(value))
    except Exception as exc:
        log_event("theme.titlebar_failed", {"error": str(exc)})
