"""V53 COMMANDER 3D consensus, veto and read-only regression tests."""
import sys
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parent))
from dashboard_api_v28 import make_handler

PAGE=Path(__file__).resolve().parent.parent/"web"/"office_3d.html"

class CommanderRoomTests(unittest.TestCase):
    def setUp(self):
        self.html=PAGE.read_text(encoding="utf-8")
    def test_3d_consensus_has_true_scene_and_six_links(self):
        for snippet in ('new THREE.CanvasTexture(consensusCanvas)',
                        'new THREE.PlaneGeometry(3.05,3.05)',
                        'new THREE.LineBasicMaterial',
                        'consensusLinks=new Map()',
                        'voteNames=names.filter(name=>name!=="COMMANDER")',
                        'function renderCommanderConsensus(verified)',
                        'function paintConsensusWall(result)',
                        'const entry=data.get(id)',
                        'consensusLinks.get(id).material.color.setHex(colors[decision])'):
            self.assertIn(snippet,self.html)
    def test_veto_tally_and_offline_fail_closed(self):
        for snippet in ('id="commander-tally"', 'id="commander-veto"',
                        'id="commander-decision"', 'id="commander-votes"',
                        'function resetCommanderConsensus()',
                        'resetCommanderConsensus();\n clearMarketWall',
                        'renderCommanderConsensus(verified);',
                        'expected!==commander.decision',
                        'longs!==commander.long_votes',
                        'shorts!==commander.short_votes',
                        'veto.dataset.risk=commander.risk_veto?"BLOCKED":"CLEAR"',
                        'g.fillText("NO VERIFIED VOTES"'):
            self.assertIn(snippet,self.html)
    def test_does_not_create_orders_or_fake_votes(self):
        for banned in ('Math.random()', 'innerHTML=', 'fetch("/api/v1/orders"',
                       'createOrder(', 'wss://', 'marketOrder('):
            self.assertNotIn(banned,self.html)
        self.assertIn('PAPER RESEARCH ONLY',self.html)
        self.assertIn('commander.risk_veto?"WAIT"',self.html)
        self.assertIn('payload.orders_enabled!==false',self.html)
    def test_local_route_post_is_rejected(self):
        server=ThreadingHTTPServer(("127.0.0.1",0),make_handler(Path("/missing.csv")))
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        base=f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base+"/office3d",timeout=3) as response:
                page=response.read().decode("utf-8")
                self.assertIn('id="commander-consensus-panel"',page)
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(base+"/office3d",method="POST",data=b'{"BUY":true}'),timeout=3)
            self.assertEqual(error.exception.code,405)
        finally:
            server.shutdown();server.server_close();worker.join(timeout=2)

if __name__=="__main__":
    unittest.main(verbosity=2)
