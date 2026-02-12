from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from inventory import add_stock_entry


def on_stock_select(app, _event: tk.Event) -> None:
    selection = app.stock_tree.selection()
    if not selection:
        return
    name = app.stock_tree.set(selection[0], "name")
    if not name:
        return
    flower = app.flowers.get(name)
    if flower:
        app.name_entry.delete(0, tk.END)
        app.name_entry.insert(0, flower.name)
        app.thc_entry.delete(0, tk.END)
        app.thc_entry.insert(0, f"{flower.thc_pct:.1f}")
        app.cbd_entry.delete(0, tk.END)
        app.cbd_entry.insert(0, f"{flower.cbd_pct:.1f}")
        app.grams_entry.delete(0, tk.END)
        app.grams_entry.insert(0, f"{flower.grams_remaining:.3f}")
        app.stock_form_source = flower.name
        app.stock_form_dirty = False
    if name in app.flower_choice["values"]:
        app.flower_choice.set(name)


def maybe_clear_stock_selection(app, event: tk.Event) -> None:
    # If click is on empty space, clear selection.
    if not app.stock_tree.identify_row(event.y):
        app.stock_tree.selection_remove(app.stock_tree.selection())
        if app.stock_form_source and not app.stock_form_dirty:
            app._clear_stock_inputs()


def maybe_clear_log_selection(app, event: tk.Event) -> None:
    if not app.log_tree.identify_row(event.y):
        app.log_tree.selection_remove(app.log_tree.selection())


def add_stock(app) -> None:
    name = app.name_entry.get().strip()
    thc_text = app.thc_entry.get().strip()
    cbd_text = app.cbd_entry.get().strip()
    grams_text = app.grams_entry.get().strip()
    if not name or not thc_text or not grams_text:
        messagebox.showwarning("Missing info", "Enter name, THC %, and grams. CBD % can be 0.")
        return
    try:
        thc_pct = float(thc_text)
        cbd_pct = float(cbd_text) if cbd_text else 0.0
        grams = float(grams_text)
    except ValueError:
        messagebox.showerror("Invalid input", "Potency and grams must be numbers.")
        return
    if thc_pct < 0 or cbd_pct < 0 or grams <= 0:
        messagebox.showerror("Invalid input", "Potency must be non-negative and grams must be positive.")
        return
    try:
        add_stock_entry(app.flowers, name=name, grams=grams, thc_pct=thc_pct, cbd_pct=cbd_pct)
    except ValueError as exc:
        messagebox.showerror("Cannot add stock", str(exc))
        return
    app._refresh_stock()
    app._clear_stock_inputs()
    app.save_data()
    app._save_config()


def delete_stock(app) -> None:
    selection = app.stock_tree.selection()
    if not selection:
        messagebox.showwarning("Select flower", "Select a flower row to delete.")
        return
    name = app.stock_tree.set(selection[0], "name")
    if not name:
        messagebox.showerror("Not found", "Could not determine selected flower name.")
        return
    has_logs = any(log.get("flower") == name for log in app.logs)
    msg = f"Delete '{name}' from stock?"
    if has_logs:
        msg += "\nLogs exist for this flower; they will remain but stock will be removed."
    if not messagebox.askokcancel("Confirm delete", msg):
        return
    app.flowers.pop(name, None)
    app._refresh_stock()
    app._refresh_log()
    app.save_data()
    app._save_config()
    app._clear_stock_inputs()
    try:
        app.stock_tree.selection_remove(selection)
    except tk.TclError:
        # Tree was rebuilt; selected item IDs can be stale after refresh.
        try:
            app.stock_tree.selection_set(())
        except Exception:
            pass


def clear_stock_inputs(app) -> None:
    app.name_entry.delete(0, tk.END)
    app.thc_entry.delete(0, tk.END)
    app.cbd_entry.delete(0, tk.END)
    app.grams_entry.delete(0, tk.END)
    app.stock_form_source = None
    app.stock_form_dirty = False


def refresh_stock(app) -> None:
    for item in app.stock_tree.get_children():
        app.stock_tree.delete(item)
    total_all = 0.0
    total_counted = 0.0
    cbd_total = 0.0
    for flower in sorted(app.flowers.values(), key=lambda f: f.name.lower()):
        total_all += flower.grams_remaining
        if app._should_count_flower(flower):
            total_counted += flower.grams_remaining
        if app._is_cbd_dominant(flower):
            cbd_total += flower.grams_remaining
        if app.enable_stock_coloring:
            if app._is_cbd_dominant(flower):
                green_thr = getattr(app, "cbd_single_green_threshold", app.single_green_threshold)
                red_thr = getattr(app, "cbd_single_red_threshold", app.single_red_threshold)
                high_color = app.single_cbd_high_color
                low_color = app.single_cbd_low_color
            else:
                green_thr = app.single_green_threshold
                red_thr = app.single_red_threshold
                high_color = app.single_thc_high_color
                low_color = app.single_thc_low_color
            row_color = app._color_for_value(flower.grams_remaining, green_thr, red_thr, high_color, low_color)
        else:
            row_color = app.text_color
        if flower.grams_remaining <= 1e-6:
            row_color = app.muted_color
        tag = f"stock_{flower.name}"
        app.stock_tree.tag_configure(tag, foreground=row_color)
        app.stock_tree.insert(
            "",
            tk.END,
            tags=(tag,),
            values=(
                flower.name,
                f"{flower.thc_pct:.1f}",
                f"{flower.cbd_pct:.1f}",
                f"{flower.grams_remaining:.3f}",
            ),
        )
    track_cbd = getattr(app, "track_cbd_flower", False)
    combined_total = total_counted
    if track_cbd:
        app.total_label.config(text=f"Total THC stock: {total_counted:.2f} g")
        app.total_cbd_label.config(text=f"Total CBD stock: {cbd_total:.2f} g")
        if not app.total_cbd_label.winfo_ismapped():
            app.total_cbd_label.pack(side="left")
    else:
        app.total_label.config(text=f"Total flower stock: {combined_total:.2f} g")
        try:
            app.total_cbd_label.pack_forget()
        except Exception:
            pass
    total_color = (
        app._color_for_value(
            combined_total,
            app.total_green_threshold,
            app.total_red_threshold,
            app.total_thc_high_color,
            app.total_thc_low_color,
        )
        if app.enable_stock_coloring
        else app.text_color
    )
    app.total_label.configure(foreground=total_color)
    if track_cbd:
        cbd_total_color = (
            app._color_for_value(
                cbd_total,
                getattr(app, "cbd_total_green_threshold", app.total_green_threshold),
                getattr(app, "cbd_total_red_threshold", app.total_red_threshold),
                app.total_cbd_high_color,
                app.total_cbd_low_color,
            )
            if app.enable_stock_coloring
            else app.text_color
        )
        app.total_cbd_label.configure(foreground=cbd_total_color)
    used_today = app._grams_used_on_day(app.current_date)
    used_today_cbd = app._grams_used_on_day_cbd(app.current_date) if getattr(app, "track_cbd_flower", False) else 0.0
    if app.target_daily_grams > 0:
        remaining_today = app.target_daily_grams - used_today
        app.remaining_today_label.config(
            text=f"Remaining today (THC): {remaining_today:.2f} g / {app.target_daily_grams:.2f} g",
            foreground=(
                app.remaining_thc_high_color
                if (app.target_daily_grams - used_today) >= 0
                else app.remaining_thc_low_color
            )
            if app.enable_usage_coloring
            else app.text_color,
        )
    else:
        app.remaining_today_label.config(text="Remaining today (THC): N/A", foreground=app.text_color)
    if getattr(app, "track_cbd_flower", False):
        target_cbd = getattr(app, "target_daily_cbd_grams", 0.0)
        if target_cbd > 0:
            remaining_cbd = target_cbd - used_today_cbd
            app.remaining_today_cbd_label.config(
                text=f"Remaining today (CBD): {remaining_cbd:.2f} g / {target_cbd:.2f} g",
                foreground=(
                    app.remaining_cbd_high_color if remaining_cbd >= 0 else app.remaining_cbd_low_color
                )
                if app.enable_usage_coloring
                else app.text_color,
            )
        else:
            app.remaining_today_cbd_label.config(text="Remaining today (CBD): N/A", foreground=app.text_color)
        app.remaining_today_cbd_label.grid()
    else:
        app.remaining_today_cbd_label.grid_remove()
    remaining_stock = max(combined_total, 0.0)
    days_target = "N/A"
    days_target_val: float | None = None
    if app.target_daily_grams > 0:
        days_target_val = remaining_stock / app.target_daily_grams
        days_target = f"{days_target_val:.1f}"
    avg_daily = app._average_daily_usage()
    days_actual_val = None if avg_daily is None or avg_daily <= 0 else remaining_stock / avg_daily
    days_actual = "N/A" if days_actual_val is None else f"{days_actual_val:.1f}"
    actual_color = app.text_color
    if app.enable_usage_coloring and days_actual_val is not None and days_target_val is not None:
        actual_color = app.days_thc_high_color if days_actual_val >= days_target_val else app.days_thc_low_color
    if track_cbd:
        app.days_label.config(text=f"Days of THC flower left - target: {days_target} | actual: {days_actual}", foreground=actual_color)
    else:
        app.days_label.config(text=f"Days of flower left - target: {days_target} | actual: {days_actual}", foreground=actual_color)
    if not track_cbd:
        app.days_label_cbd.grid_remove()
    elif getattr(app, "track_cbd_flower", False):
        days_target_cbd = "N/A"
        days_target_val_cbd: float | None = None
        if getattr(app, "target_daily_cbd_grams", 0.0) > 0:
            days_target_val_cbd = cbd_total / max(app.target_daily_cbd_grams, 1e-9)
            days_target_cbd = f"{days_target_val_cbd:.1f}"
        avg_daily_cbd = app._average_daily_usage_cbd()
        days_actual_val_cbd = None if avg_daily_cbd is None or avg_daily_cbd <= 0 else cbd_total / avg_daily_cbd
        days_actual_cbd = "N/A" if days_actual_val_cbd is None else f"{days_actual_val_cbd:.1f}"
        color_cbd = app.text_color
        if app.enable_usage_coloring and days_actual_val_cbd is not None and days_target_val_cbd is not None:
            color_cbd = app.days_cbd_high_color if days_actual_val_cbd >= days_target_val_cbd else app.days_cbd_low_color
        app.days_label_cbd.config(
            text=f"Days of CBD flower left - target: {days_target_cbd} | actual: {days_actual_cbd}",
            foreground=color_cbd,
        )
        app.days_label_cbd.grid()
    else:
        app.days_label_cbd.grid_remove()
    app.flower_choice["values"] = [f.name for f in sorted(app.flowers.values(), key=lambda f: f.name.lower())]
    app._apply_stock_sort()


def sort_stock(app, column: str, _numeric: bool) -> None:
    if app.stock_sort_column == column:
        app.stock_sort_reverse = not app.stock_sort_reverse
    else:
        app.stock_sort_column = column
        app.stock_sort_reverse = False
    app._apply_stock_sort()


def apply_stock_sort(app) -> None:
    arrows = {"asc": " ^", "desc": " v"}
    for col in ("name", "thc", "cbd", "grams"):
        base = {
            "name": "Name",
            "thc": "THC (%)",
            "cbd": "CBD (%)",
            "grams": "Remaining (g)",
        }[col]
        if col == app.stock_sort_column:
            suffix = arrows["desc"] if app.stock_sort_reverse else arrows["asc"]
        else:
            suffix = ""
        app.stock_tree.heading(col, text=base + suffix)
    children = list(app.stock_tree.get_children())
    if not children:
        return

    def sort_key(item: str) -> tuple:
        value = app.stock_tree.set(item, app.stock_sort_column)
        if app.stock_sort_column in {"thc", "cbd", "grams"}:
            try:
                return (float(value), value)
            except ValueError:
                return (0.0, value)
        return (value.lower(), value)

    for index, iid in enumerate(sorted(children, key=sort_key, reverse=app.stock_sort_reverse)):
        app.stock_tree.move(iid, "", index)


def mark_stock_form_dirty(app, _event: tk.Event) -> None:
    app.stock_form_dirty = True
