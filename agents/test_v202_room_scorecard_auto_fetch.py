"""V202 same-origin scorecard fetch UI static contract."""
import unittest
from pathlib import Path


ROOM = Path(__file__).resolve().parents[1] / "web" / "office_3d.html"


class ScorecardAutoFetchTests(unittest.TestCase):
    def test_fetch_uses_fixed_local_route_and_no_store(self):
        html = ROOM.read_text(encoding="utf-8")
        self.assertIn('fetch("/api/v1/research/scorecard"', html)
        self.assertIn('method:"GET",cache:"no-store",credentials:"same-origin"', html)
        self.assertIn('id="v202-scorecard-refresh"', html)
        self.assertIn('refresh.addEventListener("click",loadLocalSnapshot)', html)
        self.assertIn('if(location.protocol==="http:"||location.protocol==="https:")loadLocalSnapshot()', html)

    def test_fallback_and_validation(self):
        html = ROOM.read_text(encoding="utf-8")
        self.assertIn('file.size>2000000', html)
        self.assertIn('raw.length>2000000', html)
        self.assertIn('renderRows(validate(JSON.parse(raw))', html)
        self.assertIn('renderRows(validate(data),"직접 선택한 파일")', html)
        self.assertIn('td.textContent=String(row[key])', html)
        self.assertIn('card.orders_allowed!==false', html)
        self.assertIn('card.strategy_selection_enabled!==false', html)


if __name__ == "__main__":
    unittest.main()
