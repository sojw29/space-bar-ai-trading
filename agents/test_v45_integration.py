"""V45 offline full-stack smoke test: mock public feed -> V37/V27 -> V39/V42/V43/V44 -> HTTP.

No internet access, Binance account, API key, market order or real funds.
The test uses currently complete 5m times but entirely synthetic OHLCV.
"""
import json
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))

from binance_public_ws_v38 import run_forever
from dashboard_api_v28 import make_handler
from live_dashboard_v39 import LiveResearchStore, dispatch_feed_event
from paper_monitor_v42 import LocalPaperMonitor
from paper_journal_v43 import PaperJournal, verify_session, session_events
from paper_analytics_v44 import analyze_session
from public_warmup_v40 import bootstrap_stream


class FakeSocket:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.closed = False

    def recv(self):
        return next(self.messages, None)

    def close(self):
        self.closed = True


class EndToEndOfflineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # There is one fully closed bar starting at tick-300. Preload 55
        # immediately preceding closed bars with the same synthetic clock.
        self.tick = int(time.time() // 300) * 300
        self.fixed_now = self.tick + 15
        self.origin = self.tick - 56 * 300
        self.store = LiveResearchStore(clock=lambda: self.fixed_now)
        self.paper = LocalPaperMonitor(clock=lambda: self.fixed_now)
        self.journal = PaperJournal(Path(self.tmp.name) / "paper.sqlite3")
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            make_handler(Path(self.tmp.name) / "unused.csv",
                         live_store=self.store, paper_monitor=self.paper,
                         paper_journal=self.journal))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.root = "http://127.0.0.1:%d" % self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def prices(self, n):
        price = 100.0 + 0.12 * n
        return [str(price - .04), str(price + .2), str(price - .2),
                str(price), "21"]

    def kline_row(self, n):
        t = (self.origin + n * 300) * 1000
        return [t, *self.prices(n), t + 299999, "0", 0, "0", "0", "0"]

    def ws(self, n, *, corrupt=False):
        start = (self.origin + n * 300) * 1000
        op, high, low, close, volume = self.prices(n)
        if corrupt:
            close = "9999999"
        return json.dumps({
            "e": "kline", "s": "BTCUSDT",
            "k": {"t": start, "T": start + 299999, "s": "BTCUSDT",
                  "i": "5m", "o": op, "h": high, "l": low,
                  "c": close, "v": volume, "x": True}})

    def get(self, path):
        with urlopen(self.root + path, timeout=3) as response:
            return json.load(response)

    def run_mock(self, messages):
        connection = FakeSocket(messages)
        outputs = []
        def emit(item):
            outputs.append(item)
            dispatch_feed_event(self.store, self.paper, self.journal, item)
        def warmup(stream):
            return bootstrap_stream(
                stream, fetch=lambda: [self.kline_row(i) for i in range(55)],
                now=self.fixed_now)
        run_forever(connect=lambda: connection, emit=emit, bootstrap=warmup,
                    sleep=lambda seconds: None, max_attempts=1)
        return outputs, connection

    def test_complete_mock_pipeline_and_persisted_halting_state(self):
        with self.assertRaises(HTTPError) as error:
            self.get("/api/v1/agents")
        self.assertEqual(error.exception.code, 503)
        results, socket = self.run_mock([self.ws(55)])
        self.assertTrue(socket.closed)
        self.assertEqual(sum(x["type"] == "research_events" for x in results), 1)
        self.assertEqual(results[-1]["state"], "DISCONNECTED")
        self.assertEqual(self.get("/api/v1/feed")["state"], "DISCONNECTED")
        with self.assertRaises(HTTPError) as error:
            self.get("/api/v1/agents")
        self.assertEqual(error.exception.code, 503)
        paper = self.get("/api/v1/paper")
        self.assertEqual(paper["state"], "HALTED")
        self.assertIsNone(paper["paper_mark_to_close_equity"])
        self.assertFalse(paper["orders_enabled"])
        audit = verify_session(self.journal.path, self.journal.session_id)
        self.assertEqual(audit["entries"], 2)
        events = session_events(self.journal.path, self.journal.session_id)
        self.assertEqual({x["kind"] for x in events}, {"feed_halt", "paper_snapshot"})
        analytics = self.get("/api/v1/paper/analytics")
        self.assertEqual(analytics["journal_entries"], 2)
        self.assertEqual(analytics["halt_count_in_sample"], 1)
        self.assertFalse(analytics["live_trading_approved"])
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.root + "/api/v1/paper", method="POST",
                            data=b'{"order":"BUY"}'), timeout=3)
        self.assertEqual(error.exception.code, 405)

    def test_invalid_ws_overlap_fails_closed_without_paper_trade(self):
        results, socket = self.run_mock([self.ws(54, corrupt=True)])
        self.assertTrue(socket.closed)
        self.assertEqual(sum(x["type"] == "research_events" for x in results), 0)
        self.assertEqual(self.paper.snapshot()["state"], "HALTED")
        self.assertIsNone(self.paper.snapshot()["position"])
        self.assertEqual(verify_session(self.journal.path, self.journal.session_id)["entries"], 1)
        analytics = analyze_session(self.journal.path, self.journal.session_id)
        self.assertEqual(analytics["paper_trade_events"], 0)
        self.assertEqual(analytics["halt_count_in_sample"], 1)

    def test_missing_feed_no_journal_trades_and_no_research(self):
        self.assertEqual(verify_session(self.journal.path, self.journal.session_id)["entries"], 0)
        self.assertFalse(self.get("/api/v1/feed")["ready"])
        self.assertIsNone(self.get("/api/v1/paper")["position"])
        data = self.get("/api/v1/paper/analytics")
        self.assertEqual(data["journal_entries"], 0)

    def test_history_endpoint_does_not_expose_orders(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.root + "/api/v1/paper/analytics",
                            method="POST", data=b'{"live":true}'), timeout=3)
        self.assertEqual(error.exception.code, 405)


if __name__ == "__main__":
    unittest.main(verbosity=2)
