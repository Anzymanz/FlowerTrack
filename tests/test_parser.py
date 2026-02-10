import unittest

from parser import make_identity_key, parse_api_payloads


class TestParser(unittest.TestCase):
    def test_parse_api_payloads_basic(self):
        payloads = [
            {
                "url": "https://api.example.com/formulary-products?take=1",
                "data": [
                    {
                        "productId": 123,
                        "name": "Example Flower",
                        "product": {
                            "brand": {"name": "Producer Co"},
                            "cannabisSpecification": {
                                "strainName": "Example Strain",
                                "strainType": "Hybrid",
                                "format": "Flower",
                                "size": 10,
                                "volumeUnit": "GRAMS",
                                "thcContent": 20,
                                "cbdContent": 1,
                            },
                        },
                        "pricingOptions": {
                            "STANDARD": {"price": 8.5, "totalAvailability": 5}
                        },
                    }
                ],
            }
        ]
        items = parse_api_payloads(payloads)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.get("product_type"), "flower")
        self.assertEqual(item.get("product_id"), "123")
        self.assertEqual(item.get("strain"), "Example Strain")
        self.assertEqual(item.get("strain_type"), "Hybrid")
        self.assertEqual(item.get("stock_status"), "LOW STOCK")
        self.assertEqual(item.get("stock_detail"), "5 remaining")
        self.assertAlmostEqual(item.get("grams") or 0, 10.0)
        self.assertAlmostEqual(item.get("price") or 0, 8.5)
        self.assertAlmostEqual(item.get("thc") or 0, 20.0)
        self.assertEqual(item.get("thc_unit"), "%")
        self.assertAlmostEqual(item.get("cbd") or 0, 1.0)
        self.assertEqual(item.get("cbd_unit"), "%")

    def test_parse_api_payloads_flags_and_type(self):
        payloads = [
            {
                "url": "https://api.example.com/formulary-products?take=1",
                "data": [
                    {
                        "productId": 555,
                        "name": "Example Cartridge",
                        "status": "INACTIVE",
                        "requestable": "true",
                        "product": {
                            "brand": {"name": "Brand Co"},
                            "cannabisSpecification": {
                                "strainName": "Cartridge Strain",
                                "strainType": "Sativa",
                                "format": "Cartridge",
                                "size": 1,
                                "volumeUnit": "ML",
                            },
                        },
                        "pricingOptions": {
                            "STANDARD": {"price": 20.0, "totalAvailability": 0}
                        },
                    }
                ],
            }
        ]
        items = parse_api_payloads(payloads)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.get("product_type"), "vape")
        self.assertEqual(item.get("requestable"), True)
        self.assertEqual(item.get("is_inactive"), True)
        self.assertEqual(item.get("stock_status"), "OUT OF STOCK")
        self.assertAlmostEqual(item.get("ml") or 0, 1.0)

    def test_parse_api_payloads_pastille_type(self):
        payloads = [
            {
                "url": "https://api.example.com/formulary-products?take=1",
                "data": [
                    {
                        "productId": 777,
                        "name": "Curaleaf Pastille Gums",
                        "product": {
                            "brand": {"name": "Curaleaf"},
                            "cannabisSpecification": {
                                "format": "PASTILLE",
                                "size": 30,
                                "volumeUnit": "GRAMS",
                            },
                            "metadata": {"oldProductType": "PASTILLE"},
                        },
                        "pricingOptions": {
                            "STANDARD": {"price": 12.0, "totalAvailability": 15}
                        },
                    }
                ],
            }
        ]
        items = parse_api_payloads(payloads)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.get("product_type"), "pastille")
        self.assertEqual(item.get("stock_status"), "IN STOCK")

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
