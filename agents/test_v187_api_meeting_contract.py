"""V187: meeting API exposes the V186 fail-closed validation verdict."""
import unittest
from pathlib import Path
from unittest.mock import patch

from meeting_contract_validator_v186 import validate_meeting_snapshot


class V187MeetingAPIContractTests(unittest.TestCase):
    def test_meeting_endpoint_attaches_validator(self):
        source = Path("agents/dashboard_api_v28.py").read_text(encoding="utf-8")
        self.assertIn('elif path == "/api/v1/meeting":', source)
        self.assertIn('from meeting_contract_validator_v186 import validate_meeting_snapshot', source)
        self.assertIn('report["contract_validation"] = validate_meeting_snapshot(report)', source)
        self.assertIn('self.reply(200, report)', source)

    def test_bad_snapshot_is_never_approved(self):
        result = validate_meeting_snapshot({"orders_enabled": True, "live_trading_approved": True})
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["orders_allowed"])
        self.assertFalse(result["live_trading_allowed"])

    def test_read_only_api(self):
        source = Path("agents/dashboard_api_v28.py").read_text(encoding="utf-8")
        self.assertIn('def do_POST(self):', source)
        self.assertIn('self.reply(405, {"error": "read_only"})', source)


if __name__ == "__main__":
    unittest.main()
