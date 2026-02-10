import base64
import json
import tempfile
import unittest
from pathlib import Path

from capture import CaptureStateMachine, CaptureWorker


class CaptureStateTests(unittest.TestCase):
    def test_state_transitions(self):
        sm = CaptureStateMachine()
        self.assertEqual(sm.status, "idle")
        self.assertTrue(sm.transition("running"))
        self.assertEqual(sm.status, "running")
        self.assertFalse(sm.transition("idle"))
        self.assertTrue(sm.transition("retrying"))
        self.assertTrue(sm.transition("running"))
        self.assertTrue(sm.transition("stopped"))

    def test_decode_jwt_payload(self):
        payload = {"exp": 123, "sub": "user"}
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
        token = f"header.{encoded}.sig"
        worker = CaptureWorker.__new__(CaptureWorker)
        decoded = worker._decode_jwt_payload(token)
        self.assertEqual(decoded.get("exp"), 123)
        decoded_bearer = worker._decode_jwt_payload(f"Bearer {token}")
        self.assertEqual(decoded_bearer.get("sub"), "user")

    def test_clear_auth_cache_removes_file(self):
        worker = CaptureWorker.__new__(CaptureWorker)
        with tempfile.TemporaryDirectory() as tmp:
            worker.app_dir = tmp
            worker.callbacks = {"capture_log": lambda _m: None}
            path = worker._auth_cache_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"token":"x"}', encoding="utf-8")
            self.assertTrue(path.exists())
            cleared = worker.clear_auth_cache()
            self.assertTrue(cleared)
            self.assertFalse(path.exists())

    def test_prune_dump_files_keeps_latest_10(self):
        worker = CaptureWorker.__new__(CaptureWorker)
        worker.callbacks = {"capture_log": lambda _m: None}
        with tempfile.TemporaryDirectory() as tmp:
            dump_dir = Path(tmp)
            created = []
            for i in range(12):
                path = dump_dir / f"api_dump_20260210_1200{i:02d}.json"
                path.write_text("{}", encoding="utf-8")
                created.append(path)
            worker._prune_dump_files(dump_dir, keep=10)
            remaining = sorted(dump_dir.glob("api_dump_*.json"))
            self.assertEqual(len(remaining), 10)


if __name__ == "__main__":
    unittest.main()
