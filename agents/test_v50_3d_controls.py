"""V50 WebGL scene navigation and backward-compatible read-only UI contracts."""
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parent))
from dashboard_api_v28 import make_handler

HTML=(Path(__file__).resolve().parent.parent/"web"/"office_3d.html")

class OfficeV50Tests(unittest.TestCase):
    def setUp(self):
        self.html=HTML.read_text(encoding="utf-8")

    def test_camera_presets_are_actual_interactive_controls(self):
        for marker in ('data-view="overview"','data-view="front"',
                       'data-view="top"','data-view="commander"',
                       'data-view="zoom-in"','data-view="zoom-out"',
                       'function setCameraView(view)', 'function updateCamera()',
                       'function resize()', 'pointercancel', 'lostpointercapture',
                       'button.addEventListener("click",()=>setCameraView(button.dataset.view))',
                       'button.setAttribute("aria-pressed"', 'id="camera-mode"'):
            self.assertIn(marker,self.html)

    def test_scene_shows_research_state_not_real_trade(self):
        for marker in ('id="office-legend"','new THREE.WebGLRenderer',
                       'new THREE.PerspectiveCamera','new THREE.GridHelper',
                       'new THREE.Raycaster','new THREE.CylinderGeometry',
                       'new THREE.HemisphereLight','new THREE.DirectionalLight',
                       'colors.OFFLINE','function resetResearch(reason)',
                       'function verifyEnvelope(payload)','PAPER RESEARCH ONLY'):
            self.assertIn(marker,self.html)
        for forbidden in ("innerHTML=", 'api/v1/orders', 'createOrder(',
                          'live_trading_approved:true', 'fetch("/api/v1/trade"',
                          'setInterval(openOrder'):
            self.assertNotIn(forbidden,self.html)

    def test_local_http_route_only_get_and_fallback(self):
        srv=ThreadingHTTPServer(("127.0.0.1",0),
            make_handler(Path("/missing.csv")))
        worker=threading.Thread(target=srv.serve_forever,daemon=True)
        worker.start()
        try:
            root=f"http://127.0.0.1:{srv.server_port}"
            with urlopen(root+"/office3d",timeout=3) as resp:
                self.assertEqual(resp.status,200)
                self.assertIn(b'data-view="commander"',resp.read())
            with urlopen(root+"/dashboard",timeout=3) as resp:
                self.assertIn(b'href="/office3d"',resp.read())
            with self.assertRaises(HTTPError) as err:
                urlopen(Request(root+"/office3d",data=b'{"order":"BUY"}',
                                method="POST"),timeout=3)
            self.assertEqual(err.exception.code,405)
        finally:
            srv.shutdown();srv.server_close();worker.join(timeout=3)

if __name__=="__main__":
    unittest.main(verbosity=2)
