"""V161 static guardrails for completed-candle age disclosure."""
import unittest
from pathlib import Path

class CandleAgeTests(unittest.TestCase):
    def test_historical_age_is_not_labeled_live(self):
        html=(Path(__file__).resolve().parents[1]/"web"/"office_3d.html").read_text(encoding="utf-8")
        for token in ('id="selected-candle-age"', 'if(!data){ageField.textContent="OFFLINE · 검증 데이터 없음";}',
                      'Date.now()-Date.parse(lastObserved)', 'Number.isFinite(elapsed)',
                      'sourceMode==="historical_csv"?', '(실시간 아님)',
                      'sourceMode==="public_stream"?', '"시간 검증 불가"'):
            self.assertIn(token,html)

if __name__=="__main__":
    unittest.main()
