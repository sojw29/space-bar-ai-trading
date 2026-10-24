"""V110 descriptive walk-forward stability audit.

No optimization, forecasting, statistical significance, or live approval.
"""
import argparse
import json
import math
from walkforward_v109 import run as run_walkforward

def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)

def analyze(report, minimum_folds=4, minimum_trades=30):
    if type(minimum_folds) is not int or minimum_folds < 4:
        raise ValueError("INVALID_MINIMUM_FOLDS")
    if type(minimum_trades) is not int or minimum_trades < 30:
        raise ValueError("INVALID_MINIMUM_TRADES")
    if not isinstance(report, dict) or report.get("version") != "V109.0":
        raise ValueError("INVALID_WALKFORWARD_REPORT")
    strategies = report.get("results")
    if not isinstance(strategies, list) or not strategies:
        raise ValueError("MISSING_STRATEGIES")
    results = []
    for item in strategies:
        if not isinstance(item, dict) or not isinstance(item.get("strategy"), str):
            raise ValueError("INVALID_STRATEGY")
        folds = item.get("folds")
        if not isinstance(folds, list):
            raise ValueError("INVALID_FOLDS")
        values = []
        trade_counts = []
        drawdowns = []
        last_end = None
        for fold in folds:
            if not isinstance(fold, dict) or not isinstance(fold.get("validation"), dict):
                raise ValueError("INVALID_FOLD")
            start = fold.get("validation_start_timestamp")
            end = fold.get("validation_end_timestamp")
            if start is None or end is None:
                raise ValueError("MISSING_BOUNDARIES")
            from chronological_holdout_v102 import _timestamp
            start_t, end_t = _timestamp(str(start)), _timestamp(str(end))
            if start_t > end_t or (last_end is not None and start_t <= last_end):
                raise ValueError("OVERLAPPING_OR_UNSORTED_VALIDATION")
            last_end = end_t
            metrics = fold["validation"]
            for key in ("return", "max_drawdown"):
                if not _finite(metrics.get(key)):
                    raise ValueError("NONFINITE_METRICS")
            trades = metrics.get("trades")
            if type(trades) is not int or trades < 0:
                raise ValueError("INVALID_TRADE_COUNT")
            if not (metrics["return"] >= -100 and 0 <= metrics["max_drawdown"] <= 100):
                raise ValueError("INVALID_METRIC_RANGE")
            values.append(metrics["return"])
            trade_counts.append(trades)
            drawdowns.append(metrics["max_drawdown"])
        sufficient = (len(values) >= minimum_folds and
                      all(n >= minimum_trades for n in trade_counts))
        positives = sum(x > 0 for x in values)
        negatives = sum(x < 0 for x in values)
        mean = sum(values)/len(values) if values else None
        worst = min(values) if values else None
        best = max(values) if values else None
        dispersion = (math.sqrt(sum((x-mean)**2 for x in values)/len(values))
                      if values else None)
        # Each fold starts with fresh capital: do not compound or add fold returns
        # as if they were one continuous portfolio.
        results.append({
            "strategy": item["strategy"],
            "validation_folds": len(values),
            "positive_folds": positives,
            "negative_folds": negatives,
            "positive_fold_fraction": round(positives/len(values), 6) if values else None,
            "mean_fold_return_pct": round(mean, 6) if mean is not None else None,
            "worst_fold_return_pct": round(worst, 6) if worst is not None else None,
            "best_fold_return_pct": round(best, 6) if best is not None else None,
            "population_std_fold_return_pct": round(dispersion, 6) if dispersion is not None else None,
            "worst_fold_max_drawdown_pct": round(max(drawdowns), 6) if drawdowns else None,
            "total_validation_trades": sum(trade_counts),
            "minimum_trades_in_fold": min(trade_counts) if trade_counts else None,
            "sample_sufficient": sufficient,
            "status": "DESCRIPTIVE_REVIEW_ONLY" if sufficient else "INSUFFICIENT_EVIDENCE",
        })
    return {"version": "V110.0", "status": "STABILITY_AUDIT_ONLY",
            "strategies": results, "minimum_folds": minimum_folds,
            "minimum_trades_per_fold": minimum_trades,
            "research_only": True, "orders_enabled": False,
            "live_trading_approved": False, "validated_edge": False,
            "limitations": "Fold-level summaries, not statistical confidence. Per-fold returns are not a compounded equity curve; no optimization or real fills."}

def run(source, train_size=160, validation_size=80):
    return analyze(run_walkforward(source, train_size, validation_size))

def main():
    parser = argparse.ArgumentParser(description="V110 offline walk-forward stability audit")
    parser.add_argument("history_csv")
    parser.add_argument("--train-size", type=int, default=160)
    parser.add_argument("--validation-size", type=int, default=80)
    args = parser.parse_args()
    print(json.dumps(run(args.history_csv, args.train_size, args.validation_size), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
