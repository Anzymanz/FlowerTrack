from __future__ import annotations

import csv
import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import simpledialog
from pathlib import Path
from datetime import datetime
from theme import set_titlebar_dark, apply_rounded_buttons, compute_colors, set_palette_overrides
from config import load_tracker_config
import ctypes



def _log_debug(msg: str) -> None:
    try:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{stamp}] {msg}")
    except Exception:
        pass
class HistoryViewer(tk.Toplevel):
    def __init__(self, parent, log_path: Path):
        super().__init__(parent)
        self.parent = parent
        self.log_path = Path(log_path)
        self.title("Change History")
        default_geometry = "900x600"
        geometry = getattr(parent, "history_window_geometry", default_geometry) or default_geometry
        self.geometry(geometry)
        if "+" not in str(geometry):
            try:
                self.update_idletasks()
                sw = self.winfo_screenwidth()
                sh = self.winfo_screenheight()
                w = self.winfo_reqwidth()
                h = self.winfo_reqheight()
                x = max(0, (sw - w) // 2)
                y = max(0, (sh - h) // 2)
                self.geometry(f"+{x}+{y}")
            except Exception:
                pass
        self.resizable(True, True)
        try:
            if hasattr(parent, "_resource_path"):
                self.iconbitmap(parent._resource_path("assets/icon.ico"))
        except Exception as exc:
            _log_debug(f"HistoryViewer suppressed exception: {exc}")
        self.records: list[dict] = []
        self.filtered: list[dict] = []
        self._colors = None
        self._theme_signature = ""
        self._last_dark = None
        self._build_ui()
        self._load_records()
        self._apply_filter()
        self._apply_theme()
        self.after(2000, self._refresh_theme_from_config)
        self._schedule_titlebar_updates()
        self.bind("<Map>", lambda _e: self._schedule_titlebar_updates())
        self.bind("<Visibility>", lambda _e: self._schedule_titlebar_updates())
        self.bind("<FocusIn>", lambda _e: self._schedule_titlebar_updates())
        try:
            if hasattr(parent, "_schedule_history_geometry"):
                self.bind("<Configure>", lambda _e: parent._schedule_history_geometry(self))
        except Exception:
            pass

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        top.columnconfigure(0, weight=1)
        ttk.Label(top, text="changes.ndjson viewer", font=("", 10, "bold")).grid(row=0, column=0, sticky="w")
        btns = ttk.Frame(top)
        btns.grid(row=0, column=1, sticky="e")
        ttk.Button(btns, text="Trim history", command=self._trim_history_prompt).pack(side="left")
        ttk.Button(btns, text="Clear history", command=self._clear_history).pack(side="left", padx=(6, 0))
        ttk.Button(btns, text="Refresh", command=self._refresh).pack(side="left", padx=(6, 0))

        filter_frame = ttk.Frame(self, padding=(10, 0, 10, 8))
        filter_frame.pack(fill="x")
        filter_frame.columnconfigure(1, weight=1)
        ttk.Label(filter_frame, text="Quick search (brand/strain)").grid(row=0, column=0, sticky="w")
        self.filter_var = tk.StringVar(value="")
        self.filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_var)
        self.filter_entry.grid(row=0, column=1, sticky="ew", padx=(6, 8))
        ttk.Button(filter_frame, text="Clear", command=self._clear_filter).grid(row=0, column=2, sticky="e")
        self.filter_entry.bind("<KeyRelease>", lambda _e: self._apply_filter())

        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)

        cols = ("time", "summary")
        self.tree = ttk.Treeview(body, columns=cols, show="headings", height=12, selectmode="extended")
        self.tree.heading("time", text="Timestamp")
        self.tree.heading("summary", text="Summary")
        self.tree.column("time", width=180, anchor="center")
        self.tree.column("summary", width=680, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree_scroll = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.tree_scroll.set)
        self.tree_scroll.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        self.detail_frame = ttk.LabelFrame(body, text="Details", padding=8, style="History.TLabelframe")
        self.detail_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        self.detail_frame.rowconfigure(0, weight=1)
        self.detail_frame.columnconfigure(0, weight=1)
        self.detail_text = tk.Text(
            self.detail_frame,
            wrap="word",
            height=10,
            state="disabled",
            padx=8,
            pady=6,
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
        )
        self.detail_text.grid(row=0, column=0, sticky="nsew")
        self.detail_scroll = ttk.Scrollbar(self.detail_frame, orient="vertical", command=self.detail_text.yview)
        self.detail_text.configure(yscrollcommand=self.detail_scroll.set)
        self.detail_scroll.grid(row=0, column=1, sticky="ns")

        actions = ttk.Frame(self, padding=(10, 6, 10, 10))
        actions.pack(fill="x")
        ttk.Button(actions, text="Copy JSON", command=self._copy_json).pack(side="left")
        ttk.Button(actions, text="Export CSV", command=self._export_csv).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Open Log File", command=self._open_log_file).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Open Log Folder", command=self._open_log_folder).pack(side="left", padx=(6, 0))

    def _apply_theme(self) -> None:
        dark = True
        if hasattr(self.parent, "dark_mode_var"):
            try:
                dark = bool(self.parent.dark_mode_var.get())
            except Exception:
                dark = True
        self._last_dark = dark
        self._refresh_palette_overrides_from_config()
        colors = compute_colors(dark)
        if colors is None:
            return
        self._colors = colors
        bg = colors["bg"]
        fg = colors["fg"]
        ctrl_bg = colors["ctrl_bg"]
        accent = colors["accent"]
        highlight = colors.get("highlight", colors["accent"])
        border = colors.get("border", ctrl_bg)
        list_bg = colors.get("list_bg", ctrl_bg)
        muted = colors.get("muted", fg)
        try:
            self.configure(bg=bg)
        except Exception as exc:
            _log_debug(f"HistoryViewer suppressed exception: {exc}")
        def _apply_widget(widget):
            try:
                if isinstance(widget, ttk.Treeview):
                    widget.configure(style="History.Treeview")
                elif isinstance(widget, tk.Text):
                    widget.configure(
                        bg=ctrl_bg,
                        fg=fg,
                        insertbackground=fg,
                        highlightbackground=border,
                        highlightcolor=border,
                        relief="flat",
                        borderwidth=0,
                        highlightthickness=1,
                        selectbackground=highlight,
                        selectforeground="#ffffff",
                    )
                elif isinstance(widget, tk.Listbox):
                    widget.configure(
                        bg=list_bg,
                        fg=fg,
                        selectbackground=highlight,
                        selectforeground=fg,
                        highlightbackground=bg,
                        highlightcolor=border,
                    )
                elif isinstance(widget, ttk.Widget):
                    pass
                else:
                    for opt, val in (("background", bg), ("foreground", fg)):
                        try:
                            widget.configure(**{opt: val})
                        except Exception as exc:
                            _log_debug(f"HistoryViewer suppressed exception: {exc}")
            except Exception as exc:
                _log_debug(f"HistoryViewer suppressed exception: {exc}")
            for child in widget.winfo_children():
                _apply_widget(child)
        _apply_widget(self)
        try:
            style = ttk.Style(self)
            style.configure(
                "History.TLabelframe",
                background=bg,
                bordercolor=border,
                lightcolor=border,
                darkcolor=border,
                relief="flat",
                borderwidth=1,
            )
            style.configure(
                "History.TLabelframe.Label",
                background=bg,
                foreground=fg,
            )
            style.configure(
                "History.Treeview",
                background=ctrl_bg,
                fieldbackground=ctrl_bg,
                foreground=fg,
                bordercolor=border,
                lightcolor=border,
                darkcolor=border,
            )
            style.map(
                "History.Treeview",
                background=[("selected", highlight)],
                foreground=[("selected", "#ffffff")],
            )
            style.configure(
                "History.Treeview.Heading",
                background=ctrl_bg,
                foreground=fg,
                bordercolor=border,
                lightcolor=border,
                darkcolor=border,
            )
            style.map("History.Treeview.Heading", background=[("active", accent)], foreground=[("active", "#ffffff")])
            style.configure(
                "History.Vertical.TScrollbar",
                background=ctrl_bg,
                troughcolor=bg,
                arrowcolor=fg,
                bordercolor=border,
                lightcolor=border,
                darkcolor=border,
            )
            style.map(
                "History.Vertical.TScrollbar",
                background=[("active", ctrl_bg), ("!active", ctrl_bg)],
                troughcolor=[("active", bg), ("!active", bg)],
                arrowcolor=[("active", fg), ("!active", fg)],
            )
            apply_rounded_buttons(style, {"bg": bg, "fg": fg, "ctrl_bg": ctrl_bg, "accent": accent})
        except Exception as exc:
            _log_debug(f"HistoryViewer suppressed exception: {exc}")
        try:
            self.detail_frame.configure(style="History.TLabelframe")
            self.tree.configure(style="History.Treeview")
            self.tree_scroll.configure(style="History.Vertical.TScrollbar")
            self.detail_scroll.configure(style="History.Vertical.TScrollbar")
        except Exception as exc:
            _log_debug(f"HistoryViewer suppressed exception: {exc}")
        try:
            self.detail_text.tag_configure("header", foreground=fg, font=("", 10, "bold"))
            self.detail_text.tag_configure("meta", foreground=muted, font=("", 9))
            self.detail_text.tag_configure("section", foreground=accent, font=("", 9, "bold"))
            self.detail_text.tag_configure("item", foreground=fg, font=("", 9))
            self.detail_text.tag_configure("muted", foreground=muted, font=("", 9, "italic"))
        except Exception as exc:
            _log_debug(f"HistoryViewer suppressed exception: {exc}")
        try:
            # Keep scrollbars dark even when empty.
            self.option_add("*Scrollbar.background", ctrl_bg)
            self.option_add("*Scrollbar.troughColor", bg)
            self.option_add("*Scrollbar.activeBackground", accent)
            self.option_add("*Scrollbar.arrowColor", fg)
        except Exception as exc:
            _log_debug(f"HistoryViewer suppressed exception: {exc}")
        self._schedule_titlebar_updates()

    def _refresh_palette_overrides_from_config(self) -> bool:
        config_path = Path(os.getenv("APPDATA", os.path.expanduser("~"))) / "FlowerTrack" / "flowertrack_config.json"
        try:
            cfg = load_tracker_config(config_path)
        except Exception:
            return False
        dark = cfg.get("theme_palette_dark", {}) if isinstance(cfg, dict) else {}
        light = cfg.get("theme_palette_light", {}) if isinstance(cfg, dict) else {}
        if not isinstance(dark, dict):
            dark = {}
        if not isinstance(light, dict):
            light = {}
        sig = json.dumps({"dark": dark, "light": light}, sort_keys=True)
        if sig == self._theme_signature:
            return False
        self._theme_signature = sig
        set_palette_overrides(dark, light)
        return True

    def _refresh_theme_from_config(self) -> None:
        try:
            dark = bool(self.parent.dark_mode_var.get()) if hasattr(self.parent, "dark_mode_var") else True
            palette_changed = self._refresh_palette_overrides_from_config()
            if palette_changed or dark != self._last_dark:
                self._apply_theme()
        except Exception:
            pass
        finally:
            try:
                self.after(2000, self._refresh_theme_from_config)
            except Exception:
                pass

    def _apply_titlebar(self) -> None:
        dark = True
        if hasattr(self.parent, "dark_mode_var"):
            try:
                dark = bool(self.parent.dark_mode_var.get())
            except Exception:
                dark = True
        try:
            self.update_idletasks()
        except Exception as exc:
            _log_debug(f"HistoryViewer suppressed exception: {exc}")
        try:
            set_titlebar_dark(self, dark)
        except Exception as exc:
            _log_debug(f"HistoryViewer suppressed exception: {exc}")
        try:
            self._set_titlebar_dark_native(dark)
        except Exception as exc:
            _log_debug(f"HistoryViewer suppressed exception: {exc}")
        try:
            if hasattr(self.parent, "_set_window_titlebar_dark"):
                self.parent._set_window_titlebar_dark(self, dark)
            if hasattr(self.parent, "_set_win_titlebar_dark"):
                self.parent._set_win_titlebar_dark(dark)
        except Exception as exc:
            _log_debug(f"HistoryViewer suppressed exception: {exc}")
    def _schedule_titlebar_updates(self) -> None:
        # Titlebar theming on Toplevels can be timing-sensitive; retry a few times.
        for delay in (60, 200, 500, 900):
            try:
                self.after(delay, self._apply_titlebar)
            except Exception as exc:
                _log_debug(f"HistoryViewer suppressed exception: {exc}")
    def _set_titlebar_dark_native(self, enable: bool) -> None:
        if os.name != "nt":
            return
        try:
            hwnd = self.winfo_id()
            GetAncestor = ctypes.windll.user32.GetAncestor
            GA_ROOT = 2
            GA_ROOTOWNER = 3
            root = GetAncestor(hwnd, GA_ROOT)
            if root:
                hwnd = root
            root_owner = GetAncestor(hwnd, GA_ROOTOWNER)
            if root_owner:
                hwnd = root_owner
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19
            value = ctypes.c_int(1 if enable else 0)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)
            ) != 0:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1, ctypes.byref(value), ctypes.sizeof(value)
                )
        except Exception as exc:
            _log_debug(f"HistoryViewer suppressed exception: {exc}")
    def _load_records(self) -> None:
        self.records = []
        if not self.log_path.exists():
            return
        try:
            lines = self.log_path.read_text(encoding="utf-8").splitlines()
        except Exception:
            lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    self.records.append(data)
                else:
                    self.records.append({"_raw": line})
            except Exception:
                self.records.append({"_raw": line})
        self.records.reverse()

    def _summary_for(self, record: dict) -> str:
        if "_raw" in record:
            return record.get("_raw", "")[:200]
        new_count = len(record.get("new_items") or [])
        removed_count = len(record.get("removed_items") or [])
        price_count = len(record.get("price_changes") or [])
        stock_count = len(record.get("stock_changes") or [])
        out_count = len(record.get("out_of_stock_changes") or [])
        restock_count = len(record.get("restock_changes") or [])
        parts = [
            f"+{new_count} new",
            f"-{removed_count} removed",
            f"{price_count} price",
            f"{stock_count} stock",
            f"{out_count} out",
            f"{restock_count} restock",
        ]
        return ", ".join(parts)

    def _timestamp_for(self, record: dict) -> str:
        raw = record.get("timestamp") if isinstance(record, dict) else None
        if not raw:
            return ""
        try:
            ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return ts.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(raw)

    def _render_details(self, record: dict) -> None:
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        if "_raw" in record:
            self.detail_text.insert("end", "Raw entry\n", "section")
            raw = record.get("_raw", "")
            self.detail_text.insert("end", f"{raw}\n", "item")
            self.detail_text.configure(state="disabled")
            return
        ts = self._timestamp_for(record)
        summary = self._summary_for(record)
        if ts:
            self.detail_text.insert("end", f"{ts}\n", "header")
        if summary:
            self.detail_text.insert("end", f"{summary}\n", "meta")
        self.detail_text.insert("end", "\n")
        sections = [
            ("New items", [self._item_label(it) for it in (record.get("new_items") or [])]),
            ("Removed items", [self._item_label(it) for it in (record.get("removed_items") or [])]),
            ("Price changes", [self._price_label(it) for it in (record.get("price_changes") or [])]),
            ("Stock changes", [self._stock_label(it) for it in (record.get("stock_changes") or [])]),
            ("Out of stock", [self._stock_label(it) for it in (record.get("out_of_stock_changes") or [])]),
            ("Restocks", [self._stock_label(it) for it in (record.get("restock_changes") or [])]),
        ]
        any_lines = False
        for title, items in sections:
            if not items:
                continue
            any_lines = True
            self.detail_text.insert("end", f"{title} ({len(items)})\n", "section")
            for item in items:
                self.detail_text.insert("end", f"  - {item}\n", "item")
            self.detail_text.insert("end", "\n")
        if not any_lines:
            self.detail_text.insert("end", "No change details recorded.\n", "muted")
        self.detail_text.configure(state="disabled")

    def _format_details(self, record: dict) -> str:
        if "_raw" in record:
            return str(record.get("_raw", ""))
        lines: list[str] = []
        ts = self._timestamp_for(record)
        summary = self._summary_for(record)
        if ts:
            lines.append(f"Timestamp: {ts}")
        if summary:
            lines.append(f"Summary: {summary}")
        lines.append("")
        sections = [
            ("New items", [self._item_label(it) for it in (record.get("new_items") or [])]),
            ("Removed items", [self._item_label(it) for it in (record.get("removed_items") or [])]),
            ("Price changes", [self._price_label(it) for it in (record.get("price_changes") or [])]),
            ("Stock changes", [self._stock_label(it) for it in (record.get("stock_changes") or [])]),
            ("Out of stock", [self._stock_label(it) for it in (record.get("out_of_stock_changes") or [])]),
            ("Restocks", [self._stock_label(it) for it in (record.get("restock_changes") or [])]),
        ]
        any_lines = False
        for title, items in sections:
            if not items:
                continue
            any_lines = True
            lines.append(f"{title} ({len(items)})")
            lines.extend([f"  - {item}" for item in items])
            lines.append("")
        if not any_lines:
            lines.append("No change details recorded.")
        return "\n".join(lines).rstrip() + "\n"

    def _item_label(self, entry: dict) -> str:
        if entry.get("label"):
            return str(entry.get("label"))
        parts = []
        for key in ("brand", "producer", "strain", "product_id"):
            val = entry.get(key)
            if val:
                parts.append(str(val))
        label = " ".join(parts).strip()
        return label or "Unknown"

    def _price_label(self, entry: dict) -> str:
        label = self._item_label(entry)
        before = entry.get("price_before")
        after = entry.get("price_after")
        delta = entry.get("price_delta")
        if before is None or after is None:
            return f"{label}: price changed"
        try:
            delta_txt = f"{float(delta):+.2f}" if delta is not None else ""
        except Exception:
            delta_txt = str(delta) if delta is not None else ""
        return f"{label}: {before} -> {after} ({delta_txt})".rstrip()

    def _stock_label(self, entry: dict) -> str:
        label = self._item_label(entry)
        before = entry.get("stock_before")
        after = entry.get("stock_after")
        if before is None and after is None:
            return f"{label}: stock changed"
        return f"{label}: {before} -> {after}"

    def _search_text_for(self, record: dict) -> str:
        if "_raw" in record:
            return str(record.get("_raw", "")).lower()
        values: list[str] = []
        for key in (
            "new_items",
            "removed_items",
            "price_changes",
            "stock_changes",
            "out_of_stock_changes",
            "restock_changes",
        ):
            entries = record.get(key) or []
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                for field in ("brand", "strain", "label", "producer", "product_id"):
                    val = entry.get(field)
                    if val:
                        values.append(str(val))
                label = self._item_label(entry)
                if label:
                    values.append(label)
        return " ".join(values).lower()

    def _apply_filter(self) -> None:
        text = self.filter_var.get().strip().lower()
        self.filtered = []
        for rec in self.records:
            if not text:
                self.filtered.append(rec)
                continue
            hay = self._search_text_for(rec)
            if text in hay:
                self.filtered.append(rec)
        self._refresh_tree()

    def _refresh_tree(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for idx, rec in enumerate(self.filtered):
            time_txt = self._timestamp_for(rec)
            summary = self._summary_for(rec)
            self.tree.insert("", "end", iid=str(idx), values=(time_txt, summary))

    def _refresh(self) -> None:
        self._load_records()
        self._apply_filter()

    def _clear_filter(self) -> None:
        self.filter_var.set("")
        self._apply_filter()

    def _selected_record(self) -> dict | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            idx = int(sel[0])
        except Exception:
            return None
        if idx < 0 or idx >= len(self.filtered):
            return None
        return self.filtered[idx]

    def _selected_records(self) -> list[dict]:
        sel = self.tree.selection()
        if not sel:
            return []
        indices = []
        for item in sel:
            try:
                indices.append(int(item))
            except Exception:
                continue
        indices = sorted(set(indices))
        records = []
        for idx in indices:
            if 0 <= idx < len(self.filtered):
                records.append(self.filtered[idx])
        return records

    def _on_select(self, _event=None) -> None:
        rec = self._selected_record()
        if rec is None:
            return
        self._render_details(rec)

    def _copy_json(self) -> None:
        rec = self._selected_record()
        if rec is None:
            messagebox.showinfo("Copy JSON", "Select a record to copy.")
            return
        text = json.dumps(rec, ensure_ascii=False, indent=2)
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception:
            messagebox.showerror("Copy JSON", "Could not copy to clipboard.")

    def _rows_for_record(self, record: dict) -> list[dict]:
        timestamp = self._timestamp_for(record)
        summary = self._summary_for(record)
        rows: list[dict] = []
        def add_rows(change_type: str, entries: list[dict]):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                rows.append({
                    "timestamp": timestamp,
                    "summary": summary,
                    "type": change_type,
                    "label": self._item_label(entry),
                    "brand": entry.get("brand") or "",
                    "strain": entry.get("strain") or "",
                    "producer": entry.get("producer") or "",
                    "product_id": entry.get("product_id") or "",
                    "price_before": entry.get("price_before") or "",
                    "price_after": entry.get("price_after") or "",
                    "price_delta": entry.get("price_delta") or "",
                    "stock_before": entry.get("stock_before") or "",
                    "stock_after": entry.get("stock_after") or "",
                })
        if "_raw" in record:
            rows.append({
                "timestamp": timestamp,
                "summary": summary,
                "type": "raw",
                "label": str(record.get("_raw", "")),
                "brand": "",
                "strain": "",
                "producer": "",
                "product_id": "",
                "price_before": "",
                "price_after": "",
                "price_delta": "",
                "stock_before": "",
                "stock_after": "",
            })
            return rows
        add_rows("new", record.get("new_items") or [])
        add_rows("removed", record.get("removed_items") or [])
        add_rows("price", record.get("price_changes") or [])
        add_rows("stock", record.get("stock_changes") or [])
        add_rows("out_of_stock", record.get("out_of_stock_changes") or [])
        add_rows("restock", record.get("restock_changes") or [])
        if not rows:
            rows.append({
                "timestamp": timestamp,
                "summary": summary,
                "type": "summary",
                "label": "",
                "brand": "",
                "strain": "",
                "producer": "",
                "product_id": "",
                "price_before": "",
                "price_after": "",
                "price_delta": "",
                "stock_before": "",
                "stock_after": "",
            })
        return rows

    def _export_csv(self) -> None:
        records = self._selected_records()
        if not records:
            messagebox.showinfo("Export CSV", "Select one or more records to export.")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"changes_export_{timestamp}.csv"
        initial_dir = str(self.log_path.parent) if self.log_path.parent.exists() else str(Path.cwd())
        path = filedialog.asksaveasfilename(
            title="Export CSV",
            defaultextension=".csv",
            initialdir=initial_dir,
            initialfile=default_name,
            filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return
        rows: list[dict] = []
        for rec in records:
            rows.extend(self._rows_for_record(rec))
        fieldnames = [
            "timestamp",
            "summary",
            "type",
            "label",
            "brand",
            "strain",
            "producer",
            "product_id",
            "price_before",
            "price_after",
            "price_delta",
            "stock_before",
            "stock_after",
        ]
        try:
            with open(path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        except Exception:
            messagebox.showerror("Export CSV", "Could not write CSV file.")
            return
        messagebox.showinfo("Export CSV", f"Exported {len(rows)} rows.")

    def _open_log_file(self) -> None:
        if not self.log_path.exists():
            messagebox.showinfo("Open Log", "Log file not found.")
            return
        try:
            os.startfile(str(self.log_path))  # type: ignore[attr-defined]
        except Exception:
            messagebox.showerror("Open Log", "Could not open log file.")

    def _open_log_folder(self) -> None:
        folder = self.log_path.parent
        if not folder.exists():
            messagebox.showinfo("Open Folder", "Log folder not found.")
            return
        try:
            os.startfile(str(folder))  # type: ignore[attr-defined]
        except Exception:
            messagebox.showerror("Open Folder", "Could not open log folder.")

    def _clear_history(self) -> None:
        if not self.log_path.exists():
            messagebox.showinfo("Clear History", "No history log file found.")
            return
        if not messagebox.askyesno(
            "Clear History",
            "Delete all change history entries? This cannot be undone.",
        ):
            return
        try:
            self.log_path.unlink()
        except Exception:
            messagebox.showerror("Clear History", "Could not delete the history file.")
            return
        self.records = []
        self.filtered = []
        self._refresh_tree()
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.configure(state="disabled")
        messagebox.showinfo("Clear History", "History cleared.")

    def _trim_history_prompt(self) -> None:
        if not self.log_path.exists():
            messagebox.showinfo("Trim History", "No history log file found.")
            return
        value = simpledialog.askinteger(
            "Trim History",
            "Keep the most recent N entries:",
            minvalue=1,
            maxvalue=5000,
            initialvalue=1000,
        )
        if value is None:
            return
        self._trim_history(value)

    def _trim_history(self, keep: int) -> None:
        try:
            lines = self.log_path.read_text(encoding="utf-8").splitlines()
        except Exception:
            messagebox.showerror("Trim History", "Could not read the history file.")
            return
        if len(lines) <= keep:
            messagebox.showinfo("Trim History", "History already within the requested size.")
            return
        trimmed = lines[-keep:]
        try:
            self.log_path.write_text("\n".join(trimmed) + "\n", encoding="utf-8")
        except Exception:
            messagebox.showerror("Trim History", "Could not write the trimmed history file.")
            return
        self._load_records()
        self._apply_filter()
        messagebox.showinfo("Trim History", f"Trimmed history to {keep} entries.")


def open_history_window(parent, log_path: Path) -> HistoryViewer:
    win = HistoryViewer(parent, log_path)
    try:
        win.lift()
        win.focus_force()
    except Exception as exc:
        _log_debug(f"HistoryViewer suppressed exception: {exc}")
    try:
        if hasattr(parent, "_set_window_titlebar_dark"):
            parent.after(80, lambda: parent._set_window_titlebar_dark(win, bool(parent.dark_mode_var.get())))
    except Exception as exc:
        _log_debug(f"HistoryViewer suppressed exception: {exc}")
    return win
