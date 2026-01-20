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


if __name__ == "__main__":
    unittest.main()
