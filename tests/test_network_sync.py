import json
import socket
import threading
from pathlib import Path

from network_sync import (
    fetch_library_data,
    fetch_tracker_data,
    network_ping,
    push_library_data,
    push_tracker_data,
    start_network_data_server,
    stop_network_data_server,
)


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    try:
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def _start_server(tmp_path: Path, access_key: str = "", **kwargs):
    tracker_data_path = tmp_path / "tracker_data.json"
    library_data_path = tmp_path / "library_data.json"
    logs: list[str] = []
    httpd, thread, port = start_network_data_server(
        bind_host="127.0.0.1",
        preferred_port=_free_port(),
        tracker_data_path=tracker_data_path,
        library_data_path=library_data_path,
        log=logs.append,
        access_key=access_key,
        **kwargs,
    )
    return httpd, thread, int(port or 0), tracker_data_path, library_data_path


def test_network_sync_connect_and_roundtrip(tmp_path):
    httpd = thread = None
    try:
        httpd, thread, port, tracker_path, library_path = _start_server(tmp_path)
        assert port > 0
        assert network_ping("127.0.0.1", port, timeout=1.0)

        tracker_payload = {"schema_version": 1, "logs": [{"id": "A", "dose": 0.1}]}
        assert push_tracker_data("127.0.0.1", port, tracker_payload, timeout=1.0)
        assert fetch_tracker_data("127.0.0.1", port, timeout=1.0) == tracker_payload

        library_payload = [{"brand": "Brand", "strain": "Strain"}]
        assert push_library_data("127.0.0.1", port, library_payload, timeout=1.0)
        assert fetch_library_data("127.0.0.1", port, timeout=1.0) == library_payload

        assert json.loads(tracker_path.read_text(encoding="utf-8")) == tracker_payload
        assert json.loads(library_path.read_text(encoding="utf-8")) == library_payload
    finally:
        stop_network_data_server(httpd, thread, lambda _m: None)


def test_network_sync_access_key_required_when_configured(tmp_path):
    httpd = thread = None
    try:
        access_key = "test-network-key"
        httpd, thread, port, _, _ = _start_server(tmp_path, access_key=access_key)
        assert port > 0
        assert not network_ping("127.0.0.1", port, timeout=1.0, access_key="")
        assert network_ping("127.0.0.1", port, timeout=1.0, access_key=access_key)
    finally:
        stop_network_data_server(httpd, thread, lambda _m: None)


def test_conflicting_network_writes_remain_consistent(tmp_path):
    httpd = thread = None
    try:
        access_key = "conflict-key"
        httpd, thread, port, tracker_path, library_path = _start_server(tmp_path, access_key=access_key)
        assert port > 0
        assert network_ping("127.0.0.1", port, timeout=1.0, access_key=access_key)

        tracker_a = {"schema_version": 1, "logs": [{"source": "A", "dose": 0.1}]}
        tracker_b = {"schema_version": 1, "logs": [{"source": "B", "dose": 0.2}]}
        library_a = [{"source": "A", "strain": "One"}]
        library_b = [{"source": "B", "strain": "Two"}]

        barrier = threading.Barrier(3)
        results: list[bool] = []
        result_lock = threading.Lock()

        def _write_tracker(payload: dict) -> None:
            barrier.wait()
            ok = push_tracker_data("127.0.0.1", port, payload, timeout=2.0, access_key=access_key)
            with result_lock:
                results.append(ok)

        threads = [
            threading.Thread(target=_write_tracker, args=(tracker_a,), daemon=True),
            threading.Thread(target=_write_tracker, args=(tracker_b,), daemon=True),
        ]
        for t in threads:
            t.start()
        barrier.wait()
        for t in threads:
            t.join(timeout=3.0)

        assert len(results) == 2
        assert all(results)
        tracker_final = fetch_tracker_data("127.0.0.1", port, timeout=1.0, access_key=access_key)
        assert tracker_final == tracker_a or tracker_final == tracker_b
        tracker_raw = json.loads(tracker_path.read_text(encoding="utf-8"))
        assert tracker_raw == tracker_a or tracker_raw == tracker_b

        barrier = threading.Barrier(3)
        results.clear()

        def _write_library(payload: list[dict]) -> None:
            barrier.wait()
            ok = push_library_data("127.0.0.1", port, payload, timeout=2.0, access_key=access_key)
            with result_lock:
                results.append(ok)

        threads = [
            threading.Thread(target=_write_library, args=(library_a,), daemon=True),
            threading.Thread(target=_write_library, args=(library_b,), daemon=True),
        ]
        for t in threads:
            t.start()
        barrier.wait()
        for t in threads:
            t.join(timeout=3.0)

        assert len(results) == 2
        assert all(results)
        library_final = fetch_library_data("127.0.0.1", port, timeout=1.0, access_key=access_key)
        assert library_final == library_a or library_final == library_b
        library_raw = json.loads(library_path.read_text(encoding="utf-8"))
        assert library_raw == library_a or library_raw == library_b
    finally:
        stop_network_data_server(httpd, thread, lambda _m: None)


def test_network_sync_rate_limit_blocks_and_recovers(tmp_path):
    httpd = thread = None
    try:
        httpd, thread, port, _, _ = _start_server(
            tmp_path,
            rate_limit_requests_per_minute=2,
            rate_limit_window_seconds=1.0,
        )
        assert port > 0
        assert network_ping("127.0.0.1", port, timeout=1.0)
        assert network_ping("127.0.0.1", port, timeout=1.0)
        assert not network_ping("127.0.0.1", port, timeout=1.0)
        # Window elapsed -> client can request again.
        import time as _time

        _time.sleep(1.05)
        assert network_ping("127.0.0.1", port, timeout=1.0)
    finally:
        stop_network_data_server(httpd, thread, lambda _m: None)


def test_network_denied_access_logs_are_bounded(tmp_path):
    httpd = thread = None
    logs: list[str] = []
    try:
        tracker_data_path = tmp_path / "tracker_data.json"
        library_data_path = tmp_path / "library_data.json"
        httpd, thread, port = start_network_data_server(
            bind_host="127.0.0.1",
            preferred_port=_free_port(),
            tracker_data_path=tracker_data_path,
            library_data_path=library_data_path,
            log=logs.append,
            access_key="secret-key",
            audit_log_burst=2,
            audit_log_window_seconds=1.0,
        )
        assert port and int(port) > 0
        # Repeated denied requests should be bounded by burst within window.
        assert not network_ping("127.0.0.1", int(port), timeout=1.0, access_key="")
        assert not network_ping("127.0.0.1", int(port), timeout=1.0, access_key="")
        assert not network_ping("127.0.0.1", int(port), timeout=1.0, access_key="")
        denied_logs = [m for m in logs if "denied invalid_access_key" in str(m)]
        assert len(denied_logs) <= 2
    finally:
        stop_network_data_server(httpd, thread, lambda _m: None)


def test_network_invalid_payload_type_is_audited(tmp_path):
    httpd = thread = None
    logs: list[str] = []
    try:
        tracker_data_path = tmp_path / "tracker_data.json"
        library_data_path = tmp_path / "library_data.json"
        httpd, thread, port = start_network_data_server(
            bind_host="127.0.0.1",
            preferred_port=_free_port(),
            tracker_data_path=tracker_data_path,
            library_data_path=library_data_path,
            log=logs.append,
            access_key="secret-key",
        )
        assert port and int(port) > 0
        # Wrong type for tracker endpoint (expects dict)
        assert not push_tracker_data(
            "127.0.0.1",
            int(port),
            data=[],  # type: ignore[arg-type]
            timeout=1.0,
            access_key="secret-key",
        )
        assert any("denied invalid_tracker_payload" in str(m) for m in logs)
    finally:
        stop_network_data_server(httpd, thread, lambda _m: None)
