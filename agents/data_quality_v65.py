"""V65 offline historical candle quality scorecard; research-only, no network."""
import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from archive_lag_v64 import SYMBOLS, TIMEFRAMES, diagnose_file

def score_file(path, timeframe, now=None):
    now = now or datetime.now(timezone.utc)
    lag = diagnose_file(path, timeframe, now)
    result = {"path": str(path), "timeframe_minutes": timeframe,
              "archive": lag, "rows": 0, "gaps": 0, "missing_internal_bars": 0,
              "invalid_ohlcv_rows": 0, "duplicate_or_out_of_order": 0,
              "coverage_pct": None, "status": "UNVERIFIED", "research_usable": False,
              "expected_bars": 365 * 24 * 60 // timeframe,
              "missing_start_bars": None, "missing_end_bars": None}
    if lag["status"] == "ERROR":
        result["status"] = "FAIL"
        return result
    previous = None
    first = None
    last = None
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            needed = {"timestamp", "open", "high", "low", "close", "volume"}
            if not needed.issubset(reader.fieldnames or []):
                result["status"] = "FAIL"
                return result
            for row in reader:
                result["rows"] += 1
                stamp = int(row["timestamp"])
                if first is None:
                    first = stamp
                if previous is not None:
                    delta = stamp - previous
                    if delta <= 0 or delta % (timeframe * 60):
                        result["duplicate_or_out_of_order"] += 1
                    elif delta > timeframe * 60:
                        result["gaps"] += 1
                        result["missing_internal_bars"] += delta // (timeframe * 60) - 1
                previous = stamp
                last = stamp
                try:
                    o, h, l, c, v = [float(row[k]) for k in ("open", "high", "low", "close", "volume")]
                    if (not all(math.isfinite(x) for x in (o, h, l, c, v))
                        or min(o, h, l, c) <= 0 or v < 0
                        or h < max(o, c, l) or l > min(o, c)):
                        result["invalid_ohlcv_rows"] += 1
                except (ValueError, TypeError, KeyError):
                    result["invalid_ohlcv_rows"] += 1
        if first is None or last is None:
            result["status"] = "FAIL"
            return result
        # Coverage must include the entire 365-day requested archive window.
        # A short, internally contiguous file is not sufficient evidence.
        interval = timeframe * 60
        expected_last = int(datetime.fromisoformat(
            lag["expected_last_closed_candle_utc"]).timestamp())
        expected_start = expected_last - (result["expected_bars"] - 1) * interval
        result["missing_start_bars"] = max(0, (first - expected_start) // interval)
        result["missing_end_bars"] = max(0, (expected_last - last) // interval)
        missing = (result["missing_start_bars"] + result["missing_end_bars"]
                   + result["missing_internal_bars"])
        result["coverage_pct"] = round(
            100 * max(0, result["expected_bars"] - missing) / result["expected_bars"], 4)
        invalid = result["invalid_ohlcv_rows"] or result["duplicate_or_out_of_order"]
        if invalid or first < expected_start or result["rows"] < 2:
            result["status"] = "FAIL"
        elif (missing or last > expected_last
              or lag["status"] != "ON_EXPECTED_ARCHIVE_CUTOFF"):
            result["status"] = "REVIEW"
        else:
            result["status"] = "PASS"
        result["research_usable"] = result["status"] == "PASS"
    except (OSError, ValueError, OverflowError):
        result["status"] = "FAIL"
    return result

def main():
    parser = argparse.ArgumentParser(description="V65 offline candle quality report")
    parser.add_argument("--data-dir", type=Path, default=Path("data/history"))
    parser.add_argument("--output", type=Path, default=Path("reports/v65/quality.json"))
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    rows = [score_file(args.data_dir / f"{symbol}_{tf}m.csv", tf, now)
            for symbol in SYMBOLS for tf in TIMEFRAMES]
    report = {"version": "V65.0", "generated_utc": now.isoformat(),
              "results": rows, "research_only": True,
              "independent_oos_verified": False, "live_trading_approved": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if any(r["status"] == "FAIL" for r in rows) else 0

if __name__ == "__main__":
    raise SystemExit(main())
