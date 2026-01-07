from __future__ import annotations

import json
import os
import time
import ctypes
from typing import Tuple


STATUS_RUNNING = {"running", "retrying"}
STATUS_WARN = {"faulted", "error"}
STATUS_STOP = {"stopped", "idle", "done"}


def _pid_running(pid: int | None) -> bool:
    if not pid:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False
    try:
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    except Exception:
        return False


def read_scraper_state(path) -> dict:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def write_scraper_state(path, status: str, pid: int | None = None, ts: float | None = None) -> None:
    try:
        payload = {
            "status": str(status or "").lower(),
            "ts": float(ts or time.time()),
            "pid": int(pid) if pid is not None else None,
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
    except Exception:
        pass


def resolve_scraper_status(child_procs, path) -> Tuple[bool, bool]:
    """Return (running, warn) based on shared state file."""
    state = read_scraper_state(path)
    status = str(state.get("status", "")).lower()
    pid = state.get("pid")
    pid_alive = _pid_running(pid)
    if status in STATUS_RUNNING:
        if pid is not None and not pid_alive:
            write_scraper_state(path, "stopped", pid=pid)
            return False, False
        return (pid_alive if pid is not None else True), False
    if status in STATUS_WARN:
        return False, True
    return False, False
