"""V49 read-only 3D office route, safety and compatibility contract."""
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen

import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from dashboard_api_v28 import make_handler

ROOT=Path(__file__).resolve().parent.parent
PAGE=ROOT/"web"/"office_3d.html"
OLD=ROOT/"web"/"command_center.html"


class WebGL3DOfficeTests(unittest.TestCase):
    def test_real_three_scene_components(self):
        html=PAGE.read_text(encoding="utf-8")
        for marker in ('type="module"', 'three@0.180.0/build/three.module.js',
                       'new THREE.WebGLRenderer', 'new THREE.Scene()',
                       'new THREE.PerspectiveCamera', 'THREE.Raycaster',
                       'new THREE.BoxGeometry', 'new THREE.SphereGeometry',
                       'new THREE.CylinderGeometry',
                       'renderer.domElement.addEventListener("pointerup"',
                       'setInterval(refresh,30000)', '/api/v1/agents',
                       'aria-pressed', 'PAPER RESEARCH ONLY'):
            self.assertIn(marker,html)

    def test_no_orders_keys_or_remote_broker(self):
        html=PAGE.read_text(encoding="utf-8")
        for forbidden in ('innerHTML=', 'api/v1/orders', 'api/v1/trade',
                          'apiKey', 'api_secret', 'createOrder(', 'POST"',
                          'wss://', 'Binance.FuturesOrder'):
            self.assertNotIn(forbidden,html)
        self.assertIn('payload.orders_enabled!==false',html)
        self.assertIn('payload.live_trading_approved!==false',html)
        self.assertIn('resetResearch(',html)

    def test_dashboard_remains_default_and_links_3d(self):
        html=OLD.read_text(encoding="utf-8")
        self.assertIn('href="/office3d"',html)
        self.assertIn('id="trading-room"',html)
        self.assertIn('PAPER RESEARCH ONLY',html)

    def test_http_page_and_post_denial(self):
        server=ThreadingHTTPServer(("127.0.0.1",0),
                                   make_handler(Path("/missing-history.csv")))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        root="http://127.0.0.1:%s" % server.server_port
        try:
            with urlopen(root+"/office3d",timeout=3) as result:
                self.assertEqual(result.status,200)
                self.assertIn("text/html",result.headers["Content-Type"])
                self.assertIn(b"new THREE.WebGLRenderer",result.read())
            with urlopen(root+"/dashboard",timeout=3) as result:
                self.assertIn(b"id=\"trading-room\"",result.read())
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(root+"/office3d",data=b'{"order":"BUY"}',
                                method="POST"),timeout=3)
            self.assertEqual(error.exception.code,405)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__=="__main__":
    unittest.main(verbosity=2)
