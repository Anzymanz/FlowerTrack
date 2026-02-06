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
        self.assertIn("log_window_hidden_height", cfg)
        self.assertEqual(cfg["log_window_hidden_height"], config.DEFAULT_CAPTURE_CONFIG["log_window_hidden_height"])

    def test_validate_capture_non_dict(self):
        cfg = config._validate_capture_config(None)
        self.assertEqual(cfg["url"], config.DEFAULT_CAPTURE_CONFIG["url"])
        self.assertEqual(cfg["username_selector"], config.DEFAULT_CAPTURE_CONFIG["username_selector"])

    def test_load_unified_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            cfg = config.load_unified_config(path, decrypt_scraper_keys=[], write_back=False)
            self.assertIn("tracker", cfg)
            self.assertIn("scraper", cfg)
            self.assertIn("ui", cfg)

    def test_save_unified_encrypts_scraper_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            cfg = config._default_unified_config()
            cfg["scraper"]["username"] = "user@example.com"
            cfg["scraper"]["password"] = "secret-pass"
            cfg["scraper"]["ha_token"] = "ha-token"
            config.save_unified_config(path, cfg, encrypt_scraper_keys=None)
            raw = json.loads(path.read_text(encoding="utf-8"))
            scraper = raw.get("scraper", {})
            self.assertNotEqual(scraper.get("username"), "user@example.com")
            self.assertNotEqual(scraper.get("password"), "secret-pass")
            self.assertNotEqual(scraper.get("ha_token"), "ha-token")
            self.assertEqual(config.decrypt_secret(scraper.get("username")), "user@example.com")
            self.assertEqual(config.decrypt_secret(scraper.get("password")), "secret-pass")
            self.assertEqual(config.decrypt_secret(scraper.get("ha_token")), "ha-token")


if __name__ == "__main__":
    unittest.main()
