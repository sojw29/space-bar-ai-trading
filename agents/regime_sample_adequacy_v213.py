"""V213 explicit sample-size cautions for ex-post regime comparisons.

Thresholds are descriptive reporting heuristics, not statistical validation.
"""
MIN_WINDOWS = 5
MIN_HYPOTHETICAL_TRADES = 20


def assess_regime_sample_adequacy(regime_report):
    if (not isinstance(regime_report, dict) or
            regime_report.get("version") != "V212.0" or
            regime_report.get("research_only") is not True or
            regime_report.get("orders_allowed") is not False or
            regime_report.get("live_trading_approved") is not False):
        raise ValueError("INVALID_OR_UNSAFE_REGIME_REPORT")
    rows = regime_report.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("MISSING_REGIME_STRATEGIES")
    checks = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("strategy"), str):
            raise ValueError("INVALID_REGIME_STRATEGY")
        groups = row.get("regimes")
        if not isinstance(groups, list) or len(groups) != 3:
            raise ValueError("INVALID_REGIME_GROUPS")
        seen = set()
        for group in groups:
            if not isinstance(group, dict):
                raise ValueError("INVALID_REGIME_GROUP")
            regime = group.get("regime")
            windows = group.get("windows")
            trades = group.get("total_hypothetical_trades")
            if (regime not in ("UP", "DOWN", "SIDEWAYS") or regime in seen or
                    type(windows) is not int or windows < 0 or
                    type(trades) is not int or trades < 0):
                raise ValueError("INVALID_REGIME_COUNTS")
            seen.add(regime)
            reasons = []
            if windows < MIN_WINDOWS:
                reasons.append("FEWER_THAN_5_WINDOWS")
            if trades < MIN_HYPOTHETICAL_TRADES:
                reasons.append("FEWER_THAN_20_HYPOTHETICAL_TRADES")
            checks.append({
                "strategy": row["strategy"], "regime": regime,
                "windows": windows, "hypothetical_trades": trades,
                "sample_status": "LIMITED_SAMPLE" if reasons else "DESCRIPTIVE_SAMPLE_THRESHOLD_MET",
                "cautions": reasons,
            })
    return {
        "version": "V213.0",
        "status": "DESCRIPTIVE_SAMPLE_CHECK_ONLY",
        "min_windows": MIN_WINDOWS,
        "min_hypothetical_trades": MIN_HYPOTHETICAL_TRADES,
        "checks": checks,
        "limited_groups": sum(x["sample_status"] == "LIMITED_SAMPLE" for x in checks),
        "research_only": True, "ranking_enabled": False,
        "strategy_selection_enabled": False, "orders_allowed": False,
        "live_trading_approved": False,
        "note": "Thresholds are reporting cautions only; meeting them does not establish statistical significance, predictive edge, or deployability.",
    }
