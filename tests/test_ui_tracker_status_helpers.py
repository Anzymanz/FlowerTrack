from types import SimpleNamespace

from ui_tracker_status import on_status_enter, on_status_leave, status_tooltip_text


class _FakeRoot:
    def __init__(self):
        self.after_calls: list[tuple[int, object]] = []
        self.cancelled: list[object] = []

    def after(self, delay: int, callback):
        job = f"job-{len(self.after_calls) + 1}"
        self.after_calls.append((delay, callback))
        return job

    def after_cancel(self, job):
        self.cancelled.append(job)


def test_status_tooltip_text_client_mode():
    app = SimpleNamespace(
        network_mode="client",
        scraper_notifications_muted=False,
        child_procs=[],
        _client_connection_state=lambda: ("interrupted", 3),
    )
    text = status_tooltip_text(app, lambda _children: (False, False))
    assert "Client connection: Connection interrupted" in text
    assert "Missed polls: 3" in text


def test_status_tooltip_text_host_mode():
    app = SimpleNamespace(
        network_mode="host",
        scraper_notifications_muted=True,
        child_procs=[],
        _host_active_connections_count=lambda: 2,
    )
    text = status_tooltip_text(app, lambda _children: (True, False))
    assert "Host mode | Active clients: 2" in text
    assert "Scraper: Running | Notifications: Muted" in text


def test_status_tooltip_text_standalone_mode():
    app = SimpleNamespace(
        network_mode="standalone",
        scraper_notifications_muted=False,
        child_procs=[],
    )
    text = status_tooltip_text(app, lambda _children: (False, True))
    assert "Scraper: Errored | Notifications: Unmuted" in text


def test_status_tooltip_schedule_and_cancel():
    root = _FakeRoot()
    events = {"shown": 0}
    app = SimpleNamespace(
        root=root,
        _status_tooltip_after_id=None,
        _status_tooltip_text=lambda: "status",
        _show_tooltip=lambda _text, _event=None: events.__setitem__("shown", events["shown"] + 1),
        _tooltip_after_id=None,
        _tooltip_win=None,
    )

    # Schedule delayed tooltip.
    on_status_enter(app, delay_ms=500)
    assert app._status_tooltip_after_id == "job-1"
    assert root.after_calls and root.after_calls[0][0] == 500

    # Cancel delayed tooltip + hide active tooltip.
    on_status_leave(app)
    assert "job-1" in root.cancelled
    assert app._status_tooltip_after_id is None
