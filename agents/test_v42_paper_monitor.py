"""V42 tests: injected public events, paper position, risk halts, HTTP read-only."""
import copy
import json
import sys
import threading
import unittest
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen, Request

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_events_v27 as ev
from dashboard_api_v28 import make_handler
from paper_monitor_v42 import LocalPaperMonitor, MAX_AGE

START=1700000100-(1700000100%300)


def packet(n, price=110.0):
    candles=[]
    for i in range(55):
        p=100+i*.23
        candles.append({"timestamp":START+i*300,"open":p-.01,
                        "high":p+.2,"low":p-.2,"close":p,"volume":20})
    envelope=copy.deepcopy(ev.analyze_and_emit(candles))
    ts=START+n*300
    iso=datetime.fromtimestamp(ts,timezone.utc).isoformat()
    envelope["observed_candle_utc"]=iso
    for item in envelope["events"]:
        item["observed_candle_utc"]=iso
    return {"type":"research_events","source":"public_binance_usdm_ws",
            "realtime_transport":True,"paper_only":True,"orders_enabled":False,
            "closed_candle":{"timestamp":ts,"open":price,
                             "high":price+.1,"low":price-.1,
                             "close":price,"volume":20,"closed":True},
            "payload":envelope}


class PaperMonitorTests(unittest.TestCase):
    def setUp(self):
        self.clock=[START+54*300+310]
        self.monitor=LocalPaperMonitor(clock=lambda:self.clock[0])

    def test_signal_opens_paper_then_later_close_exits(self):
        self.monitor.consume({"type":"feed_status","state":"WARMING_UP","orders_enabled":False})
        self.monitor.consume(packet(54))
        state=self.monitor.snapshot()
        self.assertEqual(state["state"],"SIMULATING")
        self.assertEqual(state["position"]["side"],"LONG")
        self.assertFalse(state["orders_enabled"])
        self.assertIsNotNone(state["paper_mark_to_close_equity"])
        self.clock[0]+=300
        self.monitor.consume(packet(55,price=108.0))
        out=self.monitor.snapshot()
        self.assertIsNone(out["position"])
        self.assertGreaterEqual(out["paper_trade_event_count"],2)

    def test_feed_disconnect_latches_halt(self):
        self.monitor.consume(packet(54))
        self.monitor.consume({"type":"feed_status","state":"DISCONNECTED","orders_enabled":False})
        self.assertEqual(self.monitor.snapshot()["state"],"HALTED")
        self.monitor.consume({"type":"feed_status","state":"WARMING_UP","orders_enabled":False})
        self.assertEqual(self.monitor.snapshot()["state"],"HALTED")
        self.assertIsNone(self.monitor.snapshot()["paper_mark_to_close_equity"])

    def test_stale_event_is_rejected_and_halts(self):
        self.clock[0]+=MAX_AGE+500
        with self.assertRaises(ValueError):
            self.monitor.consume(packet(54))
        self.assertEqual(self.monitor.snapshot()["state"],"HALTED")

    def test_stale_mark_halts_without_feed_event(self):
        self.monitor.consume(packet(54))
        self.clock[0]+=MAX_AGE+1
        self.assertEqual(self.monitor.snapshot()["state"],"HALTED")
        self.assertIsNone(self.monitor.snapshot()["paper_mark_to_close_equity"])

    def test_missing_matched_candle_fail_closed(self):
        p=packet(54)
        p.pop("closed_candle")
        with self.assertRaises(ValueError):
            self.monitor.consume(p)
        self.assertEqual(self.monitor.snapshot()["state"],"HALTED")

    def test_gap_halts(self):
        self.monitor.consume(packet(54))
        self.clock[0]+=600
        with self.assertRaises(ValueError):
            self.monitor.consume(packet(56))
        self.assertEqual(self.monitor.snapshot()["state"],"HALTED")

    def test_read_only_api(self):
        server=ThreadingHTTPServer(("127.0.0.1",0),
             make_handler(Path("/absent.csv"),paper_monitor=self.monitor))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        url="http://127.0.0.1:%d/api/v1/paper" % server.server_port
        try:
            with urlopen(url,timeout=3) as response:
                body=json.load(response)
                self.assertEqual(body["mode"],"LOCAL_PAPER_SIMULATION")
                self.assertFalse(body["orders_enabled"])
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(url,data=b"{}",method="POST"),timeout=3)
            self.assertEqual(error.exception.code,405)
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)


if __name__=="__main__":
    unittest.main(verbosity=2)
