"""V189: real HTTP contract tests for the read-only meeting API."""
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dashboard_api_v28 import make_handler


def sample_report():
    return {
        "evidence": {"source": "offline_v65_quality_report", "sha256": "a" * 64, "bytes": 123, "verified": True},
        "quality_gate": {"quality_verified": True, "quality_status": "PASS", "risk_veto": False},
        "agents": {
            "ATLAS": {"state": "DATA_VERIFIED"},
            "GUARDIAN": {"state": "CLEAR"},
            "COMMANDER": {"decision": "WAIT"},
        },
        "research_only": True,
        "orders_enabled": False,
        "live_trading_approved": False,
    }


class MeetingHTTPIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(Path("data/history/BTC_5m.csv")))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:" + str(cls.server.server_address[1])

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def get_meeting(self, report):
        with patch("meeting_quality_report_v166.build_report", return_value=report):
            with urlopen(self.base + "/api/v1/meeting", timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                return json.load(response)

    def test_verified_research_is_never_live_approved(self):
        result = self.get_meeting(sample_report())
        self.assertEqual(result["contract_validation"]["status"], "VERIFIED_RESEARCH")
        self.assertTrue(result["contract_validation"]["verified"])
        self.assertFalse(result["contract_validation"]["orders_allowed"])
        self.assertFalse(result["contract_validation"]["live_trading_allowed"])
        self.assertFalse(result["orders_enabled"])

    def test_bad_evidence_blocks(self):
        report = sample_report()
        report["evidence"]["sha256"] = "invalid"
        result = self.get_meeting(report)
        self.assertEqual(result["contract_validation"]["status"], "BLOCKED")
        self.assertIn("invalid_evidence", result["contract_validation"]["failures"])

    def test_unsafe_mode_blocks(self):
        report = sample_report()
        report["orders_enabled"] = True
        result = self.get_meeting(report)
        self.assertEqual(result["contract_validation"]["status"], "BLOCKED")
        self.assertIn("unsafe_mode", result["contract_validation"]["failures"])

    def test_post_is_rejected(self):
        with self.assertRaises(HTTPError) as ctx:
            urlopen(Request(self.base + "/api/v1/meeting", data=b"{}", method="POST"), timeout=5)
        self.assertEqual(ctx.exception.code, 405)


if __name__ == "__main__":
    unittest.main()
