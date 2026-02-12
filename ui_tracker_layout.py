from __future__ import annotations


def toggle_stock_form(app) -> None:
    prev_root_w = None
    prev_root_h = None
    prev_sash_x = None
    try:
        app.root.update_idletasks()
        prev_root_w = int(app.root.winfo_width())
        prev_root_h = int(app.root.winfo_height())
        split = getattr(app, "main_split", None)
        if split is not None:
            prev_sash_x = int(split.sash_coord(0)[0])
    except Exception:
        pass
    setattr(app, "_suspend_stock_width_save", True)
    app.show_stock_form = not bool(getattr(app, "show_stock_form", True))
    app._apply_stock_form_visibility()
    try:
        split = getattr(app, "main_split", None)
        if split is not None and prev_sash_x is not None and prev_sash_x > 0:

            def _restore_sash():
                try:
                    split.sash_place(0, prev_sash_x, 0)
                except Exception:
                    pass
                app._persist_split_ratio()
                setattr(app, "_suspend_stock_width_save", False)

            app.root.after(220, _restore_sash)
        else:
            app.root.after(220, lambda: setattr(app, "_suspend_stock_width_save", False))
        if prev_root_w and prev_root_w > 0 and prev_root_h and prev_root_h > 0:
            # Prevent temporary width growth of the whole tracker window.
            app.root.geometry(f"{prev_root_w}x{prev_root_h}")
    except Exception:
        setattr(app, "_suspend_stock_width_save", False)
    try:
        app._save_config()
    except Exception:
        pass


def persist_split_ratio(app) -> None:
    try:
        if getattr(app, "_restoring_split", False):
            return
        split = getattr(app, "main_split", None)
        if split is None:
            return
        app.root.update_idletasks()
        total_w = int(split.winfo_width())
        if total_w <= 0:
            return
        sash_x = int(split.sash_coord(0)[0])
        sash_w = int(split.cget("sashwidth") or 0)
        usable = max(total_w - sash_w, 1)
        ratio = sash_x / float(usable)
        app.main_split_ratio = min(0.85, max(0.15, ratio))
    except Exception:
        pass


def finalize_split_restore(app) -> None:
    def _tick(remaining: int) -> None:
        try:
            if not getattr(app, "_split_dragging", False):
                app._apply_split_ratio()
        except Exception:
            pass
        if remaining > 0:
            try:
                app._split_stabilize_job = app.root.after(140, lambda: _tick(remaining - 1))
            except Exception:
                app._restoring_split = False
            return
        app._restoring_split = False

    try:
        _tick(7)
    except Exception:
        app._restoring_split = False


def schedule_split_persist(app) -> None:
    try:
        app._split_dragging = False
        if app._split_save_job is not None:
            try:
                app.root.after_cancel(app._split_save_job)
            except Exception:
                pass
        app._split_save_job = app.root.after(150, app._persist_split_ratio)
    except Exception:
        app._persist_split_ratio()


def on_split_release(app) -> None:
    try:
        app._split_dragging = False
        app._persist_split_ratio()
        app._schedule_split_persist()
    except Exception:
        pass


def schedule_split_apply(app) -> None:
    try:
        if app._split_dragging:
            return
        if app._split_apply_job is not None:
            try:
                app.root.after_cancel(app._split_apply_job)
            except Exception:
                pass
        app._split_apply_job = app.root.after(10, app._apply_split_ratio)
    except Exception:
        pass


def apply_split_ratio(app) -> None:
    try:
        split = getattr(app, "main_split", None)
        if split is None:
            return
        app.root.update_idletasks()
        total_w = int(split.winfo_width())
        if total_w <= 0:
            return
        ratio = float(getattr(app, "main_split_ratio", 0.48) or 0.48)
        ratio = min(0.85, max(0.15, ratio))
        sash_w = int(split.cget("sashwidth") or 0)
        usable = max(total_w - sash_w, 1)
        x = int(usable * ratio)
        left_w = x
        right_w = max(total_w - sash_w - left_w, 1)
        try:
            split.paneconfigure(app.stock_wrap, width=left_w, minsize=220, stretch="always")
            split.paneconfigure(app.right_content, width=right_w, minsize=260, stretch="always")
        except Exception:
            pass
        split.sash_place(0, x, 0)
    except Exception:
        pass


def apply_stock_form_visibility(app) -> None:
    frame = getattr(app, "stock_form_frame", None)
    btn = getattr(app, "stock_form_toggle", None)
    if frame:
        try:
            (frame.grid if app.show_stock_form else frame.grid_remove)()
        except Exception:
            pass
    if btn:
        try:
            btn.configure(text="˅" if app.show_stock_form else "˄")
        except Exception:
            pass
    app._apply_mix_button_visibility()
