"""V120 expanding-window walk-forward frozen strategy selection.

Training strategy scores are calculated before each out-of-sample window.
No live trading, regime switching, or claim of validated profitability.
"""
import argparse
import json
from decimal import Decimal

from ema_signal_pipeline_v116 import read_history
from multi_strategy_paper_v117 import STRATEGIES, generate
from offline_signal_replay_v115 import replay

MIN_TRAIN = 240
MIN_TEST = 100
MIN_CLOSED_TRADES = 3

def walkforward(rows, initial_train=300, test_bars=150, budget_fraction=0.05):
    if not isinstance(initial_train,int) or isinstance(initial_train,bool) or initial_train<MIN_TRAIN:
        raise ValueError("INVALID_INITIAL_TRAIN")
    if not isinstance(test_bars,int) or isinstance(test_bars,bool) or test_bars<MIN_TEST:
        raise ValueError("INVALID_TEST_BARS")
    if not isinstance(rows,list) or len(rows)<initial_train+test_bars:
        raise ValueError("INSUFFICIENT_WALKFORWARD_HISTORY")
    folds=[]
    for start in range(initial_train,len(rows)-test_bars+1,test_bars):
        end=start+test_bars
        history=rows[:start]
        candidates=[]
        for strategy in STRATEGIES:
            training=replay(generate(history,strategy),budget_fraction)["performance"]
            candidates.append({
                "strategy":strategy,
                "train_return_pct":training["total_return_pct"],
                "train_closed_trades":training["hypothetical_sell_events"],
            })
        eligible=[x for x in candidates if x["train_closed_trades"]>=MIN_CLOSED_TRADES]
        selected=max(eligible,key=lambda x:(Decimal(x["train_return_pct"]),
                                             -STRATEGIES.index(x["strategy"]))) if eligible else None
        validation=None
        if selected:
            # Indicator state may use past train candles, but all executions
            # are confined to the new test window and start with fresh cash.
            prefix_signals=generate(rows[:end],selected["strategy"])
            test_signals=prefix_signals[start:end]
            performance=replay(test_signals,budget_fraction)["performance"]
            validation={
                "total_return_pct":performance["total_return_pct"],
                "max_drawdown_pct":performance["max_drawdown_pct"],
                "hypothetical_buy_events":performance["hypothetical_buy_events"],
                "hypothetical_sell_events":performance["hypothetical_sell_events"],
                "fees_paid":performance["fees_paid"],
            }
        folds.append({
            "fold":len(folds)+1,
            "train_bars":start,"test_bars":test_bars,
            "train_end_timestamp":rows[start-1]["timestamp"],
            "test_start_timestamp":rows[start]["timestamp"],
            "test_end_timestamp":rows[end-1]["timestamp"],
            "candidates":candidates,
            "selected_strategy":selected["strategy"] if selected else None,
            "validation":validation,
            "abstained":selected is None,
        })
    executed=[f for f in folds if f["validation"] is not None]
    return {
        "version":"V120.0","status":"EXPANDING_WINDOW_WALKFORWARD_RESEARCH",
        "initial_train_bars":initial_train,"test_window_bars":test_bars,
        "fold_count":len(folds),"evaluated_fold_count":len(executed),
        "abstained_fold_count":len(folds)-len(executed),
        "folds":folds,
        "selection_frozen_before_each_test":True,
        "continuous_portfolio_return_available":False,
        "research_only":True,"simulation_only":True,
        "exchange_connected":False,"orders_submitted_to_exchange":0,
        "live_trading_approved":False,"validated_edge":False,
        "limitations":"Each fold resets paper capital and starts flat; returns cannot be compounded as one live portfolio. Only complete nonoverlapping test windows. Fixed strategies, 3-trade training threshold, no slippage/spread, and no independent final untouched holdout. Selection based on in-sample returns may overfit."
    }

def run(path,initial_train=300,test_bars=150,budget_fraction=0.05):
    return walkforward(read_history(path),initial_train,test_bars,budget_fraction)

def main():
    parser=argparse.ArgumentParser(description="V120 expanding-window walk-forward paper evaluation")
    parser.add_argument("history_csv")
    parser.add_argument("--initial-train",type=int,default=300)
    parser.add_argument("--test-bars",type=int,default=150)
    parser.add_argument("--budget-fraction",type=float,default=0.05)
    args=parser.parse_args()
    print(json.dumps(run(args.history_csv,args.initial_train,args.test_bars,args.budget_fraction),indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
