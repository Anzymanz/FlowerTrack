import unittest

from diff_engine import compute_diffs


class DiffEngineTests(unittest.TestCase):
    def _item(self, **overrides):
        base = {
            "product_id": "1",
            "producer": "Prod",
            "brand": "Brand",
            "strain": "Strain",
            "grams": 10.0,
            "ml": None,
            "price": 10.0,
            "product_type": "flower",
            "strain_type": "Hybrid",
            "is_smalls": False,
            "thc": 20.0,
            "thc_unit": "%",
            "cbd": 1.0,
            "cbd_unit": "%",
            "stock": "IN STOCK",
            "stock_status": "IN STOCK",
            "stock_remaining": 10,
        }
        base.update(overrides)
        return base

    def test_price_change_detected(self):
        prev = [self._item(price=10.0)]
        cur = [self._item(price=12.5)]
        diff = compute_diffs(cur, prev)
        self.assertEqual(len(diff["price_changes"]), 1)
        self.assertEqual(diff["price_up"], 1)
        self.assertEqual(diff["price_down"], 0)
        self.assertAlmostEqual(cur[0]["price_delta"], 2.5)

    def test_restock_sets_delta(self):
        prev = [self._item(stock="OUT OF STOCK", stock_status="OUT OF STOCK", stock_remaining=0)]
        cur = [self._item(stock="IN STOCK", stock_status="IN STOCK", stock_remaining=5)]
        diff = compute_diffs(cur, prev)
        self.assertTrue(cur[0].get("is_restock"))
        self.assertEqual(diff["stock_change_count"], 1)
        self.assertIsNotNone(cur[0].get("stock_delta"))
        self.assertGreater(cur[0]["stock_delta"], 0)

    def test_out_of_stock_sets_delta(self):
        prev = [self._item(stock="IN STOCK", stock_status="IN STOCK", stock_remaining=5)]
        cur = [self._item(stock="OUT OF STOCK", stock_status="OUT OF STOCK", stock_remaining=0)]
        diff = compute_diffs(cur, prev)
        self.assertEqual(diff["stock_change_count"], 1)
        self.assertLess(cur[0].get("stock_delta"), 0)


if __name__ == "__main__":
    unittest.main()
