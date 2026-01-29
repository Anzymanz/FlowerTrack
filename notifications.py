from __future__ import annotations

from datetime import datetime
import json
import urllib.request
from pathlib import Path
from typing import Callable, Optional

try:
    from win10toast import ToastNotifier as Win10ToastNotifier  # type: ignore
except Exception:
    Win10ToastNotifier = None


def _log_debug(msg: str) -> None:
    """Lightweight stdout logger with timestamp."""
    try:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{stamp}] {msg}")
    except Exception:
        pass


def _maybe_send_windows_notification(
    title: str,
    body: str,
    icon: Optional[Path] = None,
    launch_url: Optional[str] = None,
    ui_logger: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Send a Windows toast using win10toast.
    launch_url is accepted for API compatibility but ignored (win10toast limitation).
    """
    icon_path = str(icon.resolve()) if icon and icon.exists() else None
    if Win10ToastNotifier is None:
        _log_debug("[toast] win10toast not installed.")
        if ui_logger:
            try:
                ui_logger("[toast] win10toast not installed.")
            except Exception:
                pass
        return
    try:
        notifier = Win10ToastNotifier()
        # Use threaded=True to keep Tk event loop responsive; avoid callbacks to reduce WNDPROC issues.
        notifier.show_toast(title, body, icon_path=icon_path, duration=8, threaded=True)
        _log_debug(f"[toast] sent via win10toast: {title} | {body} (icon={icon_path})")
        if ui_logger:
            try:
                ui_logger(f"[toast] sent via win10toast: {title}")
            except Exception:
                pass
    except Exception as exc:
        _log_debug(f"[toast] win10toast failed: {exc}")
        if ui_logger:
            try:
                ui_logger(f"[toast] win10toast failed: {exc}")
            except Exception:
                pass





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


    @staticmethod
    def _join(parts: list[str], max_len: int = 240) -> str:
        txt = "; ".join(parts)
        return txt if len(txt) <= max_len else (txt[: max_len - 3] + "...")

    def format_windows_body(self, payload: dict, summary: str, detail: str = "full") -> str:
        body_parts: list[str] = []
        if detail.lower() == "summary":
            return summary
        new_items = payload.get("new_item_summaries") or []
        removed_items = payload.get("removed_item_summaries") or []
        price_changes = payload.get("price_change_summaries") or []
        stock_changes = payload.get("stock_change_summaries") or []
        restock_changes = payload.get("restock_change_summaries") or []
        if new_items:
            body_parts.append("New: " + self._join(list(new_items)))
        if removed_items:
            body_parts.append("Removed: " + self._join(list(removed_items)))
        if price_changes:
            body_parts.append("Price: " + self._join(list(price_changes)))
        if stock_changes:
            body_parts.append("Stock: " + self._join(list(stock_changes)))
        if restock_changes:
            body_parts.append("Restock: " + self._join(list(restock_changes)))
        return " | ".join(body_parts) or summary

    def format_test_body(self, status: int | None) -> str:
        status_text = status if status is not None else "error"
        return (
            f"HA test status: {status_text} | "
            "New: Alpha Kush, Beta OG | Removed: None | "
            "Price: Gamma Glue GBP 2.50; Delta Dream GBP 1.00 | "
            "Stock: Zeta Zen: 10 -> 8"
        )

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
