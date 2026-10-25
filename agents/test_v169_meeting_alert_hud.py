"""V169 visual warning HUD contract: fail-closed and research only."""
import unittest
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "web" / "office_3d.html"


class AlertHudTests(unittest.TestCase):
    def test_warning_and_verified_states(self):
        html = PAGE.read_text(encoding="utf-8")
        for part in ('id="v169-alert-hud"', 'data-level="BLOCKED"',
                     'hud.dataset.level="BLOCKED"', 'hud.dataset.level="VERIFIED"',
                     'GUARDIAN VETO · COMMANDER WAIT',
                     'ATLAS VERIFIED · GUARDIAN CLEAR · COMMANDER WAIT',
                     'fetch("/api/v1/meeting",{cache:"no-store"})'):
            self.assertIn(part, html)

    def test_no_order_actions(self):
        html = PAGE.read_text(encoding="utf-8")
        for forbidden in ('fetch("/api/v1/orders"', 'createOrder(', 'innerHTML=', 'Math.random()'):
            self.assertNotIn(forbidden, html)


if __name__ == "__main__":
    unittest.main()
