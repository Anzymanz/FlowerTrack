import json
import tempfile
import unittest
from pathlib import Path

from storage import load_last_parse, save_last_parse, load_last_change, save_last_change, load_last_scrape, save_last_scrape
from scraper_state import read_scraper_state, write_scraper_state, update_scraper_state


class StorageStateTests(unittest.TestCase):
    def test_last_parse_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "last_parse.json"
            items = [{"id": 1}, {"id": 2}]
            save_last_parse(path, items)
            loaded = load_last_parse(path)
            self.assertEqual(loaded, items)

    def test_last_change_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "last_change.txt"
            save_last_change(path, "change")
            self.assertEqual(load_last_change(path), "change")

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


if __name__ == "__main__":
    unittest.main()
