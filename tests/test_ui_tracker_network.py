import threading
from types import SimpleNamespace

import ui_tracker
from network_mode import MODE_CLIENT, MODE_STANDALONE


class _ImmediateThread:
    def __init__(self, target=None, daemon=None, name=None):  # noqa: ARG002
        self._target = target

    def start(self):
        if self._target:
            self._target()


def _build_client_dummy():
    events = {
        "apply": [],
        "refresh_stock": 0,
        "refresh_log": 0,
        "closed": 0,
    }

    dummy = SimpleNamespace(
        network_mode=MODE_CLIENT,
        _client_missed_pings=0,
        _client_disconnect_since=None,
        _client_disconnect_timeout_s=30.0,
        _client_disconnect_closing=False,
        _client_ever_connected=False,
        _client_poll_inflight=False,
        _client_poll_lock=threading.Lock(),
        _network_tracker_mtime=0.0,
        network_host="127.0.0.1",
        network_port=8766,
        network_access_key="",
        root=SimpleNamespace(after=lambda _delay, cb: cb()),
    )

    def _apply_loaded_tracker_data(data, remote_mtime=None):
        events["apply"].append((data, remote_mtime))

    dummy._apply_loaded_tracker_data = _apply_loaded_tracker_data
    dummy._refresh_stock = lambda: events.__setitem__("refresh_stock", events["refresh_stock"] + 1)
    dummy._refresh_log = lambda: events.__setitem__("refresh_log", events["refresh_log"] + 1)
    dummy._on_main_close = lambda: events.__setitem__("closed", events["closed"] + 1)
    return dummy, events


def test_request_client_network_poll_connect_fetches_data(monkeypatch):
    dummy, _events = _build_client_dummy()
    consumed: list[dict] = []
    dummy._consume_client_network_result = lambda payload: consumed.append(payload)

    monkeypatch.setattr(ui_tracker, "fetch_tracker_meta", lambda *args, **kwargs: {"ok": True, "mtime": 42.0})
    monkeypatch.setattr(
        ui_tracker,
        "fetch_tracker_data",
        lambda *args, **kwargs: {"schema_version": 1, "logs": [{"id": "seed"}]},
    )
    monkeypatch.setattr(ui_tracker.threading, "Thread", _ImmediateThread)

    ui_tracker.CannabisTracker._request_client_network_poll(dummy, initial=True)

    assert len(consumed) == 1
    assert consumed[0]["ok"] is True
    assert consumed[0]["mtime"] == 42.0
    assert isinstance(consumed[0].get("data"), dict)
    assert dummy._client_poll_inflight is False


def test_consume_client_network_result_disconnect_timeout_closes(monkeypatch):
    dummy, events = _build_client_dummy()
    dummy._client_disconnect_since = 0.0
    dummy._client_disconnect_timeout_s = 5.0

    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(ui_tracker.messagebox, "showerror", lambda title, msg: shown.append((title, msg)))
    monkeypatch.setattr(ui_tracker.time, "monotonic", lambda: 10.0)

    ui_tracker.CannabisTracker._consume_client_network_result(dummy, {"ok": False})

    assert dummy._client_disconnect_closing is True
    assert dummy._client_missed_pings == 1
    assert events["closed"] == 1
    assert shown and shown[0][0] == "Host disconnected"


def test_consume_client_network_result_reconnect_resets_disconnect_state(monkeypatch):
    dummy, events = _build_client_dummy()
    payload = {"schema_version": 1, "logs": [{"id": "L1"}]}

    # First failure starts disconnect tracking.
    monkeypatch.setattr(ui_tracker.time, "monotonic", lambda: 12.0)
    ui_tracker.CannabisTracker._consume_client_network_result(dummy, {"ok": False})

    assert dummy._client_missed_pings == 1
    assert dummy._client_disconnect_since == 12.0

    # Success should clear disconnect state and apply latest payload.
    ui_tracker.CannabisTracker._consume_client_network_result(dummy, {"ok": True, "mtime": 50.0, "data": payload})

    assert dummy._client_ever_connected is True
    assert dummy._client_missed_pings == 0
    assert dummy._client_disconnect_since is None
    assert dummy._network_tracker_mtime == 50.0
    assert events["apply"] == [(payload, 50.0)]
    assert events["refresh_stock"] == 1
    assert events["refresh_log"] == 1


def test_consume_client_network_result_ignores_non_client_mode():
    dummy, events = _build_client_dummy()
    dummy.network_mode = MODE_STANDALONE
    dummy._client_missed_pings = 4

    ui_tracker.CannabisTracker._consume_client_network_result(dummy, {"ok": False})

    assert dummy._client_missed_pings == 4
    assert events["apply"] == []
