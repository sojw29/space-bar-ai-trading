"""V191: malformed source must return fail-closed HTTP 503."""
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

from dashboard_api_v28 import make_handler


class MeetingSourceFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(Path("data/history/BTC_5m.csv")))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = "http://127.0.0.1:" + str(cls.server.server_address[1]) + "/api/v1/meeting"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def assert_blocked_503(self, source):
        with patch("meeting_quality_report_v166.build_report", side_effect=source if isinstance(source, Exception) else None, return_value=None if isinstance(source, Exception) else source):
            with self.assertRaises(HTTPError) as ctx:
                urlopen(self.url, timeout=5)
            self.assertEqual(ctx.exception.code, 503)
            payload = json.load(ctx.exception)
            self.assertEqual(payload["error"], "meeting_snapshot_unavailable")
            self.assertEqual(payload["contract_validation"]["status"], "BLOCKED")
            self.assertFalse(payload["contract_validation"]["orders_allowed"])
            self.assertFalse(payload["contract_validation"]["live_trading_allowed"])
            self.assertFalse(payload["orders_enabled"])
            self.assertFalse(payload["live_trading_approved"])

    def test_malformed_source(self):
        for value in (None, [], "bad", 123):
            with self.subTest(value=value):
                self.assert_blocked_503(value)

    def test_unavailable_source(self):
        for error in (OSError("offline report missing"), ValueError("bad source"), TypeError("wrong source")):
            with self.subTest(error=type(error).__name__):
                self.assert_blocked_503(error)


if __name__ == "__main__":
    unittest.main()
