"""V215 descriptive dispersion of per-window returns and drawdowns.

No bootstrap confidence intervals, risk forecasts, strategy selection, or orders.
"""
import math


def _stats(values):
    if not values:
        return None
    if not all(type(x) in (int, float) and math.isfinite(x) for x in values):
        raise ValueError("NONFINITE_WINDOW_METRIC")
    ordered = sorted(values)
    n = len(ordered)
    mean = sum(ordered)/n
    variance = sum((x-mean)**2 for x in ordered)/n
    return {
        "windows": n,
        "mean_pct": round(mean, 6),
        "min_pct": round(ordered[0], 6),
        "max_pct": round(ordered[-1], 6),
        "range_pct": round(ordered[-1]-ordered[0], 6),
        "population_stddev_pct": round(math.sqrt(variance), 6),
    }


def assess_return_drawdown_stability(regime_report):
    if (not isinstance(regime_report, dict) or
            regime_report.get("version") != "V212.0" or
            regime_report.get("research_only") is not True or
            regime_report.get("orders_allowed") is not False or
            regime_report.get("live_trading_approved") is not False):
        raise ValueError("INVALID_OR_UNSAFE_REGIME_REPORT")
    rows = regime_report.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("MISSING_REGIME_STRATEGIES")
    output = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("strategy"), str):
            raise ValueError("INVALID_STRATEGY_ROW")
        groups = row.get("regimes")
        if not isinstance(groups, list) or len(groups) != 3:
            raise ValueError("INVALID_REGIME_GROUPS")
        summaries = []
        seen = set()
        for group in groups:
            if not isinstance(group, dict) or group.get("regime") not in ("UP", "DOWN", "SIDEWAYS") or group["regime"] in seen:
                raise ValueError("INVALID_REGIME_GROUP")
            seen.add(group["regime"])
            count = group.get("windows")
            mean_return = group.get("mean_window_return_pct")
            mean_drawdown = group.get("mean_window_max_drawdown_pct")
            if type(count) is not int or count < 0:
                raise ValueError("INVALID_WINDOW_COUNT")
            if count == 0:
                if mean_return is not None or mean_drawdown is not None:
                    raise ValueError("INCONSISTENT_EMPTY_GROUP")
                status = "NO_WINDOWS"
            else:
                if not all(type(x) in (int, float) and math.isfinite(x)
                           for x in (mean_return, mean_drawdown)):
                    raise ValueError("INVALID_WINDOW_MEANS")
                if not 0 <= mean_drawdown <= 100:
                    raise ValueError("INVALID_DRAWDOWN")
                status = "SINGLE_WINDOW_ONLY" if count == 1 else "AGGREGATE_MEANS_ONLY"
            summaries.append({
                "regime": group["regime"], "windows": count,
                "mean_window_return_pct": mean_return,
                "mean_window_max_drawdown_pct": mean_drawdown,
                "dispersion_available": False,
                "status": status,
            })
        output.append({"strategy": row["strategy"], "regimes": summaries})
    return {
        "version": "V215.0", "status": "AGGREGATE_LIMITATION_AUDIT",
        "rows": output,
        "research_only": True, "ranking_enabled": False,
        "strategy_selection_enabled": False, "orders_allowed": False,
        "live_trading_approved": False,
        "note": "V212 exposes aggregate means, not individual per-window values. Dispersion and confidence intervals cannot be reconstructed from means; explicitly withheld rather than fabricated.",
    }
