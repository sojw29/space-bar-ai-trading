"""V212 ex-post strategy metrics grouped by realized market regime.

Descriptive only: independently restarted backtests per window, with hindsight
regime labels. Never use these labels to generate or approve trade signals.
"""
import csv
import math
import tempfile
from pathlib import Path

from chronological_holdout_v102 import split_csv
from multi_strategy_holdout_v105 import MIN_BARS, STRATEGIES, _metrics

WINDOW = 90
THRESHOLD_PCT = 2.0
REGIMES = ("UP", "DOWN", "SIDEWAYS")


def compare_regime_strategy_metrics(history_csv):
    with tempfile.TemporaryDirectory(prefix="spacebar-v212-") as scratch:
        train = Path(scratch) / "train.csv"
        valid = Path(scratch) / "validation.csv"
        try:
            split_csv(history_csv, train, valid, ratio=0.7, min_rows=MIN_BARS)
        except ValueError as exc:
            if str(exc) != "INSUFFICIENT_ROWS":
                raise
            history = []
        else:
            with valid.open(newline="", encoding="utf-8") as stream:
                history = list(csv.DictReader(stream))
    observations = []
    for end in range(WINDOW, len(history) + 1, WINDOW):
        start = end - WINDOW
        segment = history[start:end]
        first = float(segment[0]["close"])
        last = float(segment[-1]["close"])
        if not (math.isfinite(first) and math.isfinite(last) and first > 0 and last > 0):
            raise ValueError("INVALID_REGIME_PRICES")
        change = (last / first - 1) * 100
        regime = ("UP" if change > THRESHOLD_PCT else
                  "DOWN" if change < -THRESHOLD_PCT else "SIDEWAYS")
        metrics = {strategy: _metrics(segment, strategy) for strategy in STRATEGIES}
        observations.append({"start_validation_index": start,
                             "end_validation_index_exclusive": end,
                             "realized_regime": regime,
                             "realized_price_change_pct": round(change, 6),
                             "strategy_metrics": metrics})
    rows = []
    for strategy in STRATEGIES:
        groups = []
        for regime in REGIMES:
            windows = [item for item in observations if item["realized_regime"] == regime]
            values = [item["strategy_metrics"][strategy] for item in windows]
            groups.append({
                "regime": regime,
                "windows": len(windows),
                "total_hypothetical_trades": sum(x["trades"] for x in values),
                "mean_window_return_pct": (round(sum(x["return"] for x in values)/len(values), 6)
                                           if values else None),
                "positive_return_windows": sum(x["return"] > 0 for x in values),
                "mean_window_max_drawdown_pct": (
                    round(sum(x["max_drawdown"] for x in values)/len(values), 6)
                    if values else None),
                "evidence_status": "DESCRIPTIVE_ONLY" if values else "NO_WINDOWS",
            })
        rows.append({"strategy": strategy, "regimes": groups})
    return {
        "version": "V212.0",
        "status": "DESCRIPTIVE_ONLY" if observations else "INSUFFICIENT_HOLDOUT_CANDLES",
        "window_candles": WINDOW, "threshold_pct": THRESHOLD_PCT,
        "classified_windows": len(observations),
        "window_observations": observations,
        "unclassified_tail_candles": len(history) % WINDOW,
        "rows": rows, "ranking_enabled": False,
        "strategy_selection_enabled": False, "research_only": True,
        "orders_allowed": False, "live_trading_approved": False,
        "limitations": [
            "Regime labels use realized end-of-window prices and cannot be known at window entry.",
            "Backtests restart independently with indicator warmup inside each window.",
            "Mean window returns are not compounded portfolio returns; window trade counts are hypothetical.",
            "Small or empty regime groups provide no evidence of predictive edge or live profitability.",
        ],
    }
