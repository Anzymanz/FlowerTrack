import tempfile
import unittest
from pathlib import Path

from exports import export_html


class ExportTests(unittest.TestCase):
    def test_export_html_writes_file(self):
        data = [
            {
                "brand": "Brand",
                "producer": "Producer",
                "strain": "Strain",
                "price": 10.0,
                "grams": 10.0,
                "product_type": "flower",
                "strain_type": "Hybrid",
                "thc": 20,
                "thc_unit": "%",
                "cbd": 1,
                "cbd_unit": "%",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.html"
            export_html(data, path)
            self.assertTrue(path.exists())
            text = path.read_text(encoding="utf-8")
            self.assertIn("Strain", text)
            self.assertIn("loadMoreSentinel", text)
            self.assertIn("const VISIBLE_STEP = 30", text)
            self.assertIn("loading='lazy'", text)
            self.assertIn("data-in-stock='1'", text)
            self.assertIn("rawChangesB64", text)

    def test_export_writes_history_sidecar(self):
        data = [
            {
                "brand": "Brand",
                "producer": "Producer",
                "strain": "Strain",
                "price": 10.0,
                "grams": 10.0,
                "product_type": "flower",
                "strain_type": "Hybrid",
                "thc": 20,
                "thc_unit": "%",
                "cbd": 1,
                "cbd_unit": "%",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.html"
            export_html(data, path)
            sidecar = path.with_name("changes_latest.json")
            self.assertTrue(sidecar.exists())
            payload = sidecar.read_text(encoding="utf-8")
            self.assertTrue(payload.strip().startswith("["))


if __name__ == "__main__":
    unittest.main()
