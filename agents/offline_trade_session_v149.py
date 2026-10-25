"""Offline-only integration: V145 fills -> V147 ledger -> V148 closed-trade metrics.

Only flat-to-position-to-flat round trips are supported. Reversals are
rejected to prevent incorrect trade attribution. No broker or network calls.
"""
from dataclasses import dataclass, field
from agents.offline_paper_execution_v145 import PaperFill
from agents.offline_position_ledger_v147 import PositionLedger
from agents.offline_performance_tracker_v148 import PerformanceTracker


@dataclass
class OfflineTradeSession:
    initial_equity: float
    ledger: PositionLedger = field(default_factory=PositionLedger)
    performance: PerformanceTracker = field(init=False)
    _trade_realized: float = 0.0

    def __post_init__(self):
        self.performance = PerformanceTracker(self.initial_equity)

    def apply_fill(self, fill: PaperFill) -> float:
        """Apply a simulated fill and record P&L only on full close.

        A position reversal must be split into close and new open fills.
        """
        signed = self.ledger.signed_qty
        direction = 1 if fill.side == "BUY" else -1 if fill.side == "SELL" else 0
        if direction == 0:
            raise ValueError("invalid side")
        if signed * direction < 0 and fill.quantity > abs(signed):
            raise ValueError("split reversing fills into close and open")
        realized = self.ledger.apply(fill)
        self._trade_realized += realized
        if self.ledger.signed_qty == 0:
            self.performance.record_closed_trade(self._trade_realized)
            self._trade_realized = 0.0
        return realized
