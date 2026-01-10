import unittest

from parser import make_identity_key, make_item_key


class ParserKeyTests(unittest.TestCase):
    def test_identity_ignores_price(self):
        a = {"brand": "X", "strain": "Y", "price": 10, "grams": 10, "product_type": "flower"}
        b = {"brand": "X", "strain": "Y", "price": 12, "grams": 10, "product_type": "flower"}
        self.assertEqual(make_identity_key(a), make_identity_key(b))
        self.assertNotEqual(make_item_key(a), make_item_key(b))


if __name__ == "__main__":
    unittest.main()
