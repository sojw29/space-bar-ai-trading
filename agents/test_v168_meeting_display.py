"""V168 3D AI meeting status fail-closed display contracts."""
import unittest
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "web" / "office_3d.html"


class MeetingDisplayTests(unittest.TestCase):
    def test_read_only_meeting_panel(self):
        html = PAGE.read_text(encoding="utf-8")
        for part in ('id="v168-meeting"', 'id="v168-atlas"', 'id="v168-guardian"',
                     'id="v168-commander"', 'id="v168-meeting-status"',
                     'fetch("/api/v1/meeting",{cache:"no-store"})',
                     'function blocked(reason)', 'gate.quality_verified===true',
                     'data.orders_enabled!==false', 'data.live_trading_approved!==false',
                     'commander.textContent="WAIT"'):
            self.assertIn(part, html)

    def test_no_order_actions(self):
        html = PAGE.read_text(encoding="utf-8")
        for forbidden in ('fetch("/api/v1/orders"', 'createOrder(', 'Math.random()', 'innerHTML='):
            self.assertNotIn(forbidden, html)


if __name__ == "__main__":
    unittest.main()
