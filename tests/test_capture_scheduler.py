import unittest
from unittest.mock import patch
from datetime import datetime

import capture


class SchedulerTests(unittest.TestCase):
    def test_interval_no_quiet(self):
        sched = capture.IntervalScheduler(None, lambda s, label: False)
        cfg = {"quiet_hours_enabled": False}
        self.assertEqual(sched.next_interval(120.0, cfg), 120.0)

    def test_interval_quiet(self):
        class FakeDateTime:
            @classmethod
            def now(cls):
                return datetime(2024, 1, 1, 1, 0, 0)
        sched = capture.IntervalScheduler(None, lambda s, label: False)
        cfg = {"quiet_hours_enabled": True, "quiet_hours_interval_seconds": 3600, "quiet_hours_start": "22:00", "quiet_hours_end": "07:00"}
        with patch.object(capture, "datetime", FakeDateTime):
            self.assertEqual(sched.next_interval(120.0, cfg), 3600.0)


if __name__ == "__main__":
    unittest.main()
