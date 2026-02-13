from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


def add_labeled_entry_row(
    parent: ttk.Frame,
    *,
    row: int,
    label: str,
    make_entry: Callable[..., tk.Entry],
    variable,
    width: int = 40,
    tooltip_bind: Callable[[tk.Widget, str], None] | None = None,
    tooltip_text: str | None = None,
) -> tuple[ttk.Label, tk.Entry]:
    lbl = ttk.Label(parent, text=label)
    lbl.grid(row=row, column=0, sticky="w", padx=6, pady=2)
    entry = make_entry(parent, variable, width=width)
    entry.grid(row=row, column=1, sticky="ew", padx=6, pady=2)
    if tooltip_bind and tooltip_text:
        tooltip_bind(entry, tooltip_text)
    return lbl, entry


def add_checkbox_row(
    parent: ttk.Frame,
    *,
    row: int,
    text: str,
    variable,
    tooltip_bind: Callable[[tk.Widget, str], None] | None = None,
    tooltip_text: str | None = None,
    columnspan: int = 2,
) -> ttk.Checkbutton:
    chk = ttk.Checkbutton(parent, text=text, variable=variable)
    chk.grid(row=row, column=0, columnspan=columnspan, sticky="w", padx=6, pady=2)
    if tooltip_bind and tooltip_text:
        tooltip_bind(chk, tooltip_text)
    return chk


def add_dump_keep_row(
    parent: ttk.Frame,
    *,
    row: int,
    text: str,
    variable,
    keep_variable,
    make_entry: Callable[..., tk.Entry],
    tooltip_bind: Callable[[tk.Widget, str], None] | None = None,
    tooltip_toggle: str | None = None,
    tooltip_keep: str | None = None,
) -> tuple[ttk.Checkbutton, tk.Entry]:
    row_frame = ttk.Frame(parent)
    row_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=6, pady=2)
    chk = ttk.Checkbutton(row_frame, text=text, variable=variable)
    chk.pack(side="left")
    ttk.Label(row_frame, text="Keep").pack(side="left", padx=(10, 4))
    keep_entry = make_entry(row_frame, keep_variable, width=5)
    keep_entry.pack(side="left")
    ttk.Label(row_frame, text="files").pack(side="left", padx=(4, 0))
    if tooltip_bind and tooltip_toggle:
        tooltip_bind(chk, tooltip_toggle)
    if tooltip_bind and tooltip_keep:
        tooltip_bind(keep_entry, tooltip_keep)
    return chk, keep_entry
