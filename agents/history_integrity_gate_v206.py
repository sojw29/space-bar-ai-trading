"""V206 fail-closed historical OHLCV integrity gate for offline research.

Validates chronology, numeric sanity, duplicate timestamps and expected cadence.
No exchange connectivity, live orders or automated strategy selection.
"""
import csv
import math
from pathlib import Path

MAX_ROWS = 500_000
INTERVAL_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000}


def inspect_history(path, timeframe="5m", max_missing=0):
    if timeframe not in INTERVAL_MS or type(max_missing) is not int or max_missing < 0:
        raise ValueError("INVALID_INTEGRITY_SETTINGS")
    source = Path(path)
    if not source.is_file() or source.stat().st_size > 200_000_000:
        raise ValueError("INVALID_HISTORY_FILE")
    prev = None
    count = 0
    missing = 0
    errors = []
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = {"timestamp", "open", "high", "low", "close", "volume"}
        if not fields.issubset(reader.fieldnames or []):
            raise ValueError("MISSING_OHLCV_FIELDS")
        for row in reader:
            count += 1
            if count > MAX_ROWS:
                raise ValueError("HISTORY_ROW_LIMIT")
            try:
                stamp = int(row["timestamp"])
                values = [float(row[k]) for k in ("open","high","low","close","volume")]
                op, hi, lo, cl, vol = values
                if not all(map(math.isfinite, values)) or min(op,hi,lo,cl) <= 0 or vol < 0:
                    raise ValueError("NONFINITE_OR_NEGATIVE")
                if lo > min(op,cl) or hi < max(op,cl) or hi < lo:
                    raise ValueError("OHLC_INCONSISTENT")
                if prev is not None:
                    delta = stamp-prev
                    if delta <= 0:
                        raise ValueError("DUPLICATE_OR_NONMONOTONIC_TIMESTAMP")
                    if delta % INTERVAL_MS[timeframe] != 0:
                        raise ValueError("IRREGULAR_TIMESTAMP_INTERVAL")
                    missing += delta // INTERVAL_MS[timeframe]-1
                prev = stamp
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                errors.append({"row": count, "reason": str(exc)[:100]})
                break
    if count < 300:
        errors.append({"row": count, "reason": "INSUFFICIENT_CANDLES"})
    if missing > max_missing:
        errors.append({"row": count, "reason": "MISSING_CANDLES"})
    return {"version": "V206.0", "status": "PASS" if not errors else "BLOCK",
            "candles": count, "missing_candles": missing, "errors": errors,
            "timeframe": timeframe, "research_only": True,
            "orders_allowed": False, "live_trading_approved": False}
