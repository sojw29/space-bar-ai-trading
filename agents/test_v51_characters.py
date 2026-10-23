"""V51 role-specific 3D agents and truthfulness/read-only contracts."""
import unittest
from pathlib import Path
HTML=Path(__file__).resolve().parent.parent/"web"/"office_3d.html"

class CharacterV51Tests(unittest.TestCase):
    def setUp(self):
        self.html=HTML.read_text(encoding="utf-8")
    def test_seven_unique_agent_styles_and_insignias(self):
        for name in ("ATLAS","ORBIT","ECHO","PULSE","QUANT","APEX","COMMANDER"):
            self.assertIn(name+":{body:",self.html)
        for insignia in ('"crest"','"satellite"','"antenna"','"pulse"',
                         '"cube"','"shield"','"crown"'):
            self.assertIn(insignia,self.html)
        self.assertIn("new THREE.TorusGeometry",self.html)
        self.assertIn("new THREE.OctahedronGeometry",self.html)
        self.assertIn("const insignia=new THREE.Group()",self.html)
    def test_status_only_from_verified_research_and_error_reset(self):
        for fragment in ('id="agent-activity"','hasValid?events.get(selected):null',
                         'function verifyEnvelope(payload)',
                         'seat.signalState=record.decision',
                         'seat.signalState="OFFLINE"',
                         'phase.dataset.status=data?"READY":"OFFLINE"',
                         'function resetResearch(reason)', 'if(reduced.matches)',
                         "실제 자율 작업 아님"):
            self.assertIn(fragment,self.html)
    def test_still_no_order_access(self):
        for unsafe in ('innerHTML=',"api/v1/orders",'createOrder(',
                       'apiKey', 'live_trading_approved:true'):
            self.assertNotIn(unsafe,self.html)
        self.assertIn("PAPER RESEARCH ONLY",self.html)
        self.assertIn('data-view="commander"',self.html)
        self.assertIn('href="/dashboard"',self.html)

if __name__=="__main__":
    unittest.main(verbosity=2)
