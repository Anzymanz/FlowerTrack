import unittest

from history_viewer import HistoryViewer


class HistoryViewerTests(unittest.TestCase):
    def _viewer(self):
        return HistoryViewer.__new__(HistoryViewer)

    def test_search_text_includes_brand_and_strain(self):
        hv = self._viewer()
        record = {
            "new_items": [
                {"brand": "Alpha", "strain": "Kush", "producer": "Prod", "product_id": "P1"},
            ]
        }
        text = hv._search_text_for(record)
        self.assertIn("alpha", text)
        self.assertIn("kush", text)
        self.assertIn("prod", text)
        self.assertIn("p1", text)

    def test_format_details_includes_sections(self):
        hv = self._viewer()
        record = {
            "timestamp": "2026-02-06T10:00:00+00:00",
            "new_items": [{"label": "New Thing"}],
            "price_changes": [{"label": "Pricey", "price_before": 1, "price_after": 2, "price_delta": 1}],
            "stock_changes": [{"label": "Stocky", "stock_before": "IN", "stock_after": "OUT"}],
            "removed_items": [],
            "out_of_stock_changes": [],
            "restock_changes": [],
        }
        text = hv._format_details(record)
        self.assertIn("Timestamp:", text)
        self.assertIn("New items", text)
        self.assertIn("Price changes", text)
        self.assertIn("Stock changes", text)


if __name__ == "__main__":
    unittest.main()
