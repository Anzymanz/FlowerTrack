from __future__ import annotations

import functools
import http.server
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

_WRITE_LOCK = threading.RLock()

DEFAULT_NETWORK_PORT = 8766
DEFAULT_EXPORT_PORT = 8765
DEFAULT_BIND_HOST = "0.0.0.0"
DEFAULT_REMOTE_HOST = "127.0.0.1"


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _port_ready(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def start_network_data_server(
    bind_host: str,
    preferred_port: int,
    tracker_data_path: Path,
    library_data_path: Path,
    log: Callable[[str], None],
) -> Tuple[Optional[http.server.ThreadingHTTPServer], Optional[threading.Thread], Optional[int]]:
    """Start host-mode JSON API server for shared tracker/library data."""
    bind = (bind_host or DEFAULT_BIND_HOST).strip() or DEFAULT_BIND_HOST
    port = int(preferred_port or DEFAULT_NETWORK_PORT)

    class Handler(http.server.BaseHTTPRequestHandler):
        def _send_json(self, payload: Any, status: int = 200) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _read_json_body(self) -> Any:
            try:
                raw_len = int(self.headers.get("Content-Length", "0") or "0")
            except Exception:
                raw_len = 0
            body = self.rfile.read(raw_len) if raw_len > 0 else b""
            if not body:
                return None
            try:
                return json.loads(body.decode("utf-8"))
            except Exception:
                return None

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0].rstrip("/")
            if path == "/api/network/ping":
                self._send_json({"ok": True, "ts": time.time()}, status=200)
                return
            if path == "/api/network/tracker-meta":
                with _WRITE_LOCK:
                    try:
                        mtime = float(os.path.getmtime(tracker_data_path))
                    except Exception:
                        mtime = 0.0
                self._send_json({"ok": True, "mtime": mtime}, status=200)
                return
            if path == "/api/network/tracker-data":
                with _WRITE_LOCK:
                    data = _read_json(tracker_data_path, {"schema_version": 1, "logs": []})
                if isinstance(data, list):
                    data = {"schema_version": 1, "logs": data}
                self._send_json(data, status=200)
                return
            if path == "/api/network/library-data":
                with _WRITE_LOCK:
                    data = _read_json(library_data_path, [])
                self._send_json(data if isinstance(data, list) else [], status=200)
                return
            self._send_json({"ok": False, "error": "not_found"}, status=404)

        def do_PUT(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0].rstrip("/")
            body = self._read_json_body()
            if path == "/api/network/tracker-data":
                if not isinstance(body, dict):
                    self._send_json({"ok": False, "error": "invalid_tracker_payload"}, status=400)
                    return
                with _WRITE_LOCK:
                    _atomic_write_json(tracker_data_path, body)
                self._send_json({"ok": True}, status=200)
                return
            if path == "/api/network/library-data":
                if not isinstance(body, list):
                    self._send_json({"ok": False, "error": "invalid_library_payload"}, status=400)
                    return
                with _WRITE_LOCK:
                    _atomic_write_json(library_data_path, body)
                self._send_json({"ok": True}, status=200)
                return
            self._send_json({"ok": False, "error": "not_found"}, status=404)

        def log_message(self, fmt: str, *args: object) -> None:
            try:
                log("[network] " + (fmt % args))
            except Exception:
                pass

    httpd: Optional[http.server.ThreadingHTTPServer] = None
    chosen_port: Optional[int] = None
    for _ in range(20):
        try:
            httpd = http.server.ThreadingHTTPServer((bind, port), Handler)
            httpd.allow_reuse_address = True
            chosen_port = port
            break
        except OSError as exc:
            log(f"[network] port {port} unavailable on {bind}: {exc}")
            port += 1
    if not httpd or not chosen_port:
        log("[network] failed to start data server")
        return None, None, None

    thread = threading.Thread(target=httpd.serve_forever, daemon=True, name="flowertrack-network-server")
    thread.start()
    log(f"[network] data server running at http://{bind}:{chosen_port}")
    return httpd, thread, chosen_port


def stop_network_data_server(
    httpd: Optional[http.server.ThreadingHTTPServer],
    thread: Optional[threading.Thread],
    log: Callable[[str], None],
) -> None:
    if not httpd:
        return
    try:
        httpd.shutdown()
        httpd.server_close()
    except Exception:
        pass
    log("[network] data server stopped")


def _request_json(
    method: str,
    host: str,
    port: int,
    path: str,
    payload: Any = None,
    timeout: float = 4.0,
) -> Any:
    base = f"http://{host}:{int(port)}{path}"
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(base, data=body, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def network_ping(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        payload = _request_json("GET", host, port, "/api/network/ping", timeout=timeout)
        return bool(isinstance(payload, dict) and payload.get("ok"))
    except Exception:
        return False


def fetch_tracker_data(host: str, port: int, timeout: float = 4.0) -> dict | None:
    try:
        payload = _request_json("GET", host, port, "/api/network/tracker-data", timeout=timeout)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def fetch_tracker_meta(host: str, port: int, timeout: float = 2.0) -> dict | None:
    try:
        payload = _request_json("GET", host, port, "/api/network/tracker-meta", timeout=timeout)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def push_tracker_data(host: str, port: int, data: dict, timeout: float = 4.0) -> bool:
    try:
        payload = _request_json("PUT", host, port, "/api/network/tracker-data", payload=data, timeout=timeout)
        return bool(isinstance(payload, dict) and payload.get("ok"))
    except Exception:
        return False


def fetch_library_data(host: str, port: int, timeout: float = 4.0) -> list[dict] | None:
    try:
        payload = _request_json("GET", host, port, "/api/network/library-data", timeout=timeout)
        if isinstance(payload, list):
            return payload
    except Exception:
        return None
    return None


def push_library_data(host: str, port: int, data: list[dict], timeout: float = 4.0) -> bool:
    try:
        payload = _request_json("PUT", host, port, "/api/network/library-data", payload=data, timeout=timeout)
        return bool(isinstance(payload, dict) and payload.get("ok"))
    except Exception:
        return False
