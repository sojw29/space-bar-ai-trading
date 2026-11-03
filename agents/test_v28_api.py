"""V28 local API tests: ephemeral loopback HTTP, no external network."""
import csv
import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dashboard_api_v28 as v28


class LocalApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.history = Path(self.temp.name) / "BTC_5m.csv"
        with self.history.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "open", "high", "low", "close", "volume"])
            writer.writeheader()
            for i in range(60):
                p = 100 + i * 0.1
                writer.writerow({"timestamp": 1700000100 + i * 300,
                                 "open": p - 0.01, "high": p + 0.1,
                                 "low": p - 0.1, "close": p, "volume": 20})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), v28.make_handler(self.history))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:%d" % self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def get(self, path):
        with urlopen(self.base + path, timeout=3) as response:
            return response.status, json.load(response)

    def test_health_and_events(self):
        status, health = self.get("/health")
        self.assertEqual(status, 200)
        self.assertFalse(health["orders_enabled"])
        status, payload = self.get("/api/v1/agents")
        self.assertEqual(status, 200)
        self.assertFalse(payload["realtime"])
        self.assertFalse(payload["orders_enabled"])
        self.assertEqual(len(payload["events"]["events"]), 7)

    def test_read_only(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.base + "/api/v1/agents", data=b"{}",
                            method="POST"), timeout=3)
        self.assertEqual(error.exception.code, 405)

    def test_missing_history_returns_503(self):
        self.history.unlink()
        with self.assertRaises(HTTPError) as error:
            self.get("/api/v1/agents")
        self.assertEqual(error.exception.code, 503)

    def test_meeting_unavailable_fails_closed_without_orders(self):
        with patch("meeting_quality_report_v166.build_report",
                   side_effect=FileNotFoundError("missing snapshot")):
            with self.assertRaises(HTTPError) as error:
                self.get("/api/v1/meeting")
            self.assertEqual(error.exception.code, 503)
            payload = json.load(error.exception)
            self.assertEqual(payload["error"], "meeting_snapshot_unavailable")
            self.assertFalse(payload["orders_enabled"])
            self.assertFalse(payload["live_trading_approved"])
            self.assertFalse(payload["contract_validation"]["verified"])

    def test_meeting_snapshot_reports_contract_validation(self):
        with patch("meeting_quality_report_v166.build_report",
                   return_value={"status": "RESEARCH_ONLY"}) as report:
            with patch("meeting_contract_validator_v186.validate_meeting_snapshot",
                       return_value={"verified": False, "status": "BLOCKED"}) as validate:
                status, payload = self.get("/api/v1/meeting")
        self.assertEqual(status, 200)
        self.assertEqual(payload["contract_validation"]["status"], "BLOCKED")
        report.assert_called_once()
        validate.assert_called_once()

    def test_meeting_get_never_invokes_live_model_or_orders(self):
        # A dashboard refresh must only read a stored research snapshot.
        with patch("meeting_quality_report_v166.build_report",
                   return_value={"research_only": True, "orders_enabled": False,
                                 "live_trading_approved": False}):
            with patch("meeting_contract_validator_v186.validate_meeting_snapshot",
                       return_value={"verified": False, "status": "BLOCKED"}):
                with patch("ai_meeting_runtime.OpenAIProvider.complete",
                           side_effect=AssertionError("live model invoked")) as live:
                    status, payload = self.get("/api/v1/meeting")
        self.assertEqual(status, 200)
        self.assertFalse(payload["orders_enabled"])
        self.assertFalse(payload["live_trading_approved"])
        live.assert_not_called()

    def test_meeting_post_is_rejected_without_running_model(self):
        with patch("ai_meeting_runtime.OpenAIProvider.complete",
                   side_effect=AssertionError("live model invoked")) as live:
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(self.base + "/api/v1/meeting", data=b"{}",
                                method="POST"), timeout=3)
        self.assertEqual(error.exception.code, 405)
        self.assertFalse(json.load(error.exception).get("orders_enabled", False))
        live.assert_not_called()

    def test_unknown_route(self):
        with self.assertRaises(HTTPError) as error:
            self.get("/api/v1/orders")
        self.assertEqual(error.exception.code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
