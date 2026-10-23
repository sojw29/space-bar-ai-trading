"""V35 post-hoc research outcome annotations.

Descriptive close-to-close moves after historical decision candles, NOT
independent out-of-sample, trade returns, accuracy or executable fills.
Never mutates the V34 immutable SQLite ledger. No network or orders.
"""
import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from decision_ledger_v34 import read_recent, validate_envelope

PERIOD_SECONDS = 300
HORIZONS = (1, 3, 12)


def read_closed_history(path):
    """Strict chronological closed candles; do not interpolate gaps."""
    candles = {}
    prior = None
    now = datetime.now(timezone.utc).timestamp()
    with Path(path).open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if not {"timestamp", "close"}.issubset(reader.fieldnames or []):
            raise ValueError("History requires timestamp and close")
        for row in reader:
            ts = int(row["timestamp"])
            close = float(row["close"])
            if not math.isfinite(close) or close <= 0:
                raise ValueError("Invalid closing price")
            if ts + PERIOD_SECONDS > now:
                raise ValueError("History includes incomplete future candle")
            if prior is not None and ts != prior + PERIOD_SECONDS:
                raise ValueError("History contains a gap, duplicate or out-of-order candle")
            candles[ts] = close
            prior = ts
    return candles


def _timestamp(iso):
    when = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if when.tzinfo is None:
        raise ValueError("Naive UTC candle")
    value = when.timestamp()
    if int(value) != value:
        raise ValueError("Candle timestamp requires seconds precision")
    return int(value)


def evaluate(entries, history, horizons=HORIZONS):
    if not horizons or any(isinstance(x, bool) or not isinstance(x, int)
                           or x < 1 or x > 288 for x in horizons):
        raise ValueError("Horizon must be 1..288 candles")
    output = []
    for entry in entries:
        envelope = entry["event_envelope"]
        validate_envelope(envelope)
        ts = _timestamp(envelope["observed_candle_utc"])
        commander = next(x for x in envelope["events"] if x["agent_id"] == "COMMANDER")
        base = history.get(ts)
        outcomes = []
        for bars in horizons:
            target = ts + bars * PERIOD_SECONDS
            # Verify each intermediate step exists, even if endpoint exists.
            complete = base is not None and all(ts + n * PERIOD_SECONDS in history
                                                 for n in range(1, bars + 1))
            if not complete:
                outcomes.append({"horizon_bars": bars, "status": "INSUFFICIENT_FUTURE_CANDLES",
                                 "raw_close_change_pct": None, "direction_match": None})
                continue
            move = 100.0 * (history[target] / base - 1.0)
            direction = commander["decision"]
            match = None if direction == "WAIT" else (move > 0 if direction == "LONG" else move < 0)
            outcomes.append({"horizon_bars": bars, "status": "POSTHOC_OBSERVED",
                             "raw_close_change_pct": round(move, 6),
                             "direction_match": match})
        output.append({
            "symbol": envelope["symbol"],
            "timeframe": envelope["timeframe"],
            "candle_utc": envelope["observed_candle_utc"],
            "recorded_utc": entry["recorded_utc"],
            "decision": commander["decision"],
            "risk_veto": commander["risk_veto"],
            "source": "HISTORICAL_POSTHOC",
            "independent_oos_verified": False,
            "trading_result": False,
            "outcomes": outcomes,
        })
    return output


def main():
    parser = argparse.ArgumentParser(description="V35 post-hoc closed-candle research annotations")
    parser.add_argument("--db", type=Path, default=Path("reports/v34/research_decisions.sqlite3"))
    parser.add_argument("--history", type=Path, default=Path("data/history/BTC_5m.csv"))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args()
    entries = read_recent(args.db, args.limit)
    history = read_closed_history(args.history)
    report = {
        "schema_version": "35.0",
        "mode": "HISTORICAL_POSTHOC",
        "independent_oos_verified": False,
        "trading_result": False,
        "notes": "Close-to-close observations only; no execution, costs, or validated edge.",
        "records": evaluate(entries, history),
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
