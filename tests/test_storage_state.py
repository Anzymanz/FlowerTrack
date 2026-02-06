import json
import tempfile
import unittest
from pathlib import Path

from storage import load_last_parse, save_last_parse, load_last_change, save_last_change, load_last_scrape, save_last_scrape, append_change_log
from scraper_state import read_scraper_state, write_scraper_state, update_scraper_state


class StorageStateTests(unittest.TestCase):
    def test_last_parse_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "last_parse.json"
            items = [{"id": 1}, {"id": 2}]
            save_last_parse(path, items)
            loaded = load_last_parse(path)
            self.assertEqual(loaded, items)

    def test_last_parse_backup_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "last_parse.json"
            items = [{"id": 3}]
            save_last_parse(path, items)
            save_last_parse(path, items)
            backup = path.with_suffix(path.suffix + ".bak")
            self.assertTrue(backup.exists())
            path.write_text("{bad json", encoding="utf-8")
            loaded = load_last_parse(path)
            self.assertEqual(loaded, items)

    def test_last_change_uses_backup_when_tmp_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "last_change.txt"
            save_last_change(path, "change")
            save_last_change(path, "change")
            backup = path.with_suffix(path.suffix + ".bak")
            self.assertTrue(backup.exists())
            tmp_path = path.with_suffix(path.suffix + ".tmp")
            tmp_path.write_text("tmp-only", encoding="utf-8")
            path.write_bytes(b"\xff")
            loaded = load_last_change(path)
            self.assertEqual(loaded, "change")

    def test_last_change_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "last_change.txt"
            save_last_change(path, "change")
            self.assertEqual(load_last_change(path), "change")

    def test_change_log_trim(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "changes.ndjson"
            for idx in range(5):
                append_change_log(path, {"timestamp": str(idx)}, max_entries=3)
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 3)
            self.assertTrue(lines[0].endswith("\"2\"}"))

    def test_last_scrape_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "last_scrape.txt"
            save_last_scrape(path, "scrape")
            self.assertEqual(load_last_scrape(path), "scrape")

    def test_scraper_state_write_and_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scraper_state.json"
            write_scraper_state(path, status="running", pid=123, last_change="x", last_scrape="y")
            data = read_scraper_state(path)
            self.assertEqual(data.get("status"), "running")
            self.assertEqual(data.get("pid"), 123)
            update_scraper_state(path, status="stopped", last_change=None)
            data = read_scraper_state(path)
            self.assertEqual(data.get("status"), "stopped")
            self.assertNotIn("last_change", data)

    def test_scraper_state_backup_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scraper_state.json"
            write_scraper_state(path, status="running", pid=123)
            write_scraper_state(path, status="running", pid=123)
            backup = path.with_suffix(path.suffix + ".bak")
            self.assertTrue(backup.exists())
            path.write_text("{bad json", encoding="utf-8")
            data = read_scraper_state(path)
            self.assertEqual(data.get("status"), "running")

    def test_scraper_state_backup_with_tmp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scraper_state.json"
            write_scraper_state(path, status="running", pid=123)
            write_scraper_state(path, status="running", pid=123)
            tmp_path = path.with_suffix(path.suffix + ".tmp")
            tmp_path.write_text("{\"status\": \"tmp\"}", encoding="utf-8")
            path.write_text("{bad json", encoding="utf-8")
            data = read_scraper_state(path)
            self.assertEqual(data.get("status"), "running")


if __name__ == "__main__":
    unittest.main()
