"""V152 local read-only audit API smoke tests."""
import csv
import sys
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agents'))
from agents.dashboard_api_v28 import make_handler


class AuditEndpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "BTC_1m.csv"
        with self.path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(("timestamp", "open", "high", "low", "close", "volume"))
            writer.writerows([(60000, 100, 101, 99, 100, 1000),
                              (120000, 100, 111, 99, 110, 1000)])
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.path))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.tmp.cleanup()

    def request(self, path):
        with urlopen("http://127.0.0.1:%s%s" % (self.server.server_port, path),
                     timeout=3) as response:
            return response.status, json.load(response)

    def test_readonly_audit(self):
        status, payload = self.request("/api/v1/replay/audit")
        self.assertEqual(status, 200)
        self.assertFalse(payload["realtime"])
        self.assertFalse(payload["orders_enabled"])
        self.assertEqual(payload["audit"]["candle_count"], 2)
        self.assertEqual(payload["audit"]["closed_trades"], 0)

    def test_invalid_history_is_not_silent(self):
        self.path.write_text("invalid")
        with self.assertRaises(HTTPError) as ctx:
            self.request("/api/v1/replay/audit")
        self.assertEqual(ctx.exception.code, 503)


if __name__ == "__main__":
    unittest.main()
