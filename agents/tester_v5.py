# ==========================================
# SPACE BAR AI TRADING
# TESTER V5.0
# ROBUSTNESS RESEARCH ENGINE
# PAPER RESEARCH ONLY
# ==========================================

import csv
import os
import math
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

REPORT_DIR = "reports/v5"

POSITION_SIZE = 0.10

BASE_FEE = 0.00055
BASE_SLIPPAGE = 0.00020

BASE_STOP = 0.006
BASE_TARGET = 0.012

MIN_TRADES = 30

SCENARIOS = {
    "BASE": (BASE_FEE, BASE_SLIPPAGE),
    "HIGH_FEE": (0.0010, BASE_SLIPPAGE),
    "HIGH_SLIPPAGE": (BASE_FEE, 0.0005),
    "STRESS": (0.0010, 0.0005),
}

RISK_SETTINGS = [
    ("BASE", 0.006, 0.012),
    ("TIGHT", 0.004, 0.008),
    ("WIDE", 0.008, 0.016),
]


def save_csv(path, rows, fields):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fields,
            extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def simulate(
    candles,
    indicators,
    strategy,
    start,
    end,
    fee,
    slippage,
    stop_loss,
    take_profit
):
    equity = INITIAL_CAPITAL
    peak = equity
    max_dd = 0.0

    position = None
    trades = []

    def mark(value):
        nonlocal peak, max_dd
        peak = max(peak, value)
        if peak > 0:
            max_dd = max(
                max_dd,
                (peak - value) / peak
            )

    def close_trade(price, reason, timestamp):
        nonlocal equity, position

        entry = position["entry"]
        amount = position["amount"]
        side = position["side"]

        if side == "LONG":
            gross = price / entry - 1
        else:
            gross = entry / price - 1

        pnl = amount * (
            gross - 2 * fee
        )

        equity += pnl

        trades.append({
            "pnl": pnl,
            "side": side,
            "reason": reason,
            "entry_time": position["time"],
            "exit_time": timestamp,
            "regime": position["regime"]
        })

        position = None
        mark(equity)

    for i in range(start, end):
        candle = candles[i]

        if position is not None:
            entry = position["entry"]
            side = position["side"]

            if side == "LONG":
                stop = entry * (1 - stop_loss)
                target = entry * (1 + take_profit)

                if candle["open"] <= stop:
                    price = candle["open"] * (1 - slippage)
                    reason = "SL_GAP"
                elif candle["open"] >= target:
                    price = target * (1 - slippage)
                    reason = "TP"
                elif candle["low"] <= stop:
                    price = stop * (1 - slippage)
                    reason = "SL"
                elif candle["high"] >= target:
                    price = target * (1 - slippage)
                    reason = "TP"
                else:
                    price = None

            else:
                stop = entry * (1 + stop_loss)
                target = entry * (1 - take_profit)

                if candle["open"] >= stop:
                    price = candle["open"] * (1 + slippage)
                    reason = "SL_GAP"
                elif candle["open"] <= target:
                    price = target * (1 + slippage)
                    reason = "TP"
                elif candle["high"] >= stop:
                    price = stop * (1 + slippage)
                    reason = "SL"
                elif candle["low"] <= target:
                    price = target * (1 + slippage)
                    reason = "TP"
                else:
                    price = None

            if price is not None:
                close_trade(
                    price,
                    reason,
                    candle["timestamp"]
                )
            else:
                amount = position["amount"]

                if side == "LONG":
                    unrealized = amount * (
                        candle["close"] / entry - 1
                    )
                else:
                    unrealized = amount * (
                        entry / candle["close"] - 1
                    )

                mark(equity + unrealized)

        else:
            if equity <= 0:
                break

            signal = get_signal(
                strategy,
                candles,
                indicators,
                i - 1
            )

            if signal is None:
                continue

            price = candle["open"]

            if signal == "LONG":
                price *= 1 + slippage
            else:
                price *= 1 - slippage

            position = {
                "side": signal,
                "entry": price,
                "amount": equity * POSITION_SIZE,
                "time": candle["timestamp"],
                "regime": market_regime(
                    indicators,
                    i - 1
                )
            }

        mark(equity)

    if position is not None:
        last = candles[end - 1]

        if position["side"] == "LONG":
            price = last["close"] * (1 - slippage)
        else:
            price = last["close"] * (1 + slippage)

        close_trade(
            price,
            "END",
            last["timestamp"]
        )

    wins = [
        t["pnl"] for t in trades
        if t["pnl"] > 0
    ]

    losses = [
        t["pnl"] for t in trades
        if t["pnl"] < 0
    ]

    profit = sum(wins)
    loss = abs(sum(losses))

    pf = (
        profit / loss
        if loss > 0
        else None
    )

    total = len(trades)

    return {
        "trades": total,
        "win_rate_pct": (
            len(wins) / total * 100
            if total else 0
        ),
        "return_pct": (
            equity / INITIAL_CAPITAL - 1
        ) * 100,
        "profit_factor": pf,
        "max_drawdown_pct": max_dd * 100,
        "expectancy_usd": (
            sum(t["pnl"] for t in trades) / total
            if total else 0
        ),
        "trade_log": trades
    }


def aggregate(results):
    all_trades = [
        trade
        for result in results
        for trade in result["trade_log"]
    ]

    total = len(all_trades)

    profits = sum(
        t["pnl"] for t in all_trades
        if t["pnl"] > 0
    )

    losses = abs(sum(
        t["pnl"] for t in all_trades
        if t["pnl"] < 0
    ))

    pnl = sum(t["pnl"] for t in all_trades)

    return {
        "trades": total,
        "return_pct": pnl / INITIAL_CAPITAL * 100,
        "profit_factor": (
            profits / losses
            if losses > 0 else None
        ),
        "positive_folds": sum(
            r["return_pct"] > 0
            for r in results
        ),
        "total_folds": len(results),
        "worst_fold_mdd_pct": max(
            (
                r["max_drawdown_pct"]
                for r in results
            ),
            default=0
        )
    }


def test_all():
    print("=" * 55)
    print("SPACE BAR AI - TESTER V5.0")
    print("ROBUSTNESS RESEARCH")
    print("=" * 55)

    rows = []

    for symbol in SYMBOLS:
        for timeframe in TIMEFRAMES:
            candles = load_data(
                symbol,
                timeframe
            )

            if len(candles) < 600:
                print(
                    "Insufficient data:",
                    symbol,
                    timeframe
                )
                continue

            indicators = prepare(candles)
            windows = walk_forward_windows(
                len(candles)
            )

            if not windows:
                continue

            for strategy in STRATEGIES:
                for risk_name, stop, target in RISK_SETTINGS:
                    for scenario, (
                        fee,
                        slippage
                    ) in SCENARIOS.items():

                        results = []

                        for window in windows:
                            result = simulate(
                                candles,
                                indicators,
                                strategy,
                                window["valid_start"],
                                window["valid_end"],
                                fee,
                                slippage,
                                stop,
                                target
                            )

                            results.append(result)

                        metrics = aggregate(results)

                        rows.append({
                            "symbol": symbol,
                            "timeframe": timeframe + "m",
                            "strategy": strategy,
                            "risk_setting": risk_name,
                            "scenario": scenario,
                            **metrics
                        })

                print(
                    "Completed:",
                    symbol,
                    timeframe + "m",
                    strategy
                )

    if not rows:
        raise RuntimeError(
            "No V5 results generated."
        )

    fields = [
        "symbol",
        "timeframe",
        "strategy",
        "risk_setting",
        "scenario",
        "trades",
        "return_pct",
        "profit_factor",
        "positive_folds",
        "total_folds",
        "worst_fold_mdd_pct"
    ]

    save_csv(
        f"{REPORT_DIR}/stress_results.csv",
        rows,
        fields
    )

    candidates = []

    for symbol in SYMBOLS:
        for timeframe in TIMEFRAMES:
            for strategy in STRATEGIES:

                group = [
                    row for row in rows
                    if row["symbol"] == symbol
                    and row["timeframe"] == timeframe + "m"
                    and row["strategy"] == strategy
                ]

                base = next(
                    (
                        row for row in group
                        if row["risk_setting"] == "BASE"
                        and row["scenario"] == "BASE"
                    ),
                    None
                )

                if base is None:
                    continue

                stress = next(
                    (
                        row for row in group
                        if row["risk_setting"] == "BASE"
                        and row["scenario"] == "STRESS"
                    ),
                    None
                )

                robust_count = sum(
                    row["return_pct"] > 0
                    and row["profit_factor"] is not None
                    and row["profit_factor"] > 1
                    for row in group
                )

                eligible = (
                    base["trades"] >= MIN_TRADES
                    and base["positive_folds"] >= 3
                    and base["return_pct"] > 0
                    and base["profit_factor"] is not None
                    and base["profit_factor"] > 1
                    and stress is not None
                    and stress["return_pct"] > 0
                    and robust_count >= 8
                )

                candidates.append({
                    "symbol": symbol,
                    "timeframe": timeframe + "m",
                    "strategy": strategy,
                    "validation_trades": base["trades"],
                    "positive_folds": base["positive_folds"],
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
                    ) if stress else None,
                    "robust_scenarios": robust_count,
                    "total_scenarios": len(group),
                    "eligible": eligible
                })

    candidates.sort(
        key=lambda x: (
            x["eligible"],
            x["robust_scenarios"],
            x["base_return_pct"]
        ),
        reverse=True
    )

    ranking_fields = [
        "symbol",
        "timeframe",
        "strategy",
        "validation_trades",
        "positive_folds",
        "base_return_pct",
        "base_pf",
        "stress_return_pct",
        "robust_scenarios",
        "total_scenarios",
        "eligible"
    ]

    save_csv(
        f"{REPORT_DIR}/ranking.csv",
        candidates,
        ranking_fields
    )

    print("\nTOP V5 CANDIDATES")

    for row in candidates[:10]:
        print(
            row["symbol"],
            row["timeframe"],
            row["strategy"],
            "| Base:", row["base_return_pct"],
            "| Stress:", row["stress_return_pct"],
            "| Robust:",
            f"{row['robust_scenarios']}/{row['total_scenarios']}",
            "| Eligible:", row["eligible"]
        )

    print("\nTESTER V5.0 COMPLETED")
    print("reports/v5/stress_results.csv")
    print("reports/v5/ranking.csv")


if __name__ == "__main__":
    test_all()
