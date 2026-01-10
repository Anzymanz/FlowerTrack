import unittest

from inventory import Flower, add_stock_entry, log_dose_entry, is_cbd_dominant


class InventoryTests(unittest.TestCase):
    def test_add_stock_new(self):
        flowers = {}
        add_stock_entry(flowers, "A", 5.0, 20.0, 1.0)
        self.assertIn("A", flowers)
        self.assertAlmostEqual(flowers["A"].grams_remaining, 5.0)

    def test_add_stock_update(self):
        flowers = {"A": Flower(name="A", thc_pct=20.0, cbd_pct=1.0, grams_remaining=2.0)}
        add_stock_entry(flowers, "A", 3.0, 20.0, 1.0)
        self.assertAlmostEqual(flowers["A"].grams_remaining, 3.0)

    def test_log_dose_entry(self):
        flowers = {"A": Flower(name="A", thc_pct=20.0, cbd_pct=1.0, grams_remaining=2.0)}
        logs = []
        remaining, entry = log_dose_entry(flowers, logs, "A", 1.0, "Vaped", {"Vaped": 0.5})
        self.assertAlmostEqual(remaining, 1.0)
        self.assertIn("thc_mg", entry)
        self.assertTrue(is_cbd_dominant(flowers["A"]) is False)


if __name__ == "__main__":
    unittest.main()
