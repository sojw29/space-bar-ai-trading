"""V184: fail-closed live-readiness audit contract tests."""
import unittest
from pathlib import Path

HTML = Path("web/office_3d.html").read_text(encoding="utf-8")


class V184ReadinessAuditTests(unittest.TestCase):
    def test_audit_is_explicitly_research_only(self):
        self.assertIn('id="v184-readiness-audit"', HTML)
        self.assertIn("BLOCKED · RESEARCH ONLY", HTML)

    def test_audit_checks_provenance_and_quality(self):
        for token in (
            'ev.source==="offline_v65_quality_report"',
            'ev.verified===true',
            'gate.quality_verified===true',
            'gate.quality_status==="PASS"',
            'gate.risk_veto===false',
        ):
            self.assertIn(token, HTML)

    def test_audit_checks_agent_consensus(self):
        for token in (
            'meeting.agents.ATLAS.state==="DATA_VERIFIED"',
            'meeting.agents.GUARDIAN.state==="CLEAR"',
            'meeting.agents.COMMANDER.decision==="WAIT"',
        ):
            self.assertIn(token, HTML)

    def test_live_transition_is_hard_blocked(self):
        self.assertIn('const blockers=[];', HTML)
        self.assertIn('live_not_approved:Boolean(meeting&&meeting.live_trading_approved===false)', HTML)
        self.assertIn('orders_disabled:Boolean(meeting&&meeting.orders_enabled===false)', HTML)
        self.assertIn('research_only:Boolean(meeting&&meeting.research_only===true)', HTML)
        self.assertNotIn('live_trading_approved=true', HTML)
        self.assertNotIn('orders_enabled=true', HTML)


if __name__ == "__main__":
    unittest.main()
