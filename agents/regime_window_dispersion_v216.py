"""V216 descriptive return/drawdown dispersion from actual V212 window observations.

Does not infer future risk or compute confidence intervals.
"""
import math


def _summary(values):
    if not values:
        return None
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in values):
        raise ValueError("NONFINITE_WINDOW_METRIC")
    n = len(values)
    mean = sum(values) / n
    return {
        "windows": n,
        "mean_pct": round(mean, 6),
        "min_pct": round(min(values), 6),
        "max_pct": round(max(values), 6),
        "range_pct": round(max(values) - min(values), 6),
        "population_stddev_pct": round(math.sqrt(sum((x - mean)**2 for x in values) / n), 6),
    }


def assess_window_dispersion(regime_report):
    if (not isinstance(regime_report, dict) or
            regime_report.get("version") != "V212.0" or
            regime_report.get("research_only") is not True or
            regime_report.get("orders_allowed") is not False or
            regime_report.get("live_trading_approved") is not False):
        raise ValueError("INVALID_OR_UNSAFE_REGIME_REPORT")
    observations = regime_report.get("window_observations")
    strategies = regime_report.get("rows")
    if not isinstance(observations, list) or not isinstance(strategies, list) or not strategies:
        raise ValueError("MISSING_WINDOW_OBSERVATIONS")
    if len(observations) != regime_report.get("classified_windows"):
        raise ValueError("WINDOW_COUNT_MISMATCH")
    expected_start = 0
    for item in observations:
        if not isinstance(item, dict) or item.get("start_validation_index") != expected_start:
            raise ValueError("NONCONTIGUOUS_WINDOWS")
        end = item.get("end_validation_index_exclusive")
        if type(end) is not int or end - expected_start != regime_report.get("window_candles"):
            raise ValueError("INVALID_WINDOW_LENGTH")
        expected_start = end
        if item.get("realized_regime") not in ("UP", "DOWN", "SIDEWAYS"):
            raise ValueError("INVALID_WINDOW_REGIME")
    output = []
    for strategy in strategies:
        if not isinstance(strategy, dict) or not isinstance(strategy.get("strategy"), str):
            raise ValueError("INVALID_STRATEGY")
        name = strategy["strategy"]
        groups = strategy.get("regimes")
        if not isinstance(groups, list) or len(groups) != 3:
            raise ValueError("INVALID_REGIME_GROUPS")
        results = []
        for group in groups:
            regime = group.get("regime")
            if regime not in ("UP", "DOWN", "SIDEWAYS"):
                raise ValueError("INVALID_REGIME")
            windows = [item for item in observations if item["realized_regime"] == regime]
            if len(windows) != group.get("windows"):
                raise ValueError("REGIME_COUNT_MISMATCH")
            metrics = []
            for item in windows:
                metric = item.get("strategy_metrics", {}).get(name)
                if not isinstance(metric, dict):
                    raise ValueError("MISSING_WINDOW_STRATEGY_METRICS")
                ret, dd = metric.get("return"), metric.get("max_drawdown")
                if (type(ret) not in (int, float) or not math.isfinite(ret) or
                        type(dd) not in (int, float) or not math.isfinite(dd) or not 0 <= dd <= 100):
                    raise ValueError("INVALID_WINDOW_METRICS")
                metrics.append((ret, dd))
            returns = _summary([x[0] for x in metrics])
            drawdowns = _summary([x[1] for x in metrics])
            if returns is not None:
                if (abs(returns["mean_pct"] - group["mean_window_return_pct"]) > 0.000002 or
                        abs(drawdowns["mean_pct"] - group["mean_window_max_drawdown_pct"]) > 0.000002):
                    raise ValueError("WINDOW_AGGREGATE_MISMATCH")
            results.append({"regime": regime, "windows": len(windows),
                            "return_dispersion": returns,
                            "drawdown_dispersion": drawdowns,
                            "status": "NO_WINDOWS" if not windows else
                                      "SINGLE_WINDOW_ONLY" if len(windows)==1 else
                                      "DESCRIPTIVE_DISPERSION_ONLY"})
        output.append({"strategy": name, "regimes": results})
    return {
        "version": "V216.0", "status": "DESCRIPTIVE_DISPERSION_ONLY",
        "rows": output, "research_only": True, "orders_allowed": False,
        "live_trading_approved": False, "ranking_enabled": False,
        "strategy_selection_enabled": False,
        "note": "Per-window population standard deviation is descriptive; windows share a time series and hindsight labels. No statistical confidence or future risk prediction.",
    }
