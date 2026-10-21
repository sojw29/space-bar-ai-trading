# ============================================================
# SPACE BAR AI TRADING
# TESTER V6.0 - DIAGNOSTIC RESEARCH ENGINE
# BINANCE USDT FUTURES | PAPER RESEARCH ONLY
# ============================================================

import csv
import os
from collections import defaultdict
from datetime import datetime, timezone

from tester import (
    load_data,
    prepare,
    get_signal,
    market_regime,
    walk_forward_windows,
    SYMBOLS,
    TIMEFRAMES,
    STRATEGIES,
    INITIAL_CAPITAL,
)

REPORT_DIR = "reports/v6"

POSITION_SIZE = 0.10

BASE_FEE = 0.00055
BASE_SLIPPAGE = 0.00020

STOP_LOSS = 0.006
TAKE_PROFIT = 0.012

MIN_TRADES = 30
MIN_POSITIVE_FOLDS = 3
MIN_PROFIT_FACTOR = 1.10

SCENARIOS = {
    "BASE": (0.00055, 0.00020),
    "HIGH_FEE": (0.00100, 0.00020),
    "HIGH_SLIPPAGE": (0.00055, 0.00050),
    "STRESS": (0.00100, 0.00050),
}

TRADE_FIELDS = [
    "symbol", "timeframe", "strategy", "fold",
    "scenario", "side", "regime",
    "entry_time", "exit_time",
    "entry_price", "exit_price",
    "quantity", "notional_usd",
    "gross_pnl_usd", "fees_usd",
    "slippage_cost_usd", "net_pnl_usd",
    "trade_return_pct", "reason",
    "ambiguous_exit",
]

RANKING_FIELDS = [
    "symbol", "timeframe", "strategy",
    "validation_trades", "wins", "losses",
    "win_rate_pct", "base_return_pct",
    "base_pf", "stress_return_pct",
    "stress_pf", "average_win_usd",
    "average_loss_usd", "payoff_ratio",
    "expectancy_usd", "max_drawdown_pct",
    "positive_folds", "total_folds",
    "ambiguous_exits", "total_fees_usd",
    "total_slippage_usd",
    "eligible", "rejection_reasons",
]

DIAGNOSTIC_FIELDS = [
    "symbol", "timeframe", "strategy",
    "scenario", "regime", "side",
    "trades", "wins", "win_rate_pct",
    "net_pnl_usd", "gross_pnl_usd",
    "fees_usd", "slippage_cost_usd",
    "profit_factor",
]


def save_csv(path, rows, fields):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=fields, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def summarize(trades, fold_results=None):
    fold_results = fold_results or []

    wins = [t for t in trades if t["net_pnl_usd"] > 0]
    losses = [t for t in trades if t["net_pnl_usd"] < 0]

    profit = sum(t["net_pnl_usd"] for t in wins)
    loss = abs(sum(t["net_pnl_usd"] for t in losses))
    total_pnl = sum(t["net_pnl_usd"] for t in trades)

    count = len(trades)

    avg_win = profit / len(wins) if wins else 0.0
    avg_loss = loss / len(losses) if losses else 0.0

    return {
        "trades": count,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": len(wins) / count * 100 if count else 0,
        "return_pct": total_pnl / INITIAL_CAPITAL * 100,
        "profit_factor": profit / loss if loss > 0 else None,
        "average_win_usd": avg_win,
        "average_loss_usd": avg_loss,
        "payoff_ratio": avg_win / avg_loss if avg_loss > 0 else None,
        "expectancy_usd": total_pnl / count if count else 0,
        "ambiguous_exits": sum(
            bool(t["ambiguous_exit"]) for t in trades
        ),
        "total_fees_usd": sum(t["fees_usd"] for t in trades),
        "total_slippage_usd": sum(
            t["slippage_cost_usd"] for t in trades
        ),
        "positive_folds": sum(
            x["return_pct"] > 0 for x in fold_results
        ),
        "total_folds": len(fold_results),
        "max_drawdown_pct": max(
            (x["max_drawdown_pct"] for x in fold_results),
            default=0,
        ),
    }


def simulate(
    candles, indicators, strategy, start, end,
    fee, slippage, symbol, timeframe, fold, scenario
):
    equity = INITIAL_CAPITAL
    peak = equity
    max_drawdown = 0.0

    position = None
    trades = []

    def mark(value):
        nonlocal peak, max_drawdown

        peak = max(peak, value)

        if peak > 0:
            max_drawdown = max(
                max_drawdown,
                (peak - value) / peak
            )

    def close_trade(raw_price, reason, timestamp, ambiguous=False):
        nonlocal equity, position

        side = position["side"]
        entry = position["entry_price"]
        quantity = position["quantity"]

        if side == "LONG":
            exit_price = raw_price * (1 - slippage)
            gross_pnl = quantity * (raw_price - entry)
            slip_cost = quantity * (
                position["entry_slip"] + raw_price * slippage
            )
        else:
            exit_price = raw_price * (1 + slippage)
            gross_pnl = quantity * (entry - raw_price)
            slip_cost = quantity * (
                position["entry_slip"] + raw_price * slippage
            )

        entry_fee = quantity * position["entry_fill"] * fee
        exit_fee = quantity * exit_price * fee
        fees = entry_fee + exit_fee

        net_pnl = gross_pnl - slip_cost - fees
        equity += net_pnl

        trades.append({
            "symbol": symbol,
            "timeframe": timeframe + "m",
            "strategy": strategy,
            "fold": fold,
            "scenario": scenario,
            "side": side,
            "regime": position["regime"],
            "entry_time": position["entry_time"],
            "exit_time": timestamp,
            "entry_price": round(position["entry_fill"], 8),
            "exit_price": round(exit_price, 8),
            "quantity": round(quantity, 10),
            "notional_usd": round(position["notional"], 4),
            "gross_pnl_usd": round(gross_pnl, 6),
            "fees_usd": round(fees, 6),
            "slippage_cost_usd": round(slip_cost, 6),
            "net_pnl_usd": round(net_pnl, 6),
            "trade_return_pct": round(
                net_pnl / position["notional"] * 100, 6
            ),
            "reason": reason,
            "ambiguous_exit": ambiguous,
        })

        position = None
        mark(equity)

    for i in range(start, end):
        candle = candles[i]

        # An existing position can exit on this candle.
        if position is not None:
            side = position["side"]
            entry = position["entry_fill"]

            if side == "LONG":
                stop = entry * (1 - STOP_LOSS)
                target = entry * (1 + TAKE_PROFIT)

                both = (
                    candle["low"] <= stop
                    and candle["high"] >= target
                )

                if candle["open"] <= stop:
                    close_trade(
                        candle["open"], "SL_GAP",
                        candle["timestamp"]
                    )
                elif candle["open"] >= target:
                    close_trade(
                        target, "TP",
                        candle["timestamp"]
                    )
                elif candle["low"] <= stop:
                    close_trade(
                        stop, "SL",
                        candle["timestamp"], both
                    )
                elif candle["high"] >= target:
                    close_trade(
                        target, "TP",
                        candle["timestamp"]
                    )

            else:
                stop = entry * (1 + STOP_LOSS)
                target = entry * (1 - TAKE_PROFIT)

                both = (
                    candle["high"] >= stop
                    and candle["low"] <= target
                )

                if candle["open"] >= stop:
                    close_trade(
                        candle["open"], "SL_GAP",
                        candle["timestamp"]
                    )
                elif candle["open"] <= target:
                    close_trade(
                        target, "TP",
                        candle["timestamp"]
                    )
                elif candle["high"] >= stop:
                    close_trade(
                        stop, "SL",
                        candle["timestamp"], both
                    )
                elif candle["low"] <= target:
                    close_trade(
                        target, "TP",
                        candle["timestamp"]
                    )

            if position is not None:
                quantity = position["quantity"]
                entry = position["entry_fill"]

                if side == "LONG":
                    unrealized = quantity * (
                        candle["close"] - entry
                    )
                else:
                    unrealized = quantity * (
                        entry - candle["close"]
                    )

                mark(equity + unrealized)

        # Entry signal is based on the previous closed candle.
        if position is None and equity > 0:
            signal = get_signal(
                strategy, candles, indicators, i - 1
            )

            if signal in ("LONG", "SHORT"):
                raw_entry = candle["open"]
                notional = equity * POSITION_SIZE

                if signal == "LONG":
                    entry_fill = raw_entry * (1 + slippage)
                else:
                    entry_fill = raw_entry * (1 - slippage)

                quantity = notional / entry_fill

                position = {
                    "side": signal,
                    "entry_price": raw_entry,
                    "entry_fill": entry_fill,
                    "entry_slip": abs(entry_fill - raw_entry),
                    "quantity": quantity,
                    "notional": notional,
                    "entry_time": candle["timestamp"],
                    "regime": market_regime(indicators, i - 1),
                }

                # Entry occurs at candle open, so SL/TP may
                # also be reached within the entry candle.
                side = position["side"]
                entry = position["entry_fill"]

                if side == "LONG":
                    stop = entry * (1 - STOP_LOSS)
                    target = entry * (1 + TAKE_PROFIT)

                    both = (
                        candle["low"] <= stop
                        and candle["high"] >= target
                    )

                    if candle["low"] <= stop:
                        close_trade(
                            stop, "SL", candle["timestamp"], both
                        )
                    elif candle["high"] >= target:
                        close_trade(
                            target, "TP", candle["timestamp"]
                        )

                else:
                    stop = entry * (1 + STOP_LOSS)
                    target = entry * (1 - TAKE_PROFIT)

                    both = (
                        candle["high"] >= stop
                        and candle["low"] <= target
                    )

                    if candle["high"] >= stop:
                        close_trade(
                            stop, "SL", candle["timestamp"], both
                        )
                    elif candle["low"] <= target:
                        close_trade(
                            target, "TP", candle["timestamp"]
                        )

        mark(equity)

    if position is not None:
        close_trade(
            candles[end - 1]["close"],
            "END",
            candles[end - 1]["timestamp"]
        )

    metrics = summarize(trades)
    metrics["max_drawdown_pct"] = max_drawdown * 100
    metrics["trade_log"] = trades

    return metrics


def build_diagnostics(trades):
    groups = defaultdict(list)

    for trade in trades:
        key = (
            trade["symbol"],
            trade["timeframe"],
            trade["strategy"],
            trade["scenario"],
            trade["regime"],
            trade["side"],
        )
        groups[key].append(trade)

    rows = []

    for key, group in sorted(groups.items()):
        metrics = summarize(group)

        rows.append({
            "symbol": key[0],
            "timeframe": key[1],
            "strategy": key[2],
            "scenario": key[3],
            "regime": key[4],
            "side": key[5],
            "trades": metrics["trades"],
            "wins": metrics["wins"],
            "win_rate_pct": round(metrics["win_rate_pct"], 4),
            "net_pnl_usd": round(
                sum(t["net_pnl_usd"] for t in group), 4
            ),
            "gross_pnl_usd": round(
                sum(t["gross_pnl_usd"] for t in group), 4
            ),
            "fees_usd": round(
                sum(t["fees_usd"] for t in group), 4
            ),
            "slippage_cost_usd": round(
                sum(t["slippage_cost_usd"] for t in group), 4
            ),
            "profit_factor": metrics["profit_factor"],
        })

    return rows


def test_all():
    print("=" * 55)
    print("SPACE BAR AI - TESTER V6.0")
    print("DIAGNOSTIC RESEARCH | PAPER ONLY")
    print("=" * 55)

    os.makedirs(REPORT_DIR, exist_ok=True)

    ranking = []
    all_base_trades = []
    all_diagnostic_trades = []

    for symbol in SYMBOLS:
        for timeframe in TIMEFRAMES:
            candles = load_data(symbol, timeframe)

            if len(candles) < 600:
                print("Insufficient data:", symbol, timeframe)
                continue

            indicators = prepare(candles)
            windows = walk_forward_windows(len(candles))

            for strategy in STRATEGIES:
                scenario_results = {}

                for scenario, (fee, slippage) in SCENARIOS.items():
                    fold_results = []
                    scenario_trades = []

                    for window in windows:
                        result = simulate(
                            candles,
                            indicators,
                            strategy,
                            window["valid_start"],
                            window["valid_end"],
                            fee,
                            slippage,
                            symbol,
                            timeframe,
                            window["fold"],
                            scenario,
                        )

                        fold_results.append(result)
                        scenario_trades.extend(result["trade_log"])

                    metrics = summarize(
                        scenario_trades, fold_results
                    )

                    scenario_results[scenario] = metrics
                    all_diagnostic_trades.extend(scenario_trades)

                    if scenario == "BASE":
                        all_base_trades.extend(scenario_trades)

                base = scenario_results["BASE"]
                stress = scenario_results["STRESS"]

                rejection = []

                if base["trades"] < MIN_TRADES:
                    rejection.append("INSUFFICIENT_TRADES")

                if base["positive_folds"] < MIN_POSITIVE_FOLDS:
                    rejection.append("INSUFFICIENT_POSITIVE_FOLDS")

                if base["return_pct"] <= 0:
                    rejection.append("NEGATIVE_RETURN")

                if (
                    base["profit_factor"] is None
                    or base["profit_factor"] < MIN_PROFIT_FACTOR
                ):
                    rejection.append("LOW_PROFIT_FACTOR")

                if stress["return_pct"] <= 0:
                    rejection.append("STRESS_TEST_FAILED")

                eligible = len(rejection) == 0

                ranking.append({
                    "symbol": symbol,
                    "timeframe": timeframe + "m",
                    "strategy": strategy,
                    "validation_trades": base["trades"],
                    "wins": base["wins"],
                    "losses": base["losses"],
                    "win_rate_pct": round(
                        base["win_rate_pct"], 4
                    ),
                    "base_return_pct": round(
                        base["return_pct"], 4
                    ),
                    "base_pf": (
                        round(base["profit_factor"], 4)
                        if base["profit_factor"] is not None
                        else None
                    ),
                    "stress_return_pct": round(
                        stress["return_pct"], 4
                    ),
                    "stress_pf": (
                        round(stress["profit_factor"], 4)
                        if stress["profit_factor"] is not None
                        else None
                    ),
                    "average_win_usd": round(
                        base["average_win_usd"], 4
                    ),
                    "average_loss_usd": round(
                        base["average_loss_usd"], 4
                    ),
                    "payoff_ratio": (
                        round(base["payoff_ratio"], 4)
                        if base["payoff_ratio"] is not None
                        else None
                    ),
                    "expectancy_usd": round(
                        base["expectancy_usd"], 4
                    ),
                    "max_drawdown_pct": round(
                        base["max_drawdown_pct"], 4
                    ),
                    "positive_folds": base["positive_folds"],
                    "total_folds": base["total_folds"],
                    "ambiguous_exits": base["ambiguous_exits"],
                    "total_fees_usd": round(
                        base["total_fees_usd"], 4
                    ),
                    "total_slippage_usd": round(
                        base["total_slippage_usd"], 4
                    ),
                    "eligible": eligible,
                    "rejection_reasons": (
                        "|".join(rejection) if rejection else "PASS"
                    ),
                })

                print(
                    "Completed:",
                    symbol,
                    timeframe + "m",
                    strategy,
                    "| Return:",
                    round(base["return_pct"], 4),
                    "| PF:",
                    base["profit_factor"],
                    "| Eligible:",
                    eligible,
                    flush=True,
                )

    if not ranking:
        raise RuntimeError("No V6 results generated.")

    ranking.sort(
        key=lambda row: (
            row["eligible"],
            row["base_return_pct"],
            row["base_pf"] or 0,
        ),
        reverse=True,
    )

    save_csv(
        f"{REPORT_DIR}/ranking.csv",
        ranking,
        RANKING_FIELDS,
    )

    save_csv(
        f"{REPORT_DIR}/trades.csv",
        all_base_trades,
        TRADE_FIELDS,
    )

    save_csv(
        f"{REPORT_DIR}/diagnostics.csv",
        build_diagnostics(all_diagnostic_trades),
        DIAGNOSTIC_FIELDS,
    )

    print("\nTOP V6 CANDIDATES")

    for row in ranking[:10]:
        print(
            row["symbol"],
            row["timeframe"],
            row["strategy"],
            "| Return:", row["base_return_pct"],
            "| PF:", row["base_pf"],
            "| Eligible:", row["eligible"],
            "| Reasons:", row["rejection_reasons"],
        )

    print("\nTESTER V6.0 COMPLETED")
    print("reports/v6/ranking.csv")
    print("reports/v6/trades.csv")
    print("reports/v6/diagnostics.csv")


if __name__ == "__main__":
    test_all()
