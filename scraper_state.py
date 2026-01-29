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

def update_scraper_state(path, **updates) -> None:
    try:
        payload = read_scraper_state(path)
        for key, value in updates.items():
            if value is None:
                payload.pop(key, None)
            else:
                payload[key] = value
        path.write_text(json.dumps(payload), encoding="utf-8")
    except Exception:
        pass

def get_last_change(path) -> str | None:
    value = read_scraper_state(path).get("last_change")
    return str(value) if value else None

def get_last_scrape(path) -> str | None:
    value = read_scraper_state(path).get("last_scrape")
    return str(value) if value else None


def write_scraper_state(path, status: str | None = None, pid: int | None = None, ts: float | None = None, last_change: str | None = None, last_scrape: str | None = None) -> None:
    try:
        payload = read_scraper_state(path)
        if status is not None:
            payload["status"] = str(status or "").lower()
            payload["ts"] = float(ts or time.time())
        elif ts is not None:
            payload["ts"] = float(ts)
        if pid is not None:
            payload["pid"] = int(pid)
        if last_change is not None:
            payload["last_change"] = str(last_change)
        if last_scrape is not None:
            payload["last_scrape"] = str(last_scrape)
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
