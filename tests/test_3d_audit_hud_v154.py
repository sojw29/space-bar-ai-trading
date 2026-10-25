"""V154: static guardrails for the 3D historical audit HUD."""
import unittest
from pathlib import Path

HTML = Path(__file__).resolve().parents[1] / "web" / "office_3d.html"


class AuditHudTests(unittest.TestCase):
    def test_read_only_hud_present(self):
        text = HTML.read_text(encoding="utf-8")
        self.assertIn('id="v154-audit-hud"', text)
        self.assertIn('fetch("/api/v1/replay/audit"', text)
        self.assertIn('payload.realtime!==false', text)
        self.assertIn('payload.orders_enabled!==false', text)
        self.assertIn('href="/audit-room"', text)

    def test_no_order_controls_in_hud(self):
        text = HTML.read_text(encoding="utf-8")
        hud = text.split("<!-- V154: read-only historical audit HUD;", 1)[1]
        self.assertNotIn("fetch('/api/v1/order", hud)
        self.assertNotIn("method:'POST'", hud)


if __name__ == "__main__":
    unittest.main()
