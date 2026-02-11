import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import ui_tracker


class TrackerBackupTests(unittest.TestCase):
    def _dummy_tracker(self, app_dir: Path) -> SimpleNamespace:
        return SimpleNamespace(
            data_path=str(app_dir / "data" / "tracker_data.json"),
            library_data_path=str(app_dir / "data" / "library_data.json"),
        )

    def test_write_backup_zip_includes_core_data_and_excludes_auth_tokens(self):
        with tempfile.TemporaryDirectory() as td:
            app_dir = Path(td) / "FlowerTrack"
            data_dir = app_dir / "data"
            logs_dir = app_dir / "logs"
            dumps_dir = app_dir / "dumps"
            exports_dir = app_dir / "Exports"
            config_path = app_dir / "flowertrack_config.json"
            backups_dir = app_dir / "backups"

            for p in (data_dir, logs_dir, dumps_dir, exports_dir, backups_dir):
                p.mkdir(parents=True, exist_ok=True)

            (data_dir / "tracker_data.json").write_text('{"flowers":[]}', encoding="utf-8")
            (data_dir / "last_parse.json").write_text("[]", encoding="utf-8")
            (data_dir / "api_auth.json").write_text('{"token":"secret"}', encoding="utf-8")
            (logs_dir / "changes.ndjson").write_text('{"x":1}\n', encoding="utf-8")
            (dumps_dir / "api_dump_1.json").write_text("{}", encoding="utf-8")
            (exports_dir / "export-latest.html").write_text("<html></html>", encoding="utf-8")
            (backups_dir / "should_not_include.txt").write_text("skip", encoding="utf-8")

            config_path.write_text(
                json.dumps(
                    {
                        "tracker": {"dark_mode": True},
                        "scraper": {"ha_token": "abc123", "username": "u"},
                    }
                ),
                encoding="utf-8",
            )

            dummy = self._dummy_tracker(app_dir)
            zip_path = Path(td) / "backup.zip"

            with mock.patch.object(ui_tracker, "APP_DIR", str(app_dir)), mock.patch.object(
                ui_tracker, "TRACKER_CONFIG_FILE", str(config_path)
            ), mock.patch.object(ui_tracker, "EXPORTS_DIR_DEFAULT", str(exports_dir)):
                count = ui_tracker.CannabisTracker._write_backup_zip(dummy, zip_path)
                self.assertGreater(count, 0)

            with zipfile.ZipFile(zip_path, "r") as zf:
                names = set(zf.namelist())
                self.assertIn("data/tracker_data.json", names)
                self.assertIn("data/last_parse.json", names)
                self.assertNotIn("data/api_auth.json", names)
                self.assertIn("logs/changes.ndjson", names)
                self.assertIn("dumps/api_dump_1.json", names)
                self.assertIn("Exports/export-latest.html", names)
                self.assertNotIn("backups/should_not_include.txt", names)
                self.assertIn("flowertrack_config.json", names)
                cfg = json.loads(zf.read("flowertrack_config.json").decode("utf-8"))
                self.assertEqual(cfg.get("scraper", {}).get("ha_token"), "")

    def test_restore_backup_zip_restores_core_dirs_and_drops_api_auth(self):
        with tempfile.TemporaryDirectory() as td:
            app_dir = Path(td) / "FlowerTrack"
            app_dir.mkdir(parents=True, exist_ok=True)
            data_dir = app_dir / "data"
            logs_dir = app_dir / "logs"
            dumps_dir = app_dir / "dumps"
            exports_dir = app_dir / "Exports"
            config_path = app_dir / "flowertrack_config.json"
            for p in (data_dir, logs_dir, dumps_dir, exports_dir):
                p.mkdir(parents=True, exist_ok=True)
                (p / "old.txt").write_text("old", encoding="utf-8")

            src = Path(td) / "src"
            (src / "data").mkdir(parents=True, exist_ok=True)
            (src / "logs").mkdir(parents=True, exist_ok=True)
            (src / "dumps").mkdir(parents=True, exist_ok=True)
            (src / "Exports").mkdir(parents=True, exist_ok=True)
            (src / "data" / "tracker_data.json").write_text('{"flowers":[1]}', encoding="utf-8")
            (src / "data" / "api_auth.json").write_text('{"token":"secret"}', encoding="utf-8")
            (src / "logs" / "changes.ndjson").write_text('{"c":1}\n', encoding="utf-8")
            (src / "dumps" / "api_dump.json").write_text("{}", encoding="utf-8")
            (src / "Exports" / "export-latest.html").write_text("<html>new</html>", encoding="utf-8")
            (src / "flowertrack_config.json").write_text(
                json.dumps({"tracker": {"dark_mode": False, "theme_palette_dark": {"bg": "#000"}}}),
                encoding="utf-8",
            )

            zip_path = Path(td) / "restore.zip"
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for file_path in src.rglob("*"):
                    if file_path.is_file():
                        zf.write(file_path, file_path.relative_to(src).as_posix())

            dummy = self._dummy_tracker(app_dir)
            with mock.patch.object(ui_tracker, "APP_DIR", str(app_dir)), mock.patch.object(
                ui_tracker, "TRACKER_CONFIG_FILE", str(config_path)
            ), mock.patch.object(ui_tracker, "EXPORTS_DIR_DEFAULT", str(exports_dir)):
                ui_tracker.CannabisTracker._restore_backup_zip(dummy, zip_path)

            self.assertTrue((data_dir / "tracker_data.json").exists())
            self.assertFalse((data_dir / "api_auth.json").exists())
            self.assertTrue((logs_dir / "changes.ndjson").exists())
            self.assertTrue((dumps_dir / "api_dump.json").exists())
            self.assertTrue((exports_dir / "export-latest.html").exists())
            self.assertTrue(config_path.exists())


if __name__ == "__main__":
    unittest.main()

