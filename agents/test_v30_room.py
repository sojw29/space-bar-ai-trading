"""V30 isometric UI static contract tests (stdlib only)."""
import unittest
from pathlib import Path

HTML = Path(__file__).resolve().parent.parent / "web" / "command_center.html"


class RoomTests(unittest.TestCase):
    def test_room_has_seven_dynamic_stations(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertIn('id="trading-room"', html)
        self.assertIn('for(const id of ids)', html)
        self.assertIn('roomNodes.set(id', html)
        self.assertIn('station.desk.className="room-desk "+decision', html)
        self.assertIn('id==="COMMANDER"', html)

    def test_no_external_resources_or_trade_execution(self):
        html = HTML.read_text(encoding="utf-8")
        self.assertNotIn("<iframe", html)
        self.assertNotIn("https://", html)
        self.assertNotIn('fetch("/api/v1/orders"', html)
        self.assertIn("PAPER RESEARCH ONLY", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
