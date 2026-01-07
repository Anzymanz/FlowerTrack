import threading
import unittest

import capture


class DummyTimeoutError(Exception):
    pass


class DummyLocator:
    def __init__(self, seq):
        self.seq = seq

    def inner_text(self):
        if self.seq:
            return self.seq.pop(0)
        return "ok"


class DummyPage:
    def __init__(self, seq):
        self.seq = seq

    def goto(self, url, timeout=0, wait_until=None):
        return True

    def reload(self, timeout=0, wait_until=None):
        return True

    def locator(self, selector):
        return DummyLocator(self.seq)

    def set_default_timeout(self, val):
        return None

    @property
    def keyboard(self):
        class K:
            def press(self, key):
                return None

        return K()


class DummyBrowser:
    def __init__(self, seq):
        self.seq = seq

    def new_page(self):
        return DummyPage(self.seq)

    def close(self):
        return None


class DummyPlaywrightCtx:
    def __init__(self, seq):
        self.seq = seq

    def __enter__(self):
        class DummyChromium:
            def __init__(self, seq):
                self.seq = seq

            def launch(self, headless=True):
                return DummyBrowser(self.seq)

        class DummyP:
            def __init__(self, seq):
                self.chromium = DummyChromium(seq)

        return DummyP(self.seq)

    def __exit__(self, exc_type, exc, tb):
        return False


class CaptureRetryTests(unittest.TestCase):
    def setUp(self):
        # Inject dummy playwright into module
        capture._Playwright = (lambda seq=None: DummyPlaywrightCtx(seq), DummyTimeoutError)

    def test_retry_flow_succeeds_on_third_attempt(self):
        # First two reads empty, third has content
        seq = ["", "", "ok text"]
        logs = []
        applied = []
        stop_event = threading.Event()

        def log(msg):
            logs.append(msg)

        def apply_text(text):
            applied.append(text)
            stop_event.set()  # stop after success

        worker = capture.CaptureWorker(
            cfg={
                "url": "http://example.com",
                "interval_seconds": 0,
                "post_nav_wait_seconds": 0,
                "retry_attempts": 3,
                "headless": True,
            },
            callbacks={
                "capture_log": log,
                "apply_text": apply_text,
                "responsive_wait": lambda seconds, label="": stop_event.is_set(),
                "stop_event": stop_event,
                "on_status": lambda status, msg=None: None,
                "on_stop": lambda: None,
            },
            app_dir=None,
            install_fn=None,
        )
        # Prime the dummy playwright with the sequence
        capture._Playwright = (lambda seq=seq: DummyPlaywrightCtx(seq), DummyTimeoutError)
        worker._run()

        self.assertIn("Page ready; collecting text.", logs)
        self.assertEqual(applied, ["ok text"])
        # Ensure retry log appears
        self.assertTrue(any("No content; retrying" in m for m in logs))


if __name__ == "__main__":
    unittest.main()
