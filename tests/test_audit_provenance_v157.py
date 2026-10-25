"""V157: reject non-offline provenance in both audit surfaces."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"web"

class ProvenanceTests(unittest.TestCase):
    def test_mobile_requires_offline_read_only(self):
        s=(ROOT/"audit_room_mobile_v153.html").read_text(encoding="utf-8")
        for t in ('body.mode!=="historical_offline_audit"', 'body.realtime!==false', 'body.orders_enabled!==false', 'body.signals_enabled!==false'):
            self.assertIn(t,s)

    def test_3d_requires_offline_read_only(self):
        s=(ROOT/"office_3d.html").read_text(encoding="utf-8")
        hud=s.split("<!-- V154: read-only historical audit HUD;",1)[1]
        for t in ('payload.mode!=="historical_offline_audit"', 'payload.realtime!==false', 'payload.orders_enabled!==false', 'payload.signals_enabled!==false'):
            self.assertIn(t,hud)

if __name__=="__main__":
    unittest.main()
