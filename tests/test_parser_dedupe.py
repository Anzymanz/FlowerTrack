import unittest

from parser import parse_api_payloads


class ParserDedupeTests(unittest.TestCase):
    def _payload(self, pid, price, remaining=10):
        return {
            "url": "https://example.test/formulary-products?take=50&skip=0",
            "data": [
                {
                    "productId": pid,
                    "name": f"Item {pid}",
                    "pricingOptions": {
                        "STANDARD": {
                            "price": f"{price:.2f}",
                            "totalAvailability": remaining,
                        }
                    },
                    "product": {
                        "brand": {"name": "Brand"},
                        "cannabisSpecification": {
                            "format": "FLOWER",
                            "measurementUnit": "PERCENTAGE",
                            "thcContent": "20.00",
                            "cbdContent": "1.00",
                            "size": "10.00",
                            "volumeUnit": "GRAMS",
                            "strainType": "HYBRID",
                            "strainName": "Strain",
                        },
                    },
                }
            ],
        }

    def test_dedupe_prefers_lower_price(self):
        payloads = [self._payload(1, 85.0), self._payload(1, 65.0)]
        items = parse_api_payloads(payloads)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["price"], 65.0)

    def test_dedupe_prefers_with_remaining(self):
        payloads = [self._payload(2, 50.0, remaining=None), self._payload(2, 50.0, remaining=5)]
        items = parse_api_payloads(payloads)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["stock_remaining"], 5)

    def test_accepts_dict_payload_items(self):
        payloads = [
            {
                "url": "https://example.test/formulary-products?take=50&skip=0",
                "data": {
                    "items": [
                        {
                            "productId": "p1",
                            "name": "Alpha Flower",
                            "pricingOptions": {
                                "STANDARD": {"price": "9.00", "totalAvailability": 5}
                            },
                            "product": {
                                "brand": {"name": "Alpha"},
                                "cannabisSpecification": {
                                    "format": "FLOWER",
                                    "measurementUnit": "PERCENTAGE",
                                    "thcContent": "20.00",
                                    "cbdContent": "1.00",
                                    "size": "10.00",
                                    "volumeUnit": "GRAMS",
                                    "strainType": "HYBRID",
                                    "strainName": "Strain",
                                },
                            },
                        }
                    ]
                },
            }
        ]
        items = parse_api_payloads(payloads)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Alpha Flower")


if __name__ == "__main__":
    unittest.main()
