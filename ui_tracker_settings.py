from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def open_tracker_settings(app) -> None:
    if app.settings_window and tk.Toplevel.winfo_exists(app.settings_window):
        try:
            app.settings_window.deiconify()
            app.settings_window.lift()
            app.settings_window.focus_force()
        except Exception:
            pass
        return
    win = tk.Toplevel(app.root)
    win.title("Settings")
    try:
        win.iconbitmap(app._resource_path('icon.ico'))
    except Exception:
        pass
    app.settings_window = win
    app._set_dark_title_bar(app.dark_var.get(), target=win)
    win.resizable(False, False)
    # Min size will be set after layout to avoid excess dead space.
    container = ttk.Frame(win, padding=6)
    container.grid(row=0, column=0, sticky="nsew")
    container.columnconfigure(0, weight=1)
    container.rowconfigure(0, weight=1)

    notebook = ttk.Notebook(container)
    notebook.configure(style="Settings.TNotebook")
    notebook.grid(row=0, column=0, sticky="nsew")

    tab_colors = ttk.Frame(notebook, padding=8)
    tab_tracker = ttk.Frame(notebook, padding=8)
    tab_roa = ttk.Frame(notebook, padding=8)
    tab_data = ttk.Frame(notebook, padding=8)
    tab_window = ttk.Frame(notebook, padding=8)
    notebook.add(tab_colors, text="Colour settings")
    notebook.add(tab_tracker, text="Tracker settings")
    notebook.add(tab_roa, text="RoA settings")
    notebook.add(tab_data, text="Data settings")
    notebook.add(tab_window, text="Window settings")

    for tab in (tab_colors, tab_tracker, tab_roa, tab_data, tab_window):
        tab.columnconfigure(0, weight=0)
        tab.columnconfigure(1, weight=0)
        tab.columnconfigure(2, weight=1)
        tab.columnconfigure(3, weight=1)

    def _color_button(parent: ttk.Frame, key: str) -> tk.Button:
        color = getattr(app, key, "#2ecc71")
        btn = tk.Button(
            parent,
            width=2,
            height=1,
            relief="flat",
            bg=color,
            activebackground=color,
            highlightthickness=1,
            highlightbackground=color,
            command=lambda: app._choose_threshold_color(key),
        )
        app._register_threshold_color_button(btn, key)
        return btn

    frame = tab_colors
    ttk.Label(frame, text="Colour settings", font=app.font_bold_small).grid(row=0, column=0, sticky="w", pady=(0, 6))

    lbl_total_green = ttk.Label(frame, text="THC total stock high threshold")
    lbl_total_green.grid(row=1, column=0, sticky="w")
    tg_frame = ttk.Frame(frame)
    app.total_green_entry = ttk.Entry(tg_frame, width=4)
    app.total_green_entry.pack(side="left", padx=(0, 2))
    ttk.Label(tg_frame, text="g").pack(side="left")
    _color_button(tg_frame, "total_thc_high_color").pack(side="left", padx=(6, 0))
    tg_frame.grid(row=1, column=1, sticky="w", padx=(12, 0))

    lbl_total_red = ttk.Label(frame, text="THC total stock low threshold")
    lbl_total_red.grid(row=2, column=0, sticky="w", pady=(6, 0))
    tr_frame = ttk.Frame(frame)
    app.total_red_entry = ttk.Entry(tr_frame, width=4)
    app.total_red_entry.pack(side="left", padx=(0, 2))
    ttk.Label(tr_frame, text="g").pack(side="left")
    _color_button(tr_frame, "total_thc_low_color").pack(side="left", padx=(6, 0))
    tr_frame.grid(row=2, column=1, sticky="w", padx=(12, 0), pady=(6, 0))

    lbl_cbd_total_green = ttk.Label(frame, text="CBD total stock high threshold")
    lbl_cbd_total_green.grid(row=3, column=0, sticky="w", pady=(6, 0))
    ctg_frame = ttk.Frame(frame)
    app.cbd_total_green_entry = ttk.Entry(ctg_frame, width=4)
    app.cbd_total_green_entry.pack(side="left", padx=(0, 2))
    ttk.Label(ctg_frame, text="g").pack(side="left")
    _color_button(ctg_frame, "total_cbd_high_color").pack(side="left", padx=(6, 0))
    ctg_frame.grid(row=3, column=1, sticky="w", padx=(12, 0), pady=(6, 0))

    lbl_cbd_total_red = ttk.Label(frame, text="CBD total stock low threshold")
    lbl_cbd_total_red.grid(row=4, column=0, sticky="w", pady=(6, 0))
    ctr_frame = ttk.Frame(frame)
    app.cbd_total_red_entry = ttk.Entry(ctr_frame, width=4)
    app.cbd_total_red_entry.pack(side="left", padx=(0, 2))
    ttk.Label(ctr_frame, text="g").pack(side="left")
    _color_button(ctr_frame, "total_cbd_low_color").pack(side="left", padx=(6, 0))
    ctr_frame.grid(row=4, column=1, sticky="w", padx=(12, 0), pady=(6, 0))

    lbl_single_green = ttk.Label(frame, text="THC individual flower stock high threshold")
    lbl_single_green.grid(row=5, column=0, sticky="w", pady=(6, 0))
    sg_frame = ttk.Frame(frame)
    app.single_green_entry = ttk.Entry(sg_frame, width=4)
    app.single_green_entry.pack(side="left", padx=(0, 2))
    ttk.Label(sg_frame, text="g").pack(side="left")
    _color_button(sg_frame, "single_thc_high_color").pack(side="left", padx=(6, 0))
    sg_frame.grid(row=5, column=1, sticky="w", padx=(12, 0), pady=(6, 0))

    lbl_single_red = ttk.Label(frame, text="THC individual flower stock low threshold")
    lbl_single_red.grid(row=6, column=0, sticky="w", pady=(6, 0))
    sr_frame = ttk.Frame(frame)
    app.single_red_entry = ttk.Entry(sr_frame, width=4)
    app.single_red_entry.pack(side="left", padx=(0, 2))
    ttk.Label(sr_frame, text="g").pack(side="left")
    _color_button(sr_frame, "single_thc_low_color").pack(side="left", padx=(6, 0))
    sr_frame.grid(row=6, column=1, sticky="w", padx=(12, 0), pady=(6, 0))

    lbl_cbd_single_green = ttk.Label(frame, text="CBD individual flower stock high threshold")
    lbl_cbd_single_green.grid(row=7, column=0, sticky="w", pady=(6, 0))
    csg_frame = ttk.Frame(frame)
    app.cbd_single_green_entry = ttk.Entry(csg_frame, width=4)
    app.cbd_single_green_entry.pack(side="left", padx=(0, 2))
    ttk.Label(csg_frame, text="g").pack(side="left")
    _color_button(csg_frame, "single_cbd_high_color").pack(side="left", padx=(6, 0))
    csg_frame.grid(row=7, column=1, sticky="w", padx=(12, 0), pady=(6, 0))

    lbl_cbd_single_red = ttk.Label(frame, text="CBD individual flower stock low threshold")
    lbl_cbd_single_red.grid(row=8, column=0, sticky="w", pady=(6, 0))
    csr_frame = ttk.Frame(frame)
    app.cbd_single_red_entry = ttk.Entry(csr_frame, width=4)
    app.cbd_single_red_entry.pack(side="left", padx=(0, 2))
    ttk.Label(csr_frame, text="g").pack(side="left")
    _color_button(csr_frame, "single_cbd_low_color").pack(side="left", padx=(6, 0))
    csr_frame.grid(row=8, column=1, sticky="w", padx=(12, 0), pady=(6, 0))

    app.enable_stock_color_var = tk.BooleanVar(value=getattr(app, "enable_stock_coloring", True))
    chk_stock_color = ttk.Checkbutton(frame, text="Enable colouring based on stock", variable=app.enable_stock_color_var)
    chk_stock_color.grid(row=9, column=0, columnspan=3, sticky="w", pady=(6, 0))
    app.enable_usage_color_var = tk.BooleanVar(value=getattr(app, "enable_usage_coloring", True))
    chk_usage_color = ttk.Checkbutton(frame, text="Enable colouring based on usage", variable=app.enable_usage_color_var)
    chk_usage_color.grid(row=10, column=0, columnspan=3, sticky="w", pady=(4, 2))

    usage_row = 11
    ttk.Label(frame, text="Remaining today (THC) colours").grid(row=usage_row, column=0, sticky="w", pady=(6, 0))
    usage_frame = ttk.Frame(frame)
    ttk.Label(usage_frame, text="High").pack(side="left", padx=(0, 4))
    _color_button(usage_frame, "remaining_thc_high_color").pack(side="left")
    ttk.Label(usage_frame, text="Low").pack(side="left", padx=(8, 4))
    _color_button(usage_frame, "remaining_thc_low_color").pack(side="left")
    usage_frame.grid(row=usage_row, column=1, sticky="w", padx=(12, 0), pady=(6, 0))
    usage_row += 1

    ttk.Label(frame, text="Remaining today (CBD) colours").grid(row=usage_row, column=0, sticky="w", pady=(2, 0))
    usage_frame = ttk.Frame(frame)
    ttk.Label(usage_frame, text="High").pack(side="left", padx=(0, 4))
    _color_button(usage_frame, "remaining_cbd_high_color").pack(side="left")
    ttk.Label(usage_frame, text="Low").pack(side="left", padx=(8, 4))
    _color_button(usage_frame, "remaining_cbd_low_color").pack(side="left")
    usage_frame.grid(row=usage_row, column=1, sticky="w", padx=(12, 0), pady=(2, 0))
    usage_row += 1

    ttk.Label(frame, text="Days left (THC) colours").grid(row=usage_row, column=0, sticky="w", pady=(2, 0))
    usage_frame = ttk.Frame(frame)
    ttk.Label(usage_frame, text="High").pack(side="left", padx=(0, 4))
    _color_button(usage_frame, "days_thc_high_color").pack(side="left")
    ttk.Label(usage_frame, text="Low").pack(side="left", padx=(8, 4))
    _color_button(usage_frame, "days_thc_low_color").pack(side="left")
    usage_frame.grid(row=usage_row, column=1, sticky="w", padx=(12, 0), pady=(2, 0))
    usage_row += 1

    ttk.Label(frame, text="Days left (CBD) colours").grid(row=usage_row, column=0, sticky="w", pady=(2, 0))
    usage_frame = ttk.Frame(frame)
    ttk.Label(usage_frame, text="High").pack(side="left", padx=(0, 4))
    _color_button(usage_frame, "days_cbd_high_color").pack(side="left")
    ttk.Label(usage_frame, text="Low").pack(side="left", padx=(8, 4))
    _color_button(usage_frame, "days_cbd_low_color").pack(side="left")
    usage_frame.grid(row=usage_row, column=1, sticky="w", padx=(12, 0), pady=(2, 0))

    frame = tab_tracker
    ttk.Label(frame, text="Tracker settings", font=app.font_bold_small).grid(row=0, column=0, sticky="w", pady=(0, 6))
    row = 1

    app.track_cbd_flower_var = tk.BooleanVar(value=getattr(app, "track_cbd_flower", False))
    chk_track_cbd = ttk.Checkbutton(frame, text="Track CBD flower", variable=app.track_cbd_flower_var)
    chk_track_cbd.grid(row=row, column=0, columnspan=3, sticky="w", pady=(2, 4))
    row += 1

    app.hide_mixed_dose_var = tk.BooleanVar(value=getattr(app, "hide_mixed_dose", False))
    chk_hide_mixed = ttk.Checkbutton(frame, text="Hide mixed dose option", variable=app.hide_mixed_dose_var)
    chk_hide_mixed.grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 6))
    row += 1
    app.hide_mix_stock_var = tk.BooleanVar(value=getattr(app, "hide_mix_stock", False))
    chk_hide_mix_stock = ttk.Checkbutton(frame, text="Hide mix stock option", variable=app.hide_mix_stock_var)
    chk_hide_mix_stock.grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 6))
    row += 1

    lbl_daily_target = ttk.Label(frame, text="Daily target (THC)")
    lbl_daily_target.grid(row=row, column=0, sticky="w", pady=(6, 0))
    dt_frame = ttk.Frame(frame)
    app.daily_target_entry = ttk.Entry(dt_frame, width=4)
    app.daily_target_entry.pack(side="left", padx=(0, 2))
    ttk.Label(dt_frame, text="g/day").pack(side="left")
    dt_frame.grid(row=row, column=1, sticky="w", padx=(12, 0), pady=(6, 0))
    row += 1

    lbl_daily_target_cbd = ttk.Label(frame, text="Daily target (CBD)")
    lbl_daily_target_cbd.grid(row=row, column=0, sticky="w", pady=(2, 0))
    dtc_frame = ttk.Frame(frame)
    app.daily_target_cbd_entry = ttk.Entry(dtc_frame, width=4)
    app.daily_target_cbd_entry.pack(side="left", padx=(0, 2))
    ttk.Label(dtc_frame, text="g/day").pack(side="left")
    dtc_frame.grid(row=row, column=1, sticky="w", padx=(12, 0), pady=(2, 0))
    row += 1

    lbl_avg_days = ttk.Label(frame, text="Average usage window")
    lbl_avg_days.grid(row=row, column=0, sticky="w", pady=(2, 0))
    avg_frame = ttk.Frame(frame)
    app.avg_usage_days_entry = ttk.Entry(avg_frame, width=4)
    app.avg_usage_days_entry.pack(side="left", padx=(0, 2))
    ttk.Label(avg_frame, text="days").pack(side="left")
    avg_frame.grid(row=row, column=1, sticky="w", padx=(12, 0), pady=(2, 0))
    row += 1

    frame = tab_roa
    ttk.Label(frame, text="RoA settings", font=app.font_bold_small).grid(row=0, column=0, sticky="w", pady=(0, 6))
    row = 1

    app.hide_roa_var = tk.BooleanVar(value=getattr(app, "hide_roa_options", False))
    chk_hide_roa = ttk.Checkbutton(frame, text="Hide ROA options in log", variable=app.hide_roa_var)
    chk_hide_roa.grid(row=row, column=0, columnspan=3, sticky="w", pady=(2, 6))
    row += 1

    ttk.Label(frame, text="Route efficiency (%)", font=app.font_bold_small).grid(
        row=row, column=0, sticky="w", pady=(6, 6)
    )
    app.roa_vars: dict[str, tk.StringVar] = {}
    app.roa_entries: dict[str, ttk.Entry] = {}
    roa_row = row + 1
    for idx, (name, eff) in enumerate(app.roa_options.items()):
        ttk.Label(frame, text=name).grid(row=roa_row + idx, column=0, sticky="w", pady=(2, 0))
        var = tk.StringVar(value=f"{eff*100:.0f}")
        app.roa_vars[name] = var
        rf = ttk.Frame(frame)
        entry = ttk.Entry(rf, textvariable=var, width=4)
        entry.pack(side="left", padx=(0, 2))
        app.roa_entries[name] = entry
        ttk.Label(rf, text="%").pack(side="left")
        rf.grid(row=roa_row + idx, column=1, sticky="w", padx=(12, 0))

    frame = tab_data
    ttk.Label(frame, text="Data settings", font=app.font_bold_small).grid(row=0, column=0, sticky="w", pady=(0, 6))
    lbl_backup = ttk.Label(frame, text="Backup & restore")
    lbl_backup.grid(row=1, column=0, sticky="w")
    btn_backup_export = ttk.Button(frame, text="Export backup..", command=app._settings_export_backup)
    btn_backup_export.grid(row=1, column=1, sticky="w", padx=(4, 0), pady=(2, 2))
    btn_backup_import = ttk.Button(frame, text="Import backup..", command=app._settings_import_backup)
    btn_backup_import.grid(row=1, column=2, sticky="w", padx=(4, 0), pady=(2, 2))

    app.open_data_folder_btn = ttk.Button(frame, text="Open data folder", command=app._settings_open_data_folder)
    app.open_data_folder_btn.grid(
        row=2, column=1, columnspan=2, sticky="w", padx=(4, 0), pady=(2, 4)
    )

    frame = tab_window
    ttk.Label(frame, text="Window settings", font=app.font_bold_small).grid(row=0, column=0, sticky="w", pady=(0, 6))
    app.dark_mode_check = ttk.Checkbutton(frame, text="Dark mode", variable=app.dark_var, command=app._toggle_theme)
    app.dark_mode_check.grid(
        row=1, column=0, columnspan=2, sticky="w", pady=(2, 0)
    )
    app.minimize_var = tk.BooleanVar(value=app.minimize_to_tray)
    app.close_var = tk.BooleanVar(value=app.close_to_tray)
    app.scraper_controls_var = tk.BooleanVar(value=getattr(app, 'show_scraper_buttons', True))
    app.scraper_status_icon_var = tk.BooleanVar(value=getattr(app, 'show_scraper_status_icon', True))
    app.scraper_controls_check = ttk.Checkbutton(frame, text="Show scraper controls", variable=app.scraper_controls_var)
    app.scraper_controls_check.grid(
        row=2, column=0, columnspan=2, sticky="w", pady=(2, 0)
    )
    app.scraper_status_icon_check = ttk.Checkbutton(frame, text="Show scraper status icon", variable=app.scraper_status_icon_var)
    app.scraper_status_icon_check.grid(
        row=3, column=0, columnspan=2, sticky="w", pady=(2, 0)
    )

    app.minimize_var_check = ttk.Checkbutton(frame, text="Minimize to tray when minimizing", variable=app.minimize_var)
    app.minimize_var_check.grid(
        row=4, column=0, columnspan=2, sticky="w", pady=(2, 0)
    )
    app.close_var_check = ttk.Checkbutton(frame, text="Minimize to tray when closing", variable=app.close_var)
    app.close_var_check.grid(
        row=5, column=0, columnspan=2, sticky="w", pady=(2, 0)
    )

    app.total_green_entry.insert(0, f"{app.total_green_threshold}")
    app.total_red_entry.insert(0, f"{app.total_red_threshold}")
    app.cbd_total_green_entry.insert(0, f"{app.cbd_total_green_threshold}")
    app.cbd_total_red_entry.insert(0, f"{app.cbd_total_red_threshold}")
    app.single_green_entry.insert(0, f"{app.single_green_threshold}")
    app.single_red_entry.insert(0, f"{app.single_red_threshold}")
    app.cbd_single_green_entry.insert(0, f"{app.cbd_single_green_threshold}")
    app.cbd_single_red_entry.insert(0, f"{app.cbd_single_red_threshold}")
    app.daily_target_entry.insert(0, f"{app.target_daily_grams}")
    app.daily_target_cbd_entry.insert(0, f"{getattr(app, 'target_daily_cbd_grams', 0.0)}")
    app.avg_usage_days_entry.insert(0, f"{getattr(app, 'avg_usage_days', 30)}")

    # Tooltips for settings
    app._bind_tooltip(lbl_total_green, "Above this total THC stock, label shows green.")
    app._bind_tooltip(app.total_green_entry, "Above this total THC stock, label shows green.")
    app._bind_tooltip(lbl_total_red, "At or below this total THC stock, label shows red.")
    app._bind_tooltip(app.total_red_entry, "At or below this total THC stock, label shows red.")
    app._bind_tooltip(lbl_cbd_total_green, "Above this total CBD stock, label shows green.")
    app._bind_tooltip(app.cbd_total_green_entry, "Above this total CBD stock, label shows green.")
    app._bind_tooltip(lbl_cbd_total_red, "At or below this total CBD stock, label shows red.")
    app._bind_tooltip(app.cbd_total_red_entry, "At or below this total CBD stock, label shows red.")
    app._bind_tooltip(lbl_single_green, "Above this THC-dominant per-flower stock, row shows green.")
    app._bind_tooltip(app.single_green_entry, "Above this THC-dominant per-flower stock, row shows green.")
    app._bind_tooltip(lbl_single_red, "At or below this THC-dominant per-flower stock, row shows red.")
    app._bind_tooltip(app.single_red_entry, "At or below this THC-dominant per-flower stock, row shows red.")
    app._bind_tooltip(lbl_cbd_single_green, "Above this CBD-dominant per-flower stock, row shows green.")
    app._bind_tooltip(app.cbd_single_green_entry, "Above this CBD-dominant per-flower stock, row shows green.")
    app._bind_tooltip(lbl_cbd_single_red, "At or below this CBD-dominant per-flower stock, row shows red.")
    app._bind_tooltip(app.cbd_single_red_entry, "At or below this CBD-dominant per-flower stock, row shows red.")
    app._bind_tooltip(chk_stock_color, "Toggle colour gradients for stock totals and per-flower rows.")
    app._bind_tooltip(chk_usage_color, "Toggle colouring for usage metrics (remaining today, days left, totals).")
    app._bind_tooltip(chk_track_cbd, "Enable separate CBD usage targets and daily totals.")
    app._bind_tooltip(chk_hide_roa, "Hide ROA selection and ROA/THC/CBD columns in the usage log.")
    app._bind_tooltip(chk_hide_mixed, "Hide the Mixed dose shortcut in the log dose window.")
    app._bind_tooltip(chk_hide_mix_stock, "Hide the Mix stock shortcut in the stock entry row.")
    app._bind_tooltip(lbl_daily_target, "Daily THC target in grams used to compute remaining today and target days left.")
    app._bind_tooltip(app.daily_target_entry, "Daily THC target in grams used to compute remaining today and target days left.")
    app._bind_tooltip(lbl_daily_target_cbd, "Daily CBD target in grams used to compute CBD remaining/used today.")
    app._bind_tooltip(app.daily_target_cbd_entry, "Daily CBD target in grams used to compute CBD remaining/used today.")
    app._bind_tooltip(lbl_avg_days, "Number of days to average for days-left calculations (0 = all time).")
    app._bind_tooltip(app.avg_usage_days_entry, "Number of days to average for days-left calculations (0 = all time).")
    app._bind_tooltip(lbl_backup, "Export/import a full backup of settings and data.")
    app._bind_tooltip(btn_backup_import, "Importing will overwrite existing data after confirmation.")
    app._bind_tooltip(app.open_data_folder_btn, "Open the data folder in File Explorer.")
    app._bind_tooltip(app.scraper_controls_check, "Show the scraper button, browser button, and status dot in the main window.")
    app._bind_tooltip(app.scraper_status_icon_check, "Show the scraper status dot in the main window.")
    app._bind_tooltip(app.minimize_var_check, "Hide to system tray when minimizing if enabled.")
    app._bind_tooltip(app.close_var_check, "Hide to system tray when closing if enabled.")
    app._bind_tooltip(app.dark_mode_check, "Toggle the tracker theme between dark and light.")
    for name, var in app.roa_vars.items():
        try:
            app._bind_tooltip(var, f"Efficiency percent used for {name.lower()} dosing.")
        except Exception:
            pass

    def _bind_numeric_entry(entry: ttk.Entry, label: str, min_value: float | None = None, max_value: float | None = None, integer: bool = False) -> None:
        fallback = entry.get().strip()

        def on_focus_out(_event=None):
            raw = entry.get().strip()
            if not raw:
                messagebox.showerror("Invalid input", f"{label} cannot be empty.")
                entry.delete(0, tk.END)
                entry.insert(0, fallback)
                return
            try:
                value = float(raw)
                if integer and int(value) != value:
                    raise ValueError
            except Exception:
                messagebox.showerror("Invalid input", f"{label} must be a {'whole number' if integer else 'number'}.")
                entry.delete(0, tk.END)
                entry.insert(0, fallback)
                return
            if min_value is not None and value < min_value:
                messagebox.showerror("Invalid input", f"{label} must be at least {min_value}.")
                entry.delete(0, tk.END)
                entry.insert(0, fallback)
                return
            if max_value is not None and value > max_value:
                messagebox.showerror("Invalid input", f"{label} must be at most {max_value}.")
                entry.delete(0, tk.END)
                entry.insert(0, fallback)
                return

        entry.bind("<FocusOut>", on_focus_out)

    _bind_numeric_entry(app.total_green_entry, "THC total stock high threshold", min_value=0.0)
    _bind_numeric_entry(app.total_red_entry, "THC total stock low threshold", min_value=0.0)
    _bind_numeric_entry(app.cbd_total_green_entry, "CBD total stock high threshold", min_value=0.0)
    _bind_numeric_entry(app.cbd_total_red_entry, "CBD total stock low threshold", min_value=0.0)
    _bind_numeric_entry(app.single_green_entry, "THC individual stock high threshold", min_value=0.0)
    _bind_numeric_entry(app.single_red_entry, "THC individual stock low threshold", min_value=0.0)
    _bind_numeric_entry(app.cbd_single_green_entry, "CBD individual stock high threshold", min_value=0.0)
    _bind_numeric_entry(app.cbd_single_red_entry, "CBD individual stock low threshold", min_value=0.0)
    _bind_numeric_entry(app.daily_target_entry, "Daily THC target", min_value=0.0)
    _bind_numeric_entry(app.daily_target_cbd_entry, "Daily CBD target", min_value=0.0)
    _bind_numeric_entry(app.avg_usage_days_entry, "Average usage window (days)", min_value=0.0, integer=True)
    for name, entry in app.roa_entries.items():
        _bind_numeric_entry(entry, f"{name} efficiency (%)", min_value=0.0, max_value=100.0)

    actions = ttk.Frame(container)
    actions.grid(row=1, column=0, sticky="ew", pady=(6, 0))
    actions.columnconfigure(0, weight=1)
    ttk.Button(actions, text="Save", command=app._save_settings).grid(
        row=0, column=1, sticky="e", padx=(0, 4)
    )
    app._update_threshold_color_buttons()
    # Place after layout to avoid resize flash
    app._prepare_toplevel(win)
    try:
        win.update_idletasks()
        width = max(container.winfo_reqwidth(), actions.winfo_reqwidth()) + 8
        height = container.winfo_reqheight() + actions.winfo_reqheight() + 12
        win.minsize(width, height)
        win.geometry(f"{width}x{height}")
    except Exception:
        pass

