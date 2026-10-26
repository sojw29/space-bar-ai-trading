"""V180 meeting evidence comparison presentation contract."""
import unittest
from pathlib import Path


class EvidenceCompareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).resolve().parents[1] / "web" / "office_3d.html").read_text(encoding="utf-8")

    def test_compare_only_observed_fingerprints(self):
        for token in ('id="v180-evidence-compare"', 'historyEntries.filter(item=>item.source!=="NO VERIFIED EVIDENCE")', 'entries.find(item=>current&&item.source!==current.source)', 'renderEvidenceCompare();'):
            self.assertIn(token, self.html)

    def test_no_fabricated_verification(self):
        for token in ('검증 가능한 SHA-256 관측 없음', '비교할 다른 지문 없음', '시장 정확성 증명 아님', '내용 개선 또는 거래 성과를 의미하지 않음'):
            self.assertIn(token, self.html)

    def test_safe_text_output(self):
        self.assertIn('evidenceCompare.textContent=', self.html)
        self.assertNotIn('evidenceCompare.innerHTML=', self.html)


if __name__ == "__main__":
    unittest.main()
