import unittest

from ui_scraper import _should_stop_on_empty


class TestEmptyStop(unittest.TestCase):
    def test_stop_threshold(self):
        self.assertFalse(_should_stop_on_empty(0, 3))
        self.assertFalse(_should_stop_on_empty(2, 3))
        self.assertTrue(_should_stop_on_empty(3, 3))
        self.assertTrue(_should_stop_on_empty(4, 3))


if __name__ == "__main__":
    unittest.main()
