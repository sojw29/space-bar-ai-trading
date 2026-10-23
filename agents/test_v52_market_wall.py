"""V52 verified read-only BTC chart contract and 3D research-wall integration."""
import json
import sys
import tempfile
import threading
import unittest
from datetime import datetime,timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen,Request
sys.path.insert(0,str(Path(__file__).resolve().parent))
from market_board_v52 import market_board
from dashboard_api_v28 import make_handler
from live_dashboard_v39 import LiveResearchStore
import agent_events_v27 as events
from closed_candle_stream_v37 import ClosedCandleStream

BASE=1700000100-(1700000100%300)
NOW=BASE+65*300

def bars(n=60):
    return [{"timestamp":BASE+i*300,
             "open":100+i*.1-.02,"high":100+i*.1+.15,
             "low":100+i*.1-.15,"close":100+i*.1,
             "volume":20+i} for i in range(n)]

class MarketBoardTests(unittest.TestCase):
    def test_ohlcv_contract_and_provenance(self):
        report=market_board(bars(60),realtime=False,
                           source="historical_csv_snapshot",now=NOW)
        self.assertEqual(len(report["candles"]),60)
        self.assertFalse(report["orders_enabled"])
        self.assertFalse(report["realtime"])
        with self.assertRaises(ValueError):
            market_board(bars(),realtime=True,source="historical_csv_snapshot",now=NOW)
        with self.assertRaises(ValueError):
            market_board(bars(),realtime=True,source="public_binance_usdm_ws",now=NOW+10000)

    def test_duplicate_future_and_malformed_bars_fail(self):
        cases=[]
        bad=bars();bad[12]["timestamp"]=bad[11]["timestamp"];cases.append(bad)
        bad=bars();bad[5]["close"]=float("nan");cases.append(bad)
        bad=bars();bad[5]["high"]=bad[5]["low"]-.01;cases.append(bad)
        bad=bars();bad[5]["volume"]=-1;cases.append(bad)
        for case in cases:
            with self.subTest(case=case[5]):
                with self.assertRaises(ValueError):
                    market_board(case,realtime=False,
                                 source="historical_csv_snapshot",now=NOW)
        with self.assertRaises(ValueError):
            market_board(bars(),realtime=False,
                         source="historical_csv_snapshot",now=BASE+300)

    def test_live_store_chart_is_fresh_and_reset_on_disconnect(self):
        sample=bars(55)
        stream=ClosedCandleStream(now=lambda:NOW)
        envelope=None
        for row in sample:
            envelope=stream.ingest({**row,"closed":True})
        self.assertIsNotNone(envelope)
        clock=[sample[-1]["timestamp"]+320]
        store=LiveResearchStore(clock=lambda:clock[0])
        store.consume({"type":"feed_status","state":"WARMING_UP","orders_enabled":False})
        store.consume({"type":"research_events","source":"public_binance_usdm_ws",
                       "realtime_transport":True,"paper_only":True,"orders_enabled":False,
                       "payload":envelope,
                       "market_candles":stream.recent_closed_candles(60)})
        report=store.market_snapshot()
        self.assertEqual(report["last_closed_timestamp"],sample[-1]["timestamp"])
        report["candles"][-1]["close"]=99999
        self.assertNotEqual(store.market_snapshot()["candles"][-1]["close"],99999)
        store.consume({"type":"feed_status","state":"DISCONNECTED","orders_enabled":False})
        with self.assertRaises(RuntimeError):store.market_snapshot()

    def test_historical_http_and_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/"bars.csv"
            with file.open("w",encoding="utf-8") as fp:
                fp.write("timestamp,open,high,low,close,volume\n")
                for b in bars():fp.write(",".join(str(b[k]) for k in
                    ("timestamp","open","high","low","close","volume"))+"\n")
            server=ThreadingHTTPServer(("127.0.0.1",0),make_handler(file))
            worker=threading.Thread(target=server.serve_forever,daemon=True)
            worker.start()
            url="http://127.0.0.1:%d/api/v1/market" % server.server_port
            try:
                with urlopen(url,timeout=3) as resp:
                    report=json.load(resp)
                self.assertFalse(report["realtime"])
                self.assertEqual(len(report["candles"]),60)
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(url,method="POST",data=b'{"BUY":1}'),timeout=3)
                self.assertEqual(error.exception.code,405)
            finally:
                server.shutdown();server.server_close();worker.join(timeout=3)

    def test_3d_scene_displays_verified_candles_never_random_series(self):
        html=(Path(__file__).resolve().parent.parent/"web"/"office_3d.html").read_text()
        for term in ('new THREE.CanvasTexture','new THREE.PlaneGeometry',
                     'function verifyMarketBoard(board,research)',
                     'function drawMarketWall(board)','function clearMarketWall(reason)',
                     'function refreshMarketWall(research)',
                     'fetch("/api/v1/market"', 'board.realtime!==research.realtime',
                     'last.timestamp*1000!==Date.parse(research.when)',
                     'await refreshMarketWall(verified)'):
            self.assertIn(term,html)
        for bad in ('Math.random()', 'innerHTML=', 'fetch("/api/v1/orders"'):
            self.assertNotIn(bad,html)

if __name__=="__main__":unittest.main(verbosity=2)
