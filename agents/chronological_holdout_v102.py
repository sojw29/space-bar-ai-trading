"""V102 strict chronological split for offline OHLCV research.

Produces disjoint, contiguous training and validation CSVs without lookahead.
It does not optimize strategies or claim out-of-sample profitability.
"""
import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")

def _timestamp(value):
    try:
        numeric = int(value)
        if str(numeric) == value.strip():
            return numeric
    except (TypeError, ValueError):
        pass
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("NAIVE_TIMESTAMP")
        return int(dt.astimezone(timezone.utc).timestamp() * 1000)
    except (TypeError, ValueError) as exc:
        raise ValueError("INVALID_TIMESTAMP") from exc

def split_csv(source, train_output, validation_output, ratio=0.7, min_rows=30):
    if not (type(ratio) is float and math.isfinite(ratio) and 0.5 <= ratio <= 0.9):
        raise ValueError("INVALID_TRAIN_RATIO")
    if type(min_rows) is not int or min_rows < 2:
        raise ValueError("INVALID_MIN_ROWS")
    source = Path(source).resolve()
    train_output = Path(train_output).resolve()
    validation_output = Path(validation_output).resolve()
    if len({source, train_output, validation_output}) != 3:
        raise ValueError("OVERLAPPING_PATHS")
    if not source.is_file() or source.stat().st_size > 20_000_000:
        raise ValueError("MISSING_OR_OVERSIZED_SOURCE")
    with source.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or set(reader.fieldnames) != set(COLUMNS):
            raise ValueError("INVALID_CSV_SCHEMA")
        rows = []
        last = None
        for row in reader:
            if None in row or any(row.get(k) is None for k in COLUMNS):
                raise ValueError("MALFORMED_ROW")
            ts = _timestamp(row["timestamp"])
            if last is not None and ts <= last:
                raise ValueError("NON_MONOTONIC_OR_DUPLICATE_TIME")
            last = ts
            values = []
            for key in COLUMNS[1:]:
                try:
                    value = float(row[key])
                except (TypeError, ValueError) as exc:
                    raise ValueError("INVALID_OHLCV") from exc
                if not math.isfinite(value) or value < 0 or (key != "volume" and value == 0):
                    raise ValueError("INVALID_OHLCV")
                values.append(value)
            op, high, low, close, volume = values
            if high < max(op, close, low) or low > min(op, close, high):
                raise ValueError("INVALID_CANDLE_RANGE")
            rows.append({key: row[key] for key in COLUMNS})
            if len(rows) > 100_000:
                raise ValueError("TOO_MANY_ROWS")
    n = len(rows)
    cut = int(n * ratio)
    if cut < min_rows or n - cut < min_rows:
        raise ValueError("INSUFFICIENT_ROWS")
    if train_output.exists() or validation_output.exists():
        raise ValueError("OUTPUT_EXISTS")
    train_output.parent.mkdir(parents=True, exist_ok=True)
    validation_output.parent.mkdir(parents=True, exist_ok=True)
    # Both outputs are deterministic; never silently overwrite prior evidence.
    for path, part in ((train_output, rows[:cut]), (validation_output, rows[cut:])):
        with path.open("x", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(part)
    return {"version": "V102.0", "status": "CHRONOLOGICAL_SPLIT_CREATED",
            "total_rows": n, "train_rows": cut, "validation_rows": n-cut,
            "train_last_timestamp": rows[cut-1]["timestamp"],
            "validation_first_timestamp": rows[cut]["timestamp"],
            "disjoint": True, "chronological": True,
            "research_only": True, "live_trading_approved": False,
            "strategy_profitable_verified": False,
            "note": "Chronological split only. Does not prevent feature leakage or validate predictive performance."}

def main():
    parser = argparse.ArgumentParser(description="V102 chronological research holdout split")
    parser.add_argument("source")
    parser.add_argument("train_output")
    parser.add_argument("validation_output")
    parser.add_argument("--ratio", type=float, default=0.7)
    parser.add_argument("--min-rows", type=int, default=30)
    args = parser.parse_args()
    result = split_csv(args.source, args.train_output, args.validation_output,
                       args.ratio, args.min_rows)
    print(json.dumps(result, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
