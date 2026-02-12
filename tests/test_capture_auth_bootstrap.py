import json
import threading
from types import SimpleNamespace

import capture


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status = status

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, D401
        return False


def _new_worker(cfg_updates: dict | None = None):
    cfg = {
        "api_only": True,
        "interval_seconds": 30.0,
        "include_inactive": False,
        "requestable_only": True,
        "in_stock_only": False,
        "headless": True,
    }
    if cfg_updates:
        cfg.update(cfg_updates)
    logs: list[str] = []
    callbacks = {
        "capture_log": logs.append,
        "apply_text": lambda _msg: None,
        "stop_event": threading.Event(),
        "responsive_wait": lambda _seconds, label="": False,  # noqa: ARG005
    }
    worker = capture.CaptureWorker(cfg, callbacks, app_dir=None, install_fn=None)
    return worker, logs


def test_run_uses_valid_auth_cache_without_bootstrap(monkeypatch):
    worker, _logs = _new_worker()
    calls = {"direct": 0, "bootstrap": 0}

    monkeypatch.setattr(worker, "_credentials_ready", lambda: True)
    monkeypatch.setattr(worker, "_auth_cache_valid", lambda: True)

    def _direct():
        calls["direct"] += 1
        return [{"url": "https://rpc/formulary-products?skip=0", "data": []}]

    def _bootstrap():
        calls["bootstrap"] += 1
        return None

    monkeypatch.setattr(worker, "_direct_api_capture", _direct)
    monkeypatch.setattr(worker, "_bootstrap_auth_with_playwright", _bootstrap)
    monkeypatch.setattr(worker, "_persist_auth_cache", lambda _payloads: None)
    worker.scheduler = SimpleNamespace(
        next_interval=lambda base, _cfg: base,
        wait=lambda _seconds, label="": True,  # noqa: ARG005
    )

    worker._run()

    assert calls["direct"] == 1
    assert calls["bootstrap"] == 0
    assert worker.status == "stopped"


def test_direct_api_capture_refreshes_expired_token(monkeypatch):
    worker, _logs = _new_worker()

    stale_auth = {
        "token": "Bearer stale_token",
        "refresh_token": "refresh_token",
        "rpc_host": "rpc.example",
        "patient_id": "patient",
        "pharmacy_id": "pharmacy",
        "user_agent": "FlowerTrackTests",
    }
    fresh_auth = dict(stale_auth)
    fresh_auth["token"] = "Bearer fresh_token"

    load_calls = {"count": 0}

    def _load_auth():
        load_calls["count"] += 1
        return stale_auth if load_calls["count"] == 1 else fresh_auth

    refresh_calls = {"count": 0}

    def _refresh():
        refresh_calls["count"] += 1
        return True

    def _fake_urlopen(req, timeout=20, context=None):  # noqa: ARG001
        url = req.full_url
        if "formulary-products/count" in url:
            return _FakeResponse({"count": 1}, status=200)
        if "formulary-products?" in url:
            return _FakeResponse([{"product_id": "P1"}], status=200)
        raise AssertionError(f"Unexpected URL in test: {url}")

    monkeypatch.setattr(worker, "_load_auth_cache", _load_auth)
    monkeypatch.setattr(worker, "_refresh_auth_token", _refresh)
    monkeypatch.setattr(worker, "_auth_is_expired", lambda token: "stale_token" in str(token))
    monkeypatch.setattr(capture.urllib.request, "urlopen", _fake_urlopen)

    payloads = worker._direct_api_capture()

    assert refresh_calls["count"] == 1
    assert isinstance(payloads, list) and payloads
    first = payloads[0]
    assert first["request_headers"]["authorization"] == "Bearer fresh_token"
    assert worker._last_auth_error is False


def test_run_manual_bootstrap_when_credentials_missing(monkeypatch):
    worker, logs = _new_worker()
    worker._auth_bootstrap_failures = 4
    worker._auth_probe_failures = 2

    calls = {"bootstrap": 0, "direct": 0, "persist": 0}

    monkeypatch.setattr(worker, "_credentials_ready", lambda: False)
    monkeypatch.setattr(worker, "_auth_cache_valid", lambda: False)

    def _bootstrap():
        calls["bootstrap"] += 1
        return [{"url": "https://rpc/auth/initialize", "data": {"tokens": {"accessToken": "A"}}}]

    def _direct():
        calls["direct"] += 1
        return [{"url": "https://rpc/formulary-products?skip=0", "data": []}]

    def _persist(_payloads):
        calls["persist"] += 1

    monkeypatch.setattr(worker, "_bootstrap_auth_with_playwright", _bootstrap)
    monkeypatch.setattr(worker, "_direct_api_capture", _direct)
    monkeypatch.setattr(worker, "_persist_auth_cache", _persist)
    worker.scheduler = SimpleNamespace(
        next_interval=lambda base, _cfg: base,
        wait=lambda _seconds, label="": True,  # noqa: ARG005
    )

    worker._run()

    assert calls["bootstrap"] == 1
    assert calls["direct"] == 1
    assert calls["persist"] >= 2  # bootstrap payloads + final API payloads
    assert worker._auth_bootstrap_failures == 0
    assert worker._auth_probe_failures == 0
    assert any("Credentials are missing. Launching browser for manual auth bootstrap..." in line for line in logs)


def test_run_bootstrap_failure_applies_auth_backoff(monkeypatch):
    worker, logs = _new_worker({"interval_seconds": 30.0})
    waited = {"seconds": None}

    monkeypatch.setattr(worker, "_credentials_ready", lambda: False)
    monkeypatch.setattr(worker, "_auth_cache_valid", lambda: False)
    monkeypatch.setattr(worker, "_bootstrap_auth_with_playwright", lambda: None)
    monkeypatch.setattr(worker, "_direct_api_capture", lambda: None)

    def _wait(seconds, label=""):  # noqa: ARG001
        waited["seconds"] = float(seconds)
        return True

    worker.scheduler = SimpleNamespace(
        next_interval=lambda base, _cfg: base,
        wait=_wait,
    )

    worker._run()

    assert worker._auth_bootstrap_failures == 1
    assert waited["seconds"] == 300.0
    assert any("Auth bootstrap backoff: waiting 300s." in line for line in logs)
