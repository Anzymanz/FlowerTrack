import re
import tempfile
import unittest
from pathlib import Path

from exports import export_html, _country_code2, _flag_cdn_url


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

    def test_country_code_and_flag_url(self):
        self.assertEqual(_country_code2("CAN"), "ca")
        self.assertEqual(_country_code2("us"), "us")
        self.assertEqual(_country_code2("GBR"), "gb")
        self.assertEqual(_country_code2("DEU"), "de")
        self.assertIsNone(_country_code2("ZZZ"))
        self.assertEqual(_flag_cdn_url("CAN"), "https://flagcdn.com/24x18/ca.png")
        self.assertIsNone(_flag_cdn_url("ZZZ"))


if __name__ == "__main__":
    unittest.main()
