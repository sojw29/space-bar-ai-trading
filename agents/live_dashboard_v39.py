"""V39 opt-in localhost live-research dashboard bridge.

Websocket feed and HTTP reader share memory in one process; no public bind,
exchange account, API keys, trading, or orders. Never persist or serve a stale
LONG/SHORT decision when disconnected, resetting or overdue.
"""
import argparse
import threading
import time
from http.server import ThreadingHTTPServer

import agent_events_v27 as v27
import binance_public_ws_v38 as feed
from dashboard_api_v28 import DEFAULT_HISTORY, make_handler

MAX_AGE_SECONDS = 420  # 5m candle + limited network/processing grace
SAFE_STATES = ("CONNECTING", "WARMING_UP", "GAP_RESET",
               "INVALID_CANDLE_RESET", "DISCONNECTED", "STOPPED")
class FeedUnavailable(RuntimeError):
    pass


class LiveResearchStore:
    def __init__(self, clock=None):
        self._lock = threading.Lock()
        self._clock = clock or time.time
        self._state = "NOT_STARTED"
        self._payload = None
        self._received_at = None

    def consume(self, item):
        """Accept V38 emitted messages only. Fail closed on unsafe envelopes."""
        if not isinstance(item, dict) or item.get("orders_enabled") is not False:
            raise ValueError("Unsafe feed event")
        kind = item.get("type")
        with self._lock:
            if kind == "feed_status":
                state = item.get("state")
                if state not in SAFE_STATES:
                    raise ValueError("Unknown feed state")
                self._state = state
                self._payload = None
                self._received_at = None
            elif kind == "research_events":
                envelope = item.get("payload")
                if (item.get("paper_only") is not True or
                        item.get("realtime_transport") is not True or
                        item.get("source") != "public_binance_usdm_ws" or
                        not isinstance(envelope, dict)):
                    raise ValueError("Invalid public research event")
                # Reuse the research contract from V34, including vote
                # checks, UTC timestamp and explicit order-disabled flags.
                from decision_ledger_v34 import validate_envelope
                validate_envelope(envelope)
                from datetime import datetime
                observed = datetime.fromisoformat(
                    envelope["observed_candle_utc"].replace("Z", "+00:00")).timestamp()
                # V27 records the opening instant of the completed bar.
                event_age = float(self._clock()) - (observed + 300)
                if not 0 <= event_age <= MAX_AGE_SECONDS:
                    raise ValueError("Candle event too old or not yet complete")
                self._payload = envelope
                self._received_at = float(self._clock())
                self._state = "RESEARCH_READY"
            else:
                raise ValueError("Unknown event type")

    def status(self):
        with self._lock:
            age = None if self._received_at is None else max(
                0, float(self._clock()) - self._received_at)
            stale = age is not None and age > MAX_AGE_SECONDS
            if stale:
                self._payload = None
                self._received_at = None
                self._state = "STALE"
            return {
                "state": self._state,
                "ready": self._state == "RESEARCH_READY" and self._payload is not None,
                "age_seconds": None if stale else age,
                "paper_only": True, "orders_enabled": False,
                "mode": "public_market_data_research",
            }

    def snapshot(self):
        info = self.status()
        if not info["ready"]:
            raise FeedUnavailable("Feed warmup, interrupted or stale")
        with self._lock:
            # Status can change while another thread disconnects.
            if self._state != "RESEARCH_READY" or self._payload is None:
                raise FeedUnavailable("No current completed-candle research")
            return {
                "service": "space-bar-local-live-research-api",
                "api_version": "39.0",
                "source": "public_binance_usdm_ws",
                "realtime": True,
                "events": self._payload,
                "paper_only": True,
                "orders_enabled": False,
                "live_trading_approved": False,
                "independent_oos_verified": False,
            }


def start_dashboard(*, port=8765, clock=None, connect=None, max_attempts=None):
    if isinstance(port, bool) or not 1024 <= port <= 65535:
        raise ValueError("Invalid localhost port")
    store = LiveResearchStore(clock=clock)
    server = ThreadingHTTPServer(
        ("127.0.0.1", port), make_handler(DEFAULT_HISTORY, live_store=store))
    worker = threading.Thread(
        target=feed.run_forever,
        kwargs={"connect": connect, "emit": store.consume,
                "max_attempts": max_attempts},
        daemon=True, name="space-bar-readonly-feed")
    worker.start()
    print("V39 read-only dashboard: http://127.0.0.1:%d/" % server.server_port,
          flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="Read-only local public-stream dashboard")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    start_dashboard(port=args.port)


if __name__ == "__main__":
    main()
