"""V122 deterministic research-risk warnings for walk-forward scorecards.

Warnings are advisory research flags, never an approval or trading permission.
"""
import argparse
import json
import math

from ema_signal_pipeline_v116 import read_history
from walkforward_selection_v120 import walkforward
from walkforward_scorecard_v121 import scorecard

def _num(value, name):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError("INVALID_"+name)
    return float(value)

def audit(summary, min_evaluated_folds=5, min_closed_trades=30,
          max_drawdown_pct=10.0, min_positive_fold_rate_pct=60.0,
          max_abstention_rate_pct=40.0):
    if not isinstance(summary,dict) or summary.get("version")!="V121.0":
        raise ValueError("INVALID_SCORECARD")
    if (type(min_evaluated_folds) is not int or min_evaluated_folds<1 or
            type(min_closed_trades) is not int or min_closed_trades<1):
        raise ValueError("INVALID_THRESHOLDS")
    drawdown_limit=_num(max_drawdown_pct,"DRAWDOWN_LIMIT")
    positive_limit=_num(min_positive_fold_rate_pct,"POSITIVE_LIMIT")
    abstention_limit=_num(max_abstention_rate_pct,"ABSTENTION_LIMIT")
    if not (0<drawdown_limit<=100 and 0<=positive_limit<=100 and
            0<=abstention_limit<=100):
        raise ValueError("INVALID_THRESHOLDS")
    try:
        evaluated=summary["evaluated_folds"]
        total=summary["total_folds"]
        closed=summary["hypothetical_sell_events"]
        positive=summary["positive_fold_rate_pct"]
        abstention=summary["abstention_rate_pct"]
        drawdown=summary["worst_fold_max_drawdown_pct"]
    except KeyError as exc:
        raise ValueError("INCOMPLETE_SCORECARD") from exc
    if (type(evaluated) is not int or type(total) is not int or
            type(closed) is not int or evaluated<0 or total<1 or
            evaluated>total or closed<0):
        raise ValueError("INVALID_SCORECARD_METRICS")
    warnings=[]
    def flag(code,detail):
        warnings.append({"code":code,"detail":detail})
    if evaluated<min_evaluated_folds:
        flag("INSUFFICIENT_FOLDS","Too few out-of-sample folds for confidence.")
    if closed<min_closed_trades:
        flag("INSUFFICIENT_CLOSED_TRADES","Too few hypothetical closed trades.")
    if evaluated==0:
        flag("NO_EVALUATED_FOLDS","All folds abstained; no validation evidence.")
    else:
        positive_value=_num(positive,"POSITIVE_FOLD_RATE")
        drawdown_value=_num(drawdown,"MAX_DRAWDOWN")
        if not (0<=positive_value<=100 and 0<=drawdown_value<=100):
            raise ValueError("INVALID_SCORECARD_METRICS")
        if positive_value<positive_limit:
            flag("LOW_POSITIVE_FOLD_RATE","Too few evaluated folds had positive returns.")
        if drawdown_value>drawdown_limit:
            flag("EXCESSIVE_SAMPLED_DRAWDOWN","Worst sampled fold drawdown exceeds threshold.")
    abstention_value=_num(abstention,"ABSTENTION_RATE")
    if not 0<=abstention_value<=100:
        raise ValueError("INVALID_SCORECARD_METRICS")
    if abstention_value>abstention_limit:
        flag("HIGH_ABSTENTION_RATE","Too many folds lacked an eligible strategy.")
    # No green light: absence of warnings is not evidence of a trading edge.
    return {
        "version":"V122.0","status":"RESEARCH_WARNINGS_ONLY",
        "warning_count":len(warnings),"warnings":warnings,
        "risk_flags_present":bool(warnings),
        "no_warnings_is_not_approval":True,
        "live_trading_approved":False,"validated_edge":False,
        "simulation_only":True,"exchange_connected":False,
        "orders_submitted_to_exchange":0,
        "limitations":"Heuristic research thresholds, not statistical significance or investment advice. Sampled fold drawdown misses intrabar losses; historical hypothetical results cannot guarantee future performance."
    }

def run(path,initial_train=300,test_bars=150,budget_fraction=0.05):
    report=walkforward(read_history(path),initial_train,test_bars,budget_fraction)
    return {"scorecard":scorecard(report),"audit":audit(scorecard(report))}

def main():
    parser=argparse.ArgumentParser(description="V122 research-only risk warning audit")
    parser.add_argument("history_csv")
    parser.add_argument("--initial-train",type=int,default=300)
    parser.add_argument("--test-bars",type=int,default=150)
    parser.add_argument("--budget-fraction",type=float,default=0.05)
    args=parser.parse_args()
    print(json.dumps(run(args.history_csv,args.initial_train,args.test_bars,args.budget_fraction),indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
