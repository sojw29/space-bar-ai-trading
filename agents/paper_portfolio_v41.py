"""V41 opt-in, in-memory, closed-candle paper portfolio (NO exchange orders).

Research-only mark-to-close accounting. Assumes a hypothetical entry/exit at
a completed candle's close with adverse slippage and per-side fees; it is NOT
a fill model for executable orders and does not model intrabar stops,
liquidation, funding, order book depth or network latency.
"""
import math
from datetime import datetime, timezone
from copy import deepcopy

from decision_ledger_v34 import validate_envelope

PERIOD = 300


class PaperIntegrityError(ValueError):
    pass


class PaperPortfolio:
    def __init__(self, initial_cash=10000.0, *, allocation=0.20,
                 stop_pct=0.006, take_pct=0.018, max_daily_loss_pct=0.02,
                 fee_bps=5.5, slippage_bps=2.0, clock=None):
        inputs = (initial_cash, allocation, stop_pct, take_pct,
                  max_daily_loss_pct, fee_bps, slippage_bps)
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
               for x in inputs):
            raise ValueError("Non-finite paper configuration")
        if not (initial_cash > 0 and 0 < allocation <= 0.20 and
                0 < stop_pct <= 0.05 and 0 < take_pct <= 0.20 and
                0 < max_daily_loss_pct <= 0.10 and
                0 <= fee_bps <= 100 and 0 <= slippage_bps <= 100):
            raise ValueError("Paper risk caps exceeded")
        self.initial_cash = float(initial_cash)
        self.cash = float(initial_cash)
        self.allocation = float(allocation)
        self.stop_pct = float(stop_pct)
        self.take_pct = float(take_pct)
        self.max_daily_loss_pct = float(max_daily_loss_pct)
        self.fee = fee_bps / 10000
        self.slippage = slippage_bps / 10000
        self.clock = clock or (lambda: datetime.now(timezone.utc).timestamp())
        self.position = None
        self.last_ts = None
        self.trades = []
        self.day = None
        self.day_open_equity = float(initial_cash)
        self.halted = False
        self.halt_reason = None
        self.realized_net = 0.0

    def _close_estimate(self, price):
        pos = self.position
        if pos is None:
            return 0.0
        slip_price = price * (1 - self.slippage if pos["side"] == "LONG" else 1 + self.slippage)
        gross = pos["quantity"] * (slip_price - pos["entry_price"]) * (1 if pos["side"] == "LONG" else -1)
        return gross - pos["quantity"] * slip_price * self.fee

    def _equity(self, close_price=None):
        return self.cash + (self._close_estimate(close_price) if self.position and close_price is not None else 0)

    def _exit(self, price, ts, reason):
        pos = self.position
        move = self._close_estimate(price)
        self.cash += move
        self.realized_net += move
        self.trades.append({"type": "EXIT", "timestamp": ts, "side": pos["side"],
                            "reason": reason, "net_exit_effect": round(move, 8),
                            "cash": round(self.cash, 8)})
        self.position = None

    def _enter(self, side, price, ts):
        notional = self.cash * self.allocation
        entry_price = price * (1 + self.slippage if side == "LONG" else 1 - self.slippage)
        qty = notional / entry_price
        entry_fee = notional * self.fee
        self.cash -= entry_fee
        self.realized_net -= entry_fee
        self.position = {"side": side, "entry_price": entry_price,
                         "quantity": qty, "timestamp": ts, "notional": notional}
        self.trades.append({"type": "ENTRY", "timestamp": ts, "side": side,
                            "paper_entry": round(entry_price, 8),
                            "notional": round(notional, 8), "entry_fee": round(entry_fee, 8)})

    def snapshot(self, close_price=None):
        return {
            "schema_version": "41.0",
            "mode": "COMPLETED_CANDLE_PAPER_RESEARCH",
            "cash": round(self.cash, 8),
            "mark_to_close_equity": round(self._equity(close_price), 8)
                if close_price is not None else None,
            "position": deepcopy(self.position),
            "halted": self.halted, "halt_reason": self.halt_reason,
            "closed_candles_processed_until": self.last_ts,
            "total_paper_net_realized": round(self.realized_net, 8),
            "trades": deepcopy(self.trades),
            "paper_only": True, "orders_enabled": False,
            "live_trading_approved": False, "independent_oos_verified": False,
        }

    def on_completed_candle(self, candle, envelope):
        """Process one completed 5m bar and its SAME bar V27 research envelope.

        Existing exposure is marked/exited FIRST, based only on the current
        bar's close; new paper entry is considered only on a later bar.
        No intrabar stop orders or guaranteed stop prices.
        """
        if self.halted:
            raise PaperIntegrityError("Paper portfolio halted; restart with new instance")
        validate_envelope(envelope)
        if not isinstance(candle, dict) or candle.get("closed") is not True:
            self._halt("UNCLOSED_CANDLE")
            raise PaperIntegrityError("Unclosed candle")
        ts = candle.get("timestamp")
        if isinstance(ts, bool) or not isinstance(ts, int) or ts < 0 or ts % PERIOD:
            self._halt("INVALID_TIMESTAMP")
            raise PaperIntegrityError("Invalid timestamp")
        try:
            price = float(candle["close"])
        except (KeyError, TypeError, ValueError):
            self._halt("INVALID_PRICE")
            raise PaperIntegrityError("Invalid close")
        if not math.isfinite(price) or price <= 0:
            self._halt("INVALID_PRICE")
            raise PaperIntegrityError("Invalid close")
        now = float(self.clock())
        if not math.isfinite(now) or ts + PERIOD > now:
            self._halt("UNCLOSED_BY_CLOCK")
            raise PaperIntegrityError("Bar not complete by local clock")
        if self.last_ts is not None and ts != self.last_ts + PERIOD:
            self._halt("CANDLE_GAP_OR_DUPLICATE")
            raise PaperIntegrityError("Discontinuous candle stream")
        observed = datetime.fromisoformat(
            envelope["observed_candle_utc"].replace("Z", "+00:00")).timestamp()
        if observed != ts:
            self._halt("SIGNAL_CANDLE_MISMATCH")
            raise PaperIntegrityError("Signal not from this completed candle")
        self.last_ts = ts
        date = datetime.fromtimestamp(ts, timezone.utc).date()
        if self.day is None:
            self.day = date
        elif date != self.day:
            self.day = date
            self.day_open_equity = self._equity(price)
        commander = next(x for x in envelope["events"] if x["agent_id"] == "COMMANDER")
        # Mark open exposure using only close. Equity guard can close a paper
        # position, but simulated stop cannot guarantee its requested price.
        if self.position:
            pos = self.position
            signed_move = (price / pos["entry_price"] - 1) * (
                1 if pos["side"] == "LONG" else -1)
            reason = None
            if signed_move <= -self.stop_pct:
                reason = "CLOSE_STOP_THRESHOLD"
            elif signed_move >= self.take_pct:
                reason = "CLOSE_TAKE_THRESHOLD"
            elif commander["risk_veto"]:
                reason = "RISK_VETO"
            elif self._equity(price) <= self.day_open_equity * (1 - self.max_daily_loss_pct):
                reason = "DAILY_LOSS_GUARD"
            if reason:
                self._exit(price, ts, reason)
                if reason == "DAILY_LOSS_GUARD":
                    self._halt(reason)
                return self.snapshot(price)
        if self._equity(price) <= self.day_open_equity * (1 - self.max_daily_loss_pct):
            self._halt("DAILY_LOSS_GUARD")
            return self.snapshot(price)
        # No same-bar reversal/entry on an exit bar; no pyramiding.
        if self.position is None and not commander["risk_veto"] and commander["decision"] in ("LONG", "SHORT"):
            self._enter(commander["decision"], price, ts)
        return self.snapshot(price)

    def _halt(self, reason):
        self.halted = True
        self.halt_reason = reason
