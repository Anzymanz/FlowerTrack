import unittest
from tray import compute_tray_state, stop_tray_icon


class TestTray(unittest.TestCase):
    def test_compute_tray_state_warn(self):
        running, warn = compute_tray_state(True, status="retrying", error_count=0, empty_retry=False)
        self.assertTrue(running)
        self.assertTrue(warn)

    def test_stop_tray_icon_noop(self):
        # Should not raise
        stop_tray_icon(None)


if __name__ == "__main__":
    unittest.main()
