"""V119 train-only strategy selection with chronological out-of-sample paper audit.

Descriptive research: choose a SINGLE strategy from training paper performance,
freeze it, and replay on later unseen validation bars. Never approves trading.
"""
import argparse
import json
from decimal import Decimal

from ema_signal_pipeline_v116 import read_history
from multi_strategy_paper_v117 import STRATEGIES, generate
from offline_signal_replay_v115 import replay

MIN_TRAIN = 240
MIN_VALIDATION = 240
WARMUP = 200

def evaluate(rows, train_fraction=0.7, budget_fraction=0.05):
    if (type(train_fraction) not in (int,float) or
            not 0.5 <= train_fraction <= 0.9):
        raise ValueError("INVALID_TRAIN_FRACTION")
    if not isinstance(rows,list):
        raise ValueError("INVALID_ROWS")
    cut=int(len(rows)*train_fraction)
    if cut < MIN_TRAIN or len(rows)-cut < MIN_VALIDATION:
        raise ValueError("INSUFFICIENT_HOLDOUT_BARS")
    # Strictly separate selection and assessment. All strategies train on
    # the same prefix; validation is evaluated only after selection freezes.
    train=rows[:cut]
    train_results=[]
    for strategy in STRATEGIES:
        paper=replay(generate(train,strategy),budget_fraction)
        performance=paper["performance"]
        train_results.append({
            "strategy":strategy,
            "return_pct":performance["total_return_pct"],
            "max_drawdown_pct":performance["max_drawdown_pct"],
            "hypothetical_buy_events":performance["hypothetical_buy_events"],
            "hypothetical_sell_events":performance["hypothetical_sell_events"],
        })
    # Minimum evidence: at least 3 closed trades; no candidate -> abstain.
    eligible=[r for r in train_results if r["hypothetical_sell_events"]>=3]
    selected=max(eligible,key=lambda r:(Decimal(r["return_pct"]),-STRATEGIES.index(r["strategy"]))) if eligible else None
    validation_report=None
    if selected is not None:
        # Use only pre-validation history to warm up indicators. Validation
        # signals begin at index cut; never execute training-period signals.
        combined=rows[:]
        signals=generate(combined,selected["strategy"])
        validation_signals=[]
        for index,row in enumerate(signals[cut:]):
            # The validation replay uses only validation bars. Signals were
            # computed with prior training history, never future candles.
            validation_signals.append(row)
        validation_report=replay(validation_signals,budget_fraction)
    return {
        "version":"V119.0","status":"CHRONOLOGICAL_HOLDOUT_RESEARCH",
        "train_bars":len(train),"validation_bars":len(rows)-cut,
        "train_end_timestamp":train[-1]["timestamp"],
        "validation_start_timestamp":rows[cut]["timestamp"],
        "selection_metric":"TRAIN_PAPER_TOTAL_RETURN_PCT",
        "minimum_train_closed_trades":3,
        "train_candidates":train_results,
        "selected_strategy":selected["strategy"] if selected else None,
        "selection_frozen_before_validation":True,
        "validation":({
            "total_return_pct":validation_report["performance"]["total_return_pct"],
            "max_drawdown_pct":validation_report["performance"]["max_drawdown_pct"],
            "fees_paid":validation_report["performance"]["fees_paid"],
            "hypothetical_buy_events":validation_report["performance"]["hypothetical_buy_events"],
            "hypothetical_sell_events":validation_report["performance"]["hypothetical_sell_events"],
        } if validation_report is not None else None),
        "validation_executed":validation_report is not None,
        "research_only":True,"simulation_only":True,
        "exchange_connected":False,"orders_submitted_to_exchange":0,
        "live_trading_approved":False,"validated_edge":False,
        "limitations":"One chronological split; train selection uses in-sample returns and only 3 trades minimum. Validation indicator warmup includes past train bars. Paper execution starts flat at validation start; no spread, slippage or real fills. Not a regime-adaptive selector or evidence of profitability."
    }

def run(path,train_fraction=0.7,budget_fraction=0.05):
    return evaluate(read_history(path),train_fraction,budget_fraction)

def main():
    parser=argparse.ArgumentParser(description="V119 frozen train-selected strategy validation")
    parser.add_argument("history_csv")
    parser.add_argument("--train-fraction",type=float,default=0.7)
    parser.add_argument("--budget-fraction",type=float,default=0.05)
    args=parser.parse_args()
    print(json.dumps(run(args.history_csv,args.train_fraction,args.budget_fraction),indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
