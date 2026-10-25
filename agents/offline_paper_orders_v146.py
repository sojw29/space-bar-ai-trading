"""Deterministic offline-only paper order lifecycle; never sends orders."""
from dataclasses import dataclass
from math import isfinite
from agents.offline_paper_execution_v145 import simulate_fill, PaperFill


@dataclass
class PaperOrder:
    side: str
    quantity: float
    created_bar: int
    ttl_bars: int = 3
    remaining: float = 0.0
    status: str = "OPEN"

    def __post_init__(self):
        if self.side not in ("BUY", "SELL"):
            raise ValueError("invalid side")
        if (not isinstance(self.quantity, (int, float)) or isinstance(self.quantity, bool)
                or not isfinite(self.quantity) or self.quantity <= 0):
            raise ValueError("invalid quantity")
        if (type(self.created_bar) is not int or self.created_bar < 0
                or type(self.ttl_bars) is not int or self.ttl_bars < 1):
            raise ValueError("invalid bar index or TTL")
        self.remaining = self.quantity

    def cancel(self):
        if self.status in ("OPEN", "PARTIAL"):
            self.status = "CANCELLED"

    def advance(self, *, bar: int, close: float, volume: float,
                participation: float = 0.01, **costs) -> PaperFill | None:
        """Use only a *completed* subsequent candle. Volume is base-asset units.

        TTL counts eligible bars after order creation. One fill per candle.
        """
        if self.status not in ("OPEN", "PARTIAL"):
            return None
        if type(bar) is not int or bar <= self.created_bar:
            raise ValueError("must use a subsequent completed bar")
        if bar > self.created_bar + self.ttl_bars:
            self.status = "EXPIRED"
            return None
        if not isinstance(volume, (int, float)) or isinstance(volume, bool) or not isfinite(volume) or volume < 0:
            raise ValueError("invalid volume")
        if not isinstance(participation, (int, float)) or isinstance(participation, bool) or not isfinite(participation) or not 0 < participation <= 1:
            raise ValueError("invalid participation")
        # No volume is reused on repeated calls for the same bar.
        if getattr(self, "_last_bar", -1) >= bar:
            raise ValueError("bars must advance strictly")
        self._last_bar = bar
        capacity = volume * participation
        if not isfinite(capacity):
            raise ValueError("nonfinite capacity")
        fill_qty = min(self.remaining, capacity)
        if fill_qty <= 0:
            return None
        fill = simulate_fill(side=self.side, quantity=fill_qty,
                             reference_price=close, available_volume=volume,
                             max_participation=participation, **costs)
        if fill is None:
            return None
        self.remaining = max(0.0, self.remaining - fill_qty)
        self.status = "FILLED" if self.remaining <= self.quantity * 1e-12 else "PARTIAL"
        return fill
