"""Offline-only FIFO-independent average-cost position ledger.

Consumes V145 PaperFill objects; no network, broker, or order APIs.
One net position per ledger. Realized P&L includes entry and exit fees.
"""
from dataclasses import dataclass
from math import isfinite
from agents.offline_paper_execution_v145 import PaperFill


@dataclass
class PositionLedger:
    signed_qty: float = 0.0
    average_entry: float = 0.0
    deferred_entry_fees: float = 0.0
    realized_pnl: float = 0.0
    total_fees: float = 0.0

    def apply(self, fill: PaperFill) -> float:
        """Apply a BUY/SELL fill; return incremental net realized P&L."""
        if fill.side not in ("BUY", "SELL"):
            raise ValueError("invalid side")
        values = (fill.quantity, fill.fill_price, fill.fee, fill.notional)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v) for v in values):
            raise ValueError("nonfinite fill")
        if fill.quantity <= 0 or fill.fill_price <= 0 or fill.fee < 0 or fill.notional <= 0:
            raise ValueError("invalid fill")
        direction = 1 if fill.side == "BUY" else -1
        old = self.signed_qty
        close_qty = min(abs(old), fill.quantity) if old * direction < 0 else 0.0
        open_qty = fill.quantity - close_qty
        realized = 0.0
        if close_qty:
            entry_fee = self.deferred_entry_fees * (close_qty / abs(old))
            exit_fee = fill.fee * (close_qty / fill.quantity)
            realized = (fill.fill_price - self.average_entry) * close_qty * (1 if old > 0 else -1) - entry_fee - exit_fee
        next_qty = old + direction * fill.quantity
        next_avg = self.average_entry
        next_deferred = self.deferred_entry_fees
        if close_qty:
            next_deferred -= entry_fee
        if open_qty:
            opening_fee = fill.fee * (open_qty / fill.quantity)
            existing_qty = max(0.0, abs(old) - close_qty)
            if existing_qty:
                next_avg = (next_avg * existing_qty + fill.fill_price * open_qty) / (existing_qty + open_qty)
            else:
                next_avg = fill.fill_price
            next_deferred += opening_fee
        if abs(next_qty) <= 1e-12:
            next_qty, next_avg, next_deferred = 0.0, 0.0, 0.0
        if not all(isfinite(x) for x in (next_qty, next_avg, next_deferred, realized, self.realized_pnl + realized, self.total_fees + fill.fee)):
            raise ValueError("position arithmetic overflow")
        self.signed_qty = next_qty
        self.average_entry = next_avg
        self.deferred_entry_fees = next_deferred
        self.realized_pnl += realized
        self.total_fees += fill.fee
        return realized

    def unrealized_pnl(self, mark: float) -> float:
        if isinstance(mark, bool) or not isinstance(mark, (int, float)) or not isfinite(mark) or mark <= 0:
            raise ValueError("invalid mark")
        return (mark - self.average_entry) * self.signed_qty - self.deferred_entry_fees
