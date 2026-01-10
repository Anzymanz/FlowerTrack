from __future__ import annotations

import os
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Literal, Optional, TypedDict

from scheduler import IntervalScheduler

_Playwright = None

Status = Literal["idle", "running", "retrying", "faulted", "stopped"]

class CaptureStateMachine:
    _transitions = {
        "idle": {"running", "stopped"},
        "running": {"retrying", "faulted", "stopped"},
        "retrying": {"running", "faulted", "stopped"},
        "faulted": {"stopped"},
        "stopped": {"idle", "running"},
    }

    def __init__(self) -> None:
        self.status: Status = "idle"

    def can_transition(self, new_status: Status) -> bool:
        if new_status == self.status:
            return False
        return new_status in self._transitions.get(self.status, set())

    def transition(self, new_status: Status) -> bool:
        if not self.can_transition(new_status):
            return False
        self.status = new_status
        return True


@dataclass(frozen=True)
class RetryPolicy:
    retry_attempts: int
    retry_wait_seconds: float
    backoff_max: float

    @classmethod
    def from_config(cls, cfg: dict) -> "RetryPolicy":
        attempts = max(0, int(cfg.get("retry_attempts", 0)))
        wait = float(cfg.get("retry_wait_seconds", 0) or 0)
        if wait <= 0:
            wait = float(cfg.get("post_nav_wait_seconds", 0) or 0)
        backoff = float(cfg.get("retry_backoff_max", 4) or 4)
        if backoff < 1:
            backoff = 1.0
        return cls(attempts, max(0.0, wait), backoff)

    def attempt_wait(self, attempt: int) -> float:
        if self.retry_wait_seconds <= 0:
            return 0.0
        factor = min(max(1, attempt), self.backoff_max)
        return self.retry_wait_seconds * factor

    def interval_with_backoff(self, base_interval: float, failures: int) -> float:
        if failures <= 0:
            return base_interval
        factor = min(1 + failures, self.backoff_max)
        return base_interval * factor


class CaptureCallbacks(TypedDict, total=False):
    capture_log: Callable[[str], None]
    apply_text: Callable[[str], None]
    on_stop: Callable[[], None]
    on_status: Callable[[Status, Optional[str]], None]
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
        self.state = CaptureStateMachine()
        self.status: Status = self.state.status
        self.empty_failures: int = 0
        self.retry_policy = RetryPolicy.from_config(cfg)
        self.retry_attempts = self.retry_policy.retry_attempts
        self.scheduler = IntervalScheduler(self.callbacks["stop_event"], self.callbacks["responsive_wait"])

    def _set_status(self, status: Status, msg: Optional[str] = None):
        if msg:
            self.callbacks.get("capture_log", lambda m: None)(msg)
        changed = self.state.transition(status)
        if not changed and status != self.status:
            self.callbacks.get("capture_log", lambda m: None)(
                f"Ignored invalid state transition {self.status} -> {status}"
            )
        if changed:
            self.status = self.state.status
            cb = self.callbacks.get("on_status")
            if cb:
                try:
                    cb(self.status, msg)
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
                try:
                    page.set_default_navigation_timeout(nav_timeout)
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
                        retries_left = self.retry_policy.retry_attempts
                        wait_post = max(self.cfg.get("post_nav_wait_seconds", 0), 0)
                        if first_cycle:
                            if not safe_goto(self.cfg["url"], "First visit"):
                                self._set_status("retrying", "Navigation failed; retrying shortly.")
                                self.callbacks["responsive_wait"](10, label="Retry after navigation failure")
                                continue
                            # Try to log in with explicit waits for selectors
                            self.callbacks["capture_log"]("Attempting login...")
                            try:
                                user_sels = [
                                    self.cfg.get("username_selector") or "",
                                    'input[data-path="email"]',
                                    'input[placeholder="Email"]',
                                    'input[type="email"]',
                                    'input#email',
                                    'input[name="email"]',
                                ]
                                pass_sels = [
                                    self.cfg.get("password_selector") or "",
                                    'input[data-path="password"]',
                                    'input[placeholder="Password"]',
                                    'input[type="password"]',
                                    'input#password',
                                    'input[name="password"]',
                                ]
                                btn_sels = [
                                    self.cfg.get("login_button_selector") or "",
                                    'button[type="submit"]',
                                    'button:has-text("Sign in")',
                                    'button:has-text("Login")',
                                ]
                                user_union = ",".join([s for s in user_sels if s])
                                pass_union = ",".join([s for s in pass_sels if s])
                                btn_union = ",".join([s for s in btn_sels if s])

                                # Short wait for form to render
                                time.sleep(3)

                                if self.cfg.get("username") and user_union:
                                    try:
                                        loc = page.wait_for_selector(user_union, timeout=10000)
                                        loc.fill(self.cfg["username"])
                                        self.callbacks["capture_log"](f"Filled username via union selector.")
                                    except Exception:
                                        self.callbacks["capture_log"]("Username selector not found.")
                                if self.cfg.get("password") and pass_union:
                                    try:
                                        loc = page.wait_for_selector(pass_union, timeout=10000)
                                        loc.fill(self.cfg["password"])
                                        self.callbacks["capture_log"](f"Filled password via union selector.")
                                    except Exception:
                                        self.callbacks["capture_log"]("Password selector not found.")
                                clicked = False
                                if btn_union:
                                    try:
                                        page.wait_for_selector(btn_union, timeout=5000)
                                        page.click(btn_union)
                                        clicked = True
                                        self.callbacks["capture_log"](f"Clicked login via union selector.")
                                    except Exception:
                                        clicked = False
                                if not clicked:
                                    page.keyboard.press("Enter")
                            except PlaywrightTimeoutError:
                                self.callbacks["capture_log"]("Login selectors not found; will retry.")
                                self._set_status("retrying", "Login selectors not found.")
                                continue
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
                        def collect_once(refresh: bool) -> bool:
                            if refresh:
                                try:
                                    self.callbacks["capture_log"]("Refreshing page before capture.")
                                    page.reload(timeout=0, wait_until="domcontentloaded")
                                except PlaywrightTimeoutError:
                                    self.callbacks["capture_log"]("Refresh timed out; using current content.")
                                except Exception as exc:
                                    self.callbacks["capture_log"](f"Refresh error; using current content. ({exc})")
                            self.callbacks["capture_log"]("Page ready; collecting text.")
                            text = page.locator("body").inner_text()
                            if not text.strip():
                                return False
                            self.empty_failures = 0
                            self.callbacks["apply_text"](text)
                            return True

                        # First attempt: no refresh, assume page loaded during waits.
                        success = collect_once(refresh=False)
                        attempt_wait = self.retry_policy.retry_wait_seconds
                        attempt = 0
                        while not success and retries_left > 0 and not self.callbacks["stop_event"].is_set():
                            retries_left -= 1
                            attempt += 1
                            self.callbacks["capture_log"](
                                f"No content; retrying after {attempt_wait}s (attempt {attempt}/{self.retry_policy.retry_attempts})."
                            )
                            if self.callbacks["responsive_wait"](attempt_wait, label="Retrying capture"):
                                break
                            # Sequence: retry 1 re-check without refresh; retry 2 refresh; retry 3 re-check without refresh.
                            refresh_flag = attempt == 2
                            success = collect_once(refresh=refresh_flag)
                        if not success:
                            self.empty_failures += 1
                            self._set_status("retrying", "Empty page content; backing off before retry.")
                        first_cycle = False
                    except PlaywrightTimeoutError:
                        self._set_status("retrying", "Navigation timed out; will retry.")
                    except Exception as exc:
                        self._set_status("retrying", f"Capture error: {exc}")
                    # Overnight slow-down
                    interval = self.scheduler.next_interval(self.cfg["interval_seconds"], self.cfg)
                    if self.empty_failures:
                        interval = self.retry_policy.interval_with_backoff(interval, self.empty_failures)
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
