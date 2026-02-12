from types import SimpleNamespace

import ui_tracker_visibility as visibility


class _FakeWidget:
    def __init__(self):
        self.visible = True
        self.grid_calls = []
        self.bind_calls = {}

    def grid(self, **kwargs):
        self.visible = True
        self.grid_calls.append(kwargs)

    def grid_remove(self):
        self.visible = False

    def bind(self, event, callback):
        self.bind_calls[event] = callback


class _FakeTree:
    def __init__(self, columns):
        self._columns = tuple(columns)
        self._display = tuple(columns)
        self._widths = {col: 100 for col in columns}

    def __getitem__(self, key):
        if key == "columns":
            return self._columns
        if key == "displaycolumns":
            return self._display
        raise KeyError(key)

    def __setitem__(self, key, value):
        if key == "displaycolumns":
            self._display = tuple(value)
            return
        raise KeyError(key)

    def configure(self, **kwargs):
        if "displaycolumns" in kwargs:
            self._display = tuple(kwargs["displaycolumns"])

    def column(self, col, option=None, **kwargs):
        if option == "width":
            return self._widths.get(col, 100)
        if "width" in kwargs:
            self._widths[col] = int(kwargs["width"])
        return None

    def update_idletasks(self):
        return None


class _FakeRoot:
    def after(self, _delay, callback):
        callback()
        return "job"


def test_apply_roa_visibility_hides_widgets_and_columns():
    calls = {"mix": 0}
    app = SimpleNamespace(
        hide_roa_options=True,
        log_tree=_FakeTree(["time", "flower", "roa", "grams", "thc_mg", "cbd_mg"]),
        roa_label=_FakeWidget(),
        roa_choice=_FakeWidget(),
        _apply_mix_button_visibility=lambda: calls.__setitem__("mix", calls["mix"] + 1),
    )

    visibility.apply_roa_visibility(app)

    assert app.log_tree["displaycolumns"] == ("time", "flower", "grams")
    assert app.roa_label.visible is False
    assert app.roa_choice.visible is False
    assert calls["mix"] == 1


def test_apply_mix_button_visibility_respects_flags_and_roa_columns():
    mixed_btn = _FakeWidget()
    stock_btn = _FakeWidget()
    app = SimpleNamespace(
        hide_roa_options=True,
        hide_mixed_dose=True,
        hide_mix_stock=False,
        mixed_dose_button=mixed_btn,
        mix_stock_button=stock_btn,
        _mixed_dose_grid={"row": 1, "column": 1},
        _mix_stock_grid={"row": 1, "column": 2},
        log_tree=_FakeTree(["time", "flower", "roa", "grams", "thc_mg", "cbd_mg"]),
        log_column_widths={},
        root=_FakeRoot(),
        _suspend_log_width_save=False,
    )

    visibility.apply_mix_button_visibility(app)

    assert mixed_btn.visible is False
    assert stock_btn.visible is True
    assert stock_btn.grid_calls[-1] == {"row": 1, "column": 2}
    assert app.log_tree["displaycolumns"] == ("time", "flower", "grams")
    assert app._suspend_log_width_save is False


def test_apply_scraper_status_visibility_host_and_hidden_states():
    label = _FakeWidget()
    host_clients = _FakeWidget()
    app = SimpleNamespace(
        scraper_status_label=label,
        host_clients_label=host_clients,
        show_scraper_status_icon=True,
        show_scraper_buttons=True,
        network_mode="host",
    )

    visibility.apply_scraper_status_visibility(app)
    assert label.visible is True
    assert host_clients.visible is True

    app.show_scraper_buttons = False
    visibility.apply_scraper_status_visibility(app)
    assert label.visible is False
    assert host_clients.visible is False


def test_bind_scraper_status_actions_wires_callbacks():
    label = _FakeWidget()
    app = SimpleNamespace(
        scraper_status_label=label,
        _on_status_double_click=lambda _e=None: None,
        _on_status_right_click=lambda _e=None: None,
        _on_status_enter=lambda _e=None: None,
        _on_status_leave=lambda _e=None: None,
    )

    visibility.bind_scraper_status_actions(app)

    assert set(label.bind_calls.keys()) == {
        "<Double-Button-1>",
        "<Button-3>",
        "<Enter>",
        "<Leave>",
    }
