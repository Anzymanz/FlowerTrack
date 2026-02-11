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
                self.cap_dump_html_keep = _Var("bad")
                self.cap_dump_api = _Var(False)
                self.cap_dump_api_keep = _Var("bad")
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
                self.cap_auto_open_export = _Var(False)
                self.cap_auto_open_export_delay = _Var("0")
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
        self.assertEqual(
            cfg["dump_html_keep_files"],
            ui_scraper.DEFAULT_CAPTURE_CONFIG["dump_html_keep_files"],
        )
        self.assertEqual(
            cfg["dump_api_keep_files"],
            ui_scraper.DEFAULT_CAPTURE_CONFIG["dump_api_keep_files"],
        )
        self.assertTrue(any("Invalid interval_seconds" in msg for msg in logs))

    def test_stage_diff_first_run_seeds_baseline(self):
        class Dummy:
            def __init__(self):
                self.prev_items = []
                self.removed_data = []
                self.price_up_count = 0
                self.price_down_count = 0
                self._baseline_capture = False

        item = {
            "product_id": "A1",
            "producer": "Brand",
            "brand": "Brand",
            "strain": "Example",
            "grams": 10.0,
            "ml": None,
            "product_type": "flower",
            "strain_type": "Hybrid",
            "is_smalls": False,
            "thc": 20.0,
            "thc_unit": "%",
            "cbd": 1.0,
            "cbd_unit": "%",
            "price": 10.0,
            "stock": "IN STOCK",
        }
        Dummy._stage_diff = ui_scraper.App._stage_diff
        app = Dummy()
        diff = app._stage_diff([item])
        self.assertTrue(app._baseline_capture)
        self.assertEqual(diff["new_items"], [])
        self.assertEqual(diff["removed_items"], [])
        self.assertEqual(diff["price_changes"], [])
        self.assertEqual(diff["stock_changes"], [])
        self.assertEqual(diff["current_keys"], {ui_scraper.make_identity_key(item)})

    def test_stage_notify_baseline_message_and_post_process(self):
        class _Status:
            def __init__(self):
                self.text = ""

            def config(self, **kwargs):
                if "text" in kwargs:
                    self.text = str(kwargs["text"])

        class Dummy:
            def __init__(self):
                self._baseline_capture = True
                self.status = _Status()
                self._logs = []
                self.post_args = None
                self.data = [{"product_id": "A1"}]
                self.price_up_count = 0
                self.price_down_count = 0

            def _log_console(self, msg):
                self._logs.append(str(msg))

            def _post_process_actions(self, diff, items):
                self.post_args = (diff, items)

        Dummy._stage_notify = ui_scraper.App._stage_notify
        app = Dummy()
        diff = {
            "new_items": [],
            "removed_items": [],
            "price_changes": [],
            "stock_changes": [],
            "restock_changes": [],
            "out_of_stock_changes": [],
            "stock_change_count": 0,
        }
        app._stage_notify(diff, 42)
        self.assertIn("Baseline established (42 items).", app.status.text)
        self.assertTrue(any("Baseline established (42 items)." in msg for msg in app._logs))
        self.assertIsNotNone(app.post_args)


if __name__ == "__main__":
    unittest.main()
