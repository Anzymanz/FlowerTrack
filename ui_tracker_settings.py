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
    try:
        win.minsize(400, 620)
    except Exception:
        pass
    frame = ttk.Frame(win, padding=6)
    frame.grid(row=0, column=0, sticky="nsew")
    frame.columnconfigure(0, weight=0)
    frame.columnconfigure(1, weight=0)
    frame.columnconfigure(2, weight=1)
    frame.columnconfigure(3, weight=1)
    ttk.Label(frame, text="Colour settings", font=app.font_bold_small).grid(row=0, column=0, sticky="w", pady=(0, 6))
    lbl_total_green = ttk.Label(frame, text="THC total stock high threshold")
    lbl_total_green.grid(row=1, column=0, sticky="w")
    tg_frame = ttk.Frame(frame)
    app.total_green_entry = ttk.Entry(tg_frame, width=4)
    app.total_green_entry.pack(side="left", padx=(0, 2))
    ttk.Label(tg_frame, text="g").pack(side="left")
    tg_frame.grid(row=1, column=1, sticky="w", padx=(12, 0))

    lbl_total_red = ttk.Label(frame, text="THC total stock low threshold")
    lbl_total_red.grid(row=2, column=0, sticky="w", pady=(6, 0))
    tr_frame = ttk.Frame(frame)
    app.total_red_entry = ttk.Entry(tr_frame, width=4)
    app.total_red_entry.pack(side="left", padx=(0, 2))
    ttk.Label(tr_frame, text="g").pack(side="left")
    tr_frame.grid(row=2, column=1, sticky="w", padx=(12, 0), pady=(6, 0))

    lbl_cbd_total_green = ttk.Label(frame, text="CBD total stock high threshold")
    lbl_cbd_total_green.grid(row=3, column=0, sticky="w", pady=(6, 0))
    ctg_frame = ttk.Frame(frame)
    app.cbd_total_green_entry = ttk.Entry(ctg_frame, width=4)
    app.cbd_total_green_entry.pack(side="left", padx=(0, 2))
    ttk.Label(ctg_frame, text="g").pack(side="left")
    ctg_frame.grid(row=3, column=1, sticky="w", padx=(12, 0), pady=(6, 0))

    lbl_cbd_total_red = ttk.Label(frame, text="CBD total stock low threshold")
    lbl_cbd_total_red.grid(row=4, column=0, sticky="w", pady=(6, 0))
    ctr_frame = ttk.Frame(frame)
    app.cbd_total_red_entry = ttk.Entry(ctr_frame, width=4)
    app.cbd_total_red_entry.pack(side="left", padx=(0, 2))
    ttk.Label(ctr_frame, text="g").pack(side="left")
    ctr_frame.grid(row=4, column=1, sticky="w", padx=(12, 0), pady=(6, 0))

    lbl_single_green = ttk.Label(frame, text="THC individual flower stock high threshold")
    lbl_single_green.grid(row=5, column=0, sticky="w", pady=(6, 0))
    sg_frame = ttk.Frame(frame)
    app.single_green_entry = ttk.Entry(sg_frame, width=4)
    app.single_green_entry.pack(side="left", padx=(0, 2))
    ttk.Label(sg_frame, text="g").pack(side="left")
    sg_frame.grid(row=5, column=1, sticky="w", padx=(12, 0), pady=(6, 0))

    lbl_single_red = ttk.Label(frame, text="THC individual flower stock low threshold")
    lbl_single_red.grid(row=6, column=0, sticky="w", pady=(6, 0))
    sr_frame = ttk.Frame(frame)
    app.single_red_entry = ttk.Entry(sr_frame, width=4)
    app.single_red_entry.pack(side="left", padx=(0, 2))
    ttk.Label(sr_frame, text="g").pack(side="left")
    sr_frame.grid(row=6, column=1, sticky="w", padx=(12, 0), pady=(6, 0))

    lbl_cbd_single_green = ttk.Label(frame, text="CBD individual flower stock high threshold")
    lbl_cbd_single_green.grid(row=7, column=0, sticky="w", pady=(6, 0))
    csg_frame = ttk.Frame(frame)
    app.cbd_single_green_entry = ttk.Entry(csg_frame, width=4)
    app.cbd_single_green_entry.pack(side="left", padx=(0, 2))
    ttk.Label(csg_frame, text="g").pack(side="left")
    csg_frame.grid(row=7, column=1, sticky="w", padx=(12, 0), pady=(6, 0))

    lbl_cbd_single_red = ttk.Label(frame, text="CBD individual flower stock low threshold")
    lbl_cbd_single_red.grid(row=8, column=0, sticky="w", pady=(6, 0))
    csr_frame = ttk.Frame(frame)
    app.cbd_single_red_entry = ttk.Entry(csr_frame, width=4)
    app.cbd_single_red_entry.pack(side="left", padx=(0, 2))
    ttk.Label(csr_frame, text="g").pack(side="left")
    csr_frame.grid(row=8, column=1, sticky="w", padx=(12, 0), pady=(6, 0))

    app.enable_stock_color_var = tk.BooleanVar(value=getattr(app, "enable_stock_coloring", True))
    chk_stock_color = ttk.Checkbutton(frame, text="Enable colouring based on stock", variable=app.enable_stock_color_var)
    chk_stock_color.grid(row=9, column=0, columnspan=3, sticky="w", pady=(6, 0))
    app.enable_usage_color_var = tk.BooleanVar(value=getattr(app, "enable_usage_coloring", True))
    chk_usage_color = ttk.Checkbutton(frame, text="Enable colouring based on usage", variable=app.enable_usage_color_var)
    chk_usage_color.grid(row=10, column=0, columnspan=3, sticky="w", pady=(4, 2))

    app.track_cbd_usage_var = tk.BooleanVar(value=getattr(app, "track_cbd_usage", False))
    chk_track_cbd = ttk.Checkbutton(frame, text="Track CBD usage separately", variable=app.track_cbd_usage_var)
    chk_track_cbd.grid(row=11, column=0, columnspan=3, sticky="w", pady=(2, 4))

    app.hide_roa_var = tk.BooleanVar(value=getattr(app, "hide_roa_options", False))
    chk_hide_roa = ttk.Checkbutton(frame, text="Hide ROA options in log", variable=app.hide_roa_var)
    chk_hide_roa.grid(row=12, column=0, columnspan=3, sticky="w", pady=(2, 6))

    app.hide_mixed_dose_var = tk.BooleanVar(value=getattr(app, "hide_mixed_dose", False))
    chk_hide_mixed = ttk.Checkbutton(frame, text="Hide mixed dose option", variable=app.hide_mixed_dose_var)
    chk_hide_mixed.grid(row=13, column=0, columnspan=3, sticky="w", pady=(0, 6))
    app.hide_mix_stock_var = tk.BooleanVar(value=getattr(app, "hide_mix_stock", False))
    chk_hide_mix_stock = ttk.Checkbutton(frame, text="Hide mix stock option", variable=app.hide_mix_stock_var)
    chk_hide_mix_stock.grid(row=14, column=0, columnspan=3, sticky="w", pady=(0, 6))

    lbl_daily_target = ttk.Label(frame, text="Daily target (THC)")
    lbl_daily_target.grid(row=15, column=0, sticky="w", pady=(6, 0))
    dt_frame = ttk.Frame(frame)
    app.daily_target_entry = ttk.Entry(dt_frame, width=4)
    app.daily_target_entry.pack(side="left", padx=(0, 2))
    ttk.Label(dt_frame, text="g/day").pack(side="left")
    dt_frame.grid(row=15, column=1, sticky="w", padx=(12, 0), pady=(6, 0))

    lbl_daily_target_cbd = ttk.Label(frame, text="Daily target (CBD)")
    lbl_daily_target_cbd.grid(row=16, column=0, sticky="w", pady=(2, 0))
    dtc_frame = ttk.Frame(frame)
    app.daily_target_cbd_entry = ttk.Entry(dtc_frame, width=4)
    app.daily_target_cbd_entry.pack(side="left", padx=(0, 2))
    ttk.Label(dtc_frame, text="g/day").pack(side="left")
    dtc_frame.grid(row=16, column=1, sticky="w", padx=(12, 0), pady=(2, 0))

    lbl_avg_days = ttk.Label(frame, text="Average usage window")
    lbl_avg_days.grid(row=17, column=0, sticky="w", pady=(2, 0))
    avg_frame = ttk.Frame(frame)
    app.avg_usage_days_entry = ttk.Entry(avg_frame, width=4)
    app.avg_usage_days_entry.pack(side="left", padx=(0, 2))
    ttk.Label(avg_frame, text="days").pack(side="left")
    avg_frame.grid(row=17, column=1, sticky="w", padx=(12, 0), pady=(2, 0))

    ttk.Label(frame, text="Route efficiency (%)", font=app.font_bold_small).grid(
        row=18, column=0, sticky="w", pady=(10, 6)
    )
    app.roa_vars: dict[str, tk.StringVar] = {}
    app.roa_entries: dict[str, ttk.Entry] = {}
    roa_row = 19
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

    sep_row = roa_row + len(app.roa_options)
    ttk.Separator(frame, orient="horizontal").grid(row=sep_row, column=0, columnspan=4, sticky="ew", pady=(10, 6))
    ttk.Label(frame, text="Data settings", font=app.font_bold_small).grid(row=sep_row + 1, column=0, sticky="w", pady=(0, 6))
    lbl_backup = ttk.Label(frame, text="Backup & restore")
    lbl_backup.grid(row=sep_row + 2, column=0, sticky="w")
    btn_backup_export = ttk.Button(frame, text="Export backup..", command=app._settings_export_backup)
    btn_backup_export.grid(row=sep_row + 2, column=1, sticky="w", padx=(4, 0), pady=(2, 2))
    btn_backup_import = ttk.Button(frame, text="Import backup..", command=app._settings_import_backup)
    btn_backup_import.grid(row=sep_row + 2, column=2, sticky="w", padx=(4, 0), pady=(2, 2))

    app.open_data_folder_btn = ttk.Button(frame, text="Open data folder", command=app._settings_open_data_folder)
    app.open_data_folder_btn.grid(
        row=sep_row + 3, column=1, columnspan=2, sticky="w", padx=(4, 0), pady=(2, 4)
    )

    ttk.Separator(frame, orient="horizontal").grid(row=sep_row + 6, column=0, columnspan=4, sticky="ew", pady=(10, 6))
    ttk.Label(frame, text="Window settings", font=app.font_bold_small).grid(row=sep_row + 7, column=0, sticky="w", pady=(0, 6))
    app.dark_mode_check = ttk.Checkbutton(frame, text="Dark mode", variable=app.dark_var, command=app._toggle_theme)
    app.dark_mode_check.grid(
        row=sep_row + 8, column=0, columnspan=2, sticky="w", pady=(2, 0)
    )
    app.minimize_var = tk.BooleanVar(value=app.minimize_to_tray)
    app.close_var = tk.BooleanVar(value=app.close_to_tray)
    app.scraper_controls_var = tk.BooleanVar(value=getattr(app, 'show_scraper_buttons', True))
    app.scraper_status_icon_var = tk.BooleanVar(value=getattr(app, 'show_scraper_status_icon', True))
    app.scraper_controls_check = ttk.Checkbutton(frame, text="Show scraper controls", variable=app.scraper_controls_var)
    app.scraper_controls_check.grid(
        row=sep_row + 9, column=0, columnspan=2, sticky="w", pady=(2, 0)
    )
    app.scraper_status_icon_check = ttk.Checkbutton(frame, text="Show scraper status icon", variable=app.scraper_status_icon_var)
    app.scraper_status_icon_check.grid(
        row=sep_row + 10, column=0, columnspan=2, sticky="w", pady=(2, 0)
    )

    app.minimize_var_check = ttk.Checkbutton(frame, text="Minimize to tray when minimizing", variable=app.minimize_var)
    app.minimize_var_check.grid(
        row=sep_row + 11, column=0, columnspan=2, sticky="w", pady=(2, 0)
    )
    app.close_var_check = ttk.Checkbutton(frame, text="Minimize to tray when closing", variable=app.close_var)
    app.close_var_check.grid(
        row=sep_row + 12, column=0, columnspan=2, sticky="w", pady=(2, 0)
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

    actions = ttk.Frame(frame)
    actions.grid(row=sep_row + 13, column=0, columnspan=4, sticky="ew", pady=(8, 0))
    actions.columnconfigure(0, weight=1)
    ttk.Button(actions, text="Save", command=app._save_settings).grid(
        row=0, column=1, sticky="e", padx=(0, 4)
    )
    # Place after layout to avoid resize flash
    app._prepare_toplevel(win)

