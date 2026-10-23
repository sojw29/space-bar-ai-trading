"""V47 interactive agent office regression, static no-broker contract."""
import unittest
from pathlib import Path

HTML = Path(__file__).resolve().parent.parent / "web" / "command_center.html"

class OfficeV47Tests(unittest.TestCase):
    def setUp(self):
        self.html = HTML.read_text(encoding="utf-8")

    def test_seven_named_role_stations_and_spotlight(self):
        for label in ("ATLAS", "ORBIT", "ECHO", "PULSE",
                      "QUANT", "APEX", "COMMANDER"):
            self.assertIn(label, self.html)
        for phrase in ('id="trading-room"', 'id="office-spotlight"',
                       'roleLabels={', 'function renderSpotlight()',
                       'aria-label="신호 범례"', 'id="inspector-panel"'):
            self.assertIn(phrase, self.html)

    def test_accessible_selection_and_error_reset(self):
        for phrase in ('desk.setAttribute("role","button")',
                       'desk.setAttribute("tabindex","0")',
                       'event.key==="Enter"||event.key===" "',
                       'renderSpotlight();',
                       'station.desk.className="room-desk WAIT offline-station"',
                       'latestEvents.clear()', 'resetConsensus();',
                       'document.getElementById("feed-state")'):
            self.assertIn(phrase, self.html)

    def test_proper_disclosure_and_no_orders(self):
        for phrase in ("CSS 기반 2.5D", "실제 주문 불가",
                       "PAPER RESEARCH ONLY", "실제 3D 엔진"):
            self.assertIn(phrase, self.html)
        for unsafe in ("innerHTML=", 'fetch("/api/v1/orders"',
                       "<iframe", '<script src="https://'):
            self.assertNotIn(unsafe, self.html)

    def test_no_external_visual_dependencies(self):
        self.assertIn(".room-desk .avatar", self.html)
        self.assertIn(".office-legend", self.html)
        self.assertIn("@media(max-width:650px)", self.html)
        self.assertIn("prefers-reduced-motion:reduce", self.html)

if __name__ == "__main__":
    unittest.main(verbosity=2)
