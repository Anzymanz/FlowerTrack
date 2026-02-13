from __future__ import annotations

import secrets
from tkinter import messagebox

from app_core import _load_capture_config, _save_capture_config
from network_mode import MODE_CLIENT, MODE_HOST
from network_sync import DEFAULT_EXPORT_PORT, DEFAULT_NETWORK_PORT, network_ping


def save_tracker_settings(app) -> bool:
    """Validate and apply tracker settings from the settings UI controls."""
    try:
        def _parse_float(label: str, raw: str, allow_empty: bool = False, default: float = 0.0) -> float:
            text = (raw or "").strip()
            if not text:
                if allow_empty:
                    return float(default)
                raise ValueError(f"{label} is required.")
            try:
                value = float(text)
            except Exception:
                raise ValueError(f"{label} must be a number.")
            if value != value or value in (float("inf"), float("-inf")):
                raise ValueError(f"{label} must be a finite number.")
            return value

        def _parse_int(label: str, raw: str, allow_empty: bool = False, default: int = 0) -> int:
            text = (raw or "").strip()
            if not text:
                if allow_empty:
                    return int(default)
                raise ValueError(f"{label} is required.")
            try:
                value = int(float(text))
            except Exception:
                raise ValueError(f"{label} must be an integer.")
            return value

        green = _parse_float("Total THC green threshold", app.total_green_entry.get())
        red = _parse_float("Total THC red threshold", app.total_red_entry.get())
        single_green = _parse_float("Single THC green threshold", app.single_green_entry.get())
        single_red = _parse_float("Single THC red threshold", app.single_red_entry.get())
        cbd_total_green = _parse_float("Total CBD green threshold", app.cbd_total_green_entry.get())
        cbd_total_red = _parse_float("Total CBD red threshold", app.cbd_total_red_entry.get())
        cbd_single_green = _parse_float("Single CBD green threshold", app.cbd_single_green_entry.get())
        cbd_single_red = _parse_float("Single CBD red threshold", app.cbd_single_red_entry.get())
        target_daily = _parse_float("Daily THC target", app.daily_target_entry.get())
        target_daily_cbd = _parse_float(
            "Daily CBD target",
            app.daily_target_cbd_entry.get(),
            allow_empty=True,
            default=0.0,
        )
        avg_usage_days = _parse_int(
            "Average usage days",
            app.avg_usage_days_entry.get(),
            allow_empty=True,
            default=0,
        )
        network_host = str(getattr(app, "network_host", "127.0.0.1")).strip() or "127.0.0.1"
        network_bind_host = str(getattr(app, "network_bind_host", "0.0.0.0")).strip() or "0.0.0.0"
        network_port = int(getattr(app, "network_port", DEFAULT_NETWORK_PORT))
        network_export_port = int(getattr(app, "export_port", DEFAULT_EXPORT_PORT))
        network_access_key = str(getattr(app, "network_access_key", "") or "").strip()
        network_rate_limit_requests_per_minute = int(
            max(0, int(getattr(app, "network_rate_limit_requests_per_minute", 0) or 0))
        )
        if getattr(app, "network_mode", MODE_HOST) == MODE_CLIENT:
            if hasattr(app, "network_host_entry"):
                network_host = str(app.network_host_entry.get()).strip()
            if not network_host:
                raise ValueError("Host IP is required in client mode.")
            if hasattr(app, "network_access_key_entry"):
                network_access_key = str(app.network_access_key_entry.get()).strip()
            if not network_access_key:
                raise ValueError("Access key is required in client mode.")
        if getattr(app, "network_mode", MODE_CLIENT) == MODE_HOST:
            if hasattr(app, "network_bind_entry"):
                network_bind_host = str(app.network_bind_entry.get()).strip() or "0.0.0.0"
            if hasattr(app, "network_access_key_entry"):
                network_access_key = str(app.network_access_key_entry.get()).strip()
            if not network_access_key:
                network_access_key = secrets.token_urlsafe(24)
        if hasattr(app, "network_port_entry"):
            network_port = _parse_int("Data port", app.network_port_entry.get())
        if hasattr(app, "network_export_port_entry"):
            network_export_port = _parse_int("Browser port", app.network_export_port_entry.get())
        if hasattr(app, "network_rate_limit_entry"):
            network_rate_limit_requests_per_minute = _parse_int(
                "Rate limit (req/min)",
                app.network_rate_limit_entry.get(),
                allow_empty=True,
                default=0,
            )
        if network_port < 1 or network_port > 65535:
            raise ValueError("Data port must be between 1 and 65535.")
        if network_export_port < 1 or network_export_port > 65535:
            raise ValueError("Browser port must be between 1 and 65535.")
        if network_rate_limit_requests_per_minute < 0:
            raise ValueError("Rate limit (req/min) cannot be negative.")
        track_cbd_flower = bool(app.track_cbd_flower_var.get())
        enable_stock_coloring = bool(app.enable_stock_color_var.get())
        enable_usage_coloring = bool(app.enable_usage_color_var.get())
        roa_opts = {}
        for name, var in app.roa_vars.items():
            val = _parse_float(f"{name} efficiency (%)", var.get())
            if val < 0 or val > 100:
                raise ValueError(f"{name} efficiency must be 0-100%.")
            roa_opts[name] = val / 100.0
    except ValueError as exc:
        messagebox.showerror("Invalid input", str(exc))
        return False
    if (
        green <= 0
        or red < 0
        or single_green <= 0
        or single_red < 0
        or red >= green
        or single_red >= single_green
        or cbd_total_green <= 0
        or cbd_total_red < 0
        or cbd_single_green <= 0
        or cbd_single_red < 0
        or cbd_total_red >= cbd_total_green
        or cbd_single_red >= cbd_single_green
        or target_daily < 0
        or target_daily_cbd < 0
        or avg_usage_days < 0
        or (track_cbd_flower and target_daily_cbd <= 0)
    ):
        messagebox.showerror("Invalid thresholds", "Use positive numbers with red thresholds below green thresholds.")
        return False
    if not roa_opts:
        messagebox.showerror("Invalid efficiencies", "Provide at least one route efficiency value.")
        return False
    app.total_green_threshold = green
    app.total_red_threshold = red
    app.single_green_threshold = single_green
    app.single_red_threshold = single_red
    app.cbd_total_green_threshold = cbd_total_green
    app.cbd_total_red_threshold = cbd_total_red
    app.cbd_single_green_threshold = cbd_single_green
    app.cbd_single_red_threshold = cbd_single_red
    app.target_daily_grams = target_daily
    app.target_daily_cbd_grams = target_daily_cbd
    app.avg_usage_days = avg_usage_days
    network_changed = (
        str(app.network_host).strip() != str(network_host).strip()
        or str(app.network_bind_host).strip() != str(network_bind_host).strip()
        or int(app.network_port) != int(network_port)
        or int(app.export_port) != int(network_export_port)
        or str(app.network_access_key).strip() != str(network_access_key).strip()
        or int(getattr(app, "network_rate_limit_requests_per_minute", 0))
        != int(network_rate_limit_requests_per_minute)
    )
    app.network_host = str(network_host).strip() or "127.0.0.1"
    app.network_bind_host = str(network_bind_host).strip() or "0.0.0.0"
    app.network_port = int(network_port)
    app.export_port = int(network_export_port)
    app.network_access_key = str(network_access_key).strip()
    app.network_rate_limit_requests_per_minute = int(max(0, network_rate_limit_requests_per_minute))
    app.track_cbd_flower = track_cbd_flower
    app.enable_stock_coloring = enable_stock_coloring
    app.enable_usage_coloring = enable_usage_coloring
    if hasattr(app, "hide_roa_var"):
        app.hide_roa_options = bool(app.hide_roa_var.get())
    if hasattr(app, "hide_mixed_dose_var"):
        app.hide_mixed_dose = bool(app.hide_mixed_dose_var.get())
    if hasattr(app, "hide_mix_stock_var"):
        app.hide_mix_stock = bool(app.hide_mix_stock_var.get())
    app.roa_options = roa_opts
    app.minimize_to_tray = app.minimize_var.get()
    app.close_to_tray = app.close_var.get()
    if hasattr(app, "scraper_status_icon_var"):
        app.show_scraper_status_icon = bool(app.scraper_status_icon_var.get())
    if hasattr(app, "scraper_controls_var"):
        app.show_scraper_buttons = bool(app.scraper_controls_var.get())
    app._apply_scraper_controls_visibility()
    if hasattr(app, "scraper_notify_windows_var"):
        app.scraper_notify_windows = bool(app.scraper_notify_windows_var.get())
        try:
            cap_cfg = _load_capture_config()
            cap_cfg["notify_windows"] = app.scraper_notify_windows
            _save_capture_config(cap_cfg)
        except Exception:
            pass
    values = list(app.roa_options.keys())
    app.roa_choice["values"] = values
    if app.roa_choice.get() not in values and values:
        app.roa_choice.set(values[0])
    app._apply_roa_visibility()
    app._apply_stock_form_visibility()
    app._refresh_stock()
    app._refresh_log()
    try:
        app.root.update_idletasks()
        app.root.after(0, app._apply_roa_visibility)
        app.root.after(0, app._refresh_stock)
    except Exception:
        pass
    if network_changed and app.network_mode == MODE_HOST:
        app._stop_export_server()
        app._stop_network_server()
        app._ensure_network_server()
        app._ensure_export_server()
    if network_changed and app.network_mode == MODE_CLIENT:
        if not network_ping(
            app.network_host,
            int(app.network_port),
            timeout=1.5,
            access_key=str(getattr(app, "network_access_key", "") or ""),
        ):
            messagebox.showwarning(
                "Client connectivity",
                f"Could not reach host {app.network_host}:{app.network_port}.",
            )
        app.load_data()
    app.save_data()
    if app.settings_window:
        app.settings_window.destroy()
        app.settings_window = None
    return True
