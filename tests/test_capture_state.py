import base64
import json
import unittest

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


if __name__ == "__main__":
    unittest.main()
