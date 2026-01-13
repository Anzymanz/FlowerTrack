import unittest
from mix_utils import validate_blend_names


class TestMixUtils(unittest.TestCase):
    def test_validate_blend_names_empty(self):
        self.assertIsNotNone(validate_blend_names("A", "B", ""))

    def test_validate_blend_names_same_source(self):
        self.assertIsNotNone(validate_blend_names("A", "a", "Blend"))

    def test_validate_blend_names_same_as_source(self):
        self.assertIsNotNone(validate_blend_names("A", "B", "a"))

    def test_validate_blend_names_ok(self):
        self.assertIsNone(validate_blend_names("A", "B", "Blend"))


if __name__ == "__main__":
    unittest.main()
