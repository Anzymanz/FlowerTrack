from __future__ import annotations

from network_mode import MODE_HOST


def apply_roa_visibility(app) -> None:
    hide = bool(getattr(app, "hide_roa_options", False))
    try:
        if hasattr(app, "log_tree"):
            cols = list(app.log_tree["columns"])
            display = tuple(c for c in cols if c not in ("roa", "thc_mg", "cbd_mg")) if hide else cols
            app.log_tree["displaycolumns"] = display
    except Exception:
        pass
    try:
        if hide:
            if hasattr(app, "roa_label"):
                app.roa_label.grid_remove()
            if hasattr(app, "roa_choice"):
                app.roa_choice.grid_remove()
        else:
            if hasattr(app, "roa_label"):
                app.roa_label.grid()
            if hasattr(app, "roa_choice"):
                app.roa_choice.grid()
    except Exception:
        pass
    app._apply_mix_button_visibility()


def apply_mix_button_visibility(app) -> None:
    hide = bool(getattr(app, "hide_roa_options", False))
    try:
        btn = getattr(app, "mixed_dose_button", None)
        if btn:
            if getattr(app, "hide_mixed_dose", False):
                btn.grid_remove()
            else:
                info = getattr(app, "_mixed_dose_grid", None)
                btn.grid(**info) if isinstance(info, dict) else btn.grid()
    except Exception:
        pass
    try:
        btn = getattr(app, "mix_stock_button", None)
        if btn:
            if getattr(app, "hide_mix_stock", False):
                btn.grid_remove()
            else:
                info = getattr(app, "_mix_stock_grid", None)
                btn.grid(**info) if isinstance(info, dict) else btn.grid()
    except Exception:
        pass
    try:
        if hasattr(app, "log_tree"):
            cols = list(app.log_tree["columns"])
            widths = app.log_column_widths or {
                col: int(app.log_tree.column(col, option="width")) for col in cols
            }
            has_prefs = bool(app.log_column_widths)
            display = cols
            if hide:
                display = tuple(c for c in cols if c not in ("roa", "thc_mg", "cbd_mg"))
            try:
                app.log_tree["displaycolumns"] = display
                app.log_tree.configure(displaycolumns=display)
            except Exception:
                pass
            if hide:
                if has_prefs:
                    adjusted = dict(widths)
                if not has_prefs:
                    if not hasattr(app, "_log_widths_before_hide"):
                        app._log_widths_before_hide = dict(widths)
                    hidden_total = sum(
                        widths.get(col, int(app.log_tree.column(col, option="width")))
                        for col in cols
                        if col not in display
                    )
                    adjusted = dict(widths)
                    visible = [c for c in display]
                    base_total = sum(adjusted.get(c, 0) for c in visible) or 1
                    min_widths = {
                        "time": 70,
                        "flower": 160,
                        "grams": 80,
                    }
                    for col in visible:
                        share = adjusted.get(col, 0) / base_total
                        adjusted[col] = max(min_widths.get(col, 50), adjusted.get(col, 0) + int(hidden_total * share))
            else:
                display = cols
                restore = getattr(app, "_log_widths_before_hide", None)
                adjusted = dict(restore or widths)
                if hasattr(app, "_log_widths_before_hide"):
                    delattr(app, "_log_widths_before_hide")
            app._suspend_log_width_save = True
            for col, width in adjusted.items():
                try:
                    app.log_tree.column(col, width=width)
                except Exception:
                    continue
            try:
                app.log_tree.update_idletasks()
                app.log_tree["displaycolumns"] = display
            except Exception:
                pass
            try:
                app.root.after(300, lambda: setattr(app, "_suspend_log_width_save", False))
            except Exception:
                app._suspend_log_width_save = False
    except Exception:
        pass

    # Final fallback to ensure ROA/THC/CBD columns are hidden when requested.
    try:
        if hasattr(app, "log_tree"):
            cols = list(app.log_tree["columns"])
            if hide:
                display = tuple(c for c in cols if c not in ("roa", "thc_mg", "cbd_mg"))
            else:
                display = cols
            app.log_tree["displaycolumns"] = display
    except Exception:
        pass


def apply_scraper_status_visibility(app) -> None:
    label = getattr(app, "scraper_status_label", None)
    if not label:
        return
    host_clients = getattr(app, "host_clients_label", None)
    if app.show_scraper_status_icon and app.show_scraper_buttons:
        try:
            label.grid()
        except Exception:
            pass
    else:
        try:
            label.grid_remove()
        except Exception:
            pass
    if host_clients:
        if (
            app.network_mode == MODE_HOST
            and app.show_scraper_status_icon
            and app.show_scraper_buttons
        ):
            try:
                host_clients.grid()
            except Exception:
                pass
        else:
            try:
                host_clients.grid_remove()
            except Exception:
                pass


def bind_scraper_status_actions(app) -> None:
    label = getattr(app, "scraper_status_label", None)
    if not label:
        return
    try:
        label.bind("<Double-Button-1>", app._on_status_double_click)
        label.bind("<Button-3>", app._on_status_right_click)
        label.bind("<Enter>", app._on_status_enter)
        label.bind("<Leave>", app._on_status_leave)
    except Exception:
        pass
