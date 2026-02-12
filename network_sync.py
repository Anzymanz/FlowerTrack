from __future__ import annotations

import functools
import hmac
import http.server
import ipaddress
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
    access_key: str = "",
    allow_public_clients: bool = False,
    rate_limit_requests_per_minute: int = 0,
    rate_limit_window_seconds: float = 60.0,
    audit_log_burst: int = 8,
    audit_log_window_seconds: float = 30.0,
) -> Tuple[Optional[http.server.ThreadingHTTPServer], Optional[threading.Thread], Optional[int]]:
    """Start host-mode JSON API server for shared tracker/library data."""
    bind = (bind_host or DEFAULT_BIND_HOST).strip() or DEFAULT_BIND_HOST
    port = int(preferred_port or DEFAULT_NETWORK_PORT)
    expected_key = str(access_key or "").strip()
    client_ttl_s = 20.0
    rate_limit = max(0, int(rate_limit_requests_per_minute or 0))
    try:
        rate_window_s = max(1.0, float(rate_limit_window_seconds or 60.0))
    except Exception:
        rate_window_s = 60.0
    try:
        audit_burst = max(1, int(audit_log_burst or 8))
    except Exception:
        audit_burst = 8
    try:
        audit_window_s = max(1.0, float(audit_log_window_seconds or 30.0))
    except Exception:
        audit_window_s = 30.0

    def _client_allowed(host: str) -> bool:
        try:
            addr = ipaddress.ip_address((host or "").strip())
        except Exception:
            return False
        if allow_public_clients:
            return True
        if addr.is_loopback or addr.is_private or addr.is_link_local:
            return True
        return False

    class Handler(http.server.BaseHTTPRequestHandler):
        def _audit_deny(self, reason: str, detail: str = "") -> None:
            # Keep denied-request logs bounded per reason+client to avoid log floods.
            try:
                client_ip = str(self.client_address[0] or "").strip()
            except Exception:
                client_ip = "unknown"
            key = f"{client_ip}|{reason}"
            now = time.monotonic()
            lock = getattr(self.server, "_ft_audit_lock", None)
            state = getattr(self.server, "_ft_audit_state", None)
            if lock is None or state is None:
                try:
                    log(f"[network] denied {reason} from {client_ip}{detail}")
                except Exception:
                    pass
                return
            with lock:
                bucket = state.get(key)
                if not isinstance(bucket, dict):
                    bucket = {"start": now, "count": 0, "suppressed": 0}
                start = float(bucket.get("start", now))
                count = int(bucket.get("count", 0))
                suppressed = int(bucket.get("suppressed", 0))
                if (now - start) > audit_window_s:
                    if suppressed > 0:
                        try:
                            log(
                                f"[network] denied {reason} from {client_ip}: suppressed {suppressed} similar events"
                            )
                        except Exception:
                            pass
                    bucket = {"start": now, "count": 0, "suppressed": 0}
                    count = 0
                if count < audit_burst:
                    try:
                        log(f"[network] denied {reason} from {client_ip}{detail}")
                    except Exception:
                        pass
                    bucket["count"] = count + 1
                else:
                    bucket["suppressed"] = int(bucket.get("suppressed", 0)) + 1
                state[key] = bucket

        def _check_rate_limit(self) -> bool:
            if rate_limit <= 0:
                return True
            client_ip = ""
            try:
                client_ip = str(self.client_address[0] or "").strip()
            except Exception:
                client_ip = ""
            if not client_ip:
                return True
            now = time.monotonic()
            lock = getattr(self.server, "_ft_rate_lock", None)
            buckets = getattr(self.server, "_ft_rate_buckets", None)
            if lock is None or buckets is None:
                return True
            with lock:
                hits = buckets.get(client_ip, [])
                cutoff = now - rate_window_s
                hits = [ts for ts in hits if float(ts) >= cutoff]
                if len(hits) >= rate_limit:
                    buckets[client_ip] = hits
                    retry_after = max(1, int((hits[0] + rate_window_s) - now)) if hits else int(rate_window_s)
                    self._send_json(
                        {"ok": False, "error": "rate_limited", "retry_after_seconds": retry_after},
                        status=429,
                    )
                    return False
                hits.append(now)
                buckets[client_ip] = hits
            return True

        def _touch_client(self) -> None:
            try:
                client_ip = str(self.client_address[0] or "").strip()
                now = time.monotonic()
                lock = getattr(self.server, "_ft_clients_lock", None)
                clients = getattr(self.server, "_ft_clients", None)
                if lock is None or clients is None:
                    return
                with lock:
                    # prune stale entries on each touch
                    stale = [ip for ip, ts in clients.items() if (now - float(ts)) > float(client_ttl_s)]
                    for ip in stale:
                        clients.pop(ip, None)
                    clients[client_ip] = now
            except Exception:
                pass

        def _send_forbidden(self, reason: str) -> None:
            self._send_json({"ok": False, "error": reason}, status=403)

        def _check_access(self) -> bool:
            client_ip = ""
            try:
                client_ip = str(self.client_address[0] or "").strip()
            except Exception:
                client_ip = ""
            if not _client_allowed(client_ip):
                self._audit_deny("client_not_allowed")
                self._send_forbidden("client_not_allowed")
                return False
            if not expected_key:
                # No key configured: only allow strict localhost access.
                if client_ip not in {"127.0.0.1", "::1"}:
                    self._audit_deny("missing_access_key")
                    self._send_forbidden("missing_access_key")
                    return False
                return True
            got_key = str(self.headers.get("X-FlowerTrack-Key", "") or "").strip()
            if not got_key or not hmac.compare_digest(got_key, expected_key):
                detail = f" (provided_key_len={len(got_key)})"
                self._audit_deny("invalid_access_key", detail)
                self._send_forbidden("invalid_access_key")
                return False
            self._touch_client()
            return True

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
            if not self._check_access():
                return
            if not self._check_rate_limit():
                return
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
            if not self._check_access():
                return
            if not self._check_rate_limit():
                return
            path = self.path.split("?", 1)[0].rstrip("/")
            body = self._read_json_body()
            if path == "/api/network/tracker-data":
                if not isinstance(body, dict):
                    self._audit_deny("invalid_tracker_payload", f" (type={type(body).__name__})")
                    self._send_json({"ok": False, "error": "invalid_tracker_payload"}, status=400)
                    return
                with _WRITE_LOCK:
                    _atomic_write_json(tracker_data_path, body)
                self._send_json({"ok": True}, status=200)
                return
            if path == "/api/network/library-data":
                if not isinstance(body, list):
                    self._audit_deny("invalid_library_payload", f" (type={type(body).__name__})")
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
    try:
        setattr(httpd, "_ft_clients", {})
        setattr(httpd, "_ft_clients_lock", threading.Lock())
        setattr(httpd, "_ft_client_ttl", float(client_ttl_s))
        setattr(httpd, "_ft_rate_buckets", {})
        setattr(httpd, "_ft_rate_lock", threading.Lock())
        setattr(httpd, "_ft_audit_state", {})
        setattr(httpd, "_ft_audit_lock", threading.Lock())
    except Exception:
        pass

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
    access_key: str = "",
) -> Any:
    base = f"http://{host}:{int(port)}{path}"
    body = None
    headers = {}
    key = str(access_key or "").strip()
    if key:
        headers["X-FlowerTrack-Key"] = key
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(base, data=body, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def network_ping(host: str, port: int, timeout: float = 2.0, access_key: str = "") -> bool:
    try:
        payload = _request_json("GET", host, port, "/api/network/ping", timeout=timeout, access_key=access_key)
        return bool(isinstance(payload, dict) and payload.get("ok"))
    except Exception:
        return False


def fetch_tracker_data(host: str, port: int, timeout: float = 4.0, access_key: str = "") -> dict | None:
    try:
        payload = _request_json(
            "GET",
            host,
            port,
            "/api/network/tracker-data",
            timeout=timeout,
            access_key=access_key,
        )
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def fetch_tracker_meta(host: str, port: int, timeout: float = 2.0, access_key: str = "") -> dict | None:
    try:
        payload = _request_json(
            "GET",
            host,
            port,
            "/api/network/tracker-meta",
            timeout=timeout,
            access_key=access_key,
        )
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def push_tracker_data(host: str, port: int, data: dict, timeout: float = 4.0, access_key: str = "") -> bool:
    try:
        payload = _request_json(
            "PUT",
            host,
            port,
            "/api/network/tracker-data",
            payload=data,
            timeout=timeout,
            access_key=access_key,
        )
        return bool(isinstance(payload, dict) and payload.get("ok"))
    except Exception:
        return False


def fetch_library_data(host: str, port: int, timeout: float = 4.0, access_key: str = "") -> list[dict] | None:
    try:
        payload = _request_json(
            "GET",
            host,
            port,
            "/api/network/library-data",
            timeout=timeout,
            access_key=access_key,
        )
        if isinstance(payload, list):
            return payload
    except Exception:
        return None
    return None


def push_library_data(host: str, port: int, data: list[dict], timeout: float = 4.0, access_key: str = "") -> bool:
    try:
        payload = _request_json(
            "PUT",
            host,
            port,
            "/api/network/library-data",
            payload=data,
            timeout=timeout,
            access_key=access_key,
        )
        return bool(isinstance(payload, dict) and payload.get("ok"))
    except Exception:
        return False
