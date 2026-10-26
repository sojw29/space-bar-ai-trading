"""V172: static read-only meeting evidence HUD contract."""
import unittest
from pathlib import Path


class MeetingEvidenceHudTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).resolve().parents[1] / "web" / "office_3d.html").read_text(encoding="utf-8")

    def test_evidence_panel_and_safe_default(self):
        self.assertIn('id="v172-evidence"', self.html)
        self.assertIn('data-verified="false"', self.html)
        self.assertIn("EVIDENCE · MISSING OR UNVERIFIED", self.html)

    def test_fingerprint_requires_valid_contract(self):
        for token in ('source.source==="offline_v65_quality_report"', '/^[a-f0-9]{64}$/.test(source.sha256)', 'Number.isSafeInteger(source.bytes)', 'source.verified===true', 'gate.quality_verified===true'):
            self.assertIn(token, self.html)

    def test_only_read_only_meeting_endpoint(self):
        self.assertIn('fetch("/api/v1/meeting",{cache:"no-store"})', self.html)
        self.assertIn('showEvidence(null);', self.html)
        self.assertIn('showEvidence(data);', self.html)
        self.assertIn('data.orders_enabled!==false', self.html)


if __name__ == "__main__":
    unittest.main()
