from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path
from datetime import datetime
from theme import set_titlebar_dark
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
        self.geometry("900x600")
        self.resizable(True, True)
        try:
            if hasattr(parent, "_resource_path"):
                self.iconbitmap(parent._resource_path("assets/icon.ico"))
        except Exception as exc:
            _log_debug(f"HistoryViewer suppressed exception: {exc}")
        self.records: list[dict] = []
        self.filtered: list[dict] = []
        self._colors = None
        self._build_ui()
        self._load_records()
        self._apply_filter()
        self._apply_theme()
        self._schedule_titlebar_updates()
        self.bind("<Map>", lambda _e: self._schedule_titlebar_updates())
        self.bind("<Visibility>", lambda _e: self._schedule_titlebar_updates())
        self.bind("<FocusIn>", lambda _e: self._schedule_titlebar_updates())

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="changes.ndjson viewer", font=("", 10, "bold")).pack(side="left")
        ttk.Button(top, text="Refresh", command=self._refresh).pack(side="right")

        filter_frame = ttk.Frame(self, padding=(10, 0, 10, 8))
        filter_frame.pack(fill="x")
        ttk.Label(filter_frame, text="Filter").pack(side="left")
        self.filter_var = tk.StringVar(value="")
        self.filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_var)
        self.filter_entry.pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(filter_frame, text="Clear", command=self._clear_filter).pack(side="right")
        self.filter_entry.bind("<KeyRelease>", lambda _e: self._apply_filter())

        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)

        cols = ("time", "summary")
        self.tree = ttk.Treeview(body, columns=cols, show="headings", height=12)
        self.tree.heading("time", text="Timestamp")
        self.tree.heading("summary", text="Summary")
        self.tree.column("time", width=180, anchor="center")
        self.tree.column("summary", width=680, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree_scroll = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.tree_scroll.set)
        self.tree_scroll.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        detail_frame = ttk.LabelFrame(body, text="Details", padding=8)
        detail_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        detail_frame.rowconfigure(0, weight=1)
        detail_frame.columnconfigure(0, weight=1)
        self.detail_text = tk.Text(detail_frame, wrap="word", height=10, state="disabled")
        self.detail_text.grid(row=0, column=0, sticky="nsew")
        self.detail_scroll = ttk.Scrollbar(detail_frame, orient="vertical", command=self.detail_text.yview)
        self.detail_text.configure(yscrollcommand=self.detail_scroll.set)
        self.detail_scroll.grid(row=0, column=1, sticky="ns")

        actions = ttk.Frame(self, padding=(10, 6, 10, 10))
        actions.pack(fill="x")
        ttk.Button(actions, text="Copy JSON", command=self._copy_json).pack(side="left")
        ttk.Button(actions, text="Open Log File", command=self._open_log_file).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Open Log Folder", command=self._open_log_folder).pack(side="left", padx=(6, 0))

    def _apply_theme(self) -> None:
        dark = True
        if hasattr(self.parent, "dark_mode_var"):
            try:
                dark = bool(self.parent.dark_mode_var.get())
            except Exception:
                dark = True
        colors = None
        try:
            from theme import compute_colors
            colors = compute_colors(dark)
        except Exception:
            colors = None
        if colors is None:
            return
        self._colors = colors
        bg = colors["bg"]
        fg = colors["fg"]
        ctrl_bg = colors["ctrl_bg"]
        accent = colors["accent"]
        try:
            self.configure(bg=bg)
        except Exception as exc:
            _log_debug(f"HistoryViewer suppressed exception: {exc}")
        def _apply_widget(widget):
            try:
                if isinstance(widget, ttk.Treeview):
                    widget.configure(style="History.Treeview")
                elif isinstance(widget, tk.Text):
                    widget.configure(bg=bg, fg=fg, insertbackground=fg, highlightbackground=bg)
                elif isinstance(widget, tk.Listbox):
                    widget.configure(bg=bg if dark else "#ffffff", fg=fg, selectbackground=accent, selectforeground="#000" if dark else "#fff", highlightbackground=bg)
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
            style.configure("History.Treeview", background=ctrl_bg, fieldbackground=ctrl_bg, foreground=fg)
            style.map(
                "History.Treeview",
                background=[("selected", accent)],
                foreground=[("selected", "#000" if dark else "#fff")],
            )
            style.configure("History.Treeview.Heading", background=ctrl_bg, foreground=fg)
            style.map("History.Treeview.Heading", background=[("active", accent)], foreground=[("active", "#000" if dark else "#fff")])
            style.configure("History.Vertical.TScrollbar", background=ctrl_bg, troughcolor=bg, arrowcolor=fg)
        except Exception as exc:
            _log_debug(f"HistoryViewer suppressed exception: {exc}")
        try:
            self.tree.configure(style="History.Treeview")
            self.tree_scroll.configure(style="History.Vertical.TScrollbar")
            self.detail_scroll.configure(style="History.Vertical.TScrollbar")
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

    def _format_list(self, title: str, items: list[str]) -> list[str]:
        if not items:
            return []
        out = [f"{title} ({len(items)}):"]
        out.extend([f"  - {item}" for item in items])
        return out

    def _format_details(self, record: dict) -> str:
        if "_raw" in record:
            return record.get("_raw", "")
        lines: list[str] = []
        ts = self._timestamp_for(record)
        if ts:
            lines.append(f"Timestamp: {ts}")
        summary = self._summary_for(record)
        if summary:
            lines.append(f"Summary: {summary}")
        lines.append("")
        new_items = [self._item_label(it) for it in (record.get("new_items") or [])]
        removed_items = [self._item_label(it) for it in (record.get("removed_items") or [])]
        price_changes = [self._price_label(it) for it in (record.get("price_changes") or [])]
        stock_changes = [self._stock_label(it) for it in (record.get("stock_changes") or [])]
        out_of_stock = [self._stock_label(it) for it in (record.get("out_of_stock_changes") or [])]
        restocks = [self._stock_label(it) for it in (record.get("restock_changes") or [])]
        lines.extend(self._format_list("New items", new_items))
        lines.extend(self._format_list("Removed items", removed_items))
        lines.extend(self._format_list("Price changes", price_changes))
        lines.extend(self._format_list("Stock changes", stock_changes))
        lines.extend(self._format_list("Out of stock", out_of_stock))
        lines.extend(self._format_list("Restocks", restocks))
        return "\n".join(lines)

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

    def _apply_filter(self) -> None:
        text = self.filter_var.get().strip().lower()
        self.filtered = []
        for rec in self.records:
            if not text:
                self.filtered.append(rec)
                continue
            hay = json.dumps(rec, ensure_ascii=False).lower()
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

    def _on_select(self, _event=None) -> None:
        rec = self._selected_record()
        if rec is None:
            return
        text = self._format_details(rec)
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", text)
        self.detail_text.configure(state="disabled")

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
