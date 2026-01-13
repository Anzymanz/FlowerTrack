import os
import unittest
from app_core import APP_DIR, DATA_DIR


class TestSmoke(unittest.TestCase):
    def test_appdata_dirs_exist(self):
        self.assertTrue(os.path.isdir(APP_DIR))
        self.assertTrue(os.path.isdir(DATA_DIR))


if __name__ == "__main__":
    unittest.main()
