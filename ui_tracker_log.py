from __future__ import annotations

import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import messagebox, ttk

from inventory import Flower, log_dose_entry


def log_dose(app) -> None:
    name = app.flower_choice.get().strip()
    grams_text = app.dose_entry.get().strip()
    if not name:
        messagebox.showwarning("Select flower", "Choose a saved flower to log a dose.")
        return
    if name not in app.flowers:
        messagebox.showerror("Unknown flower", "Selected flower is not in stock.")
        return
    if not grams_text:
        messagebox.showwarning("Missing dose", "Enter a dose in grams of flower.")
        return
    try:
        grams_used = float(grams_text)
    except ValueError:
        messagebox.showerror("Invalid dose", "Dose must be numeric.")
        return
    if grams_used <= 0:
        messagebox.showerror("Invalid dose", "Dose must be positive.")
        return
    roa = app._resolve_roa()
    try:
        log_dose_entry(
            app.flowers,
            app.logs,
            name=name,
            grams_used=grams_used,
            roa=roa,
            roa_options=app.roa_options,
        )
    except ValueError as exc:
        messagebox.showerror("Cannot log dose", str(exc))
        return
    app._refresh_stock()
    app._refresh_log()
    app._update_scraper_status_icon()
    app.dose_entry.delete(0, tk.END)
    app.save_data()


def resolve_roa(app) -> str:
    if getattr(app, "hide_roa_options", False):
        return "Unknown"
    try:
        return app.roa_choice.get().strip() or "Vaped"
    except Exception:
        return "Vaped"


def edit_log_entry(app) -> None:
    selection = app.log_tree.selection()
    if not selection:
        messagebox.showwarning("Select log", "Select a log entry to edit.")
        return
    idx = int(selection[0])
    if idx >= len(app.logs):
        messagebox.showerror("Not found", "Selected log entry is missing.")
        return
    log = app.logs[idx]
    current_flower = log["flower"]
    current_roa = log.get("roa", "Smoking")
    current_grams = float(log.get("grams_used", 0.0))
    current_time = log.get("time_display") or log.get("time", "").split(" ")[-1]
    dialog = tk.Toplevel(app.root)
    dialog.title("Edit log entry")
    dialog.resizable(False, False)
    frame = ttk.Frame(dialog, padding=12)
    frame.grid(row=0, column=0, sticky="nsew")
    ttk.Label(frame, text="Flower").grid(row=0, column=0, sticky="w")
    flower_var = tk.StringVar(value=current_flower)
    flower_combo = ttk.Combobox(
        frame,
        state="readonly",
        values=[f.name for f in sorted(app.flowers.values(), key=lambda f: f.name.lower())],
        textvariable=flower_var,
        width=22,
        style=app.combo_style,
    )
    flower_combo.grid(row=1, column=0, sticky="w", padx=(0, 8))
    flower_combo.bind("<FocusOut>", app._clear_combo_selection)
    flower_combo.bind("<<ComboboxSelected>>", app._clear_combo_selection)
    ttk.Label(frame, text="Route").grid(row=0, column=1, sticky="w")
    roa_var = tk.StringVar(value=current_roa if current_roa in app.roa_options else "Vaped")
    roa_combo = ttk.Combobox(
        frame, state="readonly", values=list(app.roa_options.keys()), textvariable=roa_var, width=12, style=app.combo_style
    )
    roa_combo.grid(row=1, column=1, sticky="w", padx=(0, 8))
    roa_combo.bind("<FocusOut>", app._clear_combo_selection)
    roa_combo.bind("<<ComboboxSelected>>", app._clear_combo_selection)
    ttk.Label(frame, text="Dose (g)").grid(row=0, column=2, sticky="w")
    grams_var = tk.StringVar(value=f"{current_grams:.3f}")
    grams_entry = ttk.Entry(frame, textvariable=grams_var, width=12)
    grams_entry.grid(row=1, column=2, sticky="w")
    ttk.Label(frame, text="Time (HH:MM)").grid(row=0, column=3, sticky="w")
    time_var = tk.StringVar(value=current_time)
    time_entry = ttk.Entry(frame, textvariable=time_var, width=10)
    time_entry.grid(row=1, column=3, sticky="w", padx=(0, 8))
    buttons = ttk.Frame(dialog, padding=(12, 8, 12, 12))
    buttons.grid(row=1, column=0, sticky="ew")
    buttons.columnconfigure(0, weight=1)
    ttk.Button(buttons, text="Cancel", command=dialog.destroy).grid(row=0, column=0, sticky="w")

    def save_edit() -> None:
        new_flower_name = flower_var.get().strip()
        new_roa = roa_var.get().strip() or "Smoking"
        try:
            new_grams = float(grams_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid dose", "Dose must be numeric.")
            return
        if new_grams <= 0:
            messagebox.showerror("Invalid dose", "Dose must be positive.")
            return
        if not new_flower_name or new_flower_name not in app.flowers:
            messagebox.showerror("Missing flower", "Select a valid flower.")
            return
        time_text = time_var.get().strip()
        try:
            dt_obj = datetime.strptime(f"{log.get('date')} {time_text}", "%Y-%m-%d %H:%M")
        except Exception:
            messagebox.showerror("Invalid time", "Enter time as HH:MM in 24-hour format.")
            return
        efficiency = app.roa_options.get(new_roa, 1.0)
        old_flower = app.flowers.get(current_flower)
        new_flower = app.flowers[new_flower_name]
        if log.get("mix_sources") or log.get("mix_thc_pct") is not None:
            app._restore_mix_stock(log)
        elif old_flower:
            old_flower.grams_remaining += current_grams
        try:
            new_flower.remove_by_grams(new_grams)
        except ValueError as exc:
            if old_flower:
                try:
                    old_flower.remove_by_grams(current_grams)
                except Exception:
                    pass
            messagebox.showerror("Not enough stock", str(exc))
            return
        log["flower"] = new_flower_name
        log["roa"] = new_roa
        log["efficiency"] = efficiency
        log["grams_used"] = new_grams
        log["thc_mg"] = new_grams * 1000 * (new_flower.thc_pct / 100.0) * efficiency
        log["cbd_mg"] = new_grams * 1000 * (new_flower.cbd_pct / 100.0) * efficiency
        log["remaining"] = new_flower.grams_remaining
        log["time"] = dt_obj.strftime("%Y-%m-%d %H:%M")
        log["time_display"] = dt_obj.strftime("%H:%M")
        log["is_cbd_dominant"] = app._is_cbd_dominant(new_flower)
        app._refresh_stock()
        app._refresh_log()
        app.save_data()
        dialog.destroy()

    ttk.Button(buttons, text="Save", command=save_edit).grid(row=0, column=1, sticky="e")
    app._prepare_toplevel(dialog)


def restore_mix_stock(app, log: dict) -> None:
    name = str(log.get("flower", "")).strip()
    if not name:
        return
    grams_used = float(log.get("grams_used", 0.0))
    if grams_used <= 0:
        return
    thc_pct = log.get("mix_thc_pct")
    cbd_pct = log.get("mix_cbd_pct")
    if thc_pct is None or cbd_pct is None:
        try:
            eff = float(log.get("efficiency", 1.0)) or 1.0
            thc_mg = float(log.get("thc_mg", 0.0))
            cbd_mg = float(log.get("cbd_mg", 0.0))
            if grams_used > 0 and eff > 0:
                thc_pct = (thc_mg / eff) / (grams_used * 1000) * 100
                cbd_pct = (cbd_mg / eff) / (grams_used * 1000) * 100
        except Exception:
            pass
    flower = app.flowers.get(name)
    if flower is None:
        for candidate in app.flowers.values():
            if candidate.name.strip().lower() == name.lower():
                flower = candidate
                break
    if flower is None:
        if thc_pct is None or cbd_pct is None:
            return
        flower = Flower(name=name, thc_pct=float(thc_pct), cbd_pct=float(cbd_pct), grams_remaining=0.0)
        app.flowers[name] = flower
    flower.grams_remaining += grams_used


def delete_log_entry(app) -> None:
    selection = app.log_tree.selection()
    if not selection:
        messagebox.showwarning("Select log", "Select a log entry to delete.")
        return
    idx = int(selection[0])
    if idx >= len(app.logs):
        messagebox.showerror("Not found", "Selected log entry is missing.")
        return
    log = app.logs[idx]
    if not messagebox.askokcancel("Confirm delete", "Delete this log entry and restore its grams to stock?"):
        return
    grams_used = float(log.get("grams_used", 0.0))
    flower_name = str(log.get("flower", "")).strip()
    if log.get("mix_sources") or log.get("mix_thc_pct") is not None:
        app._restore_mix_stock(log)
    else:
        flower = app.flowers.get(flower_name)
        if flower is None:
            # Fallback to case-insensitive match in case the name casing changed.
            for candidate in app.flowers.values():
                if candidate.name.strip().lower() == flower_name.lower():
                    flower = candidate
                    break
        if flower:
            flower.grams_remaining += grams_used
    del app.logs[idx]
    app._refresh_stock()
    app._refresh_log()
    app.save_data()


def refresh_log(app) -> None:
    for item in app.log_tree.get_children():
        app.log_tree.delete(item)
    day_str = app.current_date.isoformat()
    day_logs = [log for log in app.logs if log.get("date") == day_str]
    day_total = sum(float(log.get("grams_used", 0.0)) for log in day_logs if app._log_counts_for_totals(log))
    day_total_cbd = sum(float(log.get("grams_used", 0.0)) for log in day_logs if app._log_counts_for_cbd(log))
    if hasattr(app, "day_total_label"):
        if app.current_date < date.today():
            remaining = app.target_daily_grams - day_total if app.target_daily_grams > 0 else None
            color = app.text_color
            if app.enable_usage_coloring:
                color = app.used_thc_under_color
                if remaining is not None and remaining < 0:
                    color = app.used_thc_over_color
            app.day_total_label.config(
                text=f"Total used this day (THC): {day_total:.3f} g", foreground=color
            )
            app.day_total_label.grid()
            if getattr(app, "track_cbd_flower", False):
                color_cbd = app.text_color
                target_cbd = getattr(app, "target_daily_cbd_grams", 0.0)
                if app.enable_usage_coloring and target_cbd > 0:
                    color_cbd = app.used_cbd_under_color if (target_cbd - day_total_cbd) >= 0 else app.used_cbd_over_color
                app.day_total_cbd_label.config(
                    text=f"Total used this day (CBD): {day_total_cbd:.3f} g", foreground=color_cbd
                )
                app.day_total_cbd_label.grid()
            else:
                app.day_total_cbd_label.grid_remove()
        else:
            app.day_total_label.grid_remove()
            app.day_total_cbd_label.grid_remove()
    for idx, log in enumerate(app.logs):
        if log.get("date") != day_str:
            continue
        roa = log.get("roa", "Unknown")
        app.log_tree.insert(
            "",
            tk.END,
            iid=str(idx),
            values=(
                log.get("time_display") or log["time"].split(" ")[-1],
                log["flower"],
                roa,
                f"{log['grams_used']:.3f}",
                f"{log['thc_mg']:.1f}",
                f"{log['cbd_mg']:.1f}",
            ),
        )
    children = app.log_tree.get_children()
    if children:
        try:
            app.log_tree.yview_moveto(1.0)
        except Exception:
            pass
    app.date_label.config(text=app.current_date.strftime("%Y-%m-%d"))


def change_day(app, delta_days: int) -> None:
    app.current_date += timedelta(days=delta_days)
    app._refresh_log()
    app._refresh_stock()
