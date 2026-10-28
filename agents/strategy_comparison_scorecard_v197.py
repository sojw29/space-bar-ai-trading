"""V197 read-only holdout comparison scorecard; not a strategy selection engine.

Sorts by identifier, never by profitability. No composite score or trade approval.
"""
import math


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def build_scorecard(report):
    if not isinstance(report, dict) or report.get("version") != "V105.0":
        raise ValueError("INVALID_V105_REPORT")
    strategies = report.get("strategies")
    assessments = report.get("evidence_assessments")
    if not isinstance(strategies, list) or not isinstance(assessments, list) or not strategies or len(strategies) != len(assessments):
        raise ValueError("MISSING_OR_MISMATCHED_EVIDENCE")
    rows = []
    seen = set()
    for comparison, assessment in zip(strategies, assessments):
        if not isinstance(comparison, dict) or not isinstance(assessment, dict):
            raise ValueError("INVALID_STRATEGY_ROW")
        name = comparison.get("strategy")
        validation = comparison.get("validation")
        if not isinstance(name, str) or not name or name in seen or not isinstance(validation, dict):
            raise ValueError("INVALID_STRATEGY_IDENTITY")
        seen.add(name)
        trades = validation.get("trades")
        if type(trades) is not int or trades < 0:
            raise ValueError("INVALID_TRADE_COUNT")
        for key in ("win_rate", "return", "profit_factor", "max_drawdown"):
            if not _finite(validation.get(key)):
                raise ValueError("INVALID_METRICS")
        if not 0 <= validation["win_rate"] <= 100 or not 0 <= validation["max_drawdown"] <= 100 or validation["profit_factor"] < 0:
            raise ValueError("INVALID_METRIC_RANGE")
        if assessment.get("orders_allowed") is not False or assessment.get("live_trading_approved") is not False:
            raise ValueError("UNSAFE_EVIDENCE_ASSESSMENT")
        if assessment.get("status") not in ("INSUFFICIENT_EVIDENCE", "EVIDENCE_REVIEWABLE"):
            raise ValueError("UNKNOWN_EVIDENCE_STATUS")
        rows.append({
            "strategy": name, "holdout_trades": trades,
            "holdout_win_rate_pct": validation["win_rate"],
            "holdout_net_return_pct": validation["return"],
            "holdout_profit_factor": validation["profit_factor"],
            "holdout_max_drawdown_pct": validation["max_drawdown"],
            "evidence_status": assessment["status"],
            "evidence_failures": assessment.get("failures", []),
        })
    return {
        "version": "V197.0", "status": "RESEARCH_COMPARISON_ONLY",
        "rows": sorted(rows, key=lambda row: row["strategy"]),
        "ranking_enabled": False, "strategy_selection_enabled": False,
        "research_only": True, "orders_allowed": False, "live_trading_approved": False,
        "note": "Side-by-side descriptive holdout metrics; not evidence of statistical significance, reproducibility or deployability.",
    }
