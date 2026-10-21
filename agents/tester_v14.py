# ============================================================
# SPACE BAR AI TRADING
# TESTER V14.0
#
# MARKET REGIME & RISK RESEARCH ENGINE
#
# BTC 5M | BINANCE USDT FUTURES
# PAPER RESEARCH ONLY
#
# IMPORTANT:
# Historical V12/V13 diagnostic data has been inspected.
# Results are NOT fresh independent OOS evidence.
# ============================================================

import csv
import os
import math

from datetime import datetime, timezone
from collections import defaultdict

import tester_v10 as v10
import tester_v11 as v11

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

REPORT_DIR = "reports/v14"

TRAIN_RATIO = 0.80

INITIAL_CAPITAL = 10000.0

BASE_FEE = 0.00055
BASE_SLIPPAGE = 0.00020

STRESS_FEE = 0.00100
STRESS_SLIPPAGE = 0.00050

ATR_PERIOD = 14

CONFIG = {
    "name": "V14_BASELINE",

    "adx_min": 25,
    "volume_mult": 0.0,
    "htf_filter": True,

    "stop": 0.006,
    "target": 0.012,

    "atr_min": 0.15,
    "atr_max": 0.30,

    "side": "BOTH",
    "signal_mode": "CROSS",
}

SCENARIOS = [
    ("BASE", BASE_FEE, BASE_SLIPPAGE),
    ("STRESS", STRESS_FEE, STRESS_SLIPPAGE),
]

# ============================================================
# CSV HELPERS
# ============================================================

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
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            extrasaction="ignore"
        )

        writer.writeheader()
        writer.writerows(rows)


def safe_round(value):

    if value is None:
        return None

    if not math.isfinite(float(value)):
        return None

    return round(value, 6)


def utc_string(timestamp):

    return datetime.fromtimestamp(
        timestamp,
        tz=timezone.utc
    ).isoformat()


# ============================================================
# DATA INTEGRITY
# ============================================================

def validate_history(candles):

    if len(candles) < 1000:
        raise RuntimeError(
            "Insufficient BTC 5m history."
        )

    now = int(
        datetime.now(timezone.utc).timestamp()
    )

    first = candles[0]["timestamp"]
    last = candles[-1]["timestamp"]

    if first >= last:
        raise RuntimeError(
            "Invalid history date range."
        )

    if last > now:
        raise RuntimeError(
            "Future market data detected."
        )

    if first < 1262304000:
        raise RuntimeError(
            "Unexpected historical timestamp."
        )

    if first % 300 != 0:
        raise RuntimeError(
            "First candle is not 5m aligned."
        )

    for i, candle in enumerate(candles):

        timestamp = candle["timestamp"]

        if timestamp % 300 != 0:
            raise RuntimeError(
                f"Misaligned timestamp at {i}"
            )

        values = [
            candle["open"],
            candle["high"],
            candle["low"],
            candle["close"],
            candle["volume"],
        ]

        if not all(
            math.isfinite(x)
            for x in values
        ):
            raise RuntimeError(
                f"Non-finite candle at {i}"
            )

        if i > 0:

            gap = (
                timestamp
                - candles[i - 1]["timestamp"]
            )

            if gap != 300:
                raise RuntimeError(
                    f"Missing or duplicate candle "
                    f"at {i}: gap={gap}"
                )

    print(
        "DATA VALIDATION PASSED",
        flush=True
    )

    print(
        "First candle:",
        utc_string(first),
        flush=True
    )

    print(
        "Last candle:",
        utc_string(last),
        flush=True
    )

    print(
        "Total candles:",
        len(candles),
        flush=True
    )


# ============================================================
# MARKET REGIME
# ============================================================

def get_regime(indicators, i):

    ema50 = indicators["ema50"][i]
    ema200 = indicators["ema200"][i]

    if ema50 is None or ema200 is None:
        return "UNKNOWN"

    difference = (
        ema50 / ema200 - 1
    ) * 100

    if difference > 0.5:
        return "BULL"

    if difference < -0.5:
        return "BEAR"

    return "SIDEWAYS"


# ============================================================
# ADX CLASSIFICATION
# ============================================================

def get_adx_group(value):

    if value is None:
        return "UNKNOWN"

    if value < 20:
        return "ADX_LT20"

    if value < 25:
        return "ADX_20_25"

    if value < 30:
        return "ADX_25_30"

    if value < 35:
        return "ADX_30_35"

    return "ADX_35_PLUS"


# ============================================================
# ATR CLASSIFICATION
# ============================================================

def get_atr_group(value):

    if value is None:
        return "UNKNOWN"

    if value < 0.15:
        return "ATR_LT015"

    if value < 0.20:
        return "ATR_015_020"

    if value < 0.25:
        return "ATR_020_025"

    if value <= 0.30:
        return "ATR_025_030"

    return "ATR_GT030"


# ============================================================
# TRADE METRICS
# ============================================================

def analyze_group(trades):

    wins = [
        trade
        for trade in trades
        if trade["net_pnl_usd"] > 0
    ]

    losses = [
        trade
        for trade in trades
        if trade["net_pnl_usd"] < 0
    ]

    gross_profit = sum(
        trade["net_pnl_usd"]
        for trade in wins
    )

    gross_loss = abs(sum(
        trade["net_pnl_usd"]
        for trade in losses
    ))

    pnl = sum(
        trade["net_pnl_usd"]
        for trade in trades
    )

    count = len(trades)

    pf = (
        gross_profit / gross_loss
        if gross_loss > 0
        else None
    )

    return {
        "trades": count,
        "wins": len(wins),
        "losses": len(losses),

        "win_rate_pct": safe_round(
            len(wins) / count * 100
            if count else 0
        ),

        "net_pnl_usd": safe_round(pnl),

        "return_pct": safe_round(
            pnl / INITIAL_CAPITAL * 100
        ),

        "profit_factor": safe_round(pf),

        "expectancy_usd": safe_round(
            pnl / count
            if count else 0
        ),

        "average_win_usd": safe_round(
            gross_profit / len(wins)
            if wins else 0
        ),

        "average_loss_usd": safe_round(
            gross_loss / len(losses)
            if losses else 0
        ),
    }


# ============================================================
# ENRICH TRADE LOG
# ============================================================

def enrich_trades(
    trades,
    candles,
    indicators,
    atr_pct,
):

    timestamp_index = {
        candle["timestamp"]: i
        for i, candle in enumerate(candles)
    }

    enriched = []

    for trade in trades:

        entry_time = trade["entry_time"]

        if entry_time not in timestamp_index:
            raise RuntimeError(
                "Trade entry timestamp "
                "not found in market history."
            )

        entry_index = timestamp_index[
            entry_time
        ]

        # The signal was confirmed
        # on the preceding 5m candle.

        signal_index = entry_index - 1

        if signal_index < 0:
            raise RuntimeError(
                "Invalid signal index."
            )

        adx_value = indicators["adx"][
            signal_index
        ]

        atr_value = atr_pct[
            signal_index
        ]

        row = dict(trade)

        row["entry_utc"] = utc_string(
            trade["entry_time"]
        )

        row["exit_utc"] = utc_string(
            trade["exit_time"]
        )

        row["regime"] = get_regime(
            indicators,
            signal_index
        )

        row["adx"] = safe_round(
            adx_value
        )

        row["atr_pct"] = safe_round(
            atr_value
        )

        row["adx_group"] = get_adx_group(
            adx_value
        )

        row["atr_group"] = get_atr_group(
            atr_value
        )

        enriched.append(row)

    return enriched


# ============================================================
# GROUP ANALYSIS
# ============================================================

def build_group_report(
    trades,
    group_name,
    scenario,
    period,
):

    groups = defaultdict(list)

    for trade in trades:

        groups[trade[group_name]].append(
            trade
        )

    rows = []

    for group in sorted(groups):

        metrics = analyze_group(
            groups[group]
        )

        rows.append({
            "period": period,
            "scenario": scenario,
            "dimension": group_name,
            "group": group,
            **metrics,
        })

    return rows


# ============================================================
# CONSECUTIVE LOSSES
# ============================================================

def analyze_loss_streaks(trades):

    ordered = sorted(
        trades,
        key=lambda t: (
            t["entry_time"],
            t["exit_time"]
        )
    )

    current = 0
    maximum = 0

    streaks = []

    for trade in ordered:

        if trade["net_pnl_usd"] < 0:

            current += 1

            maximum = max(
                maximum,
                current
            )

        else:

            if current > 0:
                streaks.append(current)

            current = 0

    if current > 0:
        streaks.append(current)

    return {
        "max_consecutive_losses": maximum,
        "loss_streak_count": len(streaks),
        "average_loss_streak": safe_round(
            sum(streaks) / len(streaks)
            if streaks else 0
        ),
    }


# ============================================================
# EVALUATION
# ============================================================

def evaluate_period(
    candles,
    indicators,
    htf_directions,
    atr_pct,
    windows,
    period_name,
):

    summary_rows = []
    group_rows = []
    streak_rows = []
    trade_rows = []
    fold_rows = []

    for scenario, fee, slippage in SCENARIOS:

        results = []
        enriched_all = []

        for window in windows:

            result = v10.simulate(
                candles,
                indicators,
                htf_directions,
                CONFIG,
                window["valid_start"],
                window["valid_end"],
                fee,
                slippage,
                window["fold"],
                scenario,
            )

            results.append(result)

            enriched = enrich_trades(
                result["trades"],
                candles,
                indicators,
                atr_pct,
            )

            enriched_all.extend(enriched)

            fold_metrics = analyze_group(
                enriched
            )

            fold_rows.append({
                "period": period_name,
                "scenario": scenario,
                "fold": window["fold"],
                **fold_metrics,
                "max_drawdown_pct": safe_round(
                    result["max_drawdown_pct"]
                ),
            })

        metrics = v10.summarize(results)

        summary_rows.append({
            "period": period_name,
            "scenario": scenario,
            "trades": metrics["trades"],
            "wins": metrics["wins"],
            "losses": metrics["losses"],
            "win_rate_pct": safe_round(
                metrics["win_rate_pct"]
            ),
            "return_pct": safe_round(
                metrics["return_pct"]
            ),
            "profit_factor": safe_round(
                metrics["profit_factor"]
            ),
            "expectancy_usd": safe_round(
                metrics["expectancy_usd"]
            ),
            "positive_folds": metrics[
                "positive_folds"
            ],
            "total_folds": metrics[
                "total_folds"
            ],
            "max_drawdown_pct": safe_round(
                metrics["max_drawdown_pct"]
            ),
        })

        for dimension in [
            "side",
            "regime",
            "adx_group",
            "atr_group",
        ]:

            group_rows.extend(
                build_group_report(
                    enriched_all,
                    dimension,
                    scenario,
                    period_name,
                )
            )

        streak_rows.append({
            "period": period_name,
            "scenario": scenario,
            **analyze_loss_streaks(
                enriched_all
            ),
        })

        for trade in enriched_all:

            trade_rows.append({
                "period": period_name,
                **trade,
            })

    return (
        summary_rows,
        group_rows,
        streak_rows,
        trade_rows,
        fold_rows,
    )


# ============================================================
# MAIN
# ============================================================

def test_all():

    print("=" * 60)
    print("SPACE BAR AI - TESTER V14.0")
    print("MARKET REGIME & RISK RESEARCH")
    print("=" * 60)

    candles = load_data(
        SYMBOL,
        TIMEFRAME
    )

    validate_history(candles)

    indicators = prepare(candles)

    htf_directions = v10.build_htf_filter(
        candles
    )

    atr_pct = v11.calculate_atr_pct(
        candles,
        period=ATR_PERIOD
    )

    total = len(candles)

    split = int(
        total * TRAIN_RATIO
    )

    if split < 1000:
        raise RuntimeError(
            "Insufficient training data."
        )

    train_windows = walk_forward_windows(
        split
    )

    if len(train_windows) != 4:
        raise RuntimeError(
            "Expected four training folds."
        )

    for window in train_windows:

        if window["valid_end"] > split:
            raise RuntimeError(
                "Training overlaps diagnostic."
            )

    diagnostic_windows = [
        {
            "fold": "DIAGNOSTIC",
            "valid_start": split,
            "valid_end": total,
        }
    ]

    original_signal = v10.get_v10_signal
    original_atr = v11.ACTIVE_ATR

    v10.get_v10_signal = (
        v11.v11_signal_adapter
    )

    v11.ACTIVE_ATR = atr_pct

    try:

        outputs = []

        for period, windows in [
            ("TRAIN", train_windows),
            ("DIAGNOSTIC", diagnostic_windows),
        ]:

            result = evaluate_period(
                candles,
                indicators,
                htf_directions,
                atr_pct,
                windows,
                period,
            )

            outputs.append(result)

        summary_rows = []
        group_rows = []
        streak_rows = []
        trade_rows = []
        fold_rows = []

        for result in outputs:

            summary_rows.extend(result[0])
            group_rows.extend(result[1])
            streak_rows.extend(result[2])
            trade_rows.extend(result[3])
            fold_rows.extend(result[4])

        summary_fields = [
            "period",
            "scenario",
            "trades",
            "wins",
            "losses",
            "win_rate_pct",
            "return_pct",
            "profit_factor",
            "expectancy_usd",
            "positive_folds",
            "total_folds",
            "max_drawdown_pct",
        ]

        group_fields = [
            "period",
            "scenario",
            "dimension",
            "group",
            "trades",
            "wins",
            "losses",
            "win_rate_pct",
            "net_pnl_usd",
            "return_pct",
            "profit_factor",
            "expectancy_usd",
            "average_win_usd",
            "average_loss_usd",
        ]

        streak_fields = [
            "period",
            "scenario",
            "max_consecutive_losses",
            "loss_streak_count",
            "average_loss_streak",
        ]

        trade_fields = [
            "period",
            *v10.TRADE_FIELDS,
            "entry_utc",
            "exit_utc",
            "regime",
            "adx",
            "atr_pct",
            "adx_group",
            "atr_group",
        ]

        fold_fields = [
            "period",
            "scenario",
            "fold",
            "trades",
            "wins",
            "losses",
            "win_rate_pct",
            "net_pnl_usd",
            "return_pct",
            "profit_factor",
            "expectancy_usd",
            "average_win_usd",
            "average_loss_usd",
            "max_drawdown_pct",
        ]

        save_csv(
            f"{REPORT_DIR}/summary.csv",
            summary_rows,
            summary_fields,
        )

        save_csv(
            f"{REPORT_DIR}/regime_analysis.csv",
            group_rows,
            group_fields,
        )

        save_csv(
            f"{REPORT_DIR}/loss_streaks.csv",
            streak_rows,
            streak_fields,
        )

        save_csv(
            f"{REPORT_DIR}/trades.csv",
            trade_rows,
            trade_fields,
        )

        save_csv(
            f"{REPORT_DIR}/folds.csv",
            fold_rows,
            fold_fields,
        )

        print("\nV14 SUMMARY")

        for row in summary_rows:

            print(
                row["period"],
                row["scenario"],
                "| Trades:",
                row["trades"],
                "| Return:",
                row["return_pct"],
                "| PF:",
                row["profit_factor"],
                flush=True,
            )

        print("\nV14 COMPLETED")
        print(f"{REPORT_DIR}/summary.csv")
        print(f"{REPORT_DIR}/regime_analysis.csv")
        print(f"{REPORT_DIR}/loss_streaks.csv")
        print(f"{REPORT_DIR}/trades.csv")
        print(f"{REPORT_DIR}/folds.csv")

        print(
            "\nWARNING: Historical diagnostic "
            "is NOT fresh independent OOS."
        )

    finally:

        v10.get_v10_signal = original_signal
        v11.ACTIVE_ATR = original_atr


if __name__ == "__main__":
    test_all()
