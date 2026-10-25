"""V167 local read-only AI meeting API contract."""
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


class MeetingEndpointTests(unittest.TestCase):
    def test_meeting_endpoint_fail_closed_and_read_only(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(Path("/missing.csv")))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        root = "http://127.0.0.1:%d" % server.server_port
        try:
            with urlopen(root + "/api/v1/meeting", timeout=3) as response:
                data = json.load(response)
                self.assertEqual(data["agents"]["COMMANDER"]["decision"], "WAIT")
                self.assertFalse(data["orders_enabled"])
                self.assertFalse(data["live_trading_approved"])
            with self.assertRaises(HTTPError) as failure:
                urlopen(Request(root + "/api/v1/meeting", method="POST", data=b"{}"), timeout=3)
            self.assertEqual(failure.exception.code, 405)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
