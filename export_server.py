from __future__ import annotations

import functools
import http.server
import json
import socket
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Tuple

from unread_changes import clear_unread_changes, unread_payload

_EXPORT_EVENT_LOCK = threading.Lock()
_EXPORT_EVENT_COND = threading.Condition(_EXPORT_EVENT_LOCK)
_EXPORT_EVENT_VERSION = 0
_EXPORT_EVENT_TS = ""


def notify_export_updated(stamp: str) -> None:
    global _EXPORT_EVENT_VERSION, _EXPORT_EVENT_TS
    with _EXPORT_EVENT_COND:
        _EXPORT_EVENT_VERSION += 1
        _EXPORT_EVENT_TS = stamp
        _EXPORT_EVENT_COND.notify_all()


def _port_ready(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def start_export_server(
    preferred_port: int,
    exports_dir: Path,
    log: Callable[[str], None],
    bind_host: str = "127.0.0.1",
    probe_host: str | None = None,
) -> Tuple[Optional[http.server.ThreadingHTTPServer], Optional[threading.Thread], Optional[int]]:
    """Start a lightweight HTTP server to serve exports; returns (httpd, thread, port) or (None, None, None) on failure."""
    exports_dir.mkdir(parents=True, exist_ok=True)

    bind = (bind_host or "127.0.0.1").strip() or "127.0.0.1"
    if probe_host:
        probe = probe_host
    elif bind in {"0.0.0.0", "::"}:
        probe = "127.0.0.1"
    else:
        probe = bind

    if _port_ready(probe, preferred_port):
        log(f"[server] already running on port {preferred_port}")
        return None, None, preferred_port

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def _latest_export_name(self) -> str | None:
            try:
                files = sorted(
                    exports_dir.glob("export-*.html"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if files:
                    return files[0].name
            except Exception:
                pass
            return None

        def _send_json(self, payload: dict, status: int = 200) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            try:
                path = self.path.split("?", 1)[0]
                if path.rstrip("/") == "/api/changes/ack":
                    had_changes = clear_unread_changes()
                    payload = unread_payload()
                    payload["acknowledged"] = True
                    payload["had_changes"] = bool(had_changes)
                    self._send_json(payload, status=200)
                    return
            except Exception as e:
                log(f"[server] post handler exception: {e}")
                try:
                    self._send_json({"ok": False, "error": str(e)}, status=500)
                except Exception:
                    pass
                return
            self.send_error(404, "Not found")

        def do_GET(self):
            try:
                path = self.path.split("?", 1)[0]
                if path.rstrip("/") == "/api/changes/unread":
                    self._send_json(unread_payload(), status=200)
                    return
                if path.rstrip("/") == "/events":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "keep-alive")
                    self.end_headers()
                    last_seen = -1
                    while True:
                        with _EXPORT_EVENT_COND:
                            _EXPORT_EVENT_COND.wait(timeout=60.0)
                            version = _EXPORT_EVENT_VERSION
                            stamp = _EXPORT_EVENT_TS
                        if version != last_seen:
                            last_seen = version
                            payload = stamp or ""
                            try:
                                self.wfile.write(f"event: export\ndata: {payload}\n\n".encode("utf-8"))
                                self.wfile.flush()
                            except Exception:
                                break
                        else:
                            try:
                                self.wfile.write(b": heartbeat\n\n")
                                self.wfile.flush()
                            except Exception:
                                break
                    return
                if path.rstrip("/") == "/flowerbrowser":
                    latest = self._latest_export_name()
                    if latest:
                        self.path = f"/{latest}"
                        return super().do_GET()
                    self.send_error(404, "No exports available yet.")
                    return
            except Exception as e:
                log(f"[server] handler exception: {e}")
            return super().do_GET()

        def log_message(self, fmt, *args):
            log("[server] " + fmt % args)

        def log_error(self, fmt, *args):
            log("[server] " + fmt % args)

        def handle(self):
            try:
                super().handle()
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
                log(f"[server] client disconnected early: {e}")
            except Exception as e:
                log(f"[server] handler exception: {e}")

        def copyfile(self, source, outputfile):
            try:
                return super().copyfile(source, outputfile)
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
                log(f"[server] copy aborted: {e}")
                return

    handler = functools.partial(QuietHandler, directory=str(exports_dir))
    port = preferred_port
    log(f"[server] attempting to start on {bind}:{port} serving {exports_dir}")
    httpd = None
    for _ in range(10):
        try:
            httpd = http.server.ThreadingHTTPServer((bind, port), handler)
            httpd.allow_reuse_address = True
            break
        except OSError as e:
            log(f"[server] port {port} unavailable ({e}), trying next")
            port += 1
    if not httpd:
        log("[server] failed to start export server after attempting 10 ports")
        return None, None, None

    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    # Wait briefly for socket to be ready
    ready = False
    for _ in range(10):
        if _port_ready(probe, port, timeout=0.2):
            ready = True
            break
        time.sleep(0.1)
    if not ready:
        log(f"[server] started but not reachable on port {port}")
    else:
        log(f"[server] serving exports at http://{probe}:{port}")
    return httpd, thread, port


def stop_export_server(httpd: Optional[http.server.ThreadingHTTPServer], thread: Optional[threading.Thread], log: Callable[[str], None]) -> None:
    """Stop the running export server if present."""
    if httpd:
        try:
            httpd.shutdown()
            httpd.server_close()
        except Exception:
            pass
        log("[server] shutdown complete")
