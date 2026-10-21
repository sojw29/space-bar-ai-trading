# ============================================================
# SPACE BAR AI TRADING
# TESTER V11.0
# HTF TREND + ATR + VOLUME RESEARCH
# BTC 5M | BINANCE USDT FUTURES
# PAPER RESEARCH ONLY
# ============================================================

import csv
import os

import tester_v10 as v10

from tester import (
    load_data,
    prepare,
    walk_forward_windows,
)

# ============================================================
# SETTINGS
# ============================================================

SYMBOL = "BTC"
TIMEFRAME = "5"

REPORT_DIR = "reports/v11"

MIN_TRADES = 30
MIN_POSITIVE_FOLDS = 3
MIN_PROFIT_FACTOR = 1.10

BASE_FEE = 0.00055
BASE_SLIPPAGE = 0.00020

STRESS_FEE = 0.00100
STRESS_SLIPPAGE = 0.00050

# ============================================================
# CONFIGURATIONS
# ============================================================

CONFIGS = [
    {
        "name": "V10_HTF_BASELINE",
        "adx_min": 25,
        "volume_mult": 0.0,
        "htf_filter": True,
        "stop": 0.006,
        "target": 0.012,
        "atr_min": 0.0,
        "atr_max": 999.0,
        "side": "BOTH",
        "signal_mode": "CROSS",
    },
    {
        "name": "HTF_ADX20",
        "adx_min": 20,
        "volume_mult": 0.0,
        "htf_filter": True,
        "stop": 0.006,
        "target": 0.012,
        "atr_min": 0.0,
        "atr_max": 999.0,
        "side": "BOTH",
        "signal_mode": "CROSS",
    },
    {
        "name": "HTF_ADX30",
        "adx_min": 30,
        "volume_mult": 0.0,
        "htf_filter": True,
        "stop": 0.006,
        "target": 0.012,
        "atr_min": 0.0,
        "atr_max": 999.0,
        "side": "BOTH",
        "signal_mode": "CROSS",
    },
    {
        "name": "HTF_ATR_LOW",
        "adx_min": 25,
        "volume_mult": 0.0,
        "htf_filter": True,
        "stop": 0.006,
        "target": 0.012,
        "atr_min": 0.15,
        "atr_max": 0.60,
        "side": "BOTH",
        "signal_mode": "CROSS",
    },
    {
        "name": "HTF_ATR_MEDIUM",
        "adx_min": 25,
        "volume_mult": 0.0,
        "htf_filter": True,
        "stop": 0.006,
        "target": 0.012,
        "atr_min": 0.30,
        "atr_max": 1.00,
        "side": "BOTH",
        "signal_mode": "CROSS",
    },
    {
        "name": "HTF_VOLUME_110",
        "adx_min": 25,
        "volume_mult": 1.10,
        "htf_filter": True,
        "stop": 0.006,
        "target": 0.012,
        "atr_min": 0.0,
        "atr_max": 999.0,
        "side": "BOTH",
        "signal_mode": "CROSS",
    },
    {
        "name": "HTF_LONG_ONLY",
        "adx_min": 25,
        "volume_mult": 0.0,
        "htf_filter": True,
        "stop": 0.006,
        "target": 0.012,
        "atr_min": 0.0,
        "atr_max": 999.0,
        "side": "LONG",
        "signal_mode": "CROSS",
    },
    {
        "name": "HTF_SHORT_ONLY",
        "adx_min": 25,
        "volume_mult": 0.0,
        "htf_filter": True,
        "stop": 0.006,
        "target": 0.012,
        "atr_min": 0.0,
        "atr_max": 999.0,
        "side": "SHORT",
        "signal_mode": "CROSS",
    },
    {
        "name": "HTF_RR_1_TO_3",
        "adx_min": 25,
        "volume_mult": 0.0,
        "htf_filter": True,
        "stop": 0.006,
        "target": 0.018,
        "atr_min": 0.0,
        "atr_max": 999.0,
        "side": "BOTH",
        "signal_mode": "CROSS",
    },
    {
        "name": "HTF_RR_1_TO_1_5",
        "adx_min": 25,
        "volume_mult": 0.0,
        "htf_filter": True,
        "stop": 0.006,
        "target": 0.009,
        "atr_min": 0.0,
        "atr_max": 999.0,
        "side": "BOTH",
        "signal_mode": "CROSS",
    },
    {
        "name": "HTF_PULLBACK",
        "adx_min": 25,
        "volume_mult": 0.0,
        "htf_filter": True,
        "stop": 0.006,
        "target": 0.012,
        "atr_min": 0.0,
        "atr_max": 999.0,
        "side": "BOTH",
        "signal_mode": "PULLBACK",
    },
    {
        "name": "HTF_PULLBACK_VOLUME",
        "adx_min": 25,
        "volume_mult": 1.10,
        "htf_filter": True,
        "stop": 0.006,
        "target": 0.012,
        "atr_min": 0.0,
        "atr_max": 999.0,
        "side": "BOTH",
        "signal_mode": "PULLBACK",
    },
]

# ============================================================
# REPORT FIELDS
# ============================================================

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
    "rejection_reasons",
]

TRADE_FIELDS = v10.TRADE_FIELDS

# ============================================================
# ATR
# ============================================================

def calculate_atr_pct(candles, period=14):

    result = [None] * len(candles)

    if len(candles) <= period:
        return result

    true_ranges = []

    for i, candle in enumerate(candles):

        if i == 0:
            tr = candle["high"] - candle["low"]

        else:
            previous_close = candles[i - 1]["close"]

            tr = max(
                candle["high"] - candle["low"],
                abs(candle["high"] - previous_close),
                abs(candle["low"] - previous_close),
            )

        true_ranges.append(tr)

    atr = sum(true_ranges[:period]) / period

    for i in range(period - 1, len(candles)):

        if i > period - 1:
            atr = (
                atr * (period - 1)
                + true_ranges[i]
            ) / period

        close = candles[i]["close"]

        if close > 0:
            result[i] = atr / close * 100

    return result


# ============================================================
# SIGNAL ENGINE
# ============================================================

def generate_signal(
    candles,
    indicators,
    htf_directions,
    atr_pct,
    i,
    config,
):

    if i < 201:
        return None

    if i >= len(candles):
        return None

    current = candles[i]
    previous = candles[i - 1]

    ema50 = indicators["ema50"]
    ema200 = indicators["ema200"]

    adx = indicators["adx"]
    vol20 = indicators["vol20"]

    if (
        ema50[i] is None
        or ema200[i] is None
        or ema50[i - 1] is None
        or adx[i] is None
    ):
        return None

    if adx[i] < config["adx_min"]:
        return None

    # ATR filter
    current_atr = atr_pct[i]

    if current_atr is None:
        return None

    if not (
        config["atr_min"]
        <= current_atr
        <= config["atr_max"]
    ):
        return None

    # Volume filter
    if config["volume_mult"] > 0:

        if vol20[i] is None:
            return None

        if current["volume"] < (
            vol20[i] * config["volume_mult"]
        ):
            return None

    signal = None

    # ----------------------------------------
    # EMA CROSS / RECLAIM
    # ----------------------------------------

    if config["signal_mode"] == "CROSS":

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

    # ----------------------------------------
    # EMA PULLBACK
    # ----------------------------------------

    elif config["signal_mode"] == "PULLBACK":

        if (
            ema50[i] > ema200[i]
            and previous["low"] <= ema50[i - 1]
            and current["close"] > ema50[i]
            and current["close"] > current["open"]
            and previous["close"] > ema200[i - 1]
        ):
            signal = "LONG"

        elif (
            ema50[i] < ema200[i]
            and previous["high"] >= ema50[i - 1]
            and current["close"] < ema50[i]
            and current["close"] < current["open"]
            and previous["close"] < ema200[i - 1]
        ):
            signal = "SHORT"

    if signal is None:
        return None

    # HTF direction
    if config["htf_filter"]:

        if htf_directions[i] != signal:
            return None

    # Long / Short restriction
    if config["side"] != "BOTH":

        if signal != config["side"]:
            return None

    return signal


# ============================================================
# V10 SIMULATION COMPATIBILITY
#
# V10 simulator calls get_v10_signal().
# This wrapper lets V11 reuse the existing
# execution and fee/slippage engine.
# ============================================================

ORIGINAL_SIGNAL = v10.get_v10_signal

ACTIVE_ATR = None


def v11_signal_adapter(
    candles,
    indicators,
    htf_directions,
    i,
    config,
):

    if ACTIVE_ATR is None:
        raise RuntimeError(
            "V11 ATR data is not initialized."
        )

    return generate_signal(
        candles,
        indicators,
        htf_directions,
        ACTIVE_ATR,
        i,
        config,
    )


# ============================================================
# EVALUATION
# ============================================================

def evaluate_configuration(
    candles,
    indicators,
    htf_directions,
    windows,
    config,
):

    scenario_results = {}

    for scenario, fee, slippage in [
        (
            "BASE",
            BASE_FEE,
            BASE_SLIPPAGE,
        ),
        (
            "STRESS",
            STRESS_FEE,
            STRESS_SLIPPAGE,
        ),
    ]:

        results = []

        for window in windows:

            result = v10.simulate(
                candles,
                indicators,
                htf_directions,
                config,
                window["valid_start"],
                window["valid_end"],
                fee,
                slippage,
                window["fold"],
                scenario,
            )

            results.append(result)

        scenario_results[scenario] = (
            v10.summarize(results)
        )

    return scenario_results


# ============================================================
# MAIN
# ============================================================

def test_all():

    global ACTIVE_ATR

    print("=" * 60)
    print("SPACE BAR AI - TESTER V11.0")
    print("HTF + ATR + VOLUME RESEARCH")
    print("=" * 60)

    candles = load_data(
        SYMBOL,
        TIMEFRAME,
    )

    v10.validate_data(candles)

    indicators = prepare(candles)

    htf_directions = v10.build_htf_filter(
        candles
    )

    ACTIVE_ATR = calculate_atr_pct(
        candles,
        period=14,
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

    # Reuse V10 execution engine with V11 signals.
    # Restore original function when finished.

    v10.get_v10_signal = v11_signal_adapter

    try:

        for config in CONFIGS:

            scenarios = evaluate_configuration(
                candles,
                indicators,
                htf_directions,
                windows,
                config,
            )

            base = scenarios["BASE"]
            stress = scenarios["STRESS"]

            all_trades.extend(
                base["trade_log"]
            )

            all_trades.extend(
                stress["trade_log"]
            )

            rejection = []

            if base["trades"] < MIN_TRADES:
                rejection.append(
                    "INSUFFICIENT_TRADES"
                )

            if (
                base["positive_folds"]
                < MIN_POSITIVE_FOLDS
            ):
                rejection.append(
                    "INSUFFICIENT_POSITIVE_FOLDS"
                )

            if base["return_pct"] <= 0:
                rejection.append(
                    "NEGATIVE_RETURN"
                )

            if (
                base["profit_factor"] is None
                or base["profit_factor"]
                < MIN_PROFIT_FACTOR
            ):
                rejection.append(
                    "LOW_PROFIT_FACTOR"
                )

            if stress["return_pct"] <= 0:
                rejection.append(
                    "STRESS_TEST_FAILED"
                )

            eligible = len(rejection) == 0

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
                "rejection_reasons": (
                    "|".join(rejection)
                    if rejection
                    else "PASS"
                ),
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
                flush=True,
            )

    finally:

        v10.get_v10_signal = ORIGINAL_SIGNAL

    ranking.sort(
        key=lambda row: (
            row["eligible"],
            row["return_pct"],
            row["profit_factor"] or 0,
        ),
        reverse=True,
    )

    os.makedirs(
        REPORT_DIR,
        exist_ok=True,
    )

    v10.save_csv(
        f"{REPORT_DIR}/ranking.csv",
        ranking,
        FIELDS,
    )

    v10.save_csv(
        f"{REPORT_DIR}/trades.csv",
        all_trades,
        TRADE_FIELDS,
    )

    print("\n" + "=" * 60)
    print("TOP V11 RESEARCH RESULTS")
    print("=" * 60)

    for index, row in enumerate(
        ranking[:10],
        1,
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
            row["eligible"],
            "| Reasons:",
            row["rejection_reasons"],
        )

    print("\nV11 COMPLETED")
    print("reports/v11/ranking.csv")
    print("reports/v11/trades.csv")


if __name__ == "__main__":
    test_all()
