"""V190: HTTP fault-injection tests for meeting contract and 3D room."""
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

from dashboard_api_v28 import make_handler


def safe_report():
    return {
        "evidence": {"source": "offline_v65_quality_report", "sha256": "b" * 64, "bytes": 42, "verified": True},
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


class MeetingFaultInjectionTests(unittest.TestCase):
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

    def request(self, payload):
        with patch("meeting_quality_report_v166.build_report", return_value=payload):
            with urlopen(self.base + "/api/v1/meeting", timeout=5) as response:
                return json.load(response)

    def test_missing_fields_fail_closed(self):
        for payload in ({}, {"evidence": {}}, {"agents": []}, {"quality_gate": None}):
            with self.subTest(payload=payload):
                result = self.request(payload)["contract_validation"]
                self.assertEqual(result["status"], "BLOCKED")
                self.assertFalse(result["orders_allowed"])
                self.assertFalse(result["live_trading_allowed"])

    def test_mutated_agent_states_fail_closed(self):
        for name, field, value in (
            ("ATLAS", "state", "DATA_UNVERIFIED"),
            ("GUARDIAN", "state", "VETO"),
            ("COMMANDER", "decision", "LONG"),
        ):
            with self.subTest(name=name):
                report = safe_report()
                report["agents"][name][field] = value
                self.assertIn("agent_contract_blocked", self.request(report)["contract_validation"]["failures"])

    def test_bad_evidence_and_gate_fail_closed(self):
        report = safe_report()
        report["evidence"]["bytes"] = True
        self.assertIn("invalid_evidence", self.request(report)["contract_validation"]["failures"])
        report = safe_report()
        report["quality_gate"]["risk_veto"] = True
        self.assertIn("quality_gate_blocked", self.request(report)["contract_validation"]["failures"])

    def test_3d_room_requires_server_validation(self):
        with urlopen(self.base + "/office3d", timeout=5) as response:
            html = response.read().decode("utf-8")
        self.assertIn('showApiVerdict(data.contract_validation)', html)
        self.assertIn('if(!apiContractValid){blocked("API 검증 계약 불일치");return;}', html)
        self.assertIn('validation.orders_allowed===false', html)
        self.assertIn('validation.live_trading_allowed===false', html)


if __name__ == "__main__":
    unittest.main()
