# ============================================================
# SPACE BAR AI TRADING
# TESTER V10.0
# BTC 5M TREND ADX RESEARCH ENGINE
# BINANCE USDT FUTURES
# PAPER RESEARCH ONLY
# ============================================================

import csv
import os
from collections import defaultdict

from tester import (
    load_data,
    prepare,
    calculate_adx,
    walk_forward_windows,
    INITIAL_CAPITAL,
)

# ============================================================
# SETTINGS
# ============================================================

SYMBOL = "BTC"
TIMEFRAME = "5"

REPORT_DIR = "reports/v10"

POSITION_SIZE = 0.10

BASE_FEE = 0.00055
BASE_SLIPPAGE = 0.00020

STRESS_FEE = 0.00100
STRESS_SLIPPAGE = 0.00050

# Research configurations.
# These are hypotheses, not proven profitable settings.

CONFIGS = [
    {
        "name": "BASELINE",
        "adx_min": 25,
        "volume_mult": 0.0,
        "htf_filter": False,
        "stop": 0.006,
        "target": 0.012,
    },
    {
        "name": "ADX_30",
        "adx_min": 30,
        "volume_mult": 0.0,
        "htf_filter": False,
        "stop": 0.006,
        "target": 0.012,
    },
    {
        "name": "ADX_35",
        "adx_min": 35,
        "volume_mult": 0.0,
        "htf_filter": False,
        "stop": 0.006,
        "target": 0.012,
    },
    {
        "name": "VOLUME_120",
        "adx_min": 25,
        "volume_mult": 1.20,
        "htf_filter": False,
        "stop": 0.006,
        "target": 0.012,
    },
    {
        "name": "HTF_1H",
        "adx_min": 25,
        "volume_mult": 0.0,
        "htf_filter": True,
        "stop": 0.006,
        "target": 0.012,
    },
    {
        "name": "HTF_ADX30",
        "adx_min": 30,
        "volume_mult": 0.0,
        "htf_filter": True,
        "stop": 0.006,
        "target": 0.012,
    },
    {
        "name": "HTF_VOLUME",
        "adx_min": 25,
        "volume_mult": 1.20,
        "htf_filter": True,
        "stop": 0.006,
        "target": 0.012,
    },
    {
        "name": "HTF_ADX30_VOLUME",
        "adx_min": 30,
        "volume_mult": 1.20,
        "htf_filter": True,
        "stop": 0.006,
        "target": 0.012,
    },
    {
        "name": "RR_1_TO_1",
        "adx_min": 25,
        "volume_mult": 0.0,
        "htf_filter": False,
        "stop": 0.006,
        "target": 0.006,
    },
    {
        "name": "RR_1_TO_3",
        "adx_min": 25,
        "volume_mult": 0.0,
        "htf_filter": False,
        "stop": 0.006,
        "target": 0.018,
    },
    {
        "name": "TIGHT_STOP",
        "adx_min": 25,
        "volume_mult": 0.0,
        "htf_filter": False,
        "stop": 0.004,
        "target": 0.012,
    },
    {
        "name": "WIDE_STOP",
        "adx_min": 25,
        "volume_mult": 0.0,
        "htf_filter": False,
        "stop": 0.008,
        "target": 0.016,
    },
]

FIELDS = [
    "configuration",
    "trades",
    "wins",
    "losses",
    "win_rate_pct",
    "return_pct",
    "profit_factor",
    "stress_return_pct",
    "stress_profit_factor",
    "positive_folds",
    "total_folds",
    "expectancy_usd",
    "average_win_usd",
    "average_loss_usd",
    "payoff_ratio",
    "max_drawdown_pct",
    "eligible",
]

TRADE_FIELDS = [
    "configuration",
    "fold",
    "scenario",
    "side",
    "entry_time",
    "exit_time",
    "entry_price",
    "exit_price",
    "net_pnl_usd",
    "reason",
]

# ============================================================
# HELPERS
# ============================================================

def ema(values, period):

    result = [None] * len(values)

    if len(values) < period:
        return result

    previous = sum(values[:period]) / period
    result[period - 1] = previous

    alpha = 2 / (period + 1)

    for i in range(period, len(values)):

        previous = (
            values[i] * alpha
            + previous * (1 - alpha)
        )

        result[i] = previous

    return result


def save_csv(path, rows, fields):

    os.makedirs(
        os.path.dirname(path),
        exist_ok=True
    )

    with open(
        path,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields,
            extrasaction="ignore"
        )

        writer.writeheader()
        writer.writerows(rows)


def validate_data(candles):

    if len(candles) < 1000:
        raise RuntimeError(
            "Insufficient BTC 5m history."
        )

    for i in range(1, len(candles)):

        gap = (
            candles[i]["timestamp"]
            - candles[i - 1]["timestamp"]
        )

        if gap != 300:
            raise RuntimeError(
                f"Invalid timestamp gap at {i}: {gap}"
            )

    print(
        "Verified BTC 5m candles:",
        len(candles),
        flush=True
    )


# ============================================================
# HIGHER TIMEFRAME
# Uses only completed 1H candles.
# No future candle information.
# ============================================================

def build_htf_filter(candles):

    hourly = []
    completed_hour_index = []

    current_hour = None
    current = None

    for candle in candles:

        hour = (
            candle["timestamp"] // 3600
        ) * 3600

        if current_hour is None:
            current_hour = hour

            current = {
                "timestamp": hour,
                "open": candle["open"],
                "high": candle["high"],
                "low": candle["low"],
                "close": candle["close"],
                "volume": candle["volume"],
            }

        elif hour != current_hour:

            hourly.append(current)

            current_hour = hour

            current = {
                "timestamp": hour,
                "open": candle["open"],
                "high": candle["high"],
                "low": candle["low"],
                "close": candle["close"],
                "volume": candle["volume"],
            }

        else:

            current["high"] = max(
                current["high"],
                candle["high"]
            )

            current["low"] = min(
                current["low"],
                candle["low"]
            )

            current["close"] = candle["close"]

            current["volume"] += candle["volume"]

        # The current hour is still incomplete.
        # Only the preceding hourly candles are usable.

        completed_hour_index.append(
            len(hourly) - 1
        )

    closes = [
        c["close"] for c in hourly
    ]

    fast = ema(closes, 50)
    slow = ema(closes, 200)

    directions = []

    for index in completed_hour_index:

        if index < 0:
            directions.append(None)
            continue

        if (
            fast[index] is None
            or slow[index] is None
        ):
            directions.append(None)
            continue

        if fast[index] > slow[index]:
            directions.append("LONG")

        elif fast[index] < slow[index]:
            directions.append("SHORT")

        else:
            directions.append(None)

    return directions


# ============================================================
# SIGNAL GENERATION
# Signal is evaluated on the previous closed 5m candle.
# Entry occurs at the next candle open.
# ============================================================

def get_v10_signal(
    candles,
    indicators,
    htf_directions,
    i,
    config
):

    if i < 201:
        return None

    current = candles[i]
    previous = candles[i - 1]

    ema50 = indicators["ema50"]
    ema200 = indicators["ema200"]

    adx = indicators["adx"]
    vol20 = indicators["vol20"]

    if (
        adx[i] is None
        or adx[i] < config["adx_min"]
    ):
        return None

    if config["volume_mult"] > 0:

        if (
            vol20[i] is None
            or current["volume"]
            < vol20[i] * config["volume_mult"]
        ):
            return None

    signal = None

    if (
        ema50[i] > ema200[i]
        and current["close"] > ema50[i]
        and previous["close"] <= ema50[i - 1]
    ):
        signal = "LONG"

    elif (
        ema50[i] < ema200[i]
        and current["close"] < ema50[i]
        and previous["close"] >= ema50[i - 1]
    ):
        signal = "SHORT"

    if (
        signal is not None
        and config["htf_filter"]
    ):

        if htf_directions[i] != signal:
            return None

    return signal


# ============================================================
# BACKTEST
# Conservative stop-first handling.
# Fees and slippage included.
# ============================================================

def simulate(
    candles,
    indicators,
    htf_directions,
    config,
    start,
    end,
    fee,
    slippage,
    fold,
    scenario
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

    def close_trade(raw_exit, timestamp, reason):

        nonlocal equity, position

        side = position["side"]
        raw_entry = position["raw_entry"]
        entry_fill = position["entry_fill"]
        quantity = position["quantity"]

        if side == "LONG":

            exit_fill = raw_exit * (
                1 - slippage
            )

            gross = quantity * (
                raw_exit - raw_entry
            )

        else:

            exit_fill = raw_exit * (
                1 + slippage
            )

            gross = quantity * (
                raw_entry - raw_exit
            )

        slippage_cost = quantity * (
            abs(entry_fill - raw_entry)
            + abs(exit_fill - raw_exit)
        )

        fees = quantity * fee * (
            entry_fill + exit_fill
        )

        pnl = gross - slippage_cost - fees

        equity += pnl

        trades.append({
            "configuration": config["name"],
            "fold": fold,
            "scenario": scenario,
            "side": side,
            "entry_time": position["entry_time"],
            "exit_time": timestamp,
            "entry_price": round(entry_fill, 8),
            "exit_price": round(exit_fill, 8),
            "net_pnl_usd": round(pnl, 6),
            "reason": reason,
        })

        position = None

        mark(equity)

    for i in range(start, end):

        candle = candles[i]

        exited = False

        # ------------------------------------------
        # Manage existing position
        # ------------------------------------------

        if position is not None:

            entry = position["entry_fill"]
            side = position["side"]

            if side == "LONG":

                stop = entry * (
                    1 - config["stop"]
                )

                target = entry * (
                    1 + config["target"]
                )

                if candle["open"] <= stop:

                    close_trade(
                        candle["open"],
                        candle["timestamp"],
                        "SL_GAP"
                    )

                elif candle["open"] >= target:

                    close_trade(
                        target,
                        candle["timestamp"],
                        "TP"
                    )

                elif candle["low"] <= stop:

                    close_trade(
                        stop,
                        candle["timestamp"],
                        "SL"
                    )

                elif candle["high"] >= target:

                    close_trade(
                        target,
                        candle["timestamp"],
                        "TP"
                    )

            else:

                stop = entry * (
                    1 + config["stop"]
                )

                target = entry * (
                    1 - config["target"]
                )

                if candle["open"] >= stop:

                    close_trade(
                        candle["open"],
                        candle["timestamp"],
                        "SL_GAP"
                    )

                elif candle["open"] <= target:

                    close_trade(
                        target,
                        candle["timestamp"],
                        "TP"
                    )

                elif candle["high"] >= stop:

                    close_trade(
                        stop,
                        candle["timestamp"],
                        "SL"
                    )

                elif candle["low"] <= target:

                    close_trade(
                        target,
                        candle["timestamp"],
                        "TP"
                    )

            if position is None:

                exited = True

            else:

                quantity = position["quantity"]

                if side == "LONG":

                    unrealized = quantity * (
                        candle["close"] - entry
                    )

                else:

                    unrealized = quantity * (
                        entry - candle["close"]
                    )

                mark(equity + unrealized)

        # ------------------------------------------
        # Open position at next candle open
        # ------------------------------------------

        if (
            position is None
            and not exited
            and equity > 0
            and i > 201
        ):

            signal = get_v10_signal(
                candles,
                indicators,
                htf_directions,
                i - 1,
                config
            )

            if signal is not None:

                raw_entry = candle["open"]

                if signal == "LONG":

                    entry_fill = raw_entry * (
                        1 + slippage
                    )

                else:

                    entry_fill = raw_entry * (
                        1 - slippage
                    )

                notional = equity * POSITION_SIZE

                quantity = (
                    notional / entry_fill
                )

                position = {
                    "side": signal,
                    "raw_entry": raw_entry,
                    "entry_fill": entry_fill,
                    "quantity": quantity,
                    "entry_time": candle["timestamp"],
                }

                # Entry occurs at the open.
                # Same-candle stop/target is checked.

                if signal == "LONG":

                    stop = entry_fill * (
                        1 - config["stop"]
                    )

                    target = entry_fill * (
                        1 + config["target"]
                    )

                    if candle["low"] <= stop:

                        close_trade(
                            stop,
                            candle["timestamp"],
                            "SL"
                        )

                    elif candle["high"] >= target:

                        close_trade(
                            target,
                            candle["timestamp"],
                            "TP"
                        )

                else:

                    stop = entry_fill * (
                        1 + config["stop"]
                    )

                    target = entry_fill * (
                        1 - config["target"]
                    )

                    if candle["high"] >= stop:

                        close_trade(
                            stop,
                            candle["timestamp"],
                            "SL"
                        )

                    elif candle["low"] <= target:

                        close_trade(
                            target,
                            candle["timestamp"],
                            "TP"
                        )

        mark(equity)

    if position is not None:

        close_trade(
            candles[end - 1]["close"],
            candles[end - 1]["timestamp"],
            "END"
        )

    return {
        "trades": trades,
        "max_drawdown_pct": max_dd * 100,
        "return_pct": (
            equity / INITIAL_CAPITAL - 1
        ) * 100,
    }


# ============================================================
# METRICS
# ============================================================

def summarize(results):

    trades = [
        trade
        for result in results
        for trade in result["trades"]
    ]

    wins = [
        t for t in trades
        if t["net_pnl_usd"] > 0
    ]

    losses = [
        t for t in trades
        if t["net_pnl_usd"] < 0
    ]

    gross_profit = sum(
        t["net_pnl_usd"] for t in wins
    )

    gross_loss = abs(sum(
        t["net_pnl_usd"] for t in losses
    ))

    pnl = sum(
        t["net_pnl_usd"] for t in trades
    )

    count = len(trades)

    avg_win = (
        gross_profit / len(wins)
        if wins else 0
    )

    avg_loss = (
        gross_loss / len(losses)
        if losses else 0
    )

    pf = (
        gross_profit / gross_loss
        if gross_loss > 0
        else None
    )

    positive_folds = sum(
        r["return_pct"] > 0
        for r in results
    )

    return {
        "trades": count,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": (
            len(wins) / count * 100
            if count else 0
        ),
        "return_pct": (
            pnl / INITIAL_CAPITAL * 100
        ),
        "profit_factor": pf,
        "average_win_usd": avg_win,
        "average_loss_usd": avg_loss,
        "payoff_ratio": (
            avg_win / avg_loss
            if avg_loss > 0
            else None
        ),
        "expectancy_usd": (
            pnl / count
            if count else 0
        ),
        "positive_folds": positive_folds,
        "total_folds": len(results),
        "max_drawdown_pct": max(
            (
                r["max_drawdown_pct"]
                for r in results
            ),
            default=0
        ),
        "trade_log": trades,
    }


# ============================================================
# MAIN
# ============================================================

def test_all():

    print("=" * 60)
    print("SPACE BAR AI - TESTER V10.0")
    print("BTC 5M TREND ADX RESEARCH")
    print("=" * 60)

    candles = load_data(
        SYMBOL,
        TIMEFRAME
    )

    validate_data(candles)

    indicators = prepare(candles)

    htf_directions = build_htf_filter(
        candles
    )

    windows = walk_forward_windows(
        len(candles)
    )

    if not windows:
        raise RuntimeError(
            "No walk-forward windows available."
        )

    ranking = []
    all_trades = []

    for config in CONFIGS:

        scenario_results = {}

        for scenario, fee, slippage in [
            (
                "BASE",
                BASE_FEE,
                BASE_SLIPPAGE
            ),
            (
                "STRESS",
                STRESS_FEE,
                STRESS_SLIPPAGE
            ),
        ]:

            results = []

            for window in windows:

                result = simulate(
                    candles,
                    indicators,
                    htf_directions,
                    config,
                    window["valid_start"],
                    window["valid_end"],
                    fee,
                    slippage,
                    window["fold"],
                    scenario
                )

                results.append(result)

            metrics = summarize(results)

            scenario_results[
                scenario
            ] = metrics

            all_trades.extend(
                metrics["trade_log"]
            )

        base = scenario_results["BASE"]
        stress = scenario_results["STRESS"]

        eligible = (
            base["trades"] >= 30
            and base["positive_folds"] >= 3
            and base["return_pct"] > 0
            and base["profit_factor"] is not None
            and base["profit_factor"] >= 1.10
            and stress["return_pct"] > 0
        )

        ranking.append({
            "configuration": config["name"],
            "trades": base["trades"],
            "wins": base["wins"],
            "losses": base["losses"],
            "win_rate_pct": round(
                base["win_rate_pct"], 4
            ),
            "return_pct": round(
                base["return_pct"], 4
            ),
            "profit_factor": (
                round(
                    base["profit_factor"], 4
                )
                if base["profit_factor"] is not None
                else None
            ),
            "stress_return_pct": round(
                stress["return_pct"], 4
            ),
            "stress_profit_factor": (
                round(
                    stress["profit_factor"], 4
                )
                if stress["profit_factor"] is not None
                else None
            ),
            "positive_folds": (
                base["positive_folds"]
            ),
            "total_folds": (
                base["total_folds"]
            ),
            "expectancy_usd": round(
                base["expectancy_usd"], 4
            ),
            "average_win_usd": round(
                base["average_win_usd"], 4
            ),
            "average_loss_usd": round(
                base["average_loss_usd"], 4
            ),
            "payoff_ratio": (
                round(
                    base["payoff_ratio"], 4
                )
                if base["payoff_ratio"] is not None
                else None
            ),
            "max_drawdown_pct": round(
                base["max_drawdown_pct"], 4
            ),
            "eligible": eligible,
        })

        print(
            config["name"],
            "| Trades:", base["trades"],
            "| Return:", round(
                base["return_pct"], 4
            ),
            "| PF:", base["profit_factor"],
            "| Positive folds:",
            base["positive_folds"],
            "| Stress:", round(
                stress["return_pct"], 4
            ),
            "| Eligible:", eligible,
            flush=True
        )

    ranking.sort(
        key=lambda row: (
            row["eligible"],
            row["return_pct"],
            row["profit_factor"] or 0
        ),
        reverse=True
    )

    save_csv(
        f"{REPORT_DIR}/ranking.csv",
        ranking,
        FIELDS
    )

    save_csv(
        f"{REPORT_DIR}/trades.csv",
        all_trades,
        TRADE_FIELDS
    )

    print("\n" + "=" * 60)
    print("TOP V10 RESEARCH RESULTS")
    print("=" * 60)

    for index, row in enumerate(
        ranking[:10],
        1
    ):

        print(
            index,
            row["configuration"],
            "| Return:",
            row["return_pct"],
            "| PF:",
            row["profit_factor"],
            "| Positive folds:",
            row["positive_folds"],
            "| Eligible:",
            row["eligible"]
        )

    print("\nV10 COMPLETED")
    print("reports/v10/ranking.csv")
    print("reports/v10/trades.csv")


if __name__ == "__main__":
    test_all()
