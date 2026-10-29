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
DASHBOARD_HTML = Path(__file__).resolve().parent.parent / "web" / "command_center.html"
AUDIT_ROOM_HTML = Path(__file__).resolve().parent.parent / "web" / "audit_room_mobile_v153.html"
OFFICE_3D_HTML = Path(__file__).resolve().parent.parent / "web" / "office_3d.html"
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


def make_handler(history_path, live_store=None, paper_monitor=None, paper_journal=None):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlsplit(self.path).path
            if path in ("/", "/dashboard", "/office3d", "/audit-room"):
                try:
                    content = (AUDIT_ROOM_HTML if path == "/audit-room" else OFFICE_3D_HTML if path == "/office3d" else DASHBOARD_HTML).read_bytes()
                except OSError:
                    self.reply(503, {"error": "dashboard_unavailable"})
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(content)
            elif path == "/health":
                self.reply(200, {"status": "ok", "mode": "local-paper-only",
                                 "orders_enabled": False})
            elif path == "/api/v1/research/scorecard":
                # Local static snapshot only; never computes/optimizes or trades.
                try:
                    from strategy_scorecard_html_v199 import render
                    scorecard_path = Path(__file__).resolve().parent.parent / "reports" / "strategy_scorecard_latest.json"
                    if not scorecard_path.is_file() or scorecard_path.stat().st_size > 2_000_000:
                        self.reply(404, {"error": "offline_scorecard_not_available",
                                         "orders_enabled": False})
                        return
                    payload = json.loads(scorecard_path.read_text(encoding="utf-8"))
                    render(payload)  # Strict V199 schema and safety validation.
                    # The shared HTTP reply cap is smaller than the input-file cap.
                    # Reject oversized JSON as unavailable, not as a 500 response.
                    if len(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")) > MAX_BYTES:
                        raise ValueError("scorecard_response_too_large")
                    self.reply(200, payload)
                except (OSError, ValueError, TypeError, KeyError, UnicodeError, RecursionError):
                    self.reply(503, {"error": "offline_scorecard_invalid",
                                     "orders_enabled": False})
            elif path == "/api/v1/market":
                try:
                    if live_store is not None:
                        if not live_store.status()["ready"]:
                            self.reply(503, {"error": "market_feed_not_ready",
                                             "orders_enabled": False})
                            return
                        self.reply(200, live_store.market_snapshot())
                    else:
                        from market_board_v52 import market_board
                        self.reply(200, market_board(
                            load_candles(history_path, limit=60), realtime=False,
                            source="historical_csv_snapshot"))
                except (OSError, ValueError, KeyError, RuntimeError) as exc:
                    self.reply(503, {"error": "market_chart_unavailable",
                                     "orders_enabled": False})
            elif path == "/api/v1/replay/audit":
                try:
                    from agents.offline_replay_audit_v151 import audit_history
                    import re
                    match = re.fullmatch(r"(BTC|ETH|SOL)_(1|5|15)m[.]csv", history_path.name)
                    if match is None:
                        self.reply(503, {"error": "history_filename_must_identify_symbol_timeframe",
                                         "orders_enabled": False})
                        return
                    result = audit_history(history_path, symbol=match.group(1),
                                           timeframe_minutes=int(match.group(2)))
                    self.reply(200, {"mode": "historical_offline_audit",
                                     "realtime": False, "orders_enabled": False,
                                     "signals_enabled": False,
                                     "audit": result.as_dict()})
                except (OSError, ValueError, KeyError, OverflowError):
                    self.reply(503, {"error": "history_audit_unavailable_or_invalid",
                                     "orders_enabled": False})
            elif path == "/api/v1/paper/analytics":
                if paper_journal is None:
                    self.reply(404, {"error": "paper_journal_not_enabled", "orders_enabled": False})
                else:
                    try:
                        from paper_analytics_v44 import analyze_session
                        self.reply(200, analyze_session(paper_journal.path, paper_journal.session_id))
                    except (OSError, ValueError, KeyError) as exc:
                        self.reply(503, {"error": "paper_journal_invalid_or_unavailable",
                                         "orders_enabled": False})
            elif path == "/api/v1/paper":
                if paper_monitor is None:
                    self.reply(404, {"error": "paper_monitor_not_enabled", "orders_enabled": False})
                else:
                    self.reply(200, paper_monitor.snapshot())
            elif path == "/api/v1/feed":
                if live_store is None:
                    self.reply(200, {"state": "HISTORICAL", "ready": False, "orders_enabled": False})
                else:
                    self.reply(200, live_store.status())
            elif path == "/api/v1/meeting":
                from meeting_quality_report_v166 import build_report
                from meeting_contract_validator_v186 import validate_meeting_snapshot
                try:
                    report = build_report(Path("reports/v65/quality.json"))
                    if not isinstance(report, dict):
                        raise ValueError("invalid_meeting_snapshot")
                    report["contract_validation"] = validate_meeting_snapshot(report)
                    self.reply(200, report)
                except (OSError, ValueError, TypeError, KeyError):
                    self.reply(503, {"error": "meeting_snapshot_unavailable",
                                     "research_only": True, "orders_enabled": False,
                                     "live_trading_approved": False,
                                     "contract_validation": {
                                         "verified": False, "status": "BLOCKED",
                                         "failures": ["source_unavailable"],
                                         "orders_allowed": False, "live_trading_allowed": False}})
            elif path == "/api/v1/agents":
                try:
                    if live_store is not None:
                        if not live_store.status()["ready"]:
                            self.reply(503, {"error": "feed_not_ready", "mode": "public_market_data_research", "orders_enabled": False})
                            return
                        self.reply(200, live_store.snapshot())
                    else:
                        self.reply(200, snapshot(history_path))
                except (OSError, ValueError, KeyError, RuntimeError) as exc:
                    self.reply(503, {"error": type(exc).__name__,
                                     "message": "Research data unavailable or stale"})
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
