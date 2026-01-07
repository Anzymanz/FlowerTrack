import re
import tempfile
import unittest
from pathlib import Path

from exports import export_html


class TestExports(unittest.TestCase):
    def test_per_gram_calculation(self):
        data = [
            {
                "producer": "Prod",
                "brand": "Brand",
                "strain": "Strain",
                "product_type": "flower",
                "grams": 3.0,
                "price": 12.0,
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "out.html"
            export_html(data, out_path, fetch_images=False)
            html = out_path.read_text(encoding="utf-8")
        match = re.search(r"/g\s+([0-9]+\.[0-9]{2})", html)
        self.assertIsNotNone(match, "per-gram price not rendered")
        self.assertEqual(match.group(1), "4.00")


if __name__ == "__main__":
    unittest.main()
