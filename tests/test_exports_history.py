import json
import os
import tempfile
import unittest
from pathlib import Path

import exports


class ExportHistoryTests(unittest.TestCase):
    def test_history_json_embeds_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            appdata = Path(tmp)
            logs_dir = appdata / "FlowerTrack" / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            history_path = logs_dir / "changes.ndjson"
            history_path.write_text(
                json.dumps({"timestamp": "2026-02-06T10:02:09+00:00", "new_items": []}) + "\n",
                encoding="utf-8",
            )
            exports_dir = appdata / "FlowerTrack" / "Exports"
            exports_dir.mkdir(parents=True, exist_ok=True)
            old_appdata = os.environ.get("APPDATA")
            os.environ["APPDATA"] = str(appdata)
            try:
                path = exports.export_html_auto([], exports_dir=exports_dir, open_file=False, fetch_images=False)
            finally:
                if old_appdata is None:
                    os.environ.pop("APPDATA", None)
                else:
                    os.environ["APPDATA"] = old_appdata
            html_text = path.read_text(encoding="utf-8")
            line = next((ln for ln in html_text.splitlines() if "const rawChangesJson =" in ln), "")
            self.assertTrue(line, "rawChangesJson line missing")
            raw = line.split("=", 1)[1].strip().rstrip(";")
            self.assertTrue(raw.startswith("["), "rawChangesJson should be an array literal")
            parsed = json.loads(raw)
            self.assertTrue(parsed)
            self.assertEqual(parsed[0].get("timestamp"), "2026-02-06T10:02:09+00:00")


if __name__ == "__main__":
    unittest.main()
