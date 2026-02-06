from __future__ import annotations

import base64
import ctypes
import struct
import zlib
from tkinter import ttk
import tkinter as tk
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
    apply_rounded_buttons(style, colors)


def _hex_to_rgba(color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    value = (color or "").lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        return (0, 0, 0, alpha)
    r = int(value[0:2], 16)
    g = int(value[2:4], 16)
    b = int(value[4:6], 16)
    return (r, g, b, alpha)


def _build_rounded_rgba(
    width: int,
    height: int,
    radius: int,
    fill: str,
    border: str,
    border_width: int = 1,
) -> bytes:
    fill_rgba = _hex_to_rgba(fill, 255)
    border_rgba = _hex_to_rgba(border, 255)
    bg_rgba = (0, 0, 0, 0)
    r = max(0, min(radius, min(width, height) // 2))
    r_inner = max(0, r - border_width)

    def inside_round(x: int, y: int, w: int, h: int, rad: int) -> bool:
        if rad <= 0:
            return True
        if rad <= x < w - rad and 0 <= y < h:
            return True
        if rad <= y < h - rad and 0 <= x < w:
            return True
        corners = (
            (rad - 0.5, rad - 0.5),
            (w - rad - 0.5, rad - 0.5),
            (rad - 0.5, h - rad - 0.5),
            (w - rad - 0.5, h - rad - 0.5),
        )
        for cx, cy in corners:
            dx = x - cx
            dy = y - cy
            if dx * dx + dy * dy <= (rad - 0.5) * (rad - 0.5):
                return True
        return False

    data = bytearray()
    for y in range(height):
        for x in range(width):
            if not inside_round(x, y, width, height, r):
                data.extend(bg_rgba)
                continue
            if border_width > 0 and not inside_round(x, y, width, height, r_inner):
                data.extend(border_rgba)
            else:
                data.extend(fill_rgba)
    return bytes(data)


def _png_bytes(width: int, height: int, rgba: bytes) -> bytes:
    raw = b"".join(
        b"\x00" + rgba[y * width * 4 : (y + 1) * width * 4]
        for y in range(height)
    )
    compressor = zlib.compressobj()
    compressed = compressor.compress(raw) + compressor.flush()

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", ihdr),
            chunk(b"IDAT", compressed),
            chunk(b"IEND", b""),
        ]
    )


def _make_rounded_image(
    master: tk.Misc,
    width: int,
    height: int,
    radius: int,
    fill: str,
    border: str,
    border_width: int = 1,
) -> tk.PhotoImage:
    rgba = _build_rounded_rgba(width, height, radius, fill, border, border_width)
    png = _png_bytes(width, height, rgba)
    return tk.PhotoImage(master=master, data=base64.b64encode(png))


def apply_rounded_buttons(style: ttk.Style, colors: dict, radius: int = 8) -> None:
    try:
        master = getattr(style, "master", None) or tk._default_root
    except Exception:
        master = tk._default_root
    if master is None:
        return
    bg = colors.get("bg", "#111")
    ctrl_bg = colors.get("ctrl_bg", "#222")
    accent = colors.get("accent", "#3c3c3c")
    border = colors.get("ctrl_bg", "#222")
    disabled = "#2a2a2a" if bg == "#111" else "#d0d0d0"
    element_name = f"Rounded.Button.{ctrl_bg.replace('#','')}.{accent.replace('#','')}"

    images = {
        "normal": _make_rounded_image(master, 24, 24, radius, ctrl_bg, border),
        "active": _make_rounded_image(master, 24, 24, radius, accent, border),
        "pressed": _make_rounded_image(master, 24, 24, radius, accent, border),
        "disabled": _make_rounded_image(master, 24, 24, radius, disabled, border),
    }
    try:
        style.element_create(
            element_name,
            "image",
            images["normal"],
            ("active", images["active"]),
            ("pressed", images["pressed"]),
            ("disabled", images["disabled"]),
            border=radius,
            sticky="nsew",
        )
    except Exception:
        pass
    try:
        style.layout(
            "TButton",
            [
                (
                    element_name,
                    {
                        "children": [
                            (
                                "Button.padding",
                                {
                                    "children": [("Button.label", {"sticky": "nsew"})],
                                    "sticky": "nsew",
                                },
                            )
                        ],
                        "sticky": "nsew",
                    },
                )
            ],
        )
    except Exception:
        pass
    style.configure("TButton", padding=(8, 4))
    cache = getattr(style, "_rounded_button_images", None)
    if cache is None:
        cache = {}
        setattr(style, "_rounded_button_images", cache)
    cache[element_name] = images


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
