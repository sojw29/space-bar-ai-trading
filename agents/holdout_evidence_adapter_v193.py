"""V193 bridge existing V104/V105 holdout summaries to the V192 gate.

Never invents execution costs or out-of-sample attestation. Existing V104/V105
omit slippage, so the adapted report MUST remain insufficient evidence.
"""
from backtest_evidence_gate_v192 import evaluate_backtest_evidence


def assess_legacy_holdout(result):
    """Return conservative assessment of legacy offline holdout outputs."""
    if not isinstance(result, dict):
        return evaluate_backtest_evidence(result)
    comparison = result.get("comparison")
    comparison = comparison if isinstance(comparison, dict) else {}
    validation = comparison.get("validation")
    validation = validation if isinstance(validation, dict) else {}

    fee_rate = result.get("fee_rate_per_side")
    # Legacy fee rate is a fraction, whereas V192 uses percent.
    fee_pct = fee_rate * 100 if type(fee_rate) in (int, float) else None

    report = {
        "mode": "historical_offline_backtest",
        "holdout_is_out_of_sample": comparison.get("independent_holdout") is True,
        "strategy_parameters_frozen_before_holdout": comparison.get("strategy_frozen_before_validation") is True,
        "research_only": result.get("research_only"),
        "orders_enabled": result.get("orders_enabled"),
        "fee_pct_per_side": fee_pct,
        # Never fill in slippage with zero unless a source explicitly attests it.
        "slippage_pct_per_side": None,
        "holdout_includes_fees_and_slippage": False,
        "holdout": {
            "trades": validation.get("trades"),
            "net_return_pct": validation.get("return"),
            "max_drawdown_pct": validation.get("max_drawdown"),
            "profit_factor": validation.get("profit_factor"),
        },
    }
    assessment = evaluate_backtest_evidence(report)
    assessment["source_version"] = result.get("version")
    assessment["cost_model_limitation"] = "Legacy V104/V105 omit slippage/spread/funding; reported returns are not all-in execution-cost adjusted."
    return assessment
