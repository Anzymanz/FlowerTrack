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


if __name__ == "__main__":
    unittest.main()
