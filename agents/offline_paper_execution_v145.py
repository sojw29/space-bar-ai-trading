"""Offline-only conservative paper fill simulation. No network or order APIs."""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class PaperFill:
    side: str
    quantity: float
    reference_price: float
    fill_price: float
    fee: float
    spread_cost: float
    slippage_cost: float
    notional: float


def simulate_fill(*, side: str, quantity: float, reference_price: float,
                  available_volume: float, spread_bps: float = 2.0,
                  slippage_bps: float = 3.0, fee_bps: float = 5.5,
                  max_participation: float = 0.01) -> PaperFill | None:
    """Simulate a fill against a completed candle's volume (base units).

    Returns None if the order cannot fit within the configured participation
    cap. Spread cost and slippage cost are reported separately. Never
    submits, queues or routes an order.
    """
    if side not in ("BUY", "SELL"):
        raise ValueError("side must be BUY or SELL")
    fields = (quantity, reference_price, available_volume, spread_bps,
              slippage_bps, fee_bps, max_participation)
    if any(not isinstance(x, (int, float)) or isinstance(x, bool)
           or not isfinite(x) for x in fields):
        raise ValueError("all numeric inputs must be finite real numbers")
    if quantity <= 0 or reference_price <= 0 or available_volume < 0:
        raise ValueError("invalid quantity, price or volume")
    if min(spread_bps, slippage_bps, fee_bps) < 0 or not 0 < max_participation <= 1:
        raise ValueError("invalid execution assumptions")
    impact = (spread_bps / 2 + slippage_bps) / 10000
    if not isfinite(impact) or impact >= 1:
        raise ValueError("invalid modeled price impact")
    if quantity > available_volume * max_participation:
        return None
    fill_price = reference_price * (1 + impact if side == "BUY" else 1 - impact)
    notional = quantity * fill_price
    fee = notional * fee_bps / 10000
    spread_cost = quantity * reference_price * (spread_bps / 2) / 10000
    slippage_cost = quantity * reference_price * slippage_bps / 10000
    if any(not isfinite(x) or x < 0 for x in
           (fill_price, notional, fee, spread_cost, slippage_cost)) or fill_price <= 0:
        raise ValueError("nonfinite or invalid simulated fill")
    return PaperFill(
        side=side, quantity=quantity, reference_price=reference_price,
        fill_price=fill_price, fee=fee,
        spread_cost=spread_cost, slippage_cost=slippage_cost,
        notional=notional,
    )
