import unittest

from parser import make_identity_key, parse_clinic_text


class TestParser(unittest.TestCase):
    def test_parse_clinic_text_basic(self):
        text = """
IN STOCK
Producer Co CANNABIS FLOWER (ABC123)
Example Strain | Hybrid
10 g
GBP 8.50
THC: 20 %
CBD: 1 %
"""
        items = parse_clinic_text(text)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.get("product_type"), "flower")
        self.assertEqual(item.get("product_id"), "ABC123")
        self.assertEqual(item.get("strain"), "Example Strain")
        self.assertEqual(item.get("strain_type"), "Hybrid")
        self.assertEqual(item.get("stock"), "IN STOCK")
        self.assertAlmostEqual(item.get("grams") or 0, 10.0)
        self.assertAlmostEqual(item.get("price") or 0, 8.50)
        self.assertAlmostEqual(item.get("thc") or 0, 20.0)
        self.assertEqual(item.get("thc_unit"), "%")
        self.assertAlmostEqual(item.get("cbd") or 0, 1.0)
        self.assertEqual(item.get("cbd_unit"), "%")

    def test_identity_key_ignores_price(self):
        base = {
            "product_id": "ABC123",
            "producer": "Prod",
            "brand": "Brand",
            "strain": "Strain",
            "grams": 10.0,
            "ml": None,
            "product_type": "flower",
            "strain_type": "Hybrid",
            "is_smalls": False,
            "thc": 20.0,
            "thc_unit": "%",
            "cbd": 1.0,
            "cbd_unit": "%",
        }
        item_a = dict(base, price=8.5)
        item_b = dict(base, price=9.0)
        self.assertEqual(make_identity_key(item_a), make_identity_key(item_b))


if __name__ == "__main__":
    unittest.main()
