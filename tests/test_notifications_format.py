import unittest

from notifications import NotificationService


class DummyNotify:
    def __call__(self):
        return True


class NotificationFormatTests(unittest.TestCase):
    def setUp(self):
        self.log = lambda msg: None
        self.svc = NotificationService(lambda: "http://example", lambda: "", DummyNotify(), DummyNotify(), self.log)

    def test_format_windows_summary(self):
        payload = {
            "new_item_summaries": ["A", "B"],
            "removed_item_summaries": [],
        }
        body = self.svc.format_windows_body(payload, summary="Summary", detail="summary")
        self.assertEqual(body, "New items detected")

    def test_format_windows_full(self):
        payload = {
            "new_item_summaries": ["A"],
            "removed_item_summaries": ["B"],
            "price_change_summaries": ["C"],
            "stock_change_summaries": ["D"],
            "out_of_stock_change_summaries": ["E"],
            "restock_change_summaries": ["F"],
        }
        body = self.svc.format_windows_body(payload, summary="Summary")
        self.assertIn("New:", body)
        self.assertIn("Removed:", body)
        self.assertIn("Price:", body)
        self.assertIn("Stock:", body)
        self.assertIn("Out:", body)
        self.assertIn("Restock:", body)


if __name__ == "__main__":
    unittest.main()
