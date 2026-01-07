import unittest

from capture import RetryPolicy


class TestRetryPolicy(unittest.TestCase):
    def test_retry_wait_uses_post_nav_when_zero(self):
        cfg = {
            "retry_attempts": 3,
            "retry_wait_seconds": 0,
            "post_nav_wait_seconds": 30,
            "retry_backoff_max": 4,
        }
        policy = RetryPolicy.from_config(cfg)
        self.assertEqual(policy.retry_wait_seconds, 30)
        self.assertEqual(policy.attempt_wait(1), 30)
        self.assertEqual(policy.attempt_wait(2), 60)

    def test_interval_backoff_caps(self):
        cfg = {
            "retry_attempts": 3,
            "retry_wait_seconds": 10,
            "post_nav_wait_seconds": 10,
            "retry_backoff_max": 3,
        }
        policy = RetryPolicy.from_config(cfg)
        self.assertEqual(policy.interval_with_backoff(100, 0), 100)
        self.assertEqual(policy.interval_with_backoff(100, 1), 200)
        self.assertEqual(policy.interval_with_backoff(100, 2), 300)
        self.assertEqual(policy.interval_with_backoff(100, 5), 300)


if __name__ == "__main__":
    unittest.main()
