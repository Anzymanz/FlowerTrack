from types import SimpleNamespace

import ui_tracker_window_persistence as persistence


class _FakeRoot:
    def __init__(self):
        self.after_calls = []
        self.cancel_calls = []
        self._geometry = "1200x700+10+10"

    def after(self, delay, callback):
        job = f"job-{len(self.after_calls) + 1}"
        self.after_calls.append((delay, callback, job))
        return job

    def after_cancel(self, job):
        self.cancel_calls.append(job)

    def geometry(self):
        return self._geometry

    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080


def test_parse_resolution():
    assert persistence.parse_resolution("1920x1080") == (1920, 1080)
    assert persistence.parse_resolution("1920 X 1080") == (1920, 1080)
    assert persistence.parse_resolution("bad") is None
    assert persistence.parse_resolution("") is None


def test_apply_resolution_safety_resets_geometry_when_screen_shrinks():
    app = SimpleNamespace(
        window_geometry="1600x900+1+1",
        settings_window_geometry="600x400+2+2",
        screen_resolution="3440x1440",
        _force_center_on_start=False,
        _force_center_settings=False,
        _current_screen_resolution=lambda: "1920x1080",
        _parse_resolution=persistence.parse_resolution,
    )

    persistence.apply_resolution_safety(app)

    assert app.window_geometry == ""
    assert app.settings_window_geometry == ""
    assert app._force_center_on_start is True
    assert app._force_center_settings is True
    assert app.screen_resolution == "1920x1080"


def test_on_root_configure_debounces_persist():
    root = _FakeRoot()
    app = SimpleNamespace(root=root, _geometry_save_job="old-job", _persist_geometry=lambda: None)
    event = SimpleNamespace(widget=root)

    persistence.on_root_configure(app, event)

    assert root.cancel_calls == ["old-job"]
    assert len(root.after_calls) == 1
    assert root.after_calls[0][0] == 500
    assert app._geometry_save_job == "job-1"


def test_persist_geometry_updates_and_saves():
    calls = {"persist_tree": 0, "save_config": 0}
    app = SimpleNamespace(
        root=_FakeRoot(),
        window_geometry="",
        _persist_tree_widths=lambda: calls.__setitem__("persist_tree", calls["persist_tree"] + 1),
        _save_config=lambda: calls.__setitem__("save_config", calls["save_config"] + 1),
    )

    persistence.persist_geometry(app)

    assert app.window_geometry == "1200x700+10+10"
    assert calls["persist_tree"] == 1
    assert calls["save_config"] == 1
