"""V42 optional local paper monitor for V38 completed-candle events.

No account connection, exchange order, trading controls, or file persistence.
All outputs are simulated and cannot establish an independently validated edge.
Feed breaks irreversibly halt this paper session; restart deliberately.
"""
from copy import deepcopy
from datetime import datetime, timezone
import math
import threading
import time

from paper_portfolio_v41 import PaperPortfolio, PaperIntegrityError

FAIL_STATES = {"DISCONNECTED", "STOPPED", "INVALID_CANDLE_RESET", "GAP_RESET"}
MAX_AGE = 420


class LocalPaperMonitor:
    def __init__(self, *, clock=None):
        self.clock = clock or time.time
        self.lock = threading.RLock()
        self.portfolio = PaperPortfolio(clock=self.clock)
        self.state = "WAITING_FOR_COMPLETED_CANDLE"
        self.error = None
        self.last_receive = None
        self.last_candle = None
        self._last_mark = None

    def _halt(self, reason):
        self.state = "HALTED"
        self.error = reason
        self.portfolio._halt(reason)

    def consume(self, item):
        """Consume V38 feed events with the V42 opt-in closed_candle field."""
        if not isinstance(item, dict) or item.get("orders_enabled") is not False:
            raise ValueError("Unsafe incoming feed event")
        with self.lock:
            if self.state == "HALTED":
                return
            if item.get("type") == "feed_status":
                state = item.get("state")
                if state in FAIL_STATES:
                    self._halt("FEED_" + state)
                elif state in ("CONNECTING", "WARMING_UP"):
                    # Startup is allowed, but cannot erase a prior halt.
                    self.state = "WARMING_UP"
                else:
                    self._halt("UNKNOWN_FEED_STATUS")
                return
            if item.get("type") != "research_events":
                self._halt("UNKNOWN_FEED_EVENT")
                raise ValueError("Unknown feed event")
            if (item.get("source") != "public_binance_usdm_ws" or
                    item.get("realtime_transport") is not True or
                    item.get("paper_only") is not True):
                self._halt("WRONG_FEED_SOURCE")
                raise ValueError("Only public feed research events supported")
            candle = item.get("closed_candle")
            envelope = item.get("payload")
            if not isinstance(candle, dict) or not isinstance(envelope, dict):
                self._halt("MISSING_COMPLETED_CANDLE")
                raise ValueError("Event requires a matched completed candle")
            try:
                observed = datetime.fromisoformat(
                    envelope["observed_candle_utc"].replace("Z", "+00:00")).timestamp()
                arrival = float(self.clock())
                if not math.isfinite(arrival) or not 0 <= arrival - (observed + 300) <= MAX_AGE:
                    raise ValueError("Stale or premature observation")
                result = self.portfolio.on_completed_candle(candle, envelope)
            except (KeyError, TypeError, ValueError, PaperIntegrityError, OverflowError) as exc:
                self._halt("PAPER_INTEGRITY_ERROR")
                raise ValueError("Paper engine rejected market event") from exc
            self.last_receive = arrival
            self.last_candle = candle["timestamp"]
            self._last_mark = float(candle["close"])
            if result["halted"]:
                self._halt(result["halt_reason"] or "RISK_GUARD")
            else:
                self.state = "SIMULATING"

    def snapshot(self):
        with self.lock:
            elapsed = None if self.last_receive is None else max(
                0, float(self.clock()) - self.last_receive)
            if self.state == "SIMULATING" and elapsed is not None and elapsed > MAX_AGE:
                self._halt("STALE_PUBLIC_MARKET_DATA")
            # Do not expose a stale portfolio mark as live or tradeable.
            details = self.portfolio.snapshot(
                self._last_mark if self.state == "SIMULATING" else None)
            return {
                "schema_version": "42.0",
                "mode": "LOCAL_PAPER_SIMULATION",
                "state": self.state,
                "halt_reason": self.error,
                "last_completed_candle_timestamp": self.last_candle,
                "paper_cash": details["cash"],
                "paper_mark_to_close_equity": (
                    details["mark_to_close_equity"] if self.state == "SIMULATING" else None),
                "position": details["position"],
                "paper_realized_net": details["total_paper_net_realized"],
                "paper_trade_event_count": len(details["trades"]),
                "mark_is_stale": self.state != "SIMULATING",
                "paper_only": True,
                "orders_enabled": False,
                "live_trading_approved": False,
                "independent_oos_verified": False,
            }
