from __future__ import annotations

import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Literal, Optional, TypedDict

from scheduler import IntervalScheduler

_Playwright = None

Status = Literal["idle", "running", "retrying", "faulted", "stopped"]


class CaptureCallbacks(TypedDict, total=False):
    capture_log: Callable[[str], None]
    apply_text: Callable[[str], None]
    on_stop: Callable[[], None]
    on_status: Callable[[Status], None]
    responsive_wait: Callable[[float, str], bool]
    stop_event: threading.Event
    on_error: Optional[Callable[[str], None]]
    on_done: Optional[Callable[[], None]]
    update_tray: Optional[Callable[[str], None]]


class CaptureWorker:
    """Encapsulated Playwright worker with simple state management."""

    def __init__(
        self,
        cfg: dict,
        callbacks: CaptureCallbacks,
        app_dir: Optional[Path],
        install_fn: Optional[Callable[[], bool]],
    ):
        self.cfg: dict = cfg
        self.callbacks: CaptureCallbacks = callbacks
        self.app_dir = app_dir
        self.install_fn = install_fn
        self.thread: Optional[threading.Thread] = None
        self.status: Status = "idle"
        self.scheduler = IntervalScheduler(self.callbacks["stop_event"], self.callbacks["responsive_wait"])

    def _set_status(self, status: Status, msg: Optional[str] = None):
        self.status = status
        if msg:
            self.callbacks.get("capture_log", lambda m: None)(msg)
        cb = self.callbacks.get("on_status")
        if cb:
            try:
                cb(status)
            except Exception:
                pass

    def start(self) -> threading.Thread:
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return self.thread

    def _run(self):
        sync_playwright, PlaywrightTimeoutError = _Playwright
        try:
            self._set_status("running", "Auto-capture started.")
            with sync_playwright() as p:
                browser = None
                attempted_install = False
                while browser is None:
                    try:
                        browser = p.chromium.launch(headless=self.cfg.get("headless", True))
                    except Exception as exc:
                        if self.install_fn and not attempted_install:
                            attempted_install = True
                            self.callbacks["capture_log"]("Playwright browser missing; attempting download...")
                            if self.install_fn():
                                continue
                        self._set_status("faulted", f"Browser launch failed: {exc}")
                        return
                page = browser.new_page()
                nav_timeout = self.cfg.get("timeout_ms") or self.cfg.get("timeout") or 45000
                try:
                    page.set_default_timeout(nav_timeout)
                except Exception:
                    pass

                def safe_goto(url: str, label: str) -> bool:
                    """Navigate without enforcing a timeout to avoid getting stuck on long-running page scripts."""
                    try:
                        page.goto(url, timeout=0, wait_until="domcontentloaded")
                    except PlaywrightTimeoutError:
                        self.callbacks["capture_log"](f"{label}: navigation timed out; continuing.")
                    except Exception as exc:
                        self.callbacks["capture_log"](f"{label}: navigation error; continuing. ({exc})")
                    return True

                first_cycle = True
                while not self.callbacks["stop_event"].is_set():
                    self._set_status("running", f"Navigating to {self.cfg['url']}")
                    try:
                        wait_post = max(self.cfg.get("post_nav_wait_seconds", 0), 0)
                        if first_cycle:
                            if not safe_goto(self.cfg["url"], "First visit"):
                                self._set_status("retrying", "Navigation failed; retrying shortly.")
                                self.callbacks["responsive_wait"](10, label="Retry after navigation failure")
                                continue
                            if self.cfg.get("username_selector") and self.cfg.get("username"):
                                page.fill(self.cfg["username_selector"], self.cfg["username"])
                            if self.cfg.get("password_selector") and self.cfg.get("password"):
                                page.fill(self.cfg["password_selector"], self.cfg["password"])
                            if self.cfg.get("login_button_selector"):
                                page.click(self.cfg["login_button_selector"])
                            wait_login = self.cfg.get("login_wait_seconds", 0)
                            if wait_login:
                                self.callbacks["capture_log"](f"Waiting {wait_login}s after login")
                                if self.callbacks["responsive_wait"](wait_login, label="Waiting after login"):
                                    break
                            if not safe_goto(self.cfg["url"], "Revisit"):
                                self._set_status("retrying", "Navigation failed after login; retrying shortly.")
                                self.callbacks["responsive_wait"](10, label="Retry after navigation failure")
                                continue
                        else:
                            if not safe_goto(self.cfg["url"], "Refresh"):
                                self._set_status("retrying", "Navigation failed; retrying shortly.")
                                self.callbacks["responsive_wait"](10, label="Retry after navigation failure")
                                continue
                        if wait_post:
                            self.callbacks["capture_log"](f"Waiting {wait_post}s after navigation")
                            if self.callbacks["responsive_wait"](wait_post, label="Waiting after navigation"):
                                break
                        self.callbacks["capture_log"]("Page ready; collecting text.")
                        text = page.locator("body").inner_text()
                        self.callbacks["apply_text"](text)
                        first_cycle = False
                    except PlaywrightTimeoutError:
                        self._set_status("retrying", "Navigation timed out; will retry.")
                    except Exception as exc:
                        self._set_status("retrying", f"Capture error: {exc}")
                    # Overnight slow-down
                    interval = self.scheduler.next_interval(self.cfg["interval_seconds"])
                    if self.scheduler.wait(interval, label="Waiting for next capture"):
                        break
                browser.close()
                self._set_status("stopped")
        except Exception as exc:
            self._set_status("faulted", f"Auto-capture error: {exc}")
        finally:
            self.callbacks["stop_event"].set()
            self.callbacks["on_stop"]()


def ensure_playwright_installed(app_dir: Path, log: Callable[[str], None]) -> Optional[tuple]:
    """Ensure playwright is importable and browsers are installed; returns (sync_playwright, TimeoutError) or None."""
    global _Playwright
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError  # type: ignore
    except Exception as exc:
        log(f"Playwright not installed: {exc}")
        return None
    _Playwright = (sync_playwright, PlaywrightTimeoutError)
    return _Playwright


def ensure_browser_available(app_dir: Path, log: Callable[[str], None], install_cb: Optional[Callable[[], bool]] = None) -> Optional[tuple]:
    """
    Ensure Playwright and browser are available.
    Returns (sync_playwright, TimeoutError) or None on failure after attempts.
    """
    req = ensure_playwright_installed(app_dir, log)
    if req:
        return req
    if install_cb:
        log("Playwright not installed; attempting browser install...")
        ok = install_cb()
        if ok:
            return ensure_playwright_installed(app_dir, log)
    return None


def install_playwright_browsers(app_dir: Path, log: Callable[[str], None]) -> bool:
    """Attempt to download Playwright Chromium browsers."""
    try:
        log("Downloading Playwright browser (this may take a minute)...")
        import playwright.__main__ as pw_main  # type: ignore

        env_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", str(app_dir / "pw-browsers"))
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = env_path
        prev_argv = list(sys.argv)
        sys.argv = ["playwright", "install", "chromium"]
        try:
            pw_main.main()
        finally:
            sys.argv = prev_argv
        log(f"Playwright browser installed to {env_path}.")
        return True
    except Exception as exc:
        log(f"Playwright install failed: {exc}")
        return False


def start_capture_worker(
    cfg: dict,
    callbacks: CaptureCallbacks,
    app_dir: Optional[Path] = None,
    install_fn: Optional[Callable[[], bool]] = None,
) -> threading.Thread:
    """
    Start the capture worker thread.
    cfg keys: url, interval_seconds, login_wait_seconds, post_nav_wait_seconds, username, password, selectors, headless, minimize_to_tray, close_to_tray
    callbacks keys: log, capture_log, apply_text, update_tray, on_stop, on_error, on_done
    """
    worker = CaptureWorker(cfg, callbacks, app_dir, install_fn)
    return worker.start()
