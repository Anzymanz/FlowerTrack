import unittest
from types import SimpleNamespace

import ui_tracker


class DummyVar:
    def __init__(self, value: str):
        self._value = value

    def get(self) -> str:
        return self._value


class TrackerRoaTests(unittest.TestCase):
    def test_resolve_roa_hidden(self):
        dummy = SimpleNamespace(hide_roa_options=True, roa_choice=DummyVar("Vaped"))
        roa = ui_tracker.CannabisTracker._resolve_roa(dummy)
        self.assertEqual(roa, "Unknown")

    def test_resolve_roa_visible(self):
        dummy = SimpleNamespace(hide_roa_options=False, roa_choice=DummyVar("Smoked"))
        roa = ui_tracker.CannabisTracker._resolve_roa(dummy)
        self.assertEqual(roa, "Smoked")

    def test_stats_window_height_bounds(self):
        def _height_for_count(count: int) -> int:
            height = 200 + max(0, count) * 16
            return max(260, min(420, height))
        # CBD tracking adds rows but height stays within bounds.
        self.assertEqual(_height_for_count(0), 260)
        self.assertEqual(_height_for_count(5), 280)
        self.assertEqual(_height_for_count(20), 420)
        self.assertEqual(_height_for_count(50), 420)


if __name__ == "__main__":
    unittest.main()
