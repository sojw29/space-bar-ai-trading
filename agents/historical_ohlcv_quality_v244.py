"""V244 validate offline historical OHLCV before backtesting. No network or orders."""
import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

INTERVAL_MS = 5 * 60 * 1000
MIN_BARS = 300
MAX_BARS = 10000

def validate_candles(rows, *, now=None, min_bars=MIN_BARS):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("NAIVE_NOW")
    now = now.astimezone(timezone.utc)
    if not isinstance(rows, list) or not min_bars <= len(rows) <= MAX_BARS:
        raise ValueError("INVALID_HISTORY_LENGTH")
    if not 1 <= min_bars <= MAX_BARS:
        raise ValueError("INVALID_MIN_BARS")
    normalized = []
    previous = None
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"timestamp_ms", "open", "high", "low", "close", "volume"}:
            raise ValueError("INVALID_CANDLE_SCHEMA")
        ts = row["timestamp_ms"]
        if type(ts) is not int or ts <= 0 or ts % INTERVAL_MS != 0:
            raise ValueError("INVALID_TIMESTAMP")
        if previous is not None and ts - previous != INTERVAL_MS:
            raise ValueError("NONCONTIGUOUS_OR_DUPLICATE_CANDLES")
        if ts + INTERVAL_MS > int(now.timestamp() * 1000):
            raise ValueError("UNFINISHED_CANDLE")
        prices = []
        for key in ("open", "high", "low", "close", "volume"):
            value = row[key]
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("NONFINITE_CANDLE")
            if value < 0 if key == "volume" else value <= 0:
                raise ValueError("INVALID_CANDLE_VALUE")
            prices.append(float(value))
        o, h, l, c, v = prices
        if h < max(o, c, l) or l > min(o, c, h):
            raise ValueError("INVALID_OHLC_ORDER")
        normalized.append((ts, o, h, l, c, v))
        previous = ts
    return {"version": "V244.0", "type": "OFFLINE_OHLCV_QUALITY_REPORT",
            "interval_minutes": 5, "bars": len(normalized),
            "first_timestamp_ms": normalized[0][0], "last_timestamp_ms": normalized[-1][0],
            "research_only": True, "orders_enabled": False,
            "backtest_performed": False, "quality_gate": "PASS",
            "warning": "Contiguous candles alone do not establish exchange authenticity or historical survivorship."}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    parser.add_argument("destination")
    args = parser.parse_args()
    target = Path(args.destination)
    try:
        with Path(args.csv_path).open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        # CSV conversion is explicit; invalid values fail closed.
        converted = [{"timestamp_ms": int(row["timestamp_ms"]),
                      **{key: float(row[key]) for key in ("open", "high", "low", "close", "volume")}}
                     for row in rows]
        result = validate_candles(converted)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except (ValueError, TypeError, KeyError, OSError, OverflowError):
        target.unlink(missing_ok=True)
        raise

if __name__ == "__main__":
    main()
