"""V155 static safeguards: historical audit HUD must reject invalid payloads."""
import unittest
from pathlib import Path


class HudValidationTests(unittest.TestCase):
    def test_audit_payload_validation_is_fail_closed(self):
        html=(Path(__file__).resolve().parents[1]/"web"/"office_3d.html").read_text(encoding="utf-8")
        hud=html.split("<!-- V154: read-only historical audit HUD;",1)[1]
        for expected in ("Number.isSafeInteger(a.candle_count)",
                         "Number.isSafeInteger(a.closed_trades)",
                         "Number.isFinite(a.realized_pnl)",
                         "Number.isFinite(a.max_drawdown_pct)",
                         "a.data_sha256",
                         'throw new Error("감사 결과 형식 오류")',
                         'status.textContent="검증 데이터 미연결"'):
            self.assertIn(expected,hud)


if __name__=="__main__":
    unittest.main()
