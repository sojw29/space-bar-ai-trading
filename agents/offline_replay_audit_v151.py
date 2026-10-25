"""V151: strict, deterministic offline replay audit for real historical CSVs.

No strategy generation, API calls, network, or live order routing.
"""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from agents.offline_candle_replay_v150 import load_candles, replay


@dataclass(frozen=True)
class AuditResult:
    symbol: str
    timeframe_minutes: int
    candle_count: int
    first_timestamp: int
    last_timestamp: int
    data_sha256: str
    action_count: int
    closed_trades: int
    realized_pnl: float
    ending_realized_equity: float
    open_quantity: float
    win_rate_pct: float
    max_drawdown_pct: float

    def as_dict(self):
        return vars(self).copy()


def audit_history(path, *, symbol, timeframe_minutes, actions=None,
                  initial_equity=10000.0):
    if symbol not in ("BTC", "ETH", "SOL"):
        raise ValueError("unsupported symbol")
    if timeframe_minutes not in (1, 5, 15):
        raise ValueError("unsupported timeframe")
    path = Path(path)
    candles = load_candles(path, interval_ms=timeframe_minutes * 60000)
    actions = {} if actions is None else actions
    session = replay(candles, actions, initial_equity=initial_equity)
    perf = session.performance
    return AuditResult(
        symbol=symbol, timeframe_minutes=timeframe_minutes,
        candle_count=len(candles), first_timestamp=candles[0].timestamp,
        last_timestamp=candles[-1].timestamp,
        data_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        action_count=len(actions), closed_trades=len(perf.records),
        realized_pnl=session.ledger.realized_pnl,
        ending_realized_equity=perf.equity,
        open_quantity=session.ledger.signed_qty,
        win_rate_pct=perf.win_rate_pct,
        max_drawdown_pct=perf.max_drawdown_pct,
    )


def report_json(result):
    return json.dumps(result.as_dict(), sort_keys=True, ensure_ascii=False, indent=2)
