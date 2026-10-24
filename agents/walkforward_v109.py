"""V109 expanding-window walk-forward research (fixed strategies, no tuning).

Each validation fold follows its training fold in time; no overlap among
validation folds. No strategy selection or execution authorization.
"""
import argparse
import csv
import json
from pathlib import Path

from chronological_holdout_v102 import _timestamp
from cost_sensitivity_v106 import backtest, SCENARIOS
from multi_strategy_holdout_v105 import STRATEGIES

COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")
MIN_TRAIN = 160
MIN_VALIDATION = 80

def folds(rows, train_size=MIN_TRAIN, validation_size=MIN_VALIDATION):
    if (type(train_size) is not int or type(validation_size) is not int or
            train_size < MIN_TRAIN or validation_size < MIN_VALIDATION):
        raise ValueError("INVALID_FOLD_SIZES")
    if len(rows) < train_size + validation_size:
        raise ValueError("INSUFFICIENT_FOLD_DATA")
    result = []
    start = train_size
    while start + validation_size <= len(rows):
        result.append((rows[:start], rows[start:start+validation_size]))
        start += validation_size
    return result

def _read(source):
    path = Path(source)
    if not path.is_file() or path.stat().st_size > 20_000_000:
        raise ValueError("MISSING_OR_OVERSIZED_HISTORY")
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != list(COLUMNS):
            raise ValueError("INVALID_HISTORY_SCHEMA")
        rows = list(reader)
    if len(rows) > 100_000:
        raise ValueError("TOO_MANY_ROWS")
    previous = None
    for row in rows:
        ts = _timestamp(row["timestamp"])
        if previous is not None and ts <= previous:
            raise ValueError("NON_MONOTONIC_TIMESTAMP")
        previous = ts
        # Validate price/volume through the V102 strict validator at source.
        # Here require positive finite numbers and coherent OHLC as well.
        import math
        try:
            o, h, l, c, v = (float(row[k]) for k in COLUMNS[1:])
        except (TypeError, ValueError) as exc:
            raise ValueError("INVALID_OHLCV") from exc
        if (not all(math.isfinite(x) for x in (o,h,l,c,v)) or
                min(o,h,l,c) <= 0 or v < 0 or
                h < max(o,c,l) or l > min(o,c,h)):
            raise ValueError("INVALID_OHLCV")
    return rows

def run(source, train_size=160, validation_size=80):
    rows = _read(source)
    windows = folds(rows, train_size, validation_size)
    results = []
    for strategy in STRATEGIES:
        entries = []
        for number, (train, validation) in enumerate(windows, 1):
            costs = SCENARIOS["moderate"]
            train_result = backtest(train, strategy, costs)
            valid_result = backtest(validation, strategy, costs)
            entries.append({
                "fold": number,
                "train_end_timestamp": train[-1]["timestamp"],
                "validation_start_timestamp": validation[0]["timestamp"],
                "validation_end_timestamp": validation[-1]["timestamp"],
                "train": train_result, "validation": valid_result,
                "sample_sufficient": train_result["trades"] >= 30 and valid_result["trades"] >= 30,
            })
        results.append({
            "strategy": strategy, "folds": entries,
            "validation_positive_return_folds": sum(x["validation"]["return"] > 0 for x in entries),
            "validation_folds": len(entries),
            "all_folds_sample_sufficient": all(x["sample_sufficient"] for x in entries),
        })
    return {
        "version": "V109.0", "status": "WALK_FORWARD_DESCRIPTIVE_ONLY",
        "train_window": "EXPANDING", "validation_window": "NON_OVERLAPPING",
        "train_size": train_size, "validation_size": validation_size,
        "unused_tail_rows": len(rows)-(train_size+len(windows)*validation_size),
        "results": results, "research_only": True,
        "orders_enabled": False, "live_trading_approved": False,
        "validated_edge": False,
        "limitations": "Fixed strategy parameters; separate validation warmups; no slippage variability, uncertainty intervals or independent forward performance."
    }

def main():
    parser = argparse.ArgumentParser(description="V109 offline expanding walk-forward")
    parser.add_argument("history_csv")
    parser.add_argument("--train-size", type=int, default=160)
    parser.add_argument("--validation-size", type=int, default=80)
    args = parser.parse_args()
    print(json.dumps(run(args.history_csv, args.train_size, args.validation_size), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
