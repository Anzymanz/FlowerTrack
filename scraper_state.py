from __future__ import annotations

import ctypes
import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Tuple


def _log_state_error(message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {message}"
    try:
        print(line)
    except Exception:
        pass
    try:
        appdata = Path(os.getenv("APPDATA", os.path.expanduser("~")))
        path = appdata / "FlowerTrack" / "logs" / "scraper_state_errors.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def _atomic_write_json(path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    if path.exists():
        try:
            shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        except Exception as exc:
            _log_state_error(f"backup failed for {path}: {exc}")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)


def _read_text_with_backup(path) -> str | None:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception as exc:
        _log_state_error(f"read failed for {path}: {exc}")
    backup = path.with_suffix(path.suffix + ".bak")
    if backup.exists():
        try:
            text = backup.read_text(encoding="utf-8")
            _log_state_error(f"restored from backup for {path}")
            return text
        except Exception as exc:
            _log_state_error(f"backup read failed for {backup}: {exc}")
    return None


def _read_json_with_backup(path) -> dict | None:
    raw = _read_text_with_backup(path)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception as exc:
        _log_state_error(f"json decode failed for {path}: {exc}")
    backup = path.with_suffix(path.suffix + ".bak")
    if backup.exists():
        try:
            data = json.loads(backup.read_text(encoding="utf-8"))
            _log_state_error(f"restored json from backup for {path}")
            return data
        except Exception as exc:
            _log_state_error(f"backup json decode failed for {backup}: {exc}")
    return None


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
        data = _read_json_with_backup(path)
        if isinstance(data, dict):
            return data
    except Exception as exc:
        _log_state_error(f"read_scraper_state failed: {exc}")
    return {}

def update_scraper_state(path, **updates) -> None:
    try:
        payload = read_scraper_state(path)
        for key, value in updates.items():
            if value is None:
                payload.pop(key, None)
            else:
                payload[key] = value
        _atomic_write_json(path, payload)
    except Exception as exc:
        _log_state_error(f"update_scraper_state failed: {exc}")

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
        _atomic_write_json(path, payload)
    except Exception as exc:
        _log_state_error(f"write_scraper_state failed: {exc}")


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
