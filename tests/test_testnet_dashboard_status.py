"""Local-only dashboard testnet capability endpoint regression."""
import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents"))
from dashboard_api_v28 import make_handler


class TestReadOnlyStagingStatus(unittest.TestCase):
    def test_status_endpoint_never_claims_staging_or_orders(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(Path("nonexistent.csv")))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = "http://127.0.0.1:%d/api/v1/testnet/staging/status" % server.server_port
            with urlopen(url, timeout=3) as response:
                self.assertEqual(response.status, 200)
                status = json.load(response)
            self.assertEqual(status["status"], "NOT_CONNECTED")
            for key in ("staging_enabled", "orders_enabled", "network_enabled", "live_trading_approved"):
                self.assertIs(status[key], False)
            with self.assertRaises(HTTPError) as caught:
                urlopen(Request(url, data=b"{}", method="POST"), timeout=3)
            self.assertEqual(caught.exception.code, 405)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
