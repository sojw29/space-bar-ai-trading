"""V126 descriptive explanations for V125 offline performance warnings.

Indicators of possible contributors, not causal inference or strategy changes.
"""
import argparse
import json
from pathlib import Path

from performance_drift_alerts_v125 import detect

METRIC_EXPLANATIONS = {
    "mean_fold_return_pct": "Average independent validation-fold return changed; inspect fees, market conditions, and sample composition.",
    "worst_fold_max_drawdown_pct": "Worst sampled fold drawdown changed; inspect adverse periods and position exposure.",
    "positive_fold_rate_pct": "Fraction of positive validation folds changed; inspect distribution of outcomes across periods.",
    "hypothetical_sell_events": "Number of hypothetical closed sells changed; inspect signal frequency and sample length.",
    "evaluated_folds": "Number of evaluated folds changed; check coverage, eligibility and window configuration.",
    "abstained_folds": "Number of skipped folds changed; check minimum trade eligibility and strategy signal coverage.",
}

def diagnose(history):
    if not isinstance(history,list):
        raise ValueError("INVALID_HISTORY")
    drift=detect(history)
    if len(history)<2:
        return {"version":"V126.0","status":"INSUFFICIENT_COMPARISON_DATA",
                "drift":drift,"possible_contributors":[],
                "configuration_match_verified":False,"causality_established":False,
                "research_only":True,"simulation_only":True,
                "exchange_connected":False,"orders_submitted_to_exchange":0,
                "live_trading_approved":False,"validated_edge":False}
    changes=drift["changes"]
    contributors=[]
    for key,explanation in METRIC_EXPLANATIONS.items():
        delta=changes.get(key)
        if delta is not None and delta!=0:
            contributors.append({"metric":key,"delta":delta,
                                 "interpretation":explanation,
                                 "causal_attribution":False})
    old,new=history[-2:]
    old_label=old.get("label")
    new_label=new.get("label")
    return {
        "version":"V126.0","status":"DESCRIPTIVE_OFFLINE_DRIFT_DIAGNOSTICS",
        "previous_label":old_label,"current_label":new_label,
        "drift":drift,"possible_contributors":contributors,
        "metric_changes_count":len(contributors),
        "configuration_match_verified":False,
        "market_regime_change_verified":False,
        "causality_established":False,
        "automatic_strategy_changes":False,
        "research_only":True,"simulation_only":True,
        "exchange_connected":False,"orders_submitted_to_exchange":0,
        "live_trading_approved":False,"validated_edge":False,
        "limitations":"Snapshot summaries cannot identify causes. Trade frequency, sample coverage, costs or regime changes are hypotheses only. Source datasets, parameter settings and market conditions are not verified comparable."
    }

def run(path):
    path=Path(path)
    if path.stat().st_size>2_000_000:
        raise ValueError("HISTORY_TOO_LARGE")
    try:
        history=json.loads(path.read_text(encoding="utf-8"))
    except (ValueError,UnicodeError) as exc:
        raise ValueError("INVALID_HISTORY") from exc
    return diagnose(history)

def main():
    parser=argparse.ArgumentParser(description="V126 offline drift diagnostic explanations")
    parser.add_argument("history_json")
    args=parser.parse_args()
    print(json.dumps(run(args.history_json),indent=2,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
