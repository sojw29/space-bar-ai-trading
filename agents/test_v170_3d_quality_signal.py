"""V170 3D research quality veto visual contract."""
import unittest
from pathlib import Path

PAGE=Path(__file__).resolve().parent.parent/"web"/"office_3d.html"


class MeetingQualityVisualTests(unittest.TestCase):
    def test_quality_event_and_3d_agents(self):
        html=PAGE.read_text(encoding="utf-8")
        for part in ('window.addEventListener("spacebar:meeting-quality"',
                     'window.dispatchEvent(new CustomEvent("spacebar:meeting-quality"',
                     'keys.get("APEX")', 'keys.get("COMMANDER")',
                     'risk.group.userData.qualityVeto=!verified',
                     'chief.group.userData.qualityDecision="WAIT"',
                     'risk.screen.material.color.setHex',
                     'chief.screen.material.color.setHex'):
            self.assertIn(part,html)

    def test_read_only(self):
        html=PAGE.read_text(encoding="utf-8")
        for part in ('fetch("/api/v1/meeting",{cache:"no-store"})',
                     'data.orders_enabled!==false','data.live_trading_approved!==false'):
            self.assertIn(part,html)
        for bad in ('createOrder(', 'innerHTML=', 'Math.random()'):
            self.assertNotIn(bad,html)


if __name__=="__main__":
    unittest.main()
