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

    def test_tracker_persists_roa_and_mix_visibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            tracker_cfg = config.DEFAULT_TRACKER_CONFIG.copy()
            tracker_cfg["hide_roa_options"] = True
            tracker_cfg["hide_mixed_dose"] = True
            tracker_cfg["hide_mix_stock"] = True
            tracker_cfg["log_column_widths"] = {"time": 80, "flower": 240}
            tracker_cfg["show_stock_form"] = False
            config.save_tracker_config(path, tracker_cfg)
            reloaded = config.load_tracker_config(path)
            self.assertTrue(reloaded.get("hide_roa_options"))
            self.assertTrue(reloaded.get("hide_mixed_dose"))
            self.assertTrue(reloaded.get("hide_mix_stock"))
            self.assertEqual(reloaded.get("log_column_widths", {}).get("time"), 80)
            self.assertFalse(reloaded.get("show_stock_form", True))

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

    def test_load_unified_migrates_plaintext_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            raw = config._default_unified_config()
            raw["scraper"]["username"] = "plain-user"
            raw["scraper"]["password"] = "plain-pass"
            raw["scraper"]["ha_token"] = "plain-token"
            path.write_text(json.dumps(raw), encoding="utf-8")
            cfg = config.load_unified_config(
                path,
                decrypt_scraper_keys=["username", "password", "ha_token"],
                write_back=True,
            )
            self.assertEqual(cfg["scraper"]["username"], "plain-user")
            self.assertEqual(cfg["scraper"]["password"], "plain-pass")
            self.assertEqual(cfg["scraper"]["ha_token"], "plain-token")
            stored = json.loads(path.read_text(encoding="utf-8"))
            scraper = stored.get("scraper", {})
            self.assertNotEqual(scraper.get("username"), "plain-user")
            self.assertNotEqual(scraper.get("password"), "plain-pass")
            self.assertNotEqual(scraper.get("ha_token"), "plain-token")
            self.assertEqual(config.decrypt_secret(scraper.get("username")), "plain-user")
            self.assertEqual(config.decrypt_secret(scraper.get("password")), "plain-pass")
            self.assertEqual(config.decrypt_secret(scraper.get("ha_token")), "plain-token")


if __name__ == "__main__":
    unittest.main()
