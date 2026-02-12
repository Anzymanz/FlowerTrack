from types import SimpleNamespace

import ui_tracker


class _FakeRoot:
    def __init__(self, width=1200, height=700):
        self._width = width
        self._height = height
        self.geometry_calls: list[str] = []
        self.after_calls: list[int] = []

    def update_idletasks(self):
        return None

    def winfo_width(self):
        return self._width

    def winfo_height(self):
        return self._height

    def geometry(self, value: str):
        self.geometry_calls.append(value)

    def after(self, delay: int, callback):
        self.after_calls.append(delay)
        callback()
        return len(self.after_calls)

    def after_cancel(self, _job):
        return None


class _FakeSplit:
    def __init__(self, width=1000, sash_x=500, sashwidth=8):
        self._width = width
        self._sash_x = sash_x
        self._sashwidth = sashwidth
        self.pane_calls: list[tuple[object, dict]] = []
        self.sash_place_calls: list[tuple[int, int, int]] = []

    def cget(self, key: str):
        if key == "sashwidth":
            return self._sashwidth
        raise KeyError(key)

    def winfo_width(self):
        return self._width

    def sash_coord(self, _index: int):
        return (self._sash_x, 0)

    def sash_place(self, index: int, x: int, y: int):
        self._sash_x = x
        self.sash_place_calls.append((index, x, y))

    def paneconfigure(self, pane, **kwargs):
        self.pane_calls.append((pane, kwargs))


class _FakeFrame:
    def __init__(self):
        self.visible = True

    def grid(self):
        self.visible = True

    def grid_remove(self):
        self.visible = False


class _FakeToggle:
    def __init__(self):
        self.text = "˅"

    def configure(self, **kwargs):
        if "text" in kwargs:
            self.text = kwargs["text"]


def test_persist_split_ratio_clamps_to_bounds():
    dummy = SimpleNamespace(
        _restoring_split=False,
        main_split_ratio=0.48,
        root=_FakeRoot(),
        main_split=_FakeSplit(width=1000, sash_x=980, sashwidth=8),
    )

    ui_tracker.CannabisTracker._persist_split_ratio(dummy)
    assert dummy.main_split_ratio == 0.85

    dummy.main_split = _FakeSplit(width=1000, sash_x=0, sashwidth=8)
    ui_tracker.CannabisTracker._persist_split_ratio(dummy)
    assert dummy.main_split_ratio == 0.15


def test_apply_split_ratio_sets_panes_and_sash():
    stock_wrap = object()
    right_content = object()
    split = _FakeSplit(width=1000, sash_x=0, sashwidth=8)
    dummy = SimpleNamespace(
        root=_FakeRoot(),
        main_split=split,
        main_split_ratio=0.5,
        stock_wrap=stock_wrap,
        right_content=right_content,
    )

    ui_tracker.CannabisTracker._apply_split_ratio(dummy)

    assert split.sash_place_calls[-1] == (0, 496, 0)
    assert len(split.pane_calls) == 2
    left_call = split.pane_calls[0]
    right_call = split.pane_calls[1]
    assert left_call[0] is stock_wrap
    assert left_call[1]["width"] == 496
    assert right_call[0] is right_content
    assert right_call[1]["width"] == 496


def test_toggle_stock_form_preserves_geometry_and_restores_sash():
    root = _FakeRoot(width=1234, height=777)
    split = _FakeSplit(width=1100, sash_x=540, sashwidth=8)
    frame = _FakeFrame()
    toggle = _FakeToggle()
    calls = {"persist": 0, "save": 0}

    dummy = SimpleNamespace(
        root=root,
        main_split=split,
        show_stock_form=True,
        stock_form_frame=frame,
        stock_form_toggle=toggle,
        _apply_mix_button_visibility=lambda: None,
    )
    dummy._apply_stock_form_visibility = lambda: ui_tracker.CannabisTracker._apply_stock_form_visibility(dummy)
    dummy._persist_split_ratio = lambda: calls.__setitem__("persist", calls["persist"] + 1)
    dummy._save_config = lambda: calls.__setitem__("save", calls["save"] + 1)

    ui_tracker.CannabisTracker._toggle_stock_form(dummy)

    assert dummy.show_stock_form is False
    assert frame.visible is False
    assert toggle.text == "˄"
    assert root.geometry_calls[-1] == "1234x777"
    assert split.sash_place_calls[-1] == (0, 540, 0)
    assert calls["persist"] == 1
    assert calls["save"] == 1
    assert getattr(dummy, "_suspend_stock_width_save", None) is False


def test_finalize_split_restore_releases_restoring_flag():
    calls = {"apply": 0}
    dummy = SimpleNamespace(
        _split_dragging=False,
        _split_stabilize_job=None,
        _restoring_split=True,
        root=_FakeRoot(),
    )
    dummy._apply_split_ratio = lambda: calls.__setitem__("apply", calls["apply"] + 1)

    ui_tracker.CannabisTracker._finalize_split_restore(dummy)

    assert dummy._restoring_split is False
    assert calls["apply"] >= 1
