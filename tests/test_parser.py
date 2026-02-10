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
                        "name": "CURALEAF THC 10MG CBD 10MG MIXED BERRIES CANNABIS PASTILLES 30",
                        "product": {
                            "brand": {"name": "Curaleaf"},
                            "cannabisSpecification": {
                                "format": "PASTILLE",
                                "size": 30,
                                "volumeUnit": "UNITS",
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
        self.assertEqual(item.get("unit_count"), 30)
        self.assertAlmostEqual(item.get("price_per_unit") or 0, 0.4)
        self.assertEqual(item.get("strain"), "Mixed Berries 30 Pastilles")

    def test_parse_api_payloads_oil_balance_includes_tc_profile(self):
        payloads = [
            {
                "url": "https://api.example.com/formulary-products?take=1",
                "data": [
                    {
                        "productId": 8801,
                        "name": "CIRCLE BALANCE T25:C25 THC 25MG/ML CBD 25MG/ML CANNABIS SUBLINGUAL OIL 30ML",
                        "product": {
                            "brand": {"name": "Circle"},
                            "cannabisSpecification": {
                                "format": "OIL",
                                "size": 30,
                                "volumeUnit": "ML",
                                "thcContent": 25,
                                "cbdContent": 25,
                            },
                        },
                        "pricingOptions": {
                            "STANDARD": {"price": 89.0, "totalAvailability": 15}
                        },
                    }
                ],
            }
        ]
        items = parse_api_payloads(payloads)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.get("product_type"), "oil")
        self.assertEqual(item.get("strain"), "Balance T25C25 Sublingual Oil")

    def test_parse_api_payloads_oil_thc_only_includes_c0_profile(self):
        payloads = [
            {
                "url": "https://api.example.com/formulary-products?take=1",
                "data": [
                    {
                        "productId": 8802,
                        "name": "CURALEAF T50 THC 50MG/ML CANNABIS SUBLINGUAL OIL 30ML",
                        "product": {
                            "brand": {"name": "Curaleaf"},
                            "cannabisSpecification": {
                                "format": "OIL",
                                "size": 30,
                                "volumeUnit": "ML",
                                "thcContent": 50,
                            },
                        },
                        "pricingOptions": {
                            "STANDARD": {"price": 120.0, "totalAvailability": 15}
                        },
                    }
                ],
            }
        ]
        items = parse_api_payloads(payloads)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.get("product_type"), "oil")
        self.assertEqual(item.get("strain"), "T50 Sublingual Oil")

    def test_parse_api_payloads_oil_includes_descriptors_and_flavour(self):
        payloads = [
            {
                "url": "https://api.example.com/formulary-products?take=1",
                "data": [
                    {
                        "productId": "MCAN03596",
                        "name": "CIRCLE CANNABIS SUBLINGUAL OIL BALANCE MINT T10:C10 THC 10MG/ML CBD 10MG/ML 30ML",
                        "product": {
                            "name": "Circle T10:C10 Full Spectrum Oil Medical Cannabis",
                            "brand": {"name": "Circle"},
                            "cannabisSpecification": {
                                "format": "OIL",
                                "size": 30,
                                "volumeUnit": "ML",
                                "thcContent": 10,
                                "cbdContent": 10,
                            },
                        },
                        "pricingOptions": {
                            "STANDARD": {"price": 75.0, "totalAvailability": 15}
                        },
                    }
                ],
            }
        ]
        items = parse_api_payloads(payloads)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.get("product_type"), "oil")
        self.assertEqual(item.get("strain"), "Balance Mint T10C10 Sublingual Oil")

    def test_parse_api_payloads_oil_cbd_threshold_uses_t_only_when_cbd_le_3(self):
        payloads = [
            {
                "url": "https://api.example.com/formulary-products?take=1",
                "data": [
                    {
                        "productId": "MCAN03424",
                        "name": "CIRCLE T20 THC 20MG/ML CBD <3MG/ML CANNABIS SUBLINGUAL OIL 30ML",
                        "product": {
                            "name": "Circle T20 Full Spectrum Oil Medical Cannabis",
                            "brand": {"name": "Circle"},
                            "cannabisSpecification": {
                                "format": "OIL",
                                "size": 30,
                                "volumeUnit": "ML",
                                "thcContent": 20,
                                "cbdContent": 3,
                            },
                        },
                        "pricingOptions": {
                            "STANDARD": {"price": 60.0, "totalAvailability": 15}
                        },
                    }
                ],
            }
        ]
        items = parse_api_payloads(payloads)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.get("product_type"), "oil")
        self.assertEqual(item.get("strain"), "Full Spectrum T20 Sublingual Oil")

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

    def test_parse_api_payloads_vape_name_easy_dose(self):
        payloads = [
            {
                "url": "https://api.example.com/formulary-products?take=1",
                "data": [
                    {
                        "productId": 9901,
                        "name": "EZD-GRA 1000 THC 1000MG/1.2G CBD 24MG/1.2G CANNABIS VAPE CARTRIDGE 1.2G",
                        "product": {
                            "name": "Easy Dose GRA T1000 Grapezilla Medical Cannabis Cartridge",
                            "brand": {"name": "Easy Dose"},
                            "cannabisSpecification": {
                                "format": "VAPE",
                                "size": 1.2,
                                "volumeUnit": "GRAMS",
                            },
                        },
                        "pricingOptions": {
                            "STANDARD": {"price": 62.0, "totalAvailability": 15}
                        },
                    }
                ],
            }
        ]
        items = parse_api_payloads(payloads)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.get("product_type"), "vape")
        self.assertEqual(item.get("strain"), "Grapezilla Cartridge")

    def test_parse_api_payloads_vape_name_clearleaf_rosin(self):
        payloads = [
            {
                "url": "https://api.example.com/formulary-products?take=1",
                "data": [
                    {
                        "productId": 9902,
                        "name": "CLEARLEAF T750 CPI ROSIN (THC 750MG/ML CBD ≤ 50MG/ML) VAPE CARTRIDGE 1ML",
                        "product": {
                            "name": "Clearleaf Hash Rosin T750 Cookie Pie Medical Cannabis Cartridge",
                            "brand": {"name": "Clearleaf"},
                            "cannabisSpecification": {
                                "format": "VAPE",
                                "strainName": "Cookie Pie",
                                "size": 1.0,
                                "volumeUnit": "GRAMS",
                            },
                        },
                        "pricingOptions": {
                            "STANDARD": {"price": 80.0, "totalAvailability": 15}
                        },
                    }
                ],
            }
        ]
        items = parse_api_payloads(payloads)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.get("product_type"), "vape")
        self.assertEqual(item.get("strain"), "Cookie Pie Hash Rosin Cartridge")

    def test_parse_api_payloads_vape_name_4c_code_removed(self):
        payloads = [
            {
                "url": "https://api.example.com/formulary-products?take=1",
                "data": [
                    {
                        "productId": 9903,
                        "name": "4C LABS CLV 85/1 CHERRY LIME THC 850MG/G CBD <10MG/G VAPE CARTRIDGE 0.95G",
                        "product": {
                            "name": "4C Labs CLV T807 Cherry Lime Medical Cannabis Cartridge",
                            "brand": {"name": "4C Labs"},
                            "cannabisSpecification": {
                                "format": "VAPE",
                                "size": 0.95,
                                "volumeUnit": "GRAMS",
                            },
                        },
                        "pricingOptions": {
                            "STANDARD": {"price": 49.0, "totalAvailability": 15}
                        },
                    }
                ],
            }
        ]
        items = parse_api_payloads(payloads)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.get("product_type"), "vape")
        self.assertEqual(item.get("strain"), "Cherry Lime Cartridge")

    def test_parse_api_payloads_vape_name_includes_distillate_descriptor(self):
        payloads = [
            {
                "url": "https://api.example.com/formulary-products?take=1",
                "data": [
                    {
                        "productId": "WCAN04490",
                        "name": "CURALEAF LIQUID VAPE DISTILLATE THC 600MG/1G CBD 200MG/1G QUE VAPE CARTRIDGE 1",
                        "product": {
                            "name": "Curaleaf T600:C200 (600mg/ml THC, 200mg/ml CBD) Jack Herer Medical Cannabis Liquid Vape Cartridge",
                            "brand": {"name": "Curaleaf"},
                            "cannabisSpecification": {
                                "format": "VAPE",
                                "strainName": "Jack Herer",
                                "size": 1.0,
                                "volumeUnit": "GRAMS",
                            },
                        },
                        "pricingOptions": {
                            "STANDARD": {"price": 80.0, "totalAvailability": 15}
                        },
                    }
                ],
            }
        ]
        items = parse_api_payloads(payloads)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.get("product_type"), "vape")
        self.assertEqual(item.get("strain"), "Jack Herer Liquid Distillate Cartridge")

    def test_parse_api_payloads_vape_name_includes_full_spectrum_descriptor(self):
        payloads = [
            {
                "url": "https://api.example.com/formulary-products?take=1",
                "data": [
                    {
                        "productId": "FS-101",
                        "name": "ACME FULL SPECTRUM THC 800MG/ML CBD 20MG/ML VAPE CARTRIDGE 1ML",
                        "product": {
                            "name": "Acme Blue Dream Medical Cannabis Cartridge",
                            "brand": {"name": "Acme"},
                            "cannabisSpecification": {
                                "format": "VAPE",
                                "size": 1.0,
                                "volumeUnit": "GRAMS",
                            },
                        },
                        "pricingOptions": {
                            "STANDARD": {"price": 45.0, "totalAvailability": 15}
                        },
                    }
                ],
            }
        ]
        items = parse_api_payloads(payloads)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.get("product_type"), "vape")
        self.assertEqual(item.get("strain"), "Blue Dream Full Spectrum Cartridge")

    def test_parse_api_payloads_vape_zero_price_filtered(self):
        payloads = [
            {
                "url": "https://api.example.com/formulary-products?take=1",
                "data": [
                    {
                        "productId": "FREE-VAPE-1",
                        "name": "ACME LIVE RESIN THC 700MG/ML VAPE CARTRIDGE 1ML",
                        "product": {
                            "name": "Acme Citrus Medical Cannabis Cartridge",
                            "brand": {"name": "Acme"},
                            "cannabisSpecification": {
                                "format": "VAPE",
                                "size": 1.0,
                                "volumeUnit": "GRAMS",
                            },
                        },
                        "pricingOptions": {
                            "STANDARD": {"price": 0.0, "totalAvailability": 15}
                        },
                    }
                ],
            }
        ]
        items = parse_api_payloads(payloads)
        self.assertEqual(items, [])

    def test_parse_api_payloads_not_prescribable_filtered_from_nested_field(self):
        payloads = [
            {
                "url": "https://api.example.com/formulary-products?take=1",
                "data": [
                    {
                        "productId": "BLOCK-1",
                        "name": "Acme Cherry",
                        "product": {
                            "name": "Acme Cherry Medical Cannabis Cartridge",
                            "brand": {"name": "Acme"},
                            "metadata": {"notes": "DO NOT PRESCRIBE - TEST"},
                            "cannabisSpecification": {
                                "format": "VAPE",
                                "size": 1.0,
                                "volumeUnit": "GRAMS",
                            },
                        },
                        "pricingOptions": {
                            "STANDARD": {"price": 30.0, "totalAvailability": 15}
                        },
                    }
                ],
            }
        ]
        items = parse_api_payloads(payloads)
        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
