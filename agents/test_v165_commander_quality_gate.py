"""V165 offline commander meeting gate regression tests."""
import json
import tempfile
import unittest
from pathlib import Path
from commander_quality_gate_v165 import gate_decision, from_report


class QualityGateTests(unittest.TestCase):
    def good(self):
        return {"overall_status": "PASS", "research_usable": True,
                "results": [{"status": "PASS", "research_usable": True} for _ in range(9)]}

    def test_pass_preserves_research_decision_without_order_permission(self):
        result = gate_decision("LONG", self.good())
        self.assertEqual(result["decision"], "LONG")
        self.assertFalse(result["risk_veto"])
        self.assertFalse(result["orders_enabled"])

    def test_review_and_fail_veto(self):
        for state in ("REVIEW", "FAIL"):
            data = self.good()
            data["overall_status"] = state
            result = gate_decision("SHORT", data)
            self.assertEqual(result["decision"], "WAIT")
            self.assertTrue(result["risk_veto"])

    def test_missing_or_malformed_file_vetoes(self):
        for data in (None, {}, {"overall_status": "PASS", "research_usable": True},
                     {"overall_status": "PASS", "research_usable": True, "results": []}):
            self.assertEqual(gate_decision("LONG", data)["decision"], "WAIT")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "quality.json"
            self.assertEqual(from_report(path, "LONG")["decision"], "WAIT")
            path.write_text("{invalid", encoding="utf-8")
            self.assertEqual(from_report(path, "LONG")["decision"], "WAIT")

    def test_one_bad_asset_blocks_everything(self):
        data = self.good()
        data["results"][4]["research_usable"] = False
        self.assertEqual(gate_decision("LONG", data)["decision"], "WAIT")

    def test_unrecognized_decision_is_wait(self):
        self.assertEqual(gate_decision("BUY_NOW", self.good())["decision"], "WAIT")


if __name__ == "__main__":
    unittest.main()
