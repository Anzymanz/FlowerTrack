import unittest
from pathlib import Path

from notifications import NotificationService


class NotificationTests(unittest.TestCase):
    def test_format_test_body(self):
        svc = NotificationService(lambda: "", lambda: "", lambda: False, lambda: False, lambda m: None)
        body = svc.format_test_body(200)
        self.assertIn("GBP", body)
        self.assertIn("->", body)

    def test_summary_body(self):
        svc = NotificationService(lambda: "", lambda: "", lambda: False, lambda: False, lambda m: None)
        payload = {"new_item_summaries": ["A"], "removed_item_summaries": []}
        body = svc.format_windows_body(payload, summary="summary", detail="summary")
        self.assertEqual(body, "New items detected")


if __name__ == "__main__":
    unittest.main()
