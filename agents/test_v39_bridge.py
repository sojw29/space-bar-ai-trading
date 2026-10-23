"""V39 bridge tests with injected clock; HTTP only over local loopback."""
import json
import sys
import threading
import unittest
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen
sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_events_v27 as v27
from dashboard_api_v28 import make_handler
from live_dashboard_v39 import LiveResearchStore, MAX_AGE_SECONDS

BASE=1700000100 - 1700000100%300

def envelope():
    candles=[]
    for i in range(55):
        p=100+i*.1
        candles.append({"timestamp":BASE+i*300,"open":p-.01,
            "high":p+.1,"low":p-.1,"close":p,"volume":20})
    return v27.analyze_and_emit(candles)

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.payload=envelope()
        dt=datetime.fromisoformat(self.payload["observed_candle_utc"])
        self.now=[dt.timestamp()+330]
        self.store=LiveResearchStore(clock=lambda:self.now[0])
        self.server=ThreadingHTTPServer(("127.0.0.1",0),
             make_handler(Path("/path/that/does/not/exist.csv"),live_store=self.store))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url="http://127.0.0.1:%d" % self.server.server_port

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)

    def emit(self):
        self.store.consume({"type":"research_events","source":"public_binance_usdm_ws",
            "realtime_transport":True,"paper_only":True,"orders_enabled":False,
            "payload":self.payload})

    def get(self,path):
        with urlopen(self.url+path,timeout=3) as response:
            return response.status,json.load(response)

    def test_warmup_then_event(self):
        with self.assertRaises(HTTPError) as error:
            self.get("/api/v1/agents")
        self.assertEqual(error.exception.code,503)
        self.store.consume({"type":"feed_status","state":"WARMING_UP",
                            "orders_enabled":False})
        self.assertFalse(self.get("/api/v1/feed")[1]["ready"])
        self.emit()
        _,data=self.get("/api/v1/agents")
        self.assertTrue(data["realtime"])
        self.assertFalse(data["orders_enabled"])
        self.assertEqual(data["events"],self.payload)

    def test_disconnect_clears_signal(self):
        self.emit()
        self.store.consume({"type":"feed_status","state":"DISCONNECTED",
                            "orders_enabled":False})
        with self.assertRaises(HTTPError) as error:
            self.get("/api/v1/agents")
        self.assertEqual(error.exception.code,503)

    def test_stale_clears_signal(self):
        self.emit()
        self.now[0]+=MAX_AGE_SECONDS+1
        self.assertEqual(self.get("/api/v1/feed")[1]["state"],"STALE")
        with self.assertRaises(HTTPError):
            self.get("/api/v1/agents")

    def test_rejects_old_event(self):
        self.now[0]+=MAX_AGE_SECONDS+100
        with self.assertRaises(ValueError):
            self.emit()
        self.assertFalse(self.store.status()["ready"])

    def test_rejects_unsafe_payload(self):
        bad=dict(self.payload)
        bad["orders_enabled"]=True
        with self.assertRaises(ValueError):
            self.store.consume({"type":"research_events","source":"public_binance_usdm_ws",
                "realtime_transport":True,"paper_only":True,"orders_enabled":False,
                "payload":bad})
        self.assertFalse(self.store.status()["ready"])

    def test_server_is_read_only(self):
        from urllib.request import Request
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.url+"/api/v1/agents",method="POST",data=b"{}"),timeout=3)
        self.assertEqual(error.exception.code,405)

if __name__=="__main__":
    unittest.main(verbosity=2)
