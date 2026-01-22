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
            app.settings_window.lift()
            app.settings_window.focus_force()
        except Exception:
            pass
        return app.settings_window

    win = tk.Toplevel(app)
    app.settings_window = win
    if not hasattr(app, "show_advanced_scraper"):
        app.show_advanced_scraper = tk.BooleanVar(value=False)
    else:
        app.show_advanced_scraper.set(False)
    win.title("Settings")
    base_geometry = getattr(app, "scraper_settings_geometry", "560x600")
    win.geometry(base_geometry)
    try:
        base_width, base_height = [int(x) for x in base_geometry.split("x", 1)]
    except ValueError:
        base_width, base_height = 560, 600
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

    # Scraper content (single tab)
    scraper_tab = ttk.Frame(win, padding=8)
    scraper_tab.pack(fill="both", expand=True, padx=8, pady=8)
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
    ttk.Label(form, text="Username").grid(row=row_idx, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(form, textvariable=app.cap_user, width=40).grid(row=row_idx, column=1, sticky="ew", padx=6, pady=2)
    row_idx += 1

    ttk.Label(form, text="Password").grid(row=row_idx, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(form, textvariable=app.cap_pass, show="*", width=40).grid(row=row_idx, column=1, sticky="ew", padx=6, pady=2)
    row_idx += 1

    ttk.Label(form, text="Organization").grid(row=row_idx, column=0, sticky="w", padx=6, pady=2)
    org_values = ["", "Medicann Isle of Mann", "Medicann Guernsey", "Medicann Jersey", "Medicann UK"]
    org_combo = ttk.Combobox(form, textvariable=app.cap_org, values=org_values, state="readonly", width=38)
    org_combo.grid(row=row_idx, column=1, sticky="ew", padx=6, pady=2)
    row_idx += 1

    ttk.Separator(form, orient="horizontal").grid(row=row_idx, column=0, columnspan=2, sticky="ew", pady=6)
    row_idx += 1

    advanced_toggle = ttk.Checkbutton(form, text="Show advanced scraper settings", variable=app.show_advanced_scraper)
    advanced_toggle.grid(row=row_idx, column=0, columnspan=2, sticky="w", padx=6, pady=(6, 2))
    row_idx += 1

    advanced_frame = ttk.Frame(form)
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

    ttk.Label(advanced_frame, text="Headless").grid(row=adv_row, column=0, sticky="w", padx=6, pady=2)
    ttk.Checkbutton(advanced_frame, variable=app.cap_headless).grid(row=adv_row, column=1, sticky="w", padx=6, pady=2)
    adv_row += 1

    ttk.Checkbutton(advanced_frame, text="Dump page HTML to file", variable=app.cap_dump_html).grid(row=adv_row, column=0, columnspan=2, sticky="w", padx=6, pady=2)
    adv_row += 1

    ttk.Checkbutton(advanced_frame, text="Dump API JSON responses", variable=app.cap_dump_api).grid(row=adv_row, column=0, columnspan=2, sticky="w", padx=6, pady=2)
    adv_row += 1

    ttk.Checkbutton(advanced_frame, text="Include inactive products", variable=app.cap_include_inactive).grid(row=adv_row, column=0, columnspan=2, sticky="w", padx=6, pady=2)
    adv_row += 1

    ttk.Checkbutton(advanced_frame, text="Requestable only", variable=app.cap_requestable_only).grid(row=adv_row, column=0, columnspan=2, sticky="w", padx=6, pady=2)
    adv_row += 1

    ttk.Checkbutton(advanced_frame, text="In stock only", variable=app.cap_in_stock_only).grid(row=adv_row, column=0, columnspan=2, sticky="w", padx=6, pady=2)
    adv_row += 1

    ttk.Label(advanced_frame, text="HA webhook URL").grid(row=adv_row, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(advanced_frame, textvariable=app.cap_ha_webhook, width=50).grid(row=adv_row, column=1, sticky="ew", padx=6, pady=2)
    adv_row += 1

    ttk.Label(advanced_frame, text="HA token (optional)").grid(row=adv_row, column=0, sticky="w", padx=6, pady=2)
    ttk.Entry(advanced_frame, textvariable=app.cap_ha_token, show="*", width=50).grid(row=adv_row, column=1, sticky="ew", padx=6, pady=2)
    adv_row += 1

    selector_hint = ttk.Label(advanced_frame, text="", style="Hint.TLabel")
    selector_hint.grid(row=adv_row, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 6))
    adv_row += 1

    def _resize_to_content():
        win.update_idletasks()
        width = max(win.winfo_width(), base_width)
        height = max(win.winfo_reqheight(), base_height)
        win.geometry(f"{width}x{height}")

    def toggle_advanced():
        if app.show_advanced_scraper.get():
            advanced_frame.grid()
        else:
            advanced_frame.grid_remove()
        _resize_to_content()

    toggle_advanced()
    advanced_toggle.config(command=toggle_advanced)
    row_idx += 1

    ttk.Separator(form, orient="horizontal").grid(row=row_idx, column=0, columnspan=2, sticky="ew", pady=6)
    row_idx += 1

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

    notify_frame = ttk.Labelframe(scraper_tab, text="Notification Settings", padding=8)
    notify_frame.pack(fill="x", padx=4, pady=(0, 10))
    ttk.Checkbutton(notify_frame, text="Notify on price changes", variable=app.notify_price_changes).pack(anchor="w", pady=2)
    ttk.Checkbutton(notify_frame, text="Notify on stock changes", variable=app.notify_stock_changes).pack(anchor="w", pady=2)
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

