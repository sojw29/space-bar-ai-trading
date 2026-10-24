"""V115 offline completed-bar signals to next-bar hypothetical fills.

Only deterministic CSV replay. No network, exchange credentials or real orders.
A signal at bar i can execute no earlier than bar i+1 open.
"""
import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from offline_paper_ledger_v113 import PaperLedger
from paper_performance_v114 import analyze

COLUMNS = ("timestamp", "open", "high", "low", "close", "volume", "signal")
SIGNALS = frozenset(("BUY", "SELL", "HOLD"))
MAX_BYTES = 20000000
MAX_ROWS = 100000

def _timestamp(value):
    try:
        n = int(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("INVALID_TIMESTAMP") from exc
    if n < 0 or n > 253402300799999:
        raise ValueError("INVALID_TIMESTAMP")
    return n

def _day(timestamp):
    return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).strftime("%Y-%m-%d")

def read_signals(path):
    source = Path(path)
    if not source.is_file() or source.stat().st_size > MAX_BYTES:
        raise ValueError("MISSING_OR_OVERSIZED_SIGNALS")
    with source.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != list(COLUMNS):
            raise ValueError("INVALID_SIGNAL_SCHEMA")
        rows = list(reader)
    if len(rows) < 2 or len(rows) > MAX_ROWS:
        raise ValueError("INVALID_SIGNAL_ROWS")
    previous = None
    for row in rows:
        ts = _timestamp(row["timestamp"])
        if previous is not None and ts <= previous:
            raise ValueError("NON_MONOTONIC_TIMESTAMP")
        previous = ts
        if row["signal"] not in SIGNALS:
            raise ValueError("INVALID_SIGNAL")
        try:
            o, h, l, c, v = (float(row[k]) for k in ("open","high","low","close","volume"))
        except (TypeError, ValueError) as exc:
            raise ValueError("INVALID_OHLCV") from exc
        if (not all(math.isfinite(x) for x in (o,h,l,c,v)) or
                min(o,h,l,c) <= 0 or v < 0 or h < max(o,l,c) or l > min(o,h,c)):
            raise ValueError("INVALID_OHLCV")
    return rows

def replay(rows, budget_fraction=0.05):
    if (type(budget_fraction) not in (float, int) or
            not math.isfinite(budget_fraction) or
            not 0 < budget_fraction <= 0.1):
        raise ValueError("INVALID_BUDGET_FRACTION")
    if not isinstance(rows, list) or len(rows) < 2:
        raise ValueError("INSUFFICIENT_BARS")
    # Validate direct-call input through the same strict path as CSV ingestion.
    # No action on first bar: no earlier completed-bar signal exists.
    ledger = PaperLedger()
    commands = []
    executed = []
    blocked = []
    for i, bar in enumerate(rows):
        day = _day(_timestamp(bar["timestamp"]))
        opening_price = bar["open"]
        if i > 0:
            signal = rows[i-1]["signal"]
            if signal == "BUY" and ledger.units == 0 and not ledger.kill_switch:
                from decimal import Decimal
                budget = ledger._equity(Decimal(str(opening_price))) * Decimal(str(budget_fraction))
                if budget > 0:
                    try:
                        ledger.buy(opening_price, str(budget), day)
                        commands.append({"action":"BUY","price":str(opening_price),
                                         "budget":str(budget),"day":day})
                        executed.append({"signal_bar_index":i-1,"fill_bar_index":i,"side":"BUY"})
                    except ValueError as exc:
                        blocked.append({"signal_bar_index":i-1,"reason":str(exc)})
            elif signal == "SELL" and ledger.units > 0:
                quantity = ledger.units
                ledger.sell(opening_price, str(quantity), day)
                commands.append({"action":"SELL","price":str(opening_price),
                                 "units":str(quantity),"day":day})
                executed.append({"signal_bar_index":i-1,"fill_bar_index":i,"side":"SELL"})
        ledger.mark(bar["close"], day)
        commands.append({"action":"MARK","price":str(bar["close"]),"day":day})
    performance = analyze(commands)
    return {
        "version":"V115.0","status":"OFFLINE_SIGNAL_REPLAY",
        "signal_timing":"PREVIOUS_COMPLETED_BAR_TO_NEXT_OPEN",
        "bars_processed":len(rows),"hypothetical_fills":executed,
        "blocked_signals":blocked,"performance":performance,
        "simulation_only":True,"exchange_connected":False,
        "orders_submitted_to_exchange":0,"live_trading_approved":False,
        "limitations":"Signals supplied externally; no strategy optimization, spreads, slippage, real fills or continuous risk monitoring. Opening gap can trigger the kill switch only when marked; results are hypothetical."
    }

def run(path, budget_fraction=0.05):
    return replay(read_signals(path), budget_fraction)

def main():
    parser = argparse.ArgumentParser(description="V115 offline signal-to-paper replay")
    parser.add_argument("signals_csv")
    parser.add_argument("--budget-fraction", type=float, default=0.05)
    args = parser.parse_args()
    print(json.dumps(run(args.signals_csv, args.budget_fraction), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
