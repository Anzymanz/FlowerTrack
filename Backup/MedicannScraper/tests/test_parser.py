import unittest

from parser import parse_clinic_text


class TestParserFailures(unittest.TestCase):
    def test_empty_text_returns_empty_list(self):
        self.assertEqual(parse_clinic_text(""), [])
        self.assertEqual(parse_clinic_text("   \n  "), [])

    def test_malformed_price_does_not_crash(self):
        text = """
        CANNABIS FLOWER (ABC-123) Producer X
        Strain X | hybrid
        PRICE: abc
        IN STOCK
        """
        items = parse_clinic_text(text)
        self.assertEqual(len(items), 1)
        self.assertIsNone(items[0].get("price"))
        self.assertEqual(items[0].get("product_id"), "ABC-123")


if __name__ == "__main__":
    unittest.main()
