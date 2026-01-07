from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from notifications import _maybe_send_windows_notification


class NotificationService:
    """Handles building and sending notifications to Home Assistant and Windows."""

    def __init__(
        self,
        ha_webhook: Callable[[], str],
        ha_token: Callable[[], str],
        send_ha: Callable[[], bool],
        notify_windows: Callable[[], bool],
        logger: Callable[[str], None],
    ) -> None:
        self.ha_webhook: Callable[[], str] = ha_webhook
        self.ha_token: Callable[[], str] = ha_token
        self.send_ha: Callable[[], bool] = send_ha
        self.notify_windows: Callable[[], bool] = notify_windows
        self.log: Callable[[str], None] = logger

    def send_windows(self, title: str, body: str, icon: Optional[Path], launch_url: Optional[str] = None) -> bool:
        if not self.notify_windows():
            return False
        try:
            _maybe_send_windows_notification(title, body, icon, launch_url=launch_url, ui_logger=self.log)
            return True
        except Exception as exc:
            self.log(f"Windows notification failed: {exc}")
            return False

    def send_home_assistant(self, payload: dict) -> tuple[bool, int | None, str | None]:
        if not self.send_ha():
            return False, None, None
        url = self.ha_webhook().strip()
        token = self.ha_token().strip()
        if not url:
            self.log("Home Assistant webhook URL is not set.")
            return False, None, None
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            if token:
                req.add_header("Authorization", f"Bearer {token}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
                self.log(f"Sent data to Home Assistant (status {resp.status}).")
                return True, resp.status, body
        except Exception as exc:
            self.log(f"Home Assistant notification failed: {exc}")
            return False, None, None

    def send_home_assistant_test(self, payload: dict) -> tuple[bool, int | None, str | None]:
        """Send a test payload to HA with detailed status/body feedback."""
        ok, status, body = self.send_home_assistant(payload)
        if ok:
            self.log(f"[HA test] status={status}")
        else:
            self.log(f"[HA test] failed status={status} body={body}")
        return ok, status, body
