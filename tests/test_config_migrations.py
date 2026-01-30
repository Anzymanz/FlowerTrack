import unittest
import json
import tempfile
from pathlib import Path

from config import DEFAULT_CAPTURE_CONFIG, load_unified_config


class TestConfigMigrations(unittest.TestCase):
    def test_defaults_applied_for_scraper_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text("{}", encoding="utf-8")
            data = load_unified_config(path, decrypt_scraper_keys=[], write_back=False)
            scraper = data.get("scraper", {})
            self.assertEqual(scraper.get("window_geometry"), DEFAULT_CAPTURE_CONFIG["window_geometry"])
            self.assertEqual(scraper.get("settings_geometry"), DEFAULT_CAPTURE_CONFIG["settings_geometry"])

    def test_unified_migration_preserves_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            raw = {
                "version": 1,
                "tracker": {
                    "dark_mode": False,
                    "target_daily_grams": 2.5,
                },
                "scraper": {
                    "url": "https://example.test",
                    "interval_seconds": 90,
                    "notify_windows": False,
                },
                "library": {
                    "dark_mode": False,
                    "column_widths": {"brand": 140},
                },
            }
            path.write_text(json.dumps(raw), encoding="utf-8")
            data = load_unified_config(path, decrypt_scraper_keys=[], write_back=False)
            tracker = data.get("tracker", {})
            scraper = data.get("scraper", {})
            library = data.get("library", {})
            self.assertEqual(tracker.get("target_daily_grams"), 2.5)
            self.assertFalse(tracker.get("dark_mode"))
            self.assertEqual(scraper.get("url"), "https://example.test")
            self.assertEqual(scraper.get("interval_seconds"), 90)
            self.assertFalse(scraper.get("notify_windows"))
            self.assertFalse(library.get("dark_mode"))
            self.assertEqual(library.get("column_widths", {}).get("brand"), 140)

    def test_legacy_files_are_renamed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unified = root / "flowertrack_config.json"
            unified.write_text("{}", encoding="utf-8")
            legacy_tracker = root / "tracker_config.json"
            legacy_scraper = root / "scraper_config.json"
            legacy_library = root / "library_config.json"
            legacy_tracker.write_text(json.dumps({"dark_mode": False}), encoding="utf-8")
            legacy_scraper.write_text(json.dumps({"url": "https://example.test"}), encoding="utf-8")
            legacy_library.write_text(json.dumps({"dark_mode": True}), encoding="utf-8")
            load_unified_config(unified, decrypt_scraper_keys=[], write_back=True)
            self.assertTrue(root.joinpath("tracker_config.json.migrated").exists())
            self.assertTrue(root.joinpath("scraper_config.json.migrated").exists())
            self.assertTrue(root.joinpath("library_config.json.migrated").exists())


if __name__ == "__main__":
    unittest.main()
