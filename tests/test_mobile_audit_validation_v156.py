"""V156 static regression: mobile audit must validate before VERIFIED."""
import unittest
from pathlib import Path


class MobileAuditValidation(unittest.TestCase):
    def test_mobile_fail_closed(self):
        html=(Path(__file__).resolve().parents[1]/"web"/"audit_room_mobile_v153.html").read_text(encoding="utf-8")
        for token in ("function validateAudit(a)", "Number.isSafeInteger(a.candle_count)",
                      "Number.isFinite(a.realized_pnl)", "Number.isFinite(a.max_drawdown_pct)",
                      "a.data_sha256", 'throw new Error("감사 결과 형식 오류")',
                      'status.textContent="데이터 미연결"'):
            self.assertIn(token,html)
        self.assertLess(html.index("validateAudit(body.audit);render(body.audit)"),
                        html.index('status.textContent="HISTORICAL · VERIFIED"'))


if __name__=="__main__":
    unittest.main()
