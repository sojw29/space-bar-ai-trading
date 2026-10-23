"""V64: offline diagnosis of historical archive publication lag.

Read-only: no network, exchange API, orders or strategy modifications.
"""
import argparse
import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_DELAY_DAYS = 3
TIMEFRAMES = (1, 5, 15)
SYMBOLS = ("BTC", "ETH", "SOL")

def diagnose_file(path, timeframe, now, delay_days=DEFAULT_DELAY_DAYS):
    cutoff = datetime.fromtimestamp(
        (int(now.timestamp()) // 86400 - delay_days) * 86400, tz=timezone.utc
    )
    expected_last = int((cutoff - timedelta(minutes=timeframe)).timestamp())
    result = {"path": str(path), "timeframe_minutes": timeframe,
              "archive_publication_delay_days": delay_days,
              "expected_last_closed_candle_utc": datetime.fromtimestamp(
                  expected_last, tz=timezone.utc).isoformat(),
              "observed_last_candle_utc": None, "missing_bars_after_observed": None,
              "status": "UNKNOWN", "reasons": []}
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "timestamp" not in reader.fieldnames:
                raise ValueError("MISSING_TIMESTAMP_COLUMN")
            last = None
            for row in reader:
                stamp = int(row["timestamp"])
                if stamp < 0 or stamp % (timeframe * 60):
                    raise ValueError("INVALID_CANDLE_ALIGNMENT")
                if last is not None and stamp <= last:
                    raise ValueError("NON_MONOTONIC_TIMESTAMPS")
                last = stamp
            if last is None:
                raise ValueError("EMPTY_CSV")
        result["observed_last_candle_utc"] = datetime.fromtimestamp(
            last, tz=timezone.utc).isoformat()
        if last > expected_last:
            result["status"] = "WARNING"
            result["reasons"].append("NEWER_THAN_ARCHIVE_CUTOFF")
        elif last < expected_last:
            result["missing_bars_after_observed"] = (expected_last - last) // (timeframe * 60)
            result["status"] = "WARNING"
            result["reasons"].append("ARCHIVE_COVERAGE_LAG")
        else:
            result["missing_bars_after_observed"] = 0
            result["status"] = "ON_EXPECTED_ARCHIVE_CUTOFF"
    except (OSError, ValueError, OverflowError) as exc:
        result["status"] = "ERROR"
        result["reasons"].append("UNREADABLE_OR_INVALID_CSV")
        result["detail"] = str(exc)
    return result

def main():
    parser = argparse.ArgumentParser(description="Offline archive lag diagnostics")
    parser.add_argument("--data-dir", type=Path, default=Path("data/history"))
    parser.add_argument("--output", type=Path, default=Path("reports/v64/archive_lag.json"))
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    rows = [diagnose_file(args.data_dir / f"{coin}_{tf}m.csv", tf, now)
            for coin in SYMBOLS for tf in TIMEFRAMES]
    report = {"version": "V64.0", "generated_utc": now.isoformat(),
              "archive_delay_is_expected_not_realtime": True,
              "results": rows, "live_trading_approved": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if any(row["status"] == "ERROR" for row in rows) else 0

if __name__ == "__main__":
    raise SystemExit(main())
