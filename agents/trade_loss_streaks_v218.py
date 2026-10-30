"""V218 hypothetical closed-trade loss streaks on independent validation holdout.

This is an offline research diagnostic, not a live trade log or a risk forecast.
"""
import csv
import math
import tempfile
from pathlib import Path

from chronological_holdout_v102 import split_csv
from multi_strategy_holdout_v105 import MIN_BARS, STRATEGIES, _metrics


def summarize_trade_losses(pnls):
    if not isinstance(pnls, list):
        raise ValueError("INVALID_TRADE_PNLS")
    longest = current = 0
    longest_start = longest_end = start = None
    worst = None
    losing_count = 0
    cumulative_loss = 0.0
    worst_streak_loss = 0.0
    for index, pnl in enumerate(pnls):
        if type(pnl) not in (int, float) or not math.isfinite(pnl):
            raise ValueError("NONFINITE_TRADE_PNL")
        if worst is None or pnl < worst:
            worst = pnl
        if pnl < 0:
            losing_count += 1
            if current == 0:
                start = index
                cumulative_loss = 0.0
            current += 1
            cumulative_loss += pnl
            worst_streak_loss = min(worst_streak_loss, cumulative_loss)
            if current > longest:
                longest = current
                longest_start, longest_end = start, index
        else:
            current = 0
            cumulative_loss = 0.0
            start = None
    return {
        "closed_hypothetical_trades": len(pnls),
        "losing_trades": losing_count,
        "longest_consecutive_losing_trades": longest,
        "longest_streak_start_trade_index": longest_start,
        "longest_streak_end_trade_index": longest_end,
        "worst_closed_trade_pnl_cash": round(worst, 6) if worst is not None else None,
        "worst_consecutive_loss_sum_cash": round(worst_streak_loss, 6),
        "status": "NO_TRADES" if not pnls else "DESCRIPTIVE_ONLY",
    }


def assess_trade_loss_streaks(history_csv):
    with tempfile.TemporaryDirectory(prefix="spacebar-v218-") as folder:
        train = Path(folder) / "train.csv"
        valid = Path(folder) / "validation.csv"
        split_csv(history_csv, train, valid, ratio=0.7, min_rows=MIN_BARS)
        with valid.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
    results = []
    for strategy in STRATEGIES:
        pnls = []
        metrics = _metrics(rows, strategy, trade_pnls=pnls)
        summary = summarize_trade_losses(pnls)
        if summary["closed_hypothetical_trades"] != metrics["trades"]:
            raise ValueError("TRADE_COUNT_MISMATCH")
        results.append({"strategy": strategy, **summary})
    return {
        "version": "V218.0", "status": "DESCRIPTIVE_TRADE_STRESS_ONLY",
        "holdout": "CHRONOLOGICAL_30_PERCENT_VALIDATION",
        "rows": results, "research_only": True,
        "ranking_enabled": False, "strategy_selection_enabled": False,
        "orders_allowed": False, "live_trading_approved": False,
        "limitations": [
            "Trade PnLs are hypothetical and include fixed fee and slippage assumptions.",
            "Zero-PnL trades break losing streaks; worst streak sum is not equity maximum drawdown.",
            "One validation holdout does not establish future losing streak limits or profitability.",
        ],
    }
