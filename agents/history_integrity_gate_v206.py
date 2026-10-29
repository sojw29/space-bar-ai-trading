"""V206 fail-closed historical OHLCV integrity gate for offline research.

Validates chronology, numeric sanity, duplicate timestamps and expected cadence.
No exchange connectivity, live orders or automated strategy selection.
"""
import csv
import math
from pathlib import Path

# Allow a complete 365-day 1-minute history (525,600 candles) with a bounded margin.
MAX_ROWS = 600_000
INTERVAL_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000}


def inspect_history(path, timeframe="5m", max_missing=0):
    if timeframe not in INTERVAL_MS or type(max_missing) is not int or max_missing < 0:
        raise ValueError("INVALID_INTEGRITY_SETTINGS")
    source = Path(path)
    if not source.is_file() or source.stat().st_size > 200_000_000:
        raise ValueError("INVALID_HISTORY_FILE")
    prev = None
    timestamp_unit = None
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
                # The history collector writes epoch seconds; other CSV sources
                # may use epoch milliseconds. Normalize without silently
                # accepting mixed units, microseconds or off-grid candles.
                if 1_000_000_000 <= stamp < 10_000_000_000:
                    row_unit, normalized_stamp = "seconds", stamp * 1000
                elif 1_000_000_000_000 <= stamp < 10_000_000_000_000:
                    row_unit, normalized_stamp = "milliseconds", stamp
                else:
                    raise ValueError("INVALID_TIMESTAMP_UNIT")
                if timestamp_unit is None:
                    timestamp_unit = row_unit
                elif timestamp_unit != row_unit:
                    raise ValueError("MIXED_TIMESTAMP_UNITS")
                # Every exchange candle must start on its UTC timeframe grid.
                # A uniformly shifted series can have valid deltas but invalid open times.
                if normalized_stamp % INTERVAL_MS[timeframe] != 0:
                    raise ValueError("MISALIGNED_TIMESTAMP")
                values = [float(row[k]) for k in ("open","high","low","close","volume")]
                op, hi, lo, cl, vol = values
                if not all(map(math.isfinite, values)) or min(op,hi,lo,cl) <= 0 or vol < 0:
                    raise ValueError("NONFINITE_OR_NEGATIVE")
                if lo > min(op,cl) or hi < max(op,cl) or hi < lo:
                    raise ValueError("OHLC_INCONSISTENT")
                if prev is not None:
                    delta = normalized_stamp-prev
                    if delta <= 0:
                        raise ValueError("DUPLICATE_OR_NONMONOTONIC_TIMESTAMP")
                    if delta % INTERVAL_MS[timeframe] != 0:
                        raise ValueError("IRREGULAR_TIMESTAMP_INTERVAL")
                    missing += delta // INTERVAL_MS[timeframe]-1
                prev = normalized_stamp
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                errors.append({"row": count, "reason": str(exc)[:100]})
                break
    if count < 300:
        errors.append({"row": count, "reason": "INSUFFICIENT_CANDLES"})
    if missing > max_missing:
        errors.append({"row": count, "reason": "MISSING_CANDLES"})
    return {"version": "V206.0", "status": "PASS" if not errors else "BLOCK",
            "candles": count, "missing_candles": missing, "errors": errors,
            "timeframe": timeframe, "timestamp_unit": timestamp_unit,
            "research_only": True,
            "orders_allowed": False, "live_trading_approved": False}
