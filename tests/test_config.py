import json
import tempfile
import unittest
from pathlib import Path

import config


class ConfigTests(unittest.TestCase):
    def test_validate_capture_defaults(self):
        cfg = config._validate_capture_config({})
        self.assertIn("quiet_hours_interval_seconds", cfg)
        self.assertEqual(cfg["quiet_hours_interval_seconds"], config.DEFAULT_CAPTURE_CONFIG["quiet_hours_interval_seconds"])

    def test_load_unified_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            cfg = config.load_unified_config(path, decrypt_scraper_keys=[], write_back=False)
            self.assertIn("tracker", cfg)
            self.assertIn("scraper", cfg)
            self.assertIn("ui", cfg)


if __name__ == "__main__":
    unittest.main()
