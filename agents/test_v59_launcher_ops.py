"""V59 localhost-only desktop operational diagnostics, no account or orders."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"agents"))
from space_bar_launcher import LocalResearchService
from launcher_diagnostics_v59 import LocalEventLog,probe_local_research,_get_local_json

def fixture(path):
    start=1700000100-(1700000100%300)
    with open(path,"w",encoding="utf-8",newline="") as fp:
        writer=csv.writer(fp)
        writer.writerow(("timestamp","open","high","low","close","volume"))
        for i in range(80):
            writer.writerow((start+i*300,100+i/10,101+i/10,99+i/10,100.5+i/10,100+i))

class LocalOpsTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.file=Path(self.directory.name)/"btc.csv"
        fixture(self.file)
    def tearDown(self):
        self.directory.cleanup()
    def test_live_localhost_research_only_probe(self):
        service=LocalResearchService(port=18659)
        self.addCleanup(service.stop)
        self.assertEqual(probe_local_research(service.base_url)["state"],"UNAVAILABLE")
        service.start(self.file)
        report=probe_local_research(service.base_url)
        self.assertEqual(report["state"],"READY")
        self.assertEqual(report["mode"],"HISTORICAL_CSV")
        self.assertEqual(report["agent_research"],"VERIFIED")
        self.assertEqual(report["market_board"],"VERIFIED")
        self.assertEqual(report["paper"],"NOT_ENABLED")
        self.assertFalse(report["orders_enabled"])
        with self.assertRaises(ValueError):
            _get_local_json(service.base_url,"/api/v1/orders")
        with self.assertRaises(ValueError):
            _get_local_json("http://example.com:8765","/health")
        with self.assertRaises(HTTPError) as exc:
            urlopen(Request(service.base_url+"/api/v1/agents",method="POST",data=b'{}'),timeout=2)
        self.assertEqual(exc.exception.code,405)
        service.stop()
        self.assertEqual(probe_local_research(service.base_url)["state"],"UNAVAILABLE")

    def test_unsafe_or_inconsistent_feed_fails_closed(self):
        service=LocalResearchService(port=18660)
        self.addCleanup(service.stop)
        service.start(self.file)
        actual=_get_local_json
        def injected(base,path,*,timeout=1.5):
            if path=="/api/v1/feed":
                return {"state":"RESEARCH_READY","mode":"public_market_data_research",
                        "ready":True,"orders_enabled":False}
            return actual(base,path,timeout=timeout)
        with patch("launcher_diagnostics_v59._get_local_json",side_effect=injected):
            report=probe_local_research(service.base_url)
        self.assertEqual(report["state"],"UNAVAILABLE")
        self.assertNotEqual(report["agent_research"],"VERIFIED")
        self.assertFalse(report["orders_enabled"])

    def test_events_bounded_and_no_untrusted_leakage(self):
        record=LocalEventLog(max_events=3)
        record.record("STARTED","HISTORICAL_CSV")
        record.record("CHECK_FAILED","sensitive/path/password=123")
        record.record("STOPPED")
        record.record("CHECK_OK","HISTORICAL_CSV")
        lines=record.recent()
        self.assertEqual(len(lines),3)
        self.assertFalse(any("password" in line or "sensitive" in line for line in lines))
        with self.assertRaises(ValueError):
            record.record("ORDER_SENT","")
        with self.assertRaises(ValueError):
            LocalEventLog(max_events=0)

    def test_gui_code_uses_worker_and_never_starts_public_feed(self):
        gui=(ROOT/"space_bar_launcher.py").read_text(encoding="utf-8")
        self.assertIn("ROOT = Path(__file__).resolve().parent",gui)
        self.assertIn("ThreadPoolExecutor(max_workers=1",gui)
        self.assertIn("executor.submit(probe_local_research,service.base_url)",gui)
        self.assertIn('ops_label.set("API CHECK FAILED',gui)
        self.assertIn('executor.shutdown(wait=False,cancel_futures=True)',gui)
        self.assertNotIn("start_dashboard(",gui)
        self.assertNotIn("createOrder(",gui)

if __name__=="__main__":
    unittest.main(verbosity=2)
