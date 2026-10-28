"""V186 offline meeting contract validator tests."""
import copy
import unittest
from meeting_contract_validator_v186 import validate_meeting_snapshot


def valid_snapshot():
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


class ContractValidatorTests(unittest.TestCase):
    def test_verified_research_never_allows_orders(self):
        result = validate_meeting_snapshot(valid_snapshot())
        self.assertTrue(result["verified"])
        self.assertEqual(result["status"], "VERIFIED_RESEARCH")
        self.assertIs(result["orders_allowed"], False)
        self.assertIs(result["live_trading_allowed"], False)

    def test_malformed_input_blocks(self):
        for value in (None, [], "bad", 123, {}, {"agents": []}):
            with self.subTest(value=value):
                self.assertEqual(validate_meeting_snapshot(value)["status"], "BLOCKED")

    def test_each_contract_failure_blocks(self):
        mutations = [
            ("evidence", "sha256", "invalid"),
            ("evidence", "bytes", True),
            ("evidence", "verified", False),
            ("quality_gate", "risk_veto", True),
            ("quality_gate", "quality_status", "FAIL"),
            ("agents", "ATLAS", {"state": "DATA_UNVERIFIED"}),
            ("agents", "GUARDIAN", {"state": "VETO"}),
            ("agents", "COMMANDER", {"decision": "LONG"}),
        ]
        for section, key, value in mutations:
            with self.subTest(section=section, key=key):
                snap = copy.deepcopy(valid_snapshot())
                snap[section][key] = value
                self.assertFalse(validate_meeting_snapshot(snap)["verified"])

    def test_unsafe_mode_blocks(self):
        for key, value in (("research_only", False), ("orders_enabled", True), ("live_trading_approved", True)):
            with self.subTest(key=key):
                snap = valid_snapshot()
                snap[key] = value
                self.assertIn("unsafe_mode", validate_meeting_snapshot(snap)["failures"])

    def test_missing_and_malformed_nested_fields(self):
        for key in ("evidence", "quality_gate", "agents"):
            for value in (None, [], "wrong"):
                with self.subTest(key=key, value=value):
                    snap = valid_snapshot()
                    snap[key] = value
                    self.assertEqual(validate_meeting_snapshot(snap)["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
