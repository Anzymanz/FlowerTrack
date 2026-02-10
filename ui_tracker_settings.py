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
    try:
        win.attributes("-alpha", 0.0)
    except Exception:
        pass
    try:
        win.withdraw()
    except Exception:
        pass
    win.title("Settings")
    try:
        win.iconbitmap(app._resource_path('icon.ico'))
    except Exception:
        pass
    app.settings_window = win
    app._set_dark_title_bar(app.dark_var.get(), target=win)
    try:
        win.bind("<FocusIn>", lambda _e: app._queue_settings_titlebar(win))
    except Exception:
        pass
    win.resizable(False, False)
    if getattr(app, "settings_window_geometry", ""):
        try:
            win.geometry(app.settings_window_geometry)
        except Exception:
            pass
    # Min size will be set after layout to avoid excess dead space.
    container = ttk.Frame(win, padding=6)
    container.grid(row=0, column=0, sticky="nsew")
    container.columnconfigure(0, weight=1)
    container.rowconfigure(0, weight=1)

    local_style = ttk.Style(win)
    local_style.theme_use("clam")
    tab_style = "SettingsLocal.TNotebook"
    tab_style_tab = "SettingsLocal.TNotebook.Tab"
    sep_style = "SettingsLocal.TSeparator"
    border = getattr(app, "current_border_color", None) or "#2a2a2a"
    ctrl_bg = getattr(app, "current_ctrl_bg", None) or "#222"
    fg = getattr(app, "text_color", "#eee")
    selected_bg = "#222222" if app.dark_var.get() else "#e0e0e0"
    local_style.configure(tab_style, background=getattr(app, "current_base_color", "#111"), bordercolor=border, lightcolor=border, darkcolor=border, relief="solid", borderwidth=1)
    local_style.configure(tab_style_tab, background=ctrl_bg, foreground=fg, lightcolor=border, bordercolor=border, focuscolor=border, padding=[10, 4])
    local_style.map(tab_style_tab, background=[("selected", selected_bg), ("!selected", ctrl_bg)], foreground=[("selected", fg), ("!selected", fg)])
    local_style.configure(sep_style, background=border)

    notebook = ttk.Notebook(container, style=tab_style)
    app.settings_notebook = notebook
    app.settings_tab_style = tab_style
    try:
        win.tk.call("ttk::style", "theme", "use", "clam")
    except Exception:
        pass
    notebook.grid(row=0, column=0, sticky="nsew")

    tab_colors = ttk.Frame(notebook, padding=8)
    tab_tracker = ttk.Frame(notebook, padding=8)
    tab_roa = ttk.Frame(notebook, padding=8)
    tab_data = ttk.Frame(notebook, padding=8)
    tab_window = ttk.Frame(notebook, padding=8)
    tab_theme = ttk.Frame(notebook, padding=8)
    notebook.add(tab_colors, text="Colour settings")
    notebook.add(tab_tracker, text="Tracker settings")
    notebook.add(tab_roa, text="RoA settings")
    notebook.add(tab_data, text="Data settings")
    notebook.add(tab_window, text="Window settings")
    notebook.add(tab_theme, text="Theme")
    notebook.configure(style=tab_style)

    for tab in (tab_colors, tab_tracker, tab_roa, tab_data, tab_window, tab_theme):
        tab.columnconfigure(0, weight=0)
        tab.columnconfigure(1, weight=0)
        tab.columnconfigure(2, weight=1)
        tab.columnconfigure(3, weight=1)

    def _clear_entry_selection(event: tk.Event | None = None) -> None:
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

    def _clear_all_entry_selections(except_widget: tk.Widget | None = None) -> None:
        try:
            stack = [win]
            while stack:
                w = stack.pop()
                stack.extend(w.winfo_children())
                if isinstance(w, (tk.Entry, ttk.Entry)) and w is not except_widget:
                    try:
                        w.selection_clear()
                    except Exception:
                        try:
                            w.tk.call(w._w, "selection", "clear")
                        except Exception:
                            pass
        except Exception:
            pass

    def _on_window_click(event: tk.Event | None = None) -> None:
        widget = getattr(event, "widget", None)
        if isinstance(widget, (tk.Entry, ttk.Entry)):
            return
        _clear_all_entry_selections()

    def _color_button(parent: ttk.Frame, key: str, tooltip_text: str | None = None) -> tk.Button:
        if key.startswith("dark:") or key.startswith("light:"):
            mode, palette_key = key.split(":", 1)
            palette = app.theme_palette_dark if mode == "dark" else app.theme_palette_light
            color = palette.get(palette_key, "#2ecc71")
            command = lambda: app._choose_theme_color(mode, palette_key)
        else:
            color = getattr(app, key, "#2ecc71")
            command = lambda: app._choose_threshold_color(key)
        border_color = "#ffffff" if app.dark_var.get() else "#000000"
        btn = tk.Button(
            parent,
            width=2,
            height=1,
            relief="solid",
            bd=1,
            bg=color,
            activebackground=color,
            activeforeground=getattr(app, "text_color", "#eee"),
            highlightthickness=1,
            highlightbackground=border_color,
            highlightcolor=border_color,
            command=command,
        )
        if key.startswith("dark:") or key.startswith("light:"):
            app._register_theme_color_button(mode, palette_key, btn)
        else:
            app._register_threshold_color_button(btn, key)
        if tooltip_text:
            try:
                app._bind_tooltip(btn, tooltip_text)
            except Exception:
                pass
        return btn

    frame = tab_colors
    ttk.Label(frame, text="Colour settings", font=app.font_bold_small).grid(row=0, column=0, sticky="w", pady=(0, 6))

    def _threshold_row(
        row: int,
        label_text: str,
        high_entry_attr: str,
        high_color_key: str,
        low_entry_attr: str,
        low_color_key: str,
        pady: tuple[int, int] = (0, 0),
    ) -> None:
        label_widget = ttk.Label(frame, text=label_text)
        label_widget.grid(row=row, column=0, sticky="w", pady=pady)
        try:
            app._bind_tooltip(label_widget, f"Configure high/low threshold and colours for {label_text.lower()}.")
        except Exception:
            pass
        row_frame = ttk.Frame(frame)
        ttk.Label(row_frame, text="High").grid(row=0, column=0, sticky="w", padx=(0, 6))
        high_entry = ttk.Entry(row_frame, width=4)
        setattr(app, high_entry_attr, high_entry)
        high_entry.grid(row=0, column=1, sticky="w")
        ttk.Label(row_frame, text="g").grid(row=0, column=2, sticky="w", padx=(2, 8))
        _color_button(row_frame, high_color_key, f"Choose the high colour for {label_text.lower()}.").grid(row=0, column=3, sticky="w", padx=(0, 12))
        ttk.Label(row_frame, text="Low").grid(row=0, column=4, sticky="w", padx=(0, 6))
        low_entry = ttk.Entry(row_frame, width=4)
        setattr(app, low_entry_attr, low_entry)
        low_entry.grid(row=0, column=5, sticky="w")
        ttk.Label(row_frame, text="g").grid(row=0, column=6, sticky="w", padx=(2, 8))
        _color_button(row_frame, low_color_key, f"Choose the low colour for {label_text.lower()}.").grid(row=0, column=7, sticky="w")
        row_frame.grid(row=row, column=1, sticky="w", padx=(12, 0), pady=pady)

    _threshold_row(
        1,
        "THC total stock threshold",
        "total_green_entry",
        "total_thc_high_color",
        "total_red_entry",
        "total_thc_low_color",
        pady=(0, 0),
    )
    _threshold_row(
        2,
        "CBD total stock threshold",
        "cbd_total_green_entry",
        "total_cbd_high_color",
        "cbd_total_red_entry",
        "total_cbd_low_color",
        pady=(6, 0),
    )
    _threshold_row(
        3,
        "THC individual flower stock threshold",
        "single_green_entry",
        "single_thc_high_color",
        "single_red_entry",
        "single_thc_low_color",
        pady=(6, 0),
    )
    _threshold_row(
        4,
        "CBD individual flower stock threshold",
        "cbd_single_green_entry",
        "single_cbd_high_color",
        "cbd_single_red_entry",
        "single_cbd_low_color",
        pady=(6, 0),
    )

    app.enable_stock_color_var = tk.BooleanVar(value=getattr(app, "enable_stock_coloring", True))
    chk_stock_color = ttk.Checkbutton(frame, text="Enable colouring based on stock", variable=app.enable_stock_color_var)
    chk_stock_color.grid(row=5, column=0, columnspan=3, sticky="w", pady=(6, 0))
    app.enable_usage_color_var = tk.BooleanVar(value=getattr(app, "enable_usage_coloring", True))
    chk_usage_color = ttk.Checkbutton(frame, text="Enable colouring based on usage", variable=app.enable_usage_color_var)
    chk_usage_color.grid(row=6, column=0, columnspan=3, sticky="w", pady=(4, 2))

    usage_row = 7
    def _usage_row(
        row: int,
        label: str,
        high_key: str,
        low_key: str,
        high_label: str = "High",
        low_label: str = "Low",
        pady: tuple[int, int] = (2, 0),
    ) -> None:
        label_widget = ttk.Label(frame, text=label)
        label_widget.grid(row=row, column=0, sticky="w", pady=pady)
        try:
            app._bind_tooltip(label_widget, f"Set {high_label.lower()} and {low_label.lower()} colours for {label.lower()}.")
        except Exception:
            pass
        usage_frame = ttk.Frame(frame)
        ttk.Label(usage_frame, text=high_label, width=6, anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 6))
        _color_button(usage_frame, high_key, f"Choose the {high_label.lower()} colour for {label.lower()}.").grid(row=0, column=1, sticky="w", padx=(0, 12))
        ttk.Label(usage_frame, text=low_label, width=6, anchor="w").grid(row=0, column=2, sticky="w", padx=(0, 6))
        _color_button(usage_frame, low_key, f"Choose the {low_label.lower()} colour for {label.lower()}.").grid(row=0, column=3, sticky="w")
        usage_frame.grid(row=row, column=1, sticky="w", padx=(12, 0), pady=pady)

    _usage_row(usage_row, "Remaining today (THC) colours", "remaining_thc_high_color", "remaining_thc_low_color", pady=(6, 0))
    usage_row += 1
    _usage_row(usage_row, "Remaining today (CBD) colours", "remaining_cbd_high_color", "remaining_cbd_low_color")
    usage_row += 1
    _usage_row(usage_row, "Days left (THC) colours", "days_thc_high_color", "days_thc_low_color")
    usage_row += 1
    _usage_row(usage_row, "Days left (CBD) colours", "days_cbd_high_color", "days_cbd_low_color")
    usage_row += 1
    _usage_row(
        usage_row,
        "Total used today (THC) colours",
        "used_thc_under_color",
        "used_thc_over_color",
        high_label="Under",
        low_label="Over",
        pady=(6, 0),
    )
    usage_row += 1
    _usage_row(
        usage_row,
        "Total used today (CBD) colours",
        "used_cbd_under_color",
        "used_cbd_over_color",
        high_label="Under",
        low_label="Over",
    )

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
    btn_backup_export = ttk.Button(frame, text="Export backup..", width=16, command=app._settings_export_backup)
    btn_backup_export.grid(row=1, column=1, sticky="w", padx=(4, 0), pady=(2, 2))
    btn_backup_import = ttk.Button(frame, text="Import backup..", width=16, command=app._settings_import_backup)
    btn_backup_import.grid(row=1, column=2, sticky="w", padx=(4, 0), pady=(2, 2))

    app.open_data_folder_btn = ttk.Button(frame, text="Open data folder", width=16, command=app._settings_open_data_folder)
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

    frame = tab_theme
    ttk.Label(frame, text="Theme", font=app.font_bold_small).grid(row=0, column=0, sticky="w", pady=(0, 6))

    theme_row = 1
    ttk.Label(frame, text="Dark palette", font=app.font_bold_small).grid(row=theme_row, column=0, sticky="w", pady=(0, 6))
    theme_row += 1
    for label, key in (
        ("Background", "bg"),
        ("Foreground", "fg"),
        ("Control background", "ctrl_bg"),
        ("Border", "border"),
        ("Accent", "accent"),
        ("Highlight", "highlight"),
        ("Highlight text", "highlight_text"),
        ("List background", "list_bg"),
        ("Muted", "muted"),
    ):
        label_widget = ttk.Label(frame, text=label)
        label_widget.grid(row=theme_row, column=0, sticky="w", pady=(2, 0))
        try:
            app._bind_tooltip(label_widget, f"Dark theme {label.lower()} colour.")
        except Exception:
            pass
        row_frame = ttk.Frame(frame)
        _color_button(row_frame, f"dark:{key}", f"Pick dark theme {label.lower()} colour.").pack(side="left")
        row_frame.grid(row=theme_row, column=1, sticky="w", padx=(12, 0))
        theme_row += 1

    ttk.Separator(frame, orient="horizontal", style=sep_style).grid(row=theme_row, column=0, columnspan=4, sticky="ew", pady=(8, 8))
    theme_row += 1
    ttk.Label(frame, text="Light palette", font=app.font_bold_small).grid(row=theme_row, column=0, sticky="w", pady=(0, 6))
    theme_row += 1
    for label, key in (
        ("Background", "bg"),
        ("Foreground", "fg"),
        ("Control background", "ctrl_bg"),
        ("Border", "border"),
        ("Accent", "accent"),
        ("Highlight", "highlight"),
        ("Highlight text", "highlight_text"),
        ("List background", "list_bg"),
        ("Muted", "muted"),
    ):
        label_widget = ttk.Label(frame, text=label)
        label_widget.grid(row=theme_row, column=0, sticky="w", pady=(2, 0))
        try:
            app._bind_tooltip(label_widget, f"Light theme {label.lower()} colour.")
        except Exception:
            pass
        row_frame = ttk.Frame(frame)
        _color_button(row_frame, f"light:{key}", f"Pick light theme {label.lower()} colour.").pack(side="left")
        row_frame.grid(row=theme_row, column=1, sticky="w", padx=(12, 0))
        theme_row += 1

    reset_theme_btn = ttk.Button(frame, text="Reset theme colours", command=app._reset_theme_palettes)
    reset_theme_btn.grid(
        row=theme_row, column=0, sticky="w", pady=(10, 0)
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

    # Prevent stale inactive text selection highlight on themed settings entries.
    for widget in win.winfo_children():
        try:
            stack = [widget]
            while stack:
                w = stack.pop()
                stack.extend(w.winfo_children())
                if isinstance(w, (tk.Entry, ttk.Entry)):
                    w.bind("<FocusOut>", _clear_entry_selection, add="+")
                    w.bind("<Escape>", lambda _e, _w=w: (_clear_all_entry_selections(_w), "break")[1], add="+")
        except Exception:
            pass
    try:
        win.bind("<Button-1>", _on_window_click, add="+")
    except Exception:
        pass

    # Tooltips for settings
    app._bind_tooltip(app.total_green_entry, "Above this total THC stock, label shows green.")
    app._bind_tooltip(app.total_red_entry, "At or below this total THC stock, label shows red.")
    app._bind_tooltip(app.cbd_total_green_entry, "Above this total CBD stock, label shows green.")
    app._bind_tooltip(app.cbd_total_red_entry, "At or below this total CBD stock, label shows red.")
    app._bind_tooltip(app.single_green_entry, "Above this THC-dominant per-flower stock, row shows green.")
    app._bind_tooltip(app.single_red_entry, "At or below this THC-dominant per-flower stock, row shows red.")
    app._bind_tooltip(app.cbd_single_green_entry, "Above this CBD-dominant per-flower stock, row shows green.")
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
    app._bind_tooltip(btn_backup_export, "Create a backup archive containing all tracker settings and data.")
    app._bind_tooltip(btn_backup_import, "Importing will overwrite existing data after confirmation.")
    app._bind_tooltip(app.open_data_folder_btn, "Open the data folder in File Explorer.")
    app._bind_tooltip(app.scraper_controls_check, "Show the scraper button, browser button, and status dot in the main window.")
    app._bind_tooltip(app.scraper_status_icon_check, "Show the scraper status dot in the main window.")
    app._bind_tooltip(app.minimize_var_check, "Hide to system tray when minimizing if enabled.")
    app._bind_tooltip(app.close_var_check, "Hide to system tray when closing if enabled.")
    app._bind_tooltip(app.dark_mode_check, "Toggle the tracker theme between dark and light.")
    app._bind_tooltip(reset_theme_btn, "Restore all theme palette colours to defaults.")
    for name, entry in app.roa_entries.items():
        try:
            app._bind_tooltip(entry, f"Efficiency percent used for {name.lower()} dosing.")
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
    ttk.Button(actions, text="Save", width=14, command=app._save_settings).grid(
        row=0, column=1, sticky="e", padx=(0, 4)
    )
    try:
        app.apply_theme(app.dark_var.get())
    except Exception:
        pass
    app._update_threshold_color_buttons()
    app._update_theme_color_buttons()
    try:
        notebook.configure(style=tab_style)
        notebook.update_idletasks()
        current = notebook.index("current")
        notebook.select(current)
    except Exception:
        pass
    try:
        app._set_dark_title_bar(app.dark_var.get(), target=win)
    except Exception:
        pass
    # Place after layout to avoid resize flash
    keep_geometry = bool(getattr(app, "settings_window_geometry", ""))
    placement = "center" if getattr(app, "_force_center_settings", False) or not keep_geometry else "pointer"
    app._prepare_toplevel(win, keep_geometry=keep_geometry, placement=placement)
    app._force_center_settings = False
    try:
        win.bind("<Configure>", lambda _e: app._schedule_settings_geometry(win))
    except Exception:
        pass
    try:
        app._set_dark_title_bar(app.dark_var.get(), target=win)
    except Exception:
        pass
    try:
        win.bind("<FocusIn>", lambda _e: app._set_dark_title_bar(app.dark_var.get(), target=win))
        win.bind("<Map>", lambda _e: win.after(0, lambda: app._set_dark_title_bar(app.dark_var.get(), target=win)))
    except Exception:
        pass
    try:
        win.update_idletasks()
        width = max(container.winfo_reqwidth(), actions.winfo_reqwidth()) + 8
        height = container.winfo_reqheight() + actions.winfo_reqheight() - 10
        win.minsize(width, height)
        win.geometry(f"{width}x{height}")
    except Exception:
        pass

