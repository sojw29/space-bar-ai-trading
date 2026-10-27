"""V182 fail-closed unified meeting integrity UI contract."""
import unittest
from pathlib import Path


class IntegritySummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).resolve().parents[1] / "web" / "office_3d.html").read_text(encoding="utf-8")

    def test_integrity_dimensions(self):
        for token in ('id="v182-integrity-summary"', 'function renderIntegritySummary()', 'ev.source==="offline_v65_quality_report"', 'hasVerifiedMeetingEvidence(meeting)', 'gate.risk_veto===false', 'meeting.agents.COMMANDER.decision==="WAIT"', 'meeting.orders_enabled===false', 'meeting.live_trading_approved===false', 'Boolean(sourceOk&&gateOk&&agentsOk&&researchOk)'):
            self.assertIn(token, self.html)

    def test_fail_closed_on_disconnect_and_refresh(self):
        self.assertIn('latestMeeting=null;\n  renderIntegritySummary();', self.html)
        self.assertIn('latestMeeting=data;\n   renderIntegritySummary();', self.html)
        self.assertIn('integritySummary.dataset.level=safe?"VERIFIED":"BLOCKED";', self.html)

    def test_missing_or_invalid_evidence_fails_closed(self):
        import re
        import subprocess
        self.assertIn('const safe=verified&&hasVerifiedMeetingEvidence(data)&&', self.html)
        match = re.search(r' function hasVerifiedMeetingEvidence\\(meeting\\)\\{.*?\\n \\}', self.html, re.S)
        self.assertIsNotNone(match)
        script = match.group(0) + """
const base={evidence:{source:"offline_v65_quality_report",sha256:"a".repeat(64),bytes:100,verified:true}};
const invalid=[
  null, {}, {evidence:null},
  {evidence:{...base.evidence,source:"unknown"}},
  {evidence:{...base.evidence,sha256:"bad"}},
  {evidence:{...base.evidence,bytes:0}},
  {evidence:{...base.evidence,verified:false}}
];
if(!hasVerifiedMeetingEvidence(base)||invalid.some(hasVerifiedMeetingEvidence))process.exit(1);
"""
        subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    def test_no_claim_of_market_accuracy(self):
        self.assertIn('파일 지문은 시장 정확성을 증명하지 않음', self.html)
        self.assertIn('NO ORDERS', self.html)


if __name__ == "__main__":
    unittest.main()
