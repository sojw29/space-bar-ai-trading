"""V121 descriptive scorecard of independent V120 walk-forward folds.

No synthetic portfolio compounding, performance approval or live execution.
"""
import argparse
import json
import math
from collections import Counter
from decimal import Decimal
from statistics import median

from ema_signal_pipeline_v116 import read_history
from walkforward_selection_v120 import walkforward

def scorecard(report):
    if not isinstance(report,dict) or report.get("version")!="V120.0":
        raise ValueError("INVALID_WALKFORWARD_REPORT")
    folds=report.get("folds")
    if not isinstance(folds,list) or not folds:
        raise ValueError("NO_FOLDS")
    selected=Counter()
    returns=[]
    drawdowns=[]
    buy_events=sell_events=0
    abstentions=0
    for fold in folds:
        if not isinstance(fold,dict):
            raise ValueError("INVALID_FOLD")
        strategy=fold.get("selected_strategy")
        validation=fold.get("validation")
        if strategy is None:
            if validation is not None:
                raise ValueError("INVALID_ABSTENTION")
            abstentions+=1
            continue
        if not isinstance(validation,dict):
            raise ValueError("MISSING_VALIDATION")
        selected[strategy]+=1
        try:
            r=float(Decimal(validation["total_return_pct"]))
            dd=float(Decimal(validation["max_drawdown_pct"]))
            buys=int(validation["hypothetical_buy_events"])
            sells=int(validation["hypothetical_sell_events"])
        except (ValueError,KeyError,TypeError,ArithmeticError) as exc:
            raise ValueError("INVALID_VALIDATION_METRICS") from exc
        if (not math.isfinite(r) or not math.isfinite(dd) or dd<0 or
                buys<0 or sells<0 or sells>buys):
            raise ValueError("INVALID_VALIDATION_METRICS")
        returns.append(r)
        drawdowns.append(dd)
        buy_events+=buys
        sell_events+=sells
    total=len(folds)
    evaluated=len(returns)
    return {
        "version":"V121.0","status":"DESCRIPTIVE_WALKFORWARD_SCORECARD",
        "total_folds":total,"evaluated_folds":evaluated,
        "abstained_folds":abstentions,
        "abstention_rate_pct":round(abstentions/total*100,6),
        "positive_return_folds":sum(r>0 for r in returns),
        "negative_return_folds":sum(r<0 for r in returns),
        "flat_return_folds":sum(r==0 for r in returns),
        "positive_fold_rate_pct":round(sum(r>0 for r in returns)/evaluated*100,6) if evaluated else None,
        "mean_fold_return_pct":round(sum(returns)/evaluated,8) if evaluated else None,
        "median_fold_return_pct":round(median(returns),8) if evaluated else None,
        "worst_fold_return_pct":round(min(returns),8) if evaluated else None,
        "best_fold_return_pct":round(max(returns),8) if evaluated else None,
        "worst_fold_max_drawdown_pct":round(max(drawdowns),8) if evaluated else None,
        "hypothetical_buy_events":buy_events,
        "hypothetical_sell_events":sell_events,
        "strategy_selection_counts":dict(sorted(selected.items())),
        "strategy_switch_count":sum(a!=b for a,b in zip(
            [f["selected_strategy"] for f in folds],
            [f["selected_strategy"] for f in folds][1:])),
        "compounded_portfolio_return_pct":None,
        "selection_or_live_approval":False,
        "research_only":True,"simulation_only":True,
        "exchange_connected":False,"orders_submitted_to_exchange":0,
        "live_trading_approved":False,"validated_edge":False,
        "limitations":"Fold returns are independently reset hypothetical accounts. Mean/median returns are descriptive, not a continuous portfolio return. Few folds/trades can mislead. No real fills, spread/slippage or untouched final holdout."
    }

def run(path,initial_train=300,test_bars=150,budget_fraction=0.05):
    return scorecard(walkforward(read_history(path),initial_train,test_bars,budget_fraction))

def main():
    parser=argparse.ArgumentParser(description="V121 descriptive walk-forward scorecard")
    parser.add_argument("history_csv")
    parser.add_argument("--initial-train",type=int,default=300)
    parser.add_argument("--test-bars",type=int,default=150)
    parser.add_argument("--budget-fraction",type=float,default=0.05)
    args=parser.parse_args()
    print(json.dumps(run(args.history_csv,args.initial_train,args.test_bars,args.budget_fraction),indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
