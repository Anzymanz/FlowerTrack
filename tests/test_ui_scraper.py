import unittest

import ui_scraper


class _Var:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value


class _DummyNotifyService:
    def __init__(self, result=(True, 200, "OK")):
        self._result = result

    def send_home_assistant_test(self, payload):
        return self._result


class UiScraperTests(unittest.TestCase):
    def test_send_test_notification_windows_toggle(self):
        calls = []

        class Dummy:
            def __init__(self, notify_windows):
                self.notify_service = _DummyNotifyService()
                self.cap_ha_webhook = _Var("https://example.test/webhook")
                self.cap_ha_token = _Var("")
                self.notify_windows = _Var(notify_windows)
                self.cap_url = _Var("http://example.test")

            def _log_console(self, msg):
                pass

            def _quiet_hours_active(self):
                return False

        def _fake_toast(title, body, icon, launch_url=None, ui_logger=None):
            calls.append((title, body, launch_url))

        old_toast = ui_scraper._maybe_send_windows_notification
        old_messagebox = ui_scraper.messagebox
        try:
            ui_scraper._maybe_send_windows_notification = _fake_toast

            class _Box:
                @staticmethod
                def showerror(*args, **kwargs):
                    return None

                @staticmethod
                def showinfo(*args, **kwargs):
                    return None

            ui_scraper.messagebox = _Box

            Dummy.send_test_notification = ui_scraper.App.send_test_notification
            Dummy(notify_windows=False).send_test_notification()
            self.assertEqual(len(calls), 0)
            Dummy(notify_windows=True).send_test_notification()
            self.assertEqual(len(calls), 1)
        finally:
            ui_scraper._maybe_send_windows_notification = old_toast
            ui_scraper.messagebox = old_messagebox

    def test_collect_capture_cfg_validation(self):
        logs = []

        class Dummy:
            def __init__(self):
                self.cap_url = _Var("http://example.test")
                self.cap_interval = _Var("bad")
                self.cap_login_wait = _Var("")
                self.cap_post_wait = _Var("nope")
                self.cap_retry_attempts = _Var("x")
                self.cap_retry_wait = _Var("y")
                self.cap_retry_backoff = _Var("z")
                self.cap_dump_html = _Var(False)
                self.cap_dump_api = _Var(False)
                self.cap_dump_api_full = _Var(False)
                self.cap_show_log_window = _Var(True)
                self.cap_user = _Var("user")
                self.cap_pass = _Var("pass")
                self.cap_user_sel = _Var("")
                self.cap_pass_sel = _Var("")
                self.cap_btn_sel = _Var("")
                self.cap_org = _Var("")
                self.cap_org_sel = _Var("")
                self.cap_headless = _Var(True)
                self.cap_auto_notify_ha = _Var(False)
                self.cap_ha_webhook = _Var("")
                self.cap_ha_token = _Var("")
                self.notify_price_changes = _Var(True)
                self.notify_stock_changes = _Var(True)
                self.notify_out_of_stock = _Var(True)
                self.notify_restock = _Var(True)
                self.notify_new_items = _Var(True)
                self.notify_removed_items = _Var(True)
                self.notify_windows = _Var(True)
                self.cap_quiet_hours_enabled = _Var(False)
                self.cap_quiet_start = _Var("22:00")
                self.cap_quiet_end = _Var("07:00")
                self.cap_quiet_interval = _Var("bad")
                self.cap_include_inactive = _Var(False)
                self.cap_requestable_only = _Var(True)
                self.cap_in_stock_only = _Var(False)
                self.cap_notify_detail = _Var("full")
                self.minimize_to_tray = _Var(False)
                self.close_to_tray = _Var(False)
                self.scraper_log_hidden_height = 222
                self.settings_window = None
                self.scraper_settings_geometry = "560x960"

            def _log_console(self, msg):
                logs.append(msg)

            def geometry(self):
                return "100x100"

        Dummy._collect_capture_cfg = ui_scraper.App._collect_capture_cfg
        cfg = Dummy()._collect_capture_cfg()
        self.assertEqual(cfg["interval_seconds"], ui_scraper.DEFAULT_CAPTURE_CONFIG["interval_seconds"])
        self.assertEqual(cfg["retry_attempts"], ui_scraper.DEFAULT_CAPTURE_CONFIG["retry_attempts"])
        self.assertEqual(
            cfg["quiet_hours_interval_seconds"],
            ui_scraper.DEFAULT_CAPTURE_CONFIG["quiet_hours_interval_seconds"],
        )
        self.assertEqual(cfg["log_window_hidden_height"], 222)
        self.assertTrue(any("Invalid interval_seconds" in msg for msg in logs))


if __name__ == "__main__":
    unittest.main()
