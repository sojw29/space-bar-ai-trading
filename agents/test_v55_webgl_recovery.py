"""V55 local WebGL runtime recovery and no-order fallback contracts."""
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parent))
from dashboard_api_v28 import make_handler

HTML=Path(__file__).resolve().parent.parent/"web"/"office_3d.html"
class WebGLRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.html=HTML.read_text(encoding="utf-8")
    def test_classic_boot_watchdog_survives_module_load_failure(self):
        for fragment in ('id="webgl-fallback"','href="/dashboard"',
                         'window.spacebar3DReady=function()',
                         'window.spacebar3DFailed=fail',
                         'stage.dataset.renderReady="true"',
                         'if(stage.dataset.renderReady!=="true")fail(',
                         'window.addEventListener("unhandledrejection"',
                         'window.addEventListener("error"',
                         'getContext("webgl2")||canvas.getContext("webgl")',
                         '<script>','<script type="module">'):
            self.assertIn(fragment,self.html)
        self.assertLess(self.html.index('<script>'),self.html.index('<script type="module">'))
    def test_context_loss_blocks_research_and_renderer_until_restore(self):
        for fragment in ('renderer.domElement.addEventListener("webglcontextlost"',
                         'renderer.domElement.addEventListener("webglcontextrestored"',
                         'event.preventDefault();',
                         'webglContextLost=true;',
                         'if(webglContextLost||refreshActive)return;',
                         'stopRendering();',
                         'resetResearch(reason);',
                         'if(webglContextLost||document.hidden)return;',
                         'if(document.hidden)stopRendering();',
                         'resetResearch("화면 복귀 · 신규 데이터 검증 중")',
                         'window.spacebar3DReady();'):
            self.assertIn(fragment,self.html)
    def test_preserves_research_only_controls(self):
        for fragment in ('PAPER RESEARCH ONLY','id="operations-panel"',
                         'id="commander-consensus-panel"',
                         'function drawMarketWall(board)',
                         'function renderCommanderConsensus(verified)',
                         'payload.orders_enabled!==false'):
            self.assertIn(fragment,self.html)
        for banned in ('innerHTML=', 'api/v1/orders','createOrder(',
                       'apiKey', 'fetch("/api/v1/trade"'):
            self.assertNotIn(banned,self.html)
    def test_local_route_get_and_post_denied(self):
        server=ThreadingHTTPServer(("127.0.0.1",0),make_handler(Path("/absent.csv")))
        t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        base=f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base+"/office3d",timeout=3) as resp:
                self.assertIn(b'id="webgl-fallback"',resp.read())
            with urlopen(base+"/dashboard",timeout=3) as resp:
                self.assertIn(b'id="trading-room"',resp.read())
            with self.assertRaises(HTTPError) as e:
                urlopen(Request(base+"/office3d",method="POST",data=b'{"BUY":true}'),timeout=3)
            self.assertEqual(e.exception.code,405)
        finally:
            server.shutdown();server.server_close();t.join(timeout=3)
if __name__=="__main__":unittest.main(verbosity=2)
