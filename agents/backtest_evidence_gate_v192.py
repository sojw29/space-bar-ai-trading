"""V192 conservative offline backtest evidence gate.

Evidence sufficiency is NOT a profitability, trading, or deployment approval.
No exchange connection, order execution, or parameter optimization.
"""
import math


def evaluate_backtest_evidence(report, *, min_holdout_trades=100):
    """Validate explicit out-of-sample metrics and cost accounting; fail closed."""
    failures = []
    if type(min_holdout_trades) is not int or min_holdout_trades < 100:
        failures.append("invalid_min_holdout_trades")
        min_holdout_trades = 100
    if not isinstance(report, dict):
        return {"status": "INSUFFICIENT_EVIDENCE", "evidence_sufficient": False,
                "failures": ["invalid_report"], "live_trading_approved": False,
                "orders_allowed": False}

    if report.get("mode") != "historical_offline_backtest":
        failures.append("not_offline_backtest")
    if report.get("holdout_is_out_of_sample") is not True:
        failures.append("holdout_not_verified")
    if report.get("strategy_parameters_frozen_before_holdout") is not True:
        failures.append("parameters_not_frozen")
    if report.get("research_only") is not True or report.get("orders_enabled") is not False:
        failures.append("unsafe_mode")

    holdout = report.get("holdout")
    holdout = holdout if isinstance(holdout, dict) else {}
    trades = holdout.get("trades")
    if type(trades) is not int or trades < min_holdout_trades:
        failures.append("insufficient_holdout_trades")

    for key in ("net_return_pct", "max_drawdown_pct", "profit_factor"):
        value = holdout.get(key)
        if type(value) not in (int, float) or not math.isfinite(value):
            failures.append("missing_or_invalid_" + key)

    fee = report.get("fee_pct_per_side")
    slip = report.get("slippage_pct_per_side")
    if any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in (fee, slip)):
        failures.append("missing_execution_costs")
    if report.get("holdout_includes_fees_and_slippage") is not True:
        failures.append("costs_not_included")

    pf = holdout.get("profit_factor")
    if type(pf) in (int, float) and math.isfinite(pf) and pf < 0:
        failures.append("invalid_profit_factor_range")

    if holdout.get("max_drawdown_pct") is not None and type(holdout.get("max_drawdown_pct")) in (int, float):
        dd = holdout["max_drawdown_pct"]
        if math.isfinite(dd) and not 0 <= dd <= 100:
            failures.append("invalid_drawdown_range")

    return {
        "status": "EVIDENCE_REVIEWABLE" if not failures else "INSUFFICIENT_EVIDENCE",
        "evidence_sufficient": not failures,
        "failures": failures,
        "live_trading_approved": False,
        "orders_allowed": False,
        "note": "Passing checks only establishes basic offline evidence completeness; it does not establish profitability, robustness, or live readiness.",
    }
