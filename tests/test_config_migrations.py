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


if __name__ == "__main__":
    unittest.main()
