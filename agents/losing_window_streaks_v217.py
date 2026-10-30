"""V217 consecutive losing-window stress diagnostic for ex-post research.

Window-level negative returns are not individual losing trades.
"""
import math


def assess_losing_window_streaks(regime_report):
    if (not isinstance(regime_report, dict) or
            regime_report.get("version") != "V212.0" or
            regime_report.get("research_only") is not True or
            regime_report.get("orders_allowed") is not False or
            regime_report.get("live_trading_approved") is not False):
        raise ValueError("INVALID_OR_UNSAFE_REGIME_REPORT")
    windows = regime_report.get("window_observations")
    rows = regime_report.get("rows")
    if (not isinstance(windows, list) or not isinstance(rows, list) or not rows or
            len(windows) != regime_report.get("classified_windows")):
        raise ValueError("INVALID_WINDOW_SERIES")
    expected_start = 0
    for window in windows:
        if not isinstance(window, dict) or window.get("start_validation_index") != expected_start:
            raise ValueError("NONCONTIGUOUS_WINDOWS")
        end = window.get("end_validation_index_exclusive")
        if type(end) is not int or end - expected_start != regime_report.get("window_candles"):
            raise ValueError("INVALID_WINDOW_LENGTH")
        expected_start = end
    output = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("strategy"), str):
            raise ValueError("INVALID_STRATEGY")
        name = row["strategy"]
        streak = longest = 0
        current_start = longest_start = longest_end = None
        worst_return = None
        negative = 0
        for i, window in enumerate(windows):
            metrics = window.get("strategy_metrics")
            if not isinstance(metrics, dict) or not isinstance(metrics.get(name), dict):
                raise ValueError("MISSING_STRATEGY_WINDOW_METRICS")
            ret = metrics[name].get("return")
            if type(ret) not in (int, float) or not math.isfinite(ret):
                raise ValueError("INVALID_WINDOW_RETURN")
            worst_return = ret if worst_return is None else min(worst_return, ret)
            if ret < 0:
                negative += 1
                if streak == 0:
                    current_start = i
                streak += 1
                if streak > longest:
                    longest = streak
                    longest_start = current_start
                    longest_end = i
            else:
                streak = 0
                current_start = None
        output.append({
            "strategy": name, "classified_windows": len(windows),
            "negative_return_windows": negative,
            "longest_consecutive_negative_windows": longest,
            "longest_streak_start_window_index": longest_start,
            "longest_streak_end_window_index": longest_end,
            "worst_single_window_return_pct": (round(worst_return, 6)
                                                if worst_return is not None else None),
            "status": "NO_WINDOWS" if not windows else "DESCRIPTIVE_ONLY",
        })
    return {
        "version": "V217.0", "status": "DESCRIPTIVE_WINDOW_STRESS_ONLY",
        "rows": output, "research_only": True, "ranking_enabled": False,
        "strategy_selection_enabled": False, "orders_allowed": False,
        "live_trading_approved": False,
        "limitations": [
            "Negative windows are not losing trades; this does not measure trade-level losing streaks.",
            "Window backtests independently restart; losses are not an executable equity curve.",
            "Historical longest streak is not a forecast or a maximum future drawdown.",
        ],
    }
