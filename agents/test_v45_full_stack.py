"""V45 black-box mock integration: public message -> seven agents -> paper -> SQLite -> API.

Never opens an external socket or performs exchange orders. Runtime candles
are deliberately recent to exercise freshness and completed-bar protections.
This is a software integration test, NOT evidence of profitable live trading.
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
import binance_public_ws_v38 as public
from dashboard_api_v28 import make_handler
from live_dashboard_v39 import LiveResearchStore
from paper_monitor_v42 import LocalPaperMonitor
from paper_journal_v43 import PaperJournal, session_events, verify_session
from paper_analytics_v44 import analyze_session


class MockSocket:
    def __init__(self, messages):
        self._messages = iter(messages)
        self.closed = False

    def recv(self):
        return next(self._messages, None)

    def close(self):
        self.closed = True


def build_public_messages(count=55):
    # Last bar was confirmed closed at the last exact 5m boundary.
    current_boundary = int(time.time() // 300) * 300
    first = current_boundary - count * 300
    messages = []
    for index in range(count):
        opened = (first + index * 300) * 1000
        price = 100 + index * 0.17
        messages.append(json.dumps({
            "e": "kline", "s": "BTCUSDT",
            "k": {"t": opened, "T": opened + 299999, "s": "BTCUSDT",
                  "i": "5m", "x": True,
                  "o": str(price - .02), "h": str(price + .1),
                  "l": str(price - .1), "c": str(price), "v": "20"}
        }))
    return messages


class FullStackTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.journal = PaperJournal(Path(self.directory.name) / "paper.sqlite3")
        self.live = LiveResearchStore()
        self.paper = LocalPaperMonitor()
        self.events = []

        def consume(event):
            self.events.append(event)
            self.live.consume(event)
            previous_state = self.paper.state
            self.paper.consume(event)
            if event["type"] == "research_events" or (
                    self.paper.state == "HALTED" and previous_state != "HALTED"):
                snapshot = self.paper.snapshot()
                kind = "feed_halt" if snapshot["state"] == "HALTED" else "paper_snapshot"
                self.journal.append(kind, snapshot)

        self.consume = consume
        self.http = ThreadingHTTPServer(("127.0.0.1", 0),
            make_handler(Path("/no-history.csv"), live_store=self.live,
                         paper_monitor=self.paper, paper_journal=self.journal))
        self.worker = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.worker.start()
        self.base = "http://127.0.0.1:%d" % self.http.server_port

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.worker.join(timeout=3)
        self.directory.cleanup()

    def get(self, route):
        with urlopen(self.base + route, timeout=3) as resp:
            return resp.status, json.load(resp)

    def test_public_event_end_to_end_then_disconnection_halts(self):
        with self.assertRaises(HTTPError) as error:
            self.get("/api/v1/agents")
        self.assertEqual(error.exception.code, 503)
        with self.assertRaises(HTTPError) as error:
            self._post()
        self.assertEqual(error.exception.code, 405)

        sock = MockSocket(build_public_messages())
        public.run_forever(connect=lambda: sock, emit=self.consume,
                           max_attempts=1, sleep=lambda _: None)
        self.assertTrue(sock.closed)
        published = [e for e in self.events if e["type"] == "research_events"]
        self.assertEqual(len(published), 1)
        self.assertEqual(len(published[0]["payload"]["events"]), 7)
        self.assertTrue(published[0]["payload"]["paper_only"])
        self.assertFalse(published[0]["payload"]["orders_enabled"])
        # The mock WebSocket closes: research signals MUST disappear.
        self.assertEqual(self.live.status()["state"], "DISCONNECTED")
        with self.assertRaises(HTTPError) as error:
            self.get("/api/v1/agents")
        self.assertEqual(error.exception.code, 503)
        _, paper = self.get("/api/v1/paper")
        self.assertEqual(paper["state"], "HALTED")
        self.assertIsNone(paper["paper_mark_to_close_equity"])
        _, report = self.get("/api/v1/paper/analytics")
        self.assertEqual(report["mode"], "SIMULATED_PAPER_ANALYTICS")
        self.assertEqual(report["journal_entries"], 2)
        self.assertEqual(report["halt_count_in_sample"], 1)
        self.assertFalse(report["orders_enabled"])
        self.assertFalse(report["independent_oos_verified"])
        self.assertTrue(verify_session(self.journal.path, self.journal.session_id)["valid"])
        kinds = [x["kind"] for x in session_events(
            self.journal.path, self.journal.session_id)]
        self.assertEqual(kinds, ["feed_halt", "paper_snapshot"])

    def _post(self):
        return urlopen(Request(self.base + "/api/v1/paper/analytics",
                               data=b"{}", method="POST"), timeout=3)

    def test_invalid_public_message_cannot_create_snapshot(self):
        msg = json.loads(build_public_messages(1)[0])
        msg["k"]["i"] = "15m"
        sock = MockSocket([json.dumps(msg)])
        public.run_forever(connect=lambda: sock, emit=self.consume,
                           max_attempts=1, sleep=lambda _: None)
        self.assertEqual(self.paper.state, "HALTED")
        report = analyze_session(self.journal.path, self.journal.session_id)
        self.assertEqual(report["journal_entries"], 1)
        self.assertIsNone(report["observed_equity_max_drawdown_pct"])
        self.assertFalse(any(x["type"] == "research_events" for x in self.events))


if __name__ == "__main__":
    unittest.main(verbosity=2)
