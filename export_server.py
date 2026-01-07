from __future__ import annotations

import functools
import http.server
import socket
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Tuple


def _port_ready(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def start_export_server(preferred_port: int, exports_dir: Path, log: Callable[[str], None]) -> Tuple[Optional[http.server.ThreadingHTTPServer], Optional[threading.Thread], Optional[int]]:
    """Start a lightweight HTTP server to serve exports; returns (httpd, thread, port) or (None, None, None) on failure."""
    exports_dir.mkdir(parents=True, exist_ok=True)

    if _port_ready("127.0.0.1", preferred_port):
        log(f"[server] already running on port {preferred_port}")
        return None, None, preferred_port

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
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
    log(f"[server] attempting to start on port {port} serving {exports_dir}")
    httpd = None
    for _ in range(10):
        try:
            httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
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
        if _port_ready("127.0.0.1", port, timeout=0.2):
            ready = True
            break
        time.sleep(0.1)
    if not ready:
        log(f"[server] started but not reachable on port {port}")
    else:
        log(f"[server] serving exports at http://127.0.0.1:{port}")
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
