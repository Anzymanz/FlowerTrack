import unittest
from types import SimpleNamespace

import ui_scraper
from parser import make_identity_key


class DummyVar:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value


class DummyNotifyService:
    def __init__(self):
        self.payload = None

    def send_windows(self, title, body, icon, launch_url=None):
        return True

    def send_home_assistant(self, payload):
        self.payload = payload
        return True, 200, "ok"

    def format_windows_body(self, payload, summary):
        return summary


class ChangeDetectionTests(unittest.TestCase):
    def setUp(self):
        ui_scraper.append_change_log = lambda *args, **kwargs: None

    def _make_item(self, **overrides):
        base = {
            "product_id": "ABC123",
            "producer": "Prod",
            "brand": "Brand",
            "strain": "Strain",
            "grams": 10.0,
            "ml": None,
            "price": 8.5,
            "product_type": "flower",
            "strain_type": "Hybrid",
            "is_smalls": False,
            "thc": 20.0,
            "thc_unit": "%",
            "cbd": 1.0,
            "cbd_unit": "%",
            "stock": "IN STOCK",
        }
        base.update(overrides)
        return base

    def _make_app(self, items, prev_items):
        prev_keys = {make_identity_key(it) for it in prev_items}
        return SimpleNamespace(
            cap_ha_webhook=DummyVar("http://example.test"),
            cap_ha_token=DummyVar(""),
            notify_windows=DummyVar(False),
            notify_service=DummyNotifyService(),
            data=items,
            prev_items=prev_items,
            prev_keys=prev_keys,
            _capture_log=lambda msg: None,
            _log_console=lambda msg: None,
            _update_last_change=lambda summary: None,
            _generate_change_export=lambda items: None,
            _get_export_items=lambda: [],
        )

    def test_price_and_stock_change(self):
        prev = [self._make_item(price=8.5, stock="IN STOCK")]
        cur = [self._make_item(price=9.0, stock="LOW STOCK")]
        app = self._make_app(cur, prev)

        ui_scraper.App.send_home_assistant(app, log_only=False)
        payload = app.notify_service.payload
        self.assertIsNotNone(payload)
        self.assertEqual(payload["new_count"], 0)
        self.assertEqual(payload["removed_count"], 0)
        self.assertEqual(len(payload["price_changes"]), 1)
        self.assertEqual(len(payload["stock_changes"]), 1)
        self.assertEqual(payload["price_changes"][0]["price_before"], 8.5)
        self.assertEqual(payload["price_changes"][0]["price_after"], 9.0)
        self.assertEqual(payload["stock_changes"][0]["stock_before"], "IN STOCK")
        self.assertEqual(payload["stock_changes"][0]["stock_after"], "LOW STOCK")

    def test_new_and_removed_items(self):
        prev = [self._make_item(product_id="OLD1")]
        cur = [self._make_item(product_id="NEW1")]
        app = self._make_app(cur, prev)

        ui_scraper.App.send_home_assistant(app, log_only=False)
        payload = app.notify_service.payload
        self.assertEqual(payload["new_count"], 1)
        self.assertEqual(payload["removed_count"], 1)
        self.assertEqual(len(payload["new_items"]), 1)
        self.assertEqual(len(payload["removed_items"]), 1)

    def test_diff_override_keeps_stock_notifications(self):
        prev = [self._make_item(stock="IN STOCK")]
        cur = [self._make_item(stock="LOW STOCK")]
        diff = ui_scraper.compute_diffs(cur, prev)
        app = self._make_app([], [])

        ui_scraper.App.send_home_assistant(app, log_only=False, diff_override=diff, items_override=cur)
        payload = app.notify_service.payload
        self.assertIsNotNone(payload)
        self.assertEqual(len(payload["stock_changes"]), 1)
        self.assertEqual(payload["stock_changes"][0]["stock_before"], "IN STOCK")
        self.assertEqual(payload["stock_changes"][0]["stock_after"], "LOW STOCK")


if __name__ == "__main__":
    unittest.main()
