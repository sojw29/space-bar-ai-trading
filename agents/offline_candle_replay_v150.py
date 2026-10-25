"""Deterministic, read-only OHLCV replay for predeclared paper actions.

Actions are decided on a *completed* candle and filled at the NEXT candle's
open. No signal generation, strategy tuning, exchange or network operations.
"""
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from agents.offline_paper_execution_v145 import simulate_fill
from agents.offline_trade_session_v149 import OfflineTradeSession


@dataclass(frozen=True)
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


def load_candles(path: str | Path, *, interval_ms: int = 60000) -> list[Candle]:
    """Read strict millisecond-timestamp OHLCV CSV; reject gaps/duplicates."""
    if interval_ms <= 0 or isinstance(interval_ms, bool):
        raise ValueError("interval_ms must be positive")
    candles = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("missing OHLCV columns")
        for row in reader:
            raw = row["timestamp"]
            if not raw or not raw.isascii() or not raw.isdecimal():
                raise ValueError("timestamp must be epoch milliseconds")
            ts = int(raw)
            values = [float(row[k]) for k in ("open", "high", "low", "close", "volume")]
            o, h, l, c, v = values
            if not all(isfinite(x) for x in values) or min(o, h, l, c) <= 0 or v < 0:
                raise ValueError("invalid candle numeric values")
            if h < max(o, c, l) or l > min(o, c, h):
                raise ValueError("inconsistent OHLC")
            if candles and ts - candles[-1].timestamp != interval_ms:
                raise ValueError("duplicate, missing or unordered candles")
            candles.append(Candle(ts, o, h, l, c, v))
    if len(candles) < 2:
        raise ValueError("at least two candles required")
    return candles


def replay(candles: list[Candle], actions: dict[int, tuple[str, float]], *,
           initial_equity: float = 10000.0,
           max_participation: float = 0.01) -> OfflineTradeSession:
    """Map completed candle index to (side, qty); fill on next candle open.

    All actions must be declared before replay. Rejected/over-capacity orders
    remain unfilled (no partial fill); outstanding positions stay open.
    """
    if not isinstance(actions, dict):
        raise ValueError("actions must be a dict")
    if any(not isinstance(i, int) or isinstance(i, bool) or i < 0 or i >= len(candles)-1
           for i in actions):
        raise ValueError("action must have a subsequent candle")
    session = OfflineTradeSession(initial_equity)
    for index in sorted(actions):
        side, qty = actions[index]
        next_bar = candles[index + 1]
        fill = simulate_fill(side=side, quantity=qty,
                             reference_price=next_bar.open,
                             available_volume=next_bar.volume,
                             max_participation=max_participation)
        if fill is not None:
            session.apply_fill(fill)
    return session
