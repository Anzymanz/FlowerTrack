import threading
import urllib.parse
from types import SimpleNamespace

import capture


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status = status

    def read(self):
        import json

        return json.dumps(self._payload).encode("utf-8")

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False


def _build_worker():
    logs: list[str] = []
    apply_calls = {"count": 0}
    cfg = {
        "api_only": True,
        "interval_seconds": 30.0,
        "include_inactive": False,
        "requestable_only": True,
        "in_stock_only": False,
    }
    callbacks = {
        "capture_log": logs.append,
        "apply_text": lambda _text: apply_calls.__setitem__("count", apply_calls["count"] + 1),
        "stop_event": threading.Event(),
        "responsive_wait": lambda _seconds, label="": False,  # noqa: ARG005
    }
    worker = capture.CaptureWorker(cfg, callbacks, app_dir=None, install_fn=None)
    worker.scheduler = SimpleNamespace(
        next_interval=lambda base, _cfg: base,
        wait=lambda _seconds, label="": True,  # noqa: ARG005
    )
    return worker, logs, apply_calls


def _auth_payload():
    return {
        "token": "Bearer ok_token",
        "refresh_token": "refresh_token",
        "rpc_host": "rpc.example",
        "patient_id": "patient",
        "pharmacy_id": "pharmacy",
    }


def _list_items(count: int) -> list[dict]:
    return [{"product_id": f"P{idx}"} for idx in range(count)]


def test_partial_pagination_interrupted_never_applies_parse_pipeline(monkeypatch):
    worker, logs, apply_calls = _build_worker()
    persist_calls = {"count": 0}

    monkeypatch.setattr(worker, "_credentials_ready", lambda: True)
    monkeypatch.setattr(worker, "_auth_cache_valid", lambda: True)
    monkeypatch.setattr(worker, "_load_auth_cache", _auth_payload)
    monkeypatch.setattr(worker, "_auth_is_expired", lambda _token: False)
    monkeypatch.setattr(worker, "_bootstrap_auth_with_playwright", lambda: None)
    monkeypatch.setattr(worker, "_persist_auth_cache", lambda _payloads: persist_calls.__setitem__("count", persist_calls["count"] + 1))

    def _fake_urlopen(req, timeout=20, context=None):  # noqa: ARG001
        url = req.full_url
        parsed = urllib.parse.urlparse(url)
        if "formulary-products/count" in parsed.path:
            # Simulate a user stop while pagination is about to start.
            worker.callbacks["stop_event"].set()
            return _FakeResponse({"count": 100})
        if "formulary-products" in parsed.path:
            return _FakeResponse(_list_items(50))
        raise AssertionError(f"Unexpected URL in interrupted pagination test: {url}")

    monkeypatch.setattr(capture.urllib.request, "urlopen", _fake_urlopen)

    worker._run()

    assert apply_calls["count"] == 0
    assert persist_calls["count"] == 0
    assert any("API pagination interrupted by stop request; skipping parse." in line for line in logs)


def test_partial_pagination_incomplete_never_applies_parse_pipeline(monkeypatch):
    worker, logs, apply_calls = _build_worker()
    persist_calls = {"count": 0}

    monkeypatch.setattr(worker, "_credentials_ready", lambda: True)
    monkeypatch.setattr(worker, "_auth_cache_valid", lambda: True)
    monkeypatch.setattr(worker, "_load_auth_cache", _auth_payload)
    monkeypatch.setattr(worker, "_auth_is_expired", lambda _token: False)
    monkeypatch.setattr(worker, "_bootstrap_auth_with_playwright", lambda: None)
    monkeypatch.setattr(worker, "_persist_auth_cache", lambda _payloads: persist_calls.__setitem__("count", persist_calls["count"] + 1))

    def _fake_urlopen(req, timeout=20, context=None):  # noqa: ARG001
        url = req.full_url
        parsed = urllib.parse.urlparse(url)
        if "formulary-products/count" in parsed.path:
            return _FakeResponse({"count": 150})
        if "formulary-products" in parsed.path:
            skip = int((urllib.parse.parse_qs(parsed.query).get("skip") or ["0"])[0])
            if skip == 0:
                return _FakeResponse(_list_items(50))
            if skip == 50:
                return _FakeResponse(_list_items(50))
            if skip == 100:
                # Final page returns empty: technically fetched but still incomplete total.
                return _FakeResponse([])
        raise AssertionError(f"Unexpected URL in incomplete pagination test: {url}")

    monkeypatch.setattr(capture.urllib.request, "urlopen", _fake_urlopen)

    worker._run()

    assert apply_calls["count"] == 0
    assert persist_calls["count"] == 0
    assert any("API pagination incomplete (100/150); skipping parse." in line for line in logs)
