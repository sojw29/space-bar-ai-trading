"""V54 read-only operations visibility contracts, including feed API safety."""
import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard_api_v28 import make_handler
from live_dashboard_v39 import LiveResearchStore

PAGE=Path(__file__).resolve().parent.parent/"web"/"office_3d.html"

class OperationPanelTests(unittest.TestCase):
    def setUp(self):
        self.html=PAGE.read_text(encoding="utf-8")

    def test_panel_discloses_source_health_and_clock(self):
        for part in ('id="operations-panel"','id="ops-research"',
                     'id="ops-feed"','id="ops-candle-age"',
                     'id="ops-now"','id="ops-check"',
                     '실제 거래소 계좌의 연결 상태',
                     'function verifyFeedStatus()',
                     'function updateOpsClock()',
                     'const OPS_LIVE_MAX_AGE_MS=12*60*1000'):
            self.assertIn(part,self.html)

    def test_feed_agent_crosscheck_and_staleness_fails_closed(self):
        for part in ('fetch("/api/v1/feed",{cache:"no-store"})',
                     'feed.orders_enabled!==false',
                     'feed.ready===true&&state==="RESEARCH_READY"',
                     'verified.realtime!==feedIsLive',
                     'if(opsRealtime&&age>OPS_LIVE_MAX_AGE_MS)',
                     'resetResearch("확정된 공개 스트림 캔들이 오래되었습니다")',
                     'setOpsField("ops-feed","연결 확인 실패 / 사용 불가","error")',
                     'setInterval(updateOpsClock,5000)',
                     'resetCommanderConsensus();',
                     'clearMarketWall("분석 연결 종료 / 데이터 무효")'):
            self.assertIn(part,self.html)

    def test_no_trade_privileges_and_previous_scene_intact(self):
        for part in ('PAPER RESEARCH ONLY','new THREE.WebGLRenderer',
                     'function renderCommanderConsensus(verified)',
                     'function drawMarketWall(board)',
                     'function setCameraView(view)'):
            self.assertIn(part,self.html)
        for dangerous in ('innerHTML=', 'api/v1/orders','createOrder(',
                          'apiKey', 'fetch("/api/v1/trade"', 'Math.random()'):
            self.assertNotIn(dangerous,self.html)

    def test_same_origin_feed_endpoint_and_no_post(self):
        server=ThreadingHTTPServer(("127.0.0.1",0),
            make_handler(Path("/missing.csv"),live_store=LiveResearchStore()))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        root="http://127.0.0.1:%s" % server.server_port
        try:
            with urlopen(root+"/api/v1/feed",timeout=3) as res:
                feed=json.load(res)
                self.assertEqual(feed["state"],"NOT_STARTED")
                self.assertFalse(feed["ready"])
                self.assertFalse(feed["orders_enabled"])
            with urlopen(root+"/office3d",timeout=3) as res:
                self.assertIn(b'id="operations-panel"',res.read())
            with self.assertRaises(HTTPError) as err:
                urlopen(Request(root+"/api/v1/feed",method="POST",
                                data=b'{"BUY":true}'),timeout=3)
            self.assertEqual(err.exception.code,405)
        finally:
            server.shutdown();server.server_close();thread.join(timeout=3)

if __name__=="__main__":
    unittest.main(verbosity=2)
