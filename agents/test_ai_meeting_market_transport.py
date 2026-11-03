"""Exercise the real urllib redirect handler with an isolated local HTTP server."""
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

from ohlcv_indicators_v225 import fetch_public, publish


class MarketTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                cls.requests.append(self.path)
                if self.path.startswith('/redirect/'):
                    self.send_response(int(self.path.rsplit('/', 1)[1]))
                    self.send_header('Location', '/unexpected-destination')
                    self.end_headers()
                else:
                    body = json.dumps({'code': '0', 'data': []}).encode()
                    self.send_response(200)
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            def log_message(self, *args):
                pass
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def test_redirect_never_reaches_destination_or_publishes_snapshot(self):
        for provider in ('okx', 'bybit'):
            for code in (301, 302, 303, 307, 308):
                with self.subTest(provider=provider, code=code):
                    self.requests.clear()
                    route = '/redirect/' + str(code)
                    with tempfile.TemporaryDirectory() as directory:
                        target = Path(directory) / 'snapshot.json'
                        target.write_text('old snapshot')
                        with patch('ohlcv_indicators_v225.Request',
                                   side_effect=lambda *a, **k: Request(self.origin + route)):
                            with self.assertRaises(HTTPError) as error:
                                publish(target, provider=provider)
                        self.assertEqual(error.exception.code, code)
                        error.exception.close()
                        self.assertEqual(self.requests, [route])
                        self.assertFalse(target.exists())
                        self.assertEqual(list(Path(directory).iterdir()), [])

    def test_direct_success_response_still_decodes_normally(self):
        for provider in ('okx', 'bybit'):
            with self.subTest(provider=provider):
                self.requests.clear()
                with patch('ohlcv_indicators_v225.Request',
                           side_effect=lambda *a, **k: Request(self.origin + '/direct')):
                    self.assertEqual(fetch_public('BTCUSDT', provider), {'code': '0', 'data': []})
                self.assertEqual(self.requests, ['/direct'])


if __name__ == '__main__':
    unittest.main()
