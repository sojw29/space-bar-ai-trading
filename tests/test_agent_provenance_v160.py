"""V160: inspector provenance is conditional on verified research data."""
import unittest
from pathlib import Path

class InspectorProvenanceTests(unittest.TestCase):
    def test_provenance_is_fail_closed(self):
        html=(Path(__file__).resolve().parents[1]/"web"/"office_3d.html").read_text(encoding="utf-8")
        for expected in ('id="selected-provenance"', 'id="selected-safety"',
                         'provenance.textContent=data?', 'sourceMode==="historical_csv"',
                         'sourceMode==="public_stream"', '"OFFLINE · 검증 데이터 없음"',
                         '"읽기 전용 · 주문 비활성 · 전략 실행 아님"'):
            self.assertIn(expected,html)
        self.assertIn('const data=hasValid?events.get(selected):null;',html)

if __name__=="__main__":
    unittest.main()
