from __future__ import annotations

from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

def open_settings_window(app, assets_dir: Path) -> tk.Toplevel:
    """
    Build and show the settings window for the given app instance.
    Expects the app to expose the same attributes/methods as the prior inline implementation.
    """
    if app.settings_window and tk.Toplevel.winfo_exists(app.settings_window):
        try:
            app.settings_window.deiconify()
            app.settings_window.lift()
            app.settings_window.focus_force()
        except Exception:
            pass
        return app.settings_window

    win = tk.Toplevel(app)
    try:
        win.attributes("-alpha", 0.0)
    except Exception:
        pass
    try:
        win.withdraw()
    except Exception:
        pass
    app.settings_window = win
    if not hasattr(app, "show_advanced_scraper"):
        app.show_advanced_scraper = tk.BooleanVar(value=True)
    else:
        app.show_advanced_scraper.set(True)
    win.title("Settings")
    base_geometry = getattr(app, "scraper_settings_geometry", "560x820")
    win.geometry(base_geometry)
    try:
        base_width, base_height = [int(x) for x in base_geometry.split("x", 1)]
    except ValueError:
        base_width, base_height = 560, 600
    min_height = 700
    min_height_compact = 740
    win.update_idletasks()
    screen_height = max(win.winfo_screenheight() - 80, min_height)
    max_height = min(screen_height, 1000)
    max_height = min(max_height, 860)
    if base_height < min_height:
        base_height = min_height
    if base_height > max_height:
        base_height = max_height
    has_position = "+" in base_geometry
    win.geometry(f"{base_width}x{base_height}")
    if has_position:
        try:
            win.geometry(base_geometry)
        except Exception:
            pass
    else:
        try:
            app.update_idletasks()
            win.update_idletasks()
            parent_x = app.winfo_rootx()
            parent_y = app.winfo_rooty()
            parent_w = app.winfo_width()
            parent_h = app.winfo_height()
            win_w = win.winfo_reqwidth()
            win_h = win.winfo_reqheight()
            x = max(parent_x, parent_x + (parent_w - win_w) // 2)
            y = max(parent_y, parent_y + (parent_h - win_h) // 2)
            win.geometry(f"+{x}+{y}")
        except Exception:
            pass
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
    try:
        win.deiconify()
        win.attributes("-alpha", 1.0)
    except Exception:
        pass
    try:
        win.bind("<Configure>", lambda _e: app._schedule_settings_geometry(win))
    except Exception:
        pass

    outer = ttk.Frame(win)
    outer.pack(fill="both", expand=True)
    def _clear_combo_selection(event: tk.Event | None = None) -> None:
        widget = getattr(event, "widget", None)
        if widget is None:
            return
        try:
            widget.selection_clear()
        except Exception:
            try:
                widget.tk.call(widget._w, "selection", "clear")
            except Exception:
                pass
        try:
            widget.icursor("end")
        except Exception:
            pass
    notebook = ttk.Notebook(outer, style="Settings.TNotebook")
    notebook.pack(fill="both", expand=True, padx=8, pady=(6, 0))

    tab_account = ttk.Frame(notebook, padding=8)
    tab_capture = ttk.Frame(notebook, padding=8)
    tab_filters = ttk.Frame(notebook, padding=8)
    tab_notifications = ttk.Frame(notebook, padding=8)
    tab_maintenance = ttk.Frame(notebook, padding=8)
    notebook.add(tab_account, text="Account")
    notebook.add(tab_capture, text="Capture")
    notebook.add(tab_filters, text="Filters")
    notebook.add(tab_notifications, text="Notifications")
    notebook.add(tab_maintenance, text="Maintenance")

    ttk.Label(
        tab_capture,
        text="Configure how the scraper logs in, waits, and captures the page.",
        wraplength=520,
        anchor="w",
        justify="left",
    ).pack(fill="x", pady=(0, 6))

    account_grid = ttk.Frame(tab_account)
    account_grid.pack(fill="x", expand=True)
    account_grid.columnconfigure(0, weight=1)
    account_grid.columnconfigure(1, weight=1)

    creds_frame = ttk.Labelframe(account_grid, text="Credentials")
    creds_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=4)
    creds_frame.columnconfigure(1, weight=1)
    row_idx = 0
    ttk.Label(creds_frame, text="Username").grid(row=row_idx, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(creds_frame, textvariable=app.cap_user, width=40).grid(row=row_idx, column=1, sticky="ew", padx=6, pady=2)
    row_idx += 1
    ttk.Label(creds_frame, text="Password").grid(row=row_idx, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(creds_frame, textvariable=app.cap_pass, show="*", width=40).grid(row=row_idx, column=1, sticky="ew", padx=6, pady=2)

    org_frame = ttk.Labelframe(account_grid, text="Organisation")
    org_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=4)
    org_frame.columnconfigure(1, weight=1)
    ttk.Label(org_frame, text="Organisation").grid(row=0, column=0, sticky="w", padx=6, pady=2)
    org_values = ["", "Medicann Isle of Mann", "Medicann Guernsey", "Medicann Jersey", "Medicann UK"]
    org_combo = ttk.Combobox(org_frame, textvariable=app.cap_org, values=org_values, state="readonly", width=38)
    org_combo.grid(row=0, column=1, sticky="ew", padx=6, pady=2)
    org_combo.bind("<FocusOut>", _clear_combo_selection)
    org_combo.bind("<<ComboboxSelected>>", _clear_combo_selection)

    capture_form = ttk.Frame(tab_capture)
    capture_form.pack(fill="x", expand=True)
    capture_form.columnconfigure(1, weight=1)
    row_idx = 0

    advanced_frame = ttk.Frame(capture_form)
    advanced_frame.grid(row=row_idx, column=0, columnspan=2, sticky="ew", padx=0, pady=(0, 6))
    advanced_frame.columnconfigure(1, weight=1)
    adv_row = 0
    ttk.Label(advanced_frame, text="Target URL").grid(row=adv_row, column=0, sticky="w", padx=6, pady=2)
    url_entry = ttk.Entry(advanced_frame, textvariable=app.cap_url, width=50)
    url_entry.grid(row=adv_row, column=1, sticky="ew", padx=6, pady=2)
    adv_row += 1

    ttk.Label(advanced_frame, text="Organization selector").grid(row=adv_row, column=0, sticky="w", padx=6, pady=2)
    org_sel_entry = ttk.Entry(advanced_frame, textvariable=app.cap_org_sel, width=40)
    org_sel_entry.grid(row=adv_row, column=1, sticky="ew", padx=6, pady=2)
    adv_row += 1

    ttk.Label(advanced_frame, text="Username selector").grid(row=adv_row, column=0, sticky="w", padx=6, pady=2)
    user_sel_entry = ttk.Entry(advanced_frame, textvariable=app.cap_user_sel, width=40)
    user_sel_entry.grid(row=adv_row, column=1, sticky="ew", padx=6, pady=2)
    adv_row += 1

    ttk.Label(advanced_frame, text="Password selector").grid(row=adv_row, column=0, sticky="w", padx=6, pady=2)
    pass_sel_entry = ttk.Entry(advanced_frame, textvariable=app.cap_pass_sel, width=40)
    pass_sel_entry.grid(row=adv_row, column=1, sticky="ew", padx=6, pady=2)
    adv_row += 1

    ttk.Label(advanced_frame, text="Login button selector").grid(row=adv_row, column=0, sticky="w", padx=6, pady=2)
    btn_sel_entry = ttk.Entry(advanced_frame, textvariable=app.cap_btn_sel, width=40)
    btn_sel_entry.grid(row=adv_row, column=1, sticky="ew", padx=6, pady=2)
    adv_row += 1

    ttk.Label(advanced_frame, text="Wait after login (s)").grid(row=adv_row, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(advanced_frame, textvariable=app.cap_login_wait, width=10).grid(row=adv_row, column=1, sticky="w", padx=6, pady=2)
    adv_row += 1

    ttk.Label(advanced_frame, text="Wait after navigation (s, min 5)").grid(row=adv_row, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(advanced_frame, textvariable=app.cap_post_wait, width=10).grid(row=adv_row, column=1, sticky="w", padx=6, pady=2)
    adv_row += 1

    ttk.Label(advanced_frame, text="Interval (seconds)").grid(row=adv_row, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(advanced_frame, textvariable=app.cap_interval, width=10).grid(row=adv_row, column=1, sticky="w", padx=6, pady=2)
    adv_row += 1

    ttk.Label(advanced_frame, text="Capture retries on failure").grid(row=adv_row, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(advanced_frame, textvariable=app.cap_retry_attempts, width=10).grid(row=adv_row, column=1, sticky="w", padx=6, pady=2)
    adv_row += 1

    ttk.Label(advanced_frame, text="Retry wait (s, 0 = post-nav)").grid(row=adv_row, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(advanced_frame, textvariable=app.cap_retry_wait, width=10).grid(row=adv_row, column=1, sticky="w", padx=6, pady=2)
    adv_row += 1

    ttk.Label(advanced_frame, text="Retry backoff max (x)").grid(row=adv_row, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(advanced_frame, textvariable=app.cap_retry_backoff, width=10).grid(row=adv_row, column=1, sticky="w", padx=6, pady=2)
    adv_row += 1

    ttk.Checkbutton(advanced_frame, text="Headless", variable=app.cap_headless).grid(
        row=adv_row, column=0, columnspan=2, sticky="w", padx=6, pady=2
    )
    adv_row += 1

    ttk.Checkbutton(advanced_frame, text="Dump page HTML to file", variable=app.cap_dump_html).grid(row=adv_row, column=0, columnspan=2, sticky="w", padx=6, pady=2)
    adv_row += 1

    ttk.Checkbutton(advanced_frame, text="Dump API JSON responses", variable=app.cap_dump_api).grid(row=adv_row, column=0, columnspan=2, sticky="w", padx=6, pady=2)
    adv_row += 1

    ttk.Checkbutton(advanced_frame, text="Dump full API traffic (XHR/fetch)", variable=app.cap_dump_api_full).grid(row=adv_row, column=0, columnspan=2, sticky="w", padx=6, pady=2)
    adv_row += 1

    ttk.Checkbutton(advanced_frame, text="Show log window", variable=app.cap_show_log_window).grid(row=adv_row, column=0, columnspan=2, sticky="w", padx=6, pady=2)
    adv_row += 1

    selector_hint = ttk.Label(advanced_frame, text="", style="Hint.TLabel")
    selector_hint.grid(row=adv_row, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 6))
    adv_row += 1

    def _resize_to_content():
        win.update_idletasks()
        desired_width = max(520, min(base_width, tab_capture.winfo_reqwidth() + 24))
        desired = max(tab_capture.winfo_reqheight() + 24, min_height)
        height = min(desired, max_height)
        win.geometry(f"{desired_width}x{height}")

    _resize_to_content()

    def update_scraper_hints(event=None):
        selectors = [app.cap_user_sel.get().strip(), app.cap_pass_sel.get().strip(), app.cap_btn_sel.get().strip()]
        if any(not s for s in selectors):
            selector_hint.config(text="Hint: One or more login selectors are blank; auto-login may fail.")
        else:
            selector_hint.config(text="")

    for entry in (url_entry, user_sel_entry, pass_sel_entry, btn_sel_entry, org_sel_entry):
        entry.bind("<FocusOut>", update_scraper_hints)
        entry.bind("<KeyRelease>", update_scraper_hints)
    update_scraper_hints()

    notify_frame = ttk.Labelframe(tab_notifications, text="Notification Settings", padding=8)
    notify_frame.pack(fill="x", padx=4, pady=(0, 10))
    ttk.Checkbutton(notify_frame, text="Notify on price changes", variable=app.notify_price_changes).pack(anchor="w", pady=2)
    ttk.Checkbutton(notify_frame, text="Notify on stock changes", variable=app.notify_stock_changes).pack(anchor="w", pady=2)
    ttk.Checkbutton(notify_frame, text="Notify on out of stock", variable=app.notify_out_of_stock).pack(anchor="w", pady=2)
    ttk.Checkbutton(notify_frame, text="Notify on restock", variable=app.notify_restock).pack(anchor="w", pady=2)
    ttk.Checkbutton(notify_frame, text="Notify on new products", variable=app.notify_new_items).pack(anchor="w", pady=2)
    ttk.Checkbutton(notify_frame, text="Notify on removed products", variable=app.notify_removed_items).pack(anchor="w", pady=2)
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
    detail_combo.bind("<FocusOut>", _clear_combo_selection)
    detail_combo.bind("<<ComboboxSelected>>", _clear_combo_selection)

    filters_grid = ttk.Frame(tab_filters)
    filters_grid.pack(fill="x", expand=True)
    filters_grid.columnconfigure(0, weight=1)
    filters_grid.columnconfigure(1, weight=1)

    availability_frame = ttk.Labelframe(filters_grid, text="Availability")
    availability_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=4)
    ttk.Checkbutton(availability_frame, text="Include inactive products", variable=app.cap_include_inactive).pack(anchor="w", pady=2)
    ttk.Checkbutton(availability_frame, text="Requestable only", variable=app.cap_requestable_only).pack(anchor="w", pady=2)
    ttk.Checkbutton(availability_frame, text="In stock only", variable=app.cap_in_stock_only).pack(anchor="w", pady=2)

    type_frame = ttk.Labelframe(filters_grid, text="Product type (optional)")
    type_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=4)
    ttk.Checkbutton(type_frame, text="Flower only", variable=app.cap_filter_flower).pack(anchor="w", pady=2)
    ttk.Checkbutton(type_frame, text="Oil only", variable=app.cap_filter_oil).pack(anchor="w", pady=2)
    ttk.Checkbutton(type_frame, text="Vape only", variable=app.cap_filter_vape).pack(anchor="w", pady=2)

    ha_frame = ttk.Frame(tab_notifications)
    ha_frame.pack(fill="x", pady=(0, 6))
    ttk.Label(ha_frame, text="HA webhook URL").grid(row=0, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(ha_frame, textvariable=app.cap_ha_webhook, width=50).grid(row=0, column=1, sticky="ew", padx=6, pady=2)
    ttk.Label(ha_frame, text="HA token (optional)").grid(row=1, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(ha_frame, textvariable=app.cap_ha_token, show="*", width=50).grid(row=1, column=1, sticky="ew", padx=6, pady=2)
    ha_frame.columnconfigure(1, weight=1)

    def save_and_close():
        try:
            app._save_capture_window()
        except Exception as exc:
            messagebox.showerror("Save", f"Failed to save scraper settings:\n{exc}")
            return
        try:
            if win and tk.Toplevel.winfo_exists(win):
                win.destroy()
            app.settings_window = None
        except Exception:
            pass

    maintenance_grid = ttk.Frame(tab_maintenance)
    maintenance_grid.pack(fill="x", expand=True)
    maintenance_grid.columnconfigure(0, weight=1)
    maintenance_grid.columnconfigure(1, weight=1)

    config_frame = ttk.Labelframe(maintenance_grid, text="Config")
    config_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=4)
    ttk.Button(config_frame, text="Load config", command=app.load_capture_config).pack(side="left", padx=4, pady=4)
    ttk.Button(config_frame, text="Export config", command=app.save_capture_config).pack(side="left", padx=4, pady=4)

    tools_frame = ttk.Labelframe(maintenance_grid, text="Tools")
    tools_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=4)
    ttk.Button(tools_frame, text="Send test notification", command=app.send_test_notification).pack(side="left", padx=4, pady=4)
    ttk.Button(tools_frame, text="Clear auth cache", command=app._clear_auth_cache).pack(side="left", padx=4, pady=4)
    ttk.Button(tools_frame, text="Clear cache", command=app.clear_cache).pack(side="left", padx=4, pady=4)

    btn_row = ttk.Frame(win)
    btn_row.pack(fill="x", pady=10, padx=10)
    ttk.Button(btn_row, text="Save", command=save_and_close).pack(side="right", padx=4)
    app._apply_theme_to_window(win)
    try:
        notebook.configure(style="Settings.TNotebook")
        notebook.update_idletasks()
        current = notebook.index("current")
        notebook.select(current)
    except Exception:
        pass
    return win

