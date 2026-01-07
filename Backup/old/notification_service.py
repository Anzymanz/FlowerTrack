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

    def send_windows(self, title: str, body: str, icon: Optional[Path], launch_url: Optional[str] = None) -> None:
        if not self.notify_windows():
            return
        _maybe_send_windows_notification(title, body, icon, launch_url=launch_url, ui_logger=self.log)

    def send_home_assistant(self, payload: dict) -> None:
        if not self.send_ha():
            return
        url = self.ha_webhook().strip()
        token = self.ha_token().strip()
        if not url:
            self.log("Home Assistant webhook URL is not set.")
            return
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            if token:
                req.add_header("Authorization", f"Bearer {token}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.log(f"Sent data to Home Assistant (status {resp.status}).")
        except Exception as exc:
            self.log(f"Home Assistant notification failed: {exc}")
