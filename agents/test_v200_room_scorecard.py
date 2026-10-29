"""V200 3D office scorecard local import contract."""
import unittest
from pathlib import Path


ROOM = Path(__file__).resolve().parents[1] / "web" / "office_3d.html"


class RoomScorecardTests(unittest.TestCase):
    def test_local_file_import_and_safe_dom(self):
        html = ROOM.read_text(encoding="utf-8")
        self.assertIn('id="v200-scorecard-file"', html)
        self.assertIn('id="v200-scorecard-table" hidden', html)
        self.assertIn('file.text()', html)
        self.assertIn('JSON.parse(await file.text())', html)
        self.assertIn('file.size>2000000', html)
        self.assertIn('td.textContent=String(row[key])', html)
        self.assertIn('tbody.replaceChildren(fragment)', html)

    def test_fail_closed_flags_and_no_ranking(self):
        html = ROOM.read_text(encoding="utf-8")
        for token in ('data.orders_enabled!==false',
                      'data.live_trading_approved!==false',
                      'card.ranking_enabled!==false',
                      'card.strategy_selection_enabled!==false',
                      'card.orders_allowed!==false',
                      'card.live_trading_approved!==false',
                      'card.status!=="RESEARCH_COMPARISON_ONLY"'):
            self.assertIn(token, html)


if __name__ == "__main__":
    unittest.main()
