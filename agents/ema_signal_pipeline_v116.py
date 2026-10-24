"""V116 deterministic closed-bar EMA20/50 signals -> V115 offline paper replay.

Long-only research signals. No exchange connections or live trading.
"""
import argparse
import csv
import json
from pathlib import Path

from offline_signal_replay_v115 import read_signals, replay

RAW_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")
MAX_FILE_BYTES = 20000000
MAX_ROWS = 100000

def _ema(previous, close, period):
    return close if previous is None else previous + (2.0/(period+1))*(close-previous)

def generate(rows):
    if not isinstance(rows, list) or len(rows) < 52:
        raise ValueError("INSUFFICIENT_EMA_HISTORY")
    enriched = []
    fast = slow = None
    prev_fast = prev_slow = None
    for i, row in enumerate(rows):
        close = float(row["close"])
        fast = _ema(fast, close, 20)
        slow = _ema(slow, close, 50)
        signal = "HOLD"
        # Avoid signals until at least 50 fully closed bars are available.
        if i >= 50 and prev_fast is not None and prev_slow is not None:
            if prev_fast <= prev_slow and fast > slow:
                signal = "BUY"
            elif prev_fast >= prev_slow and fast < slow:
                signal = "SELL"
        enriched.append({**row, "signal":signal})
        prev_fast, prev_slow = fast, slow
    return enriched

def read_history(path):
    source = Path(path)
    if not source.is_file() or source.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("MISSING_OR_OVERSIZED_HISTORY")
    with source.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != list(RAW_COLUMNS):
            raise ValueError("INVALID_HISTORY_SCHEMA")
        rows = list(reader)
    if len(rows) < 52 or len(rows) > MAX_ROWS:
        raise ValueError("INSUFFICIENT_OR_OVERSIZED_HISTORY")
    # Reuse V115 strict timestamp and OHLCV validation by supplying HOLD labels.
    from offline_signal_replay_v115 import _timestamp
    import math
    previous = None
    for row in rows:
        ts = _timestamp(row["timestamp"])
        if previous is not None and ts <= previous:
            raise ValueError("NON_MONOTONIC_TIMESTAMP")
        previous = ts
        try:
            o,h,l,c,v = (float(row[k]) for k in RAW_COLUMNS[1:])
        except (ValueError, TypeError) as exc:
            raise ValueError("INVALID_OHLCV") from exc
        if (not all(math.isfinite(x) for x in (o,h,l,c,v)) or
                min(o,h,l,c) <= 0 or v < 0 or h < max(o,l,c) or l > min(o,h,c)):
            raise ValueError("INVALID_OHLCV")
    return rows

def run(path, budget_fraction=0.05):
    rows = read_history(path)
    signals = generate(rows)
    result = replay(signals, budget_fraction)
    return {
        "version":"V116.0","status":"OFFLINE_STRATEGY_TO_PAPER",
        "strategy":"EMA20_50_CROSS_LONG_ONLY",
        "signal_count_buy":sum(row["signal"]=="BUY" for row in signals),
        "signal_count_sell":sum(row["signal"]=="SELL" for row in signals),
        "signal_warmup_bars":50,
        "signal_timing":"COMPLETED_BAR_TO_NEXT_OPEN",
        "paper_replay":result,
        "simulation_only":True,"exchange_connected":False,
        "orders_submitted_to_exchange":0,"live_trading_approved":False,
        "limitations":"Fixed EMA parameters; independent replay on supplied historical bars. No real market data feed, spreads, slippage, latency or validated profitability.",
    }

def main():
    parser = argparse.ArgumentParser(description="V116 EMA signals to offline paper replay")
    parser.add_argument("history_csv")
    parser.add_argument("--budget-fraction", type=float, default=0.05)
    args = parser.parse_args()
    print(json.dumps(run(args.history_csv, args.budget_fraction), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
