import unittest

from capture import pagination_is_complete


class PaginationTests(unittest.TestCase):
    def test_complete_when_no_failure(self):
        self.assertTrue(pagination_is_complete([1, 2], 10, False))

    def test_incomplete_when_failed_and_short(self):
        self.assertFalse(pagination_is_complete([1, 2], 10, True))

    def test_complete_when_failed_but_full(self):
        self.assertTrue(pagination_is_complete(list(range(10)), 10, True))


if __name__ == "__main__":
    unittest.main()
