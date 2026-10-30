"""V210 descriptive chronological stability across non-overlapping holdout slices.

Research only. No strategy selection, orders, optimization or profitability claim.
"""
import csv
import math
from pathlib import Path

from chronological_holdout_v102 import split_csv
from multi_strategy_holdout_v105 import MIN_BARS, STRATEGIES, _metrics

SLICES = 3


def assess_stability(history_csv):
    # Use the exact 70/30 chronological split as the V105 baseline.
    import tempfile
    with tempfile.TemporaryDirectory(prefix="spacebar-v210-") as folder:
        train = Path(folder) / "train.csv"
        valid = Path(folder) / "validation.csv"
        split_csv(history_csv, train, valid, ratio=0.7, min_rows=MIN_BARS)
        with valid.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
    # Each independent slice needs enough candles for its own indicator warmup.
    if len(rows) < SLICES * MIN_BARS:
        return {"version": "V210.0", "status": "INSUFFICIENT_HOLDOUT_CANDLES",
                "slice_count": SLICES, "min_candles_per_slice": MIN_BARS,
                "rows": [], "research_only": True, "orders_allowed": False,
                "live_trading_approved": False, "ranking_enabled": False}
    sizes = [len(rows)//SLICES + (1 if i < len(rows)%SLICES else 0)
             for i in range(SLICES)]
    segments = []
    start = 0
    for size in sizes:
        segments.append(rows[start:start+size])
        start += size
    results = []
    for strategy in STRATEGIES:
        metrics = [_metrics(segment, strategy) for segment in segments]
        returns = [m["return"] for m in metrics]
        results.append({
            "strategy": strategy,
            "slices": [{"index": i+1, "candles": len(segments[i]),
                        "trades": metrics[i]["trades"],
                        "net_return_pct": metrics[i]["return"],
                        "max_drawdown_pct": metrics[i]["max_drawdown"]}
                       for i in range(SLICES)],
            "positive_slices": sum(x > 0 for x in returns),
            "negative_slices": sum(x < 0 for x in returns),
            "return_range_pct": round(max(returns)-min(returns), 6),
            "status": "DESCRIPTIVE_ONLY",
        })
    return {"version": "V210.0", "status": "DESCRIPTIVE_STABILITY_ONLY",
            "slice_count": SLICES, "min_candles_per_slice": MIN_BARS,
            "rows": results, "ranking_enabled": False,
            "strategy_selection_enabled": False, "research_only": True,
            "orders_allowed": False, "live_trading_approved": False,
            "limitations": [
                "Each slice independently warms indicators; slice metrics are not additive.",
                "Three adjacent non-overlapping holdout slices are not repeated independent experiments.",
                "No statistical significance, regime attribution, or live performance evidence.",
            ]}
