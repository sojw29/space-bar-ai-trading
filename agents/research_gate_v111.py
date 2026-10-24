"""V111 conservative research review gate.

Never enables orders. Sufficient evidence only means a report is eligible
for human review, not that a strategy is profitable or safe to trade.
"""
import argparse
import json
import math
from walkforward_stability_v110 import run as run_stability

def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)

def evaluate(stability_report, min_positive_fraction=0.6,
             max_worst_drawdown_pct=15.0, min_mean_return_pct=0.0):
    thresholds = (min_positive_fraction, max_worst_drawdown_pct, min_mean_return_pct)
    if (not all(_finite(x) for x in thresholds) or
            not 0 <= min_positive_fraction <= 1 or
            not 0 <= max_worst_drawdown_pct <= 100 or
            not -100 <= min_mean_return_pct <= 100):
        raise ValueError("INVALID_REVIEW_THRESHOLDS")
    if (not isinstance(stability_report, dict) or
            stability_report.get("version") != "V110.0" or
            not isinstance(stability_report.get("strategies"), list) or
            not stability_report["strategies"]):
        raise ValueError("INVALID_STABILITY_REPORT")
    results = []
    for strategy in stability_report["strategies"]:
        if not isinstance(strategy, dict) or not isinstance(strategy.get("strategy"), str):
            raise ValueError("INVALID_STRATEGY")
        count = strategy.get("validation_folds")
        trades = strategy.get("total_validation_trades")
        sufficient = strategy.get("sample_sufficient")
        if (type(count) is not int or count < 0 or
                type(trades) is not int or trades < 0 or
                type(sufficient) is not bool):
            raise ValueError("INVALID_EVIDENCE_FIELDS")
        metrics = {
            "positive_fold_fraction": strategy.get("positive_fold_fraction"),
            "mean_fold_return_pct": strategy.get("mean_fold_return_pct"),
            "worst_fold_max_drawdown_pct": strategy.get("worst_fold_max_drawdown_pct"),
        }
        if any(not _finite(v) for v in metrics.values()):
            if sufficient:
                raise ValueError("INVALID_SUFFICIENT_METRICS")
            passed = False
            checks = {k: False for k in metrics}
        else:
            if (not 0 <= metrics["positive_fold_fraction"] <= 1 or
                    not -100 <= metrics["mean_fold_return_pct"] <= 100 or
                    not 0 <= metrics["worst_fold_max_drawdown_pct"] <= 100):
                raise ValueError("INVALID_METRIC_RANGE")
            checks = {
                "positive_fold_fraction": metrics["positive_fold_fraction"] >= min_positive_fraction,
                "mean_fold_return_pct": metrics["mean_fold_return_pct"] > min_mean_return_pct,
                "worst_fold_max_drawdown_pct": metrics["worst_fold_max_drawdown_pct"] <= max_worst_drawdown_pct,
            }
            passed = sufficient and count >= 4 and all(checks.values())
        results.append({
            "strategy": strategy["strategy"],
            "validation_folds": count,
            "total_validation_trades": trades,
            "sample_sufficient": sufficient,
            "review_checks": checks,
            "status": "HUMAN_REVIEW_CANDIDATE" if passed else "INSUFFICIENT_OR_UNFAVORABLE_EVIDENCE",
            "live_trading_approved": False,
        })
    return {
        "version": "V111.0", "status": "HUMAN_REVIEW_ONLY",
        "thresholds": {
            "min_positive_fold_fraction": min_positive_fraction,
            "max_worst_fold_drawdown_pct": max_worst_drawdown_pct,
            "min_mean_fold_return_pct_exclusive": min_mean_return_pct,
        },
        "strategies": results,
        "research_only": True, "orders_enabled": False,
        "live_trading_approved": False, "validated_edge": False,
        "limitations": "Heuristic review filters, not statistically calibrated. Selection on repeated holdouts can overfit; no live execution, forward evidence or profitability guarantee.",
    }

def run(source, train_size=160, validation_size=80):
    return evaluate(run_stability(source, train_size, validation_size))

def main():
    parser = argparse.ArgumentParser(description="V111 conservative research review gate")
    parser.add_argument("history_csv")
    parser.add_argument("--train-size", type=int, default=160)
    parser.add_argument("--validation-size", type=int, default=80)
    args = parser.parse_args()
    print(json.dumps(run(args.history_csv, args.train_size, args.validation_size), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
