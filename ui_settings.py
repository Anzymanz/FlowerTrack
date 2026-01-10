from __future__ import annotations

from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from parser import _load_brand_hints, _save_brand_hints


def open_settings_window(app, assets_dir: Path) -> tk.Toplevel:
    """
    Build and show the settings window for the given app instance.
    Expects the app to expose the same attributes/methods as the prior inline implementation.
    """
    if app.settings_window and tk.Toplevel.winfo_exists(app.settings_window):
        try:
            app.settings_window.lift()
            app.settings_window.focus_force()
        except Exception:
            pass
        return app.settings_window

    win = tk.Toplevel(app)
    app.settings_window = win
    win.title("Settings")
    win.geometry("560x960")
    try:
        icon_path = assets_dir / "icon.ico"
        if icon_path.exists():
            win.iconbitmap(str(icon_path))
        else:
            win.iconbitmap(app._resource_path("assets/icon2.ico"))
        app._set_window_titlebar_dark(win, app.dark_mode_var.get())
    except Exception:
        pass
    app.after(50, lambda: app._set_window_titlebar_dark(win, app.dark_mode_var.get()))

    notebook = ttk.Notebook(win, style="Settings.TNotebook")
    notebook.pack(fill="both", expand=True, padx=8, pady=8)

    # Scraper tab
    scraper_tab = ttk.Frame(notebook, padding=8)
    notebook.add(scraper_tab, text="Scraper")
    ttk.Label(
        scraper_tab,
        text="Configure how the scraper logs in, waits, and captures the page. "
        "Notifications fire only on new/removed items or price/stock changes.",
        wraplength=520,
        anchor="w",
        justify="left",
    ).pack(fill="x", pady=(0, 10))

    form = ttk.Frame(scraper_tab)
    form.pack(fill="x", expand=True)
    form.columnconfigure(1, weight=1)

    row_idx = 0
    ttk.Label(form, text="Target URL").grid(row=row_idx, column=0, sticky="w", padx=6, pady=2)
    url_entry = ttk.Entry(form, textvariable=app.cap_url, width=50)
    url_entry.grid(row=row_idx, column=1, sticky="ew", padx=6, pady=2)
    row_idx += 1

    url_hint = ttk.Label(form, text="", style="Hint.TLabel")
    url_hint.grid(row=row_idx, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 6))
    row_idx += 1

    ttk.Label(form, text="Interval (seconds)").grid(row=row_idx, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(form, textvariable=app.cap_interval, width=10).grid(row=row_idx, column=1, sticky="w", padx=6, pady=2)
    row_idx += 1

    ttk.Label(form, text="Headless").grid(row=row_idx, column=0, sticky="w", padx=6, pady=2)
    ttk.Checkbutton(form, variable=app.cap_headless).grid(row=row_idx, column=1, sticky="w", padx=6, pady=2)
    row_idx += 1

    ttk.Label(form, text="Wait after login (s)").grid(row=row_idx, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(form, textvariable=app.cap_login_wait, width=10).grid(row=row_idx, column=1, sticky="w", padx=6, pady=2)
    row_idx += 1

    ttk.Label(form, text="Wait after navigation (s, min 5)").grid(row=row_idx, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(form, textvariable=app.cap_post_wait, width=10).grid(row=row_idx, column=1, sticky="w", padx=6, pady=2)
    row_idx += 1

    ttk.Label(form, text="Capture retries on failure").grid(row=row_idx, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(form, textvariable=app.cap_retry_attempts, width=10).grid(row=row_idx, column=1, sticky="w", padx=6, pady=2)
    row_idx += 1

    ttk.Label(form, text="Retry wait (s, 0 = post-nav)").grid(row=row_idx, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(form, textvariable=app.cap_retry_wait, width=10).grid(row=row_idx, column=1, sticky="w", padx=6, pady=2)
    row_idx += 1

    ttk.Label(form, text="Retry backoff max (x)").grid(row=row_idx, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(form, textvariable=app.cap_retry_backoff, width=10).grid(row=row_idx, column=1, sticky="w", padx=6, pady=2)
    row_idx += 1

    ttk.Separator(form, orient="horizontal").grid(row=row_idx, column=0, columnspan=2, sticky="ew", pady=6)
    row_idx += 1

    ttk.Label(form, text="Username").grid(row=row_idx, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(form, textvariable=app.cap_user, width=40).grid(row=row_idx, column=1, sticky="ew", padx=6, pady=2)
    row_idx += 1

    ttk.Label(form, text="Password").grid(row=row_idx, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(form, textvariable=app.cap_pass, show="*", width=40).grid(row=row_idx, column=1, sticky="ew", padx=6, pady=2)
    row_idx += 1

    ttk.Label(form, text="Username selector").grid(row=row_idx, column=0, sticky="w", padx=6, pady=2)
    user_sel_entry = ttk.Entry(form, textvariable=app.cap_user_sel, width=40)
    user_sel_entry.grid(row=row_idx, column=1, sticky="ew", padx=6, pady=2)
    row_idx += 1

    ttk.Label(form, text="Password selector").grid(row=row_idx, column=0, sticky="w", padx=6, pady=2)
    pass_sel_entry = ttk.Entry(form, textvariable=app.cap_pass_sel, width=40)
    pass_sel_entry.grid(row=row_idx, column=1, sticky="ew", padx=6, pady=2)
    row_idx += 1

    ttk.Label(form, text="Login button selector").grid(row=row_idx, column=0, sticky="w", padx=6, pady=2)
    btn_sel_entry = ttk.Entry(form, textvariable=app.cap_btn_sel, width=40)
    btn_sel_entry.grid(row=row_idx, column=1, sticky="ew", padx=6, pady=2)
    row_idx += 1

    selector_hint = ttk.Label(form, text="", style="Hint.TLabel")
    selector_hint.grid(row=row_idx, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 6))
    row_idx += 1

    ttk.Separator(form, orient="horizontal").grid(row=row_idx, column=0, columnspan=2, sticky="ew", pady=6)
    row_idx += 1

    def update_scraper_hints(event=None):
        url_val = app.cap_url.get().strip()
        if not url_val:
            url_hint.config(text="Hint: Target URL is required for auto-scraper.")
        elif not (url_val.startswith("http://") or url_val.startswith("https://")):
            url_hint.config(text="Hint: URL should start with http:// or https://")
        else:
            url_hint.config(text="")
        selectors = [app.cap_user_sel.get().strip(), app.cap_pass_sel.get().strip(), app.cap_btn_sel.get().strip()]
        if any(not s for s in selectors):
            selector_hint.config(text="Hint: One or more login selectors are blank; auto-login may fail.")
        else:
            selector_hint.config(text="")

    for entry in (url_entry, user_sel_entry, pass_sel_entry, btn_sel_entry):
        entry.bind("<FocusOut>", update_scraper_hints)
        entry.bind("<KeyRelease>", update_scraper_hints)
    update_scraper_hints()

    notify_frame = ttk.Labelframe(scraper_tab, text="Notification Settings", padding=8)
    notify_frame.pack(fill="x", padx=4, pady=(0, 10))
    ttk.Checkbutton(notify_frame, text="Send notifications for price changes", variable=app.notify_price_changes).pack(anchor="w", pady=2)
    ttk.Checkbutton(notify_frame, text="Send notifications for stock changes", variable=app.notify_stock_changes).pack(anchor="w", pady=2)
    ttk.Checkbutton(notify_frame, text="Send Windows desktop notifications", variable=app.notify_windows).pack(anchor="w", pady=2)
    ttk.Checkbutton(notify_frame, text="Send Home Assistant notifications", variable=app.cap_auto_notify_ha).pack(anchor="w", pady=2)

    quiet_frame = ttk.Frame(notify_frame)
    quiet_frame.pack(fill="x", pady=(6, 2))
    ttk.Checkbutton(quiet_frame, text="Quiet hours", variable=app.cap_quiet_hours_enabled).pack(side="left")
    ttk.Label(quiet_frame, text="From").pack(side="left", padx=(8, 2))
    ttk.Entry(quiet_frame, textvariable=app.cap_quiet_start, width=6).pack(side="left")
    ttk.Label(quiet_frame, text="To").pack(side="left", padx=(8, 2))
    ttk.Entry(quiet_frame, textvariable=app.cap_quiet_end, width=6).pack(side="left")
    ttk.Label(quiet_frame, text="Interval (s)").pack(side="left", padx=(8, 2))
    ttk.Entry(quiet_frame, textvariable=app.cap_quiet_interval, width=7).pack(side="left")

    detail_frame = ttk.Frame(notify_frame)
    detail_frame.pack(fill="x", pady=(2, 2))
    ttk.Label(detail_frame, text="Notification detail").pack(side="left")
    detail_combo = ttk.Combobox(detail_frame, state="readonly", width=14, values=["full", "summary"], textvariable=app.cap_notify_detail)
    detail_combo.pack(side="left", padx=(8, 0))

    ttk.Label(form, text="HA webhook URL").grid(row=row_idx, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(form, textvariable=app.cap_ha_webhook, width=50).grid(row=row_idx, column=1, sticky="ew", padx=6, pady=2)
    row_idx += 1

    ttk.Label(form, text="HA token (optional)").grid(row=row_idx, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(form, textvariable=app.cap_ha_token, show="*", width=50).grid(row=row_idx, column=1, sticky="ew", padx=6, pady=2)
    row_idx += 1

    # Parser tab (brands/patterns)
    parser_tab = ttk.Frame(notebook, padding=8)
    notebook.add(parser_tab, text="Parser / Brands")
    hints = [dict(brand=h.get("brand"), patterns=list(h.get("patterns") or h.get("phrases") or []), display=h.get("display")) for h in _load_brand_hints()]
    dark = app.dark_mode_var.get()
    bg = "#111" if dark else "#f4f4f4"
    fg = "#eee" if dark else "#111"
    accent = "#4a90e2" if dark else "#666666"
    list_bg = "#1e1e1e" if dark else "#ffffff"
    list_fg = fg
    entry_bg = list_bg
    parser_tab.configure()
    brand_var = tk.StringVar()
    pattern_var = tk.StringVar()
    entry_style = "ParserEntry.TEntry"
    try:
        app.style.configure(entry_style, fieldbackground=entry_bg, background=entry_bg, foreground=fg, insertcolor=fg)
    except Exception:
        pass
    try:
        app.style.configure("Parser.TLabelframe", borderwidth=2, relief="groove")
        app.style.configure("Parser.TLabelframe.Label", padding=(6, 0))
    except Exception:
        pass

    container = ttk.Frame(parser_tab, padding=8)
    container.pack(fill="both", expand=True)
    container.columnconfigure(0, weight=1, uniform="parser")
    container.columnconfigure(1, weight=1, uniform="parser")
    container.rowconfigure(0, weight=1)

    left = ttk.Labelframe(container, text="Brands", padding=8, style="Parser.TLabelframe")
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
    right = ttk.Labelframe(container, text="Patterns", padding=8, style="Parser.TLabelframe")
    right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

    brand_list = tk.Listbox(left, width=32, height=18, bg=list_bg, fg=list_fg, selectbackground=accent, selectforeground=bg, highlightbackground=bg, relief="flat")
    brand_list.pack(fill="both", expand=True, pady=(0, 6))
    brand_entry = ttk.Entry(left, textvariable=brand_var, style=entry_style)
    brand_entry.pack(fill="x", pady=(0, 6))

    pattern_list = tk.Listbox(right, width=32, height=18, bg=list_bg, fg=list_fg, selectbackground=accent, selectforeground=bg, highlightbackground=bg, relief="flat")
    pattern_list.pack(fill="both", expand=True, pady=(0, 6))
    pattern_entry = ttk.Entry(right, textvariable=pattern_var, style=entry_style)
    pattern_entry.pack(fill="x", pady=(0, 6))

    def sort_hints():
        hints.sort(key=lambda h: (h.get("brand") or "").lower())

    def refresh_brands(sel_index=0):
        sort_hints()
        brand_list.delete(0, tk.END)
        for h in hints:
            brand_list.insert(tk.END, h.get("brand") or "")
        if hints:
            idx = min(sel_index, len(hints) - 1)
            brand_list.select_set(idx)
            brand_list.event_generate("<<ListboxSelect>>")

    def refresh_patterns():
        pattern_list.delete(0, tk.END)
        sel = brand_list.curselection()
        if not sel:
            return
        idx = sel[0]
        pats = hints[idx].get("patterns") or []
        for p in pats:
            pattern_list.insert(tk.END, p)

    def add_brand():
        name = brand_var.get().strip()
        if not name:
            return
        hints.append(dict(brand=name, patterns=[], display=name))
        brand_var.set("")
        refresh_brands(len(hints) - 1)

    def update_brand():
        sel = brand_list.curselection()
        if not sel:
            return
        idx = sel[0]
        new_name = brand_var.get().strip()
        if not new_name:
            return
        hints[idx]["brand"] = new_name
        hints[idx]["display"] = new_name
        refresh_brands(idx)

    def delete_brand():
        sel = brand_list.curselection()
        if not sel:
            return
        idx = sel[0]
        hints.pop(idx)
        brand_var.set("")
        pattern_var.set("")
        refresh_brands(max(0, idx - 1))

    def add_pattern():
        sel = brand_list.curselection()
        if not sel:
            return
        idx = sel[0]
        pat = pattern_var.get().strip()
        if not pat:
            return
        pats = hints[idx].setdefault("patterns", [])
        pats.append(pat)
        pattern_var.set("")
        refresh_patterns()

    def replace_pattern():
        sel_brand = brand_list.curselection()
        sel_pat = pattern_list.curselection()
        if not sel_brand or not sel_pat:
            return
        bidx = sel_brand[0]
        pidx = sel_pat[0]
        pat = pattern_var.get().strip()
        if not pat:
            return
        pats = hints[bidx].setdefault("patterns", [])
        pats[pidx] = pat
        refresh_patterns()

    def delete_pattern():
        sel_brand = brand_list.curselection()
        sel_pat = pattern_list.curselection()
        if not sel_brand or not sel_pat:
            return
        bidx = sel_brand[0]
        pidx = sel_pat[0]
        pats = hints[bidx].get("patterns") or []
        if pidx < len(pats):
            pats.pop(pidx)
        refresh_patterns()

    brand_list.bind("<<ListboxSelect>>", lambda e: refresh_patterns())
    refresh_brands()

    brand_btns = ttk.Frame(left)
    brand_btns.pack(fill="x")
    ttk.Button(brand_btns, text="Add Brand", command=add_brand).pack(fill="x", pady=2)
    ttk.Button(brand_btns, text="Rename Brand", command=update_brand).pack(fill="x", pady=2)
    ttk.Button(brand_btns, text="Delete Brand", command=delete_brand).pack(fill="x", pady=2)

    pattern_btns = ttk.Frame(right)
    pattern_btns.pack(fill="x")
    ttk.Button(pattern_btns, text="Add Pattern", command=add_pattern).pack(fill="x", pady=2)
    ttk.Button(pattern_btns, text="Replace Pattern", command=replace_pattern).pack(fill="x", pady=2)
    ttk.Button(pattern_btns, text="Delete Pattern", command=delete_pattern).pack(fill="x", pady=2)

    ttk.Button(parser_tab, text="Export parser database", command=lambda: _save_brand_hints(hints)).pack(anchor="e", padx=8, pady=8)

    def save_and_close():
        try:
            app._save_capture_window()
        except Exception as exc:
            messagebox.showerror("Save", f"Failed to save scraper settings:\n{exc}")
            return
        try:
            _save_brand_hints(hints)
        except Exception as exc:
            messagebox.showerror("Save", f"Failed to save parser database:\n{exc}")
            return
        try:
            if win and tk.Toplevel.winfo_exists(win):
                win.destroy()
            app.settings_window = None
        except Exception:
            pass

    scraper_btns = ttk.Frame(scraper_tab)
    scraper_btns.pack(fill="x", pady=10)
    ttk.Button(scraper_btns, text="Load config", command=app.load_capture_config).pack(side="left", padx=4)
    ttk.Button(scraper_btns, text="Export config", command=app.save_capture_config).pack(side="left", padx=4)
    ttk.Button(scraper_btns, text="Clear cache", command=app.clear_cache).pack(side="right", padx=4)
    ttk.Button(scraper_btns, text="Send test notification", command=app.send_test_notification).pack(side="right", padx=4)

    btn_row = ttk.Frame(win)
    btn_row.pack(fill="x", pady=10, padx=10)
    ttk.Button(btn_row, text="Save", command=save_and_close).pack(side="right", padx=4)
    app._apply_theme_to_window(win)
    return win
