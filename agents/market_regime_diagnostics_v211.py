"""V211 descriptive, ex-post market-regime diagnostics for frozen OHLCV history.

No trading signals, strategy ranking, live market classification, or orders.
"""
import csv
import math
from pathlib import Path

from chronological_holdout_v102 import split_csv

WINDOW = 30
THRESHOLD_PCT = 2.0
REGIMES = ("UP", "DOWN", "SIDEWAYS")


def inspect_regimes(history_csv):
    import tempfile
    with tempfile.TemporaryDirectory(prefix="spacebar-v211-") as folder:
        train = Path(folder) / "train.csv"
        valid = Path(folder) / "validation.csv"
        split_csv(history_csv, train, valid, ratio=0.7, min_rows=80)
        with valid.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
    closes = [float(row["close"]) for row in rows]
    if not all(math.isfinite(price) and price > 0 for price in closes):
        raise ValueError("INVALID_REGIME_CLOSES")
    counts = {name: 0 for name in REGIMES}
    observations = []
    for end in range(WINDOW, len(closes)+1, WINDOW):
        start = end-WINDOW
        change = (closes[end-1]/closes[start]-1)*100
        regime = ("UP" if change > THRESHOLD_PCT else
                  "DOWN" if change < -THRESHOLD_PCT else "SIDEWAYS")
        counts[regime] += 1
        observations.append({
            "start_validation_index": start, "end_validation_index_exclusive": end,
            "regime": regime, "price_change_pct": round(change, 6),
            "candles": WINDOW,
        })
    return {
        "version": "V211.0",
        "status": "DESCRIPTIVE_ONLY" if observations else "INSUFFICIENT_HOLDOUT_CANDLES",
        "method": "EX_POST_NON_OVERLAPPING_CLOSE_TO_CLOSE",
        "window_candles": WINDOW, "threshold_pct": THRESHOLD_PCT,
        "counts": counts, "observations": observations,
        "unclassified_tail_candles": len(closes) % WINDOW,
        "research_only": True, "ranking_enabled": False,
        "strategy_selection_enabled": False, "orders_allowed": False,
        "live_trading_approved": False,
        "limitations": [
            "Regimes use the full window ending close and are knowable only after the window closes.",
            "Regime counts do not measure strategy performance within each regime.",
            "No realtime classification, trade signals, or independently verified predictive edge.",
        ],
    }
