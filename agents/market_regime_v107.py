"""V107 causal market-regime diagnostics for offline OHLCV snapshots.

Labels each completed candle from only current/prior observations.
Regime labels are descriptive and not proof of a profitable strategy.
"""
import argparse
import csv
import json
import math
from pathlib import Path
from chronological_holdout_v102 import split_csv
from ema_holdout_pipeline_v104 import _ema

WINDOW = 20
MIN_ROWS = 80

def classify(rows, threshold_pct=0.5, volatility_pct=3.0):
    if not isinstance(rows, list) or len(rows) < MIN_ROWS:
        raise ValueError("INSUFFICIENT_CANDLES")
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 or v > 100
           for v in (threshold_pct, volatility_pct)):
        raise ValueError("INVALID_THRESHOLDS")
    closes = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("INVALID_ROW")
        try:
            value = float(row["close"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("INVALID_CLOSE") from exc
        if not math.isfinite(value) or value <= 0:
            raise ValueError("INVALID_CLOSE")
        closes.append(value)
    ema = _ema(closes, WINDOW)
    results = []
    for i in range(WINDOW, len(rows)):
        # No future candle information enters this label.
        base = ema[i-WINDOW]
        trend_pct = (ema[i] / base - 1) * 100
        recent = closes[i-WINDOW+1:i+1]
        high = max(recent)
        low = min(recent)
        range_pct = (high/low - 1) * 100
        if range_pct >= volatility_pct:
            label = "HIGH_VOLATILITY"
        elif trend_pct > threshold_pct:
            label = "UPTREND"
        elif trend_pct < -threshold_pct:
            label = "DOWNTREND"
        else:
            label = "SIDEWAYS"
        results.append({"index": i, "timestamp": rows[i]["timestamp"],
                        "regime": label, "trend_pct": round(trend_pct, 6),
                        "range_pct": round(range_pct, 6)})
    return results

def summarize(labels):
    counts = {k: 0 for k in ("UPTREND", "DOWNTREND", "SIDEWAYS", "HIGH_VOLATILITY")}
    for label in labels:
        if label["regime"] not in counts:
            raise ValueError("UNKNOWN_REGIME")
        counts[label["regime"]] += 1
    return {"count": len(labels), "regime_counts": counts}

def run(source):
    # Validate full source via V102 before descriptive regime calculations.
    import tempfile
    with tempfile.TemporaryDirectory(prefix="spacebar-v107-") as tmp:
        train = Path(tmp)/"train.csv"
        valid = Path(tmp)/"validation.csv"
        split = split_csv(source, train, valid, ratio=0.7, min_rows=MIN_ROWS)
        with train.open(newline="", encoding="utf-8") as f:
            train_rows = list(csv.DictReader(f))
        with valid.open(newline="", encoding="utf-8") as f:
            valid_rows = list(csv.DictReader(f))
        train_labels = classify(train_rows)
        validation_labels = classify(valid_rows)
    return {"version": "V107.0", "status": "DESCRIPTIVE_REGIME_REPORT",
            "split": split, "train": summarize(train_labels),
            "validation": summarize(validation_labels),
            "lookback_bars": WINDOW,
            "research_only": True, "orders_enabled": False,
            "live_trading_approved": False, "validated_edge": False,
            "limitations": "Heuristic causal candle labels only. No per-regime trade PnL or strategy ranking yet."}

def main():
    parser = argparse.ArgumentParser(description="V107 offline market-regime diagnostics")
    parser.add_argument("history_csv")
    args = parser.parse_args()
    print(json.dumps(run(args.history_csv), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
