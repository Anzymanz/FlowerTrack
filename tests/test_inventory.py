import unittest
import tempfile
from pathlib import Path

from inventory import Flower, add_stock_entry, log_dose_entry, is_cbd_dominant, _normalize_log_entry, save_tracker_data, load_tracker_data


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

    def test_normalize_log_entry_backfills(self):
        raw = {"time": "2026-01-01 12:34", "grams": 0.2}
        normalized = _normalize_log_entry(raw)
        self.assertEqual(normalized.get("grams_used"), 0.2)
        self.assertEqual(normalized.get("time_display"), "12:34")
        self.assertEqual(normalized.get("date"), "2026-01-01")
        self.assertIn("thc_mg", normalized)
        self.assertIn("cbd_mg", normalized)

    def test_add_stock_mismatch_raises(self):
        flowers = {"A": Flower(name="A", thc_pct=20.0, cbd_pct=1.0, grams_remaining=2.0)}
        with self.assertRaises(ValueError):
            add_stock_entry(flowers, "A", 3.0, 19.0, 1.0)

    def test_log_dose_insufficient_raises(self):
        flowers = {"A": Flower(name="A", thc_pct=20.0, cbd_pct=1.0, grams_remaining=0.1)}
        logs = []
        with self.assertRaises(ValueError):
            log_dose_entry(flowers, logs, "A", 0.5, "Vaped", {"Vaped": 1.0})

    def test_log_dose_entry(self):
        flowers = {"A": Flower(name="A", thc_pct=20.0, cbd_pct=1.0, grams_remaining=2.0)}
        logs = []
        remaining, entry = log_dose_entry(flowers, logs, "A", 1.0, "Vaped", {"Vaped": 0.5})
        self.assertAlmostEqual(remaining, 1.0)
        self.assertIn("thc_mg", entry)
        self.assertTrue(is_cbd_dominant(flowers["A"]) is False)

    def test_tracker_backup_retention(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "tracker_data.json"
            for idx in range(7):
                save_tracker_data({"logs": [idx]}, path=data_path)
            backup_dir = data_path.parent / "backups"
            backups = list(backup_dir.glob("tracker_data-*.json"))
            self.assertLessEqual(len(backups), 5)

    def test_load_missing_tracker_data_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "tracker_data.json"
            save_tracker_data({"logs": []}, path=data_path)
            # delete to simulate missing file
            data_path.unlink()
            loaded = load_tracker_data(path=data_path)
            self.assertEqual(loaded.get("logs"), [])
            self.assertEqual(loaded.get("schema_version"), 1)


if __name__ == "__main__":
    unittest.main()
