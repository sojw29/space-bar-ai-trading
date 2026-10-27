"""V185: research release manifest contract tests."""
import unittest
from pathlib import Path

HTML = Path("web/office_3d.html").read_text(encoding="utf-8")

class V185ReleaseManifestTests(unittest.TestCase):
    def test_manifest_exists_and_is_read_only(self):
        self.assertIn('id="v185-release-manifest"', HTML)
        self.assertIn("RESEARCH RELEASE", HTML)
        self.assertIn("실거래 승인 아님", HTML)

    def test_manifest_requires_evidence_gate_and_agents(self):
        for token in (
            'ev.source==="offline_v65_quality_report"',
            'ev.verified===true',
            'gate.quality_verified===true',
            'gate.quality_status==="PASS"',
            'gate.risk_veto===false',
            'meeting.agents.ATLAS.state==="DATA_VERIFIED"',
            'meeting.agents.GUARDIAN.state==="CLEAR"',
            'meeting.agents.COMMANDER.decision==="WAIT"',
        ):
            self.assertIn(token, HTML)

    def test_manifest_requires_research_only_contract(self):
        self.assertIn('meeting.research_only===true&&meeting.orders_enabled===false&&meeting.live_trading_approved===false', HTML)
        self.assertIn('passed===checks.length?"VERIFIED RESEARCH RELEASE":"BLOCKED RESEARCH RELEASE"', HTML)
        self.assertNotIn("live_trading_approved=true", HTML)
        self.assertNotIn("orders_enabled=true", HTML)

if __name__ == "__main__":
    unittest.main()
