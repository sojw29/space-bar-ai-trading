"""V28 local read-only dashboard API. Research/demo only; never places orders.

Serves deterministic V26/V27 agent events from completed historical candles.
Bind to 127.0.0.1 only; no public deployment or authentication provided.
"""
import argparse
import csv
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import agent_events_v27 as v27

DEFAULT_HISTORY = Path("data/history/BTC_5m.csv")
MAX_BYTES = 1_000_000


def load_candles(path, limit=120):
    if not path.is_file():
        raise FileNotFoundError("Missing BTC history: " + str(path))
    if path.stat().st_size > 200_000_000:
        raise ValueError("History file unexpectedly large")
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Missing OHLCV columns")
        from collections import deque
        tail = deque(reader, maxlen=limit)
    return [
        {"timestamp": int(row["timestamp"]),
         **{k: float(row[k]) for k in ("open", "high", "low", "close", "volume")}}
        for row in tail
    ]


def snapshot(history_path):
    candles = load_candles(history_path)
    events = v27.analyze_and_emit(candles)
    return {
        "service": "space-bar-local-research-api",
        "api_version": "28.0",
        "source": "historical_csv_snapshot",
        "realtime": False,
        "events": events,
        "paper_only": True,
        "orders_enabled": False,
        "live_trading_approved": False,
    }


def make_handler(history_path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/health":
                self.reply(200, {"status": "ok", "mode": "local-paper-only",
                                 "orders_enabled": False})
            elif path == "/api/v1/agents":
                try:
                    self.reply(200, snapshot(history_path))
                except (OSError, ValueError, KeyError) as exc:
                    self.reply(503, {"error": type(exc).__name__,
                                     "message": "Historical research data unavailable"})
            else:
                self.reply(404, {"error": "not_found"})

        def do_POST(self):
            self.reply(405, {"error": "read_only"})

        def reply(self, status, payload):
            data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            if len(data) > MAX_BYTES:
                self.send_error(500, "Response too large")
                return
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

    return Handler


def main():
    parser = argparse.ArgumentParser(description="Local read-only SPACE BAR research API")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Port must be between 1024 and 65535")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.history))
    print("Local paper-only API: http://127.0.0.1:%d/api/v1/agents" % args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
