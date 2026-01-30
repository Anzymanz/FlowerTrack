import os
import unittest
import subprocess
import sys
import json
from app_core import APP_DIR, DATA_DIR


class TestSmoke(unittest.TestCase):
    def test_appdata_dirs_exist(self):
        self.assertTrue(os.path.isdir(APP_DIR))
        self.assertTrue(os.path.isdir(DATA_DIR))

    def test_diagnostics_cli_output(self):
        proc = subprocess.run(
            [sys.executable, "flowertracker.py", "--diagnostics"],
            cwd=".",
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        for key in ("app_dir", "config_file", "scraper_state_file", "last_parse_file", "config_loaded"):
            self.assertIn(key, data)


if __name__ == "__main__":
    unittest.main()
