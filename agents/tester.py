# ==========================================
# SPACE BAR AI TRADING
# TESTER V4.0
# WALK-FORWARD RESEARCH ENGINE
# PAPER RESEARCH ONLY
# ==========================================

import csv
import json
import os
from datetime import datetime, timezone

INITIAL_CAPITAL = 10000.0

FEE_RATE = 0.00055
SLIPPAGE = 0.0002
POSITION_SIZE = 0.10

STOP_LOSS = 0.006
TAKE_PROFIT = 0.012

DATA_DIR = "data/history"
REPORT_DIR = "reports"

SYMBOLS = ["BTC", "ETH", "SOL"]
TIMEFRAMES = ["1", "5", "15"]

MIN_CANDLES = 600
MIN_VALIDATION_TRADES = 10

STRATEGIES = [
    "EMA_CROSS",
    "TREND_ADX",
    "VOLUME_BREAKOUT",
    "EMA_PULLBACK",
    "LIQUIDITY_SWEEP"
]


# ==========================================
# DATA
# ==========================================

def load_data(symbol, timeframe):

    path = (
        f"{DATA_DIR}/"
        f"{symbol}_{timeframe}m.csv"
    )

    if not os.path.exists(path):
        print("Missing:", path)
        return []

    candles = {}

    with open(
        path,
        "r",
        encoding="utf-8-sig"
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            try:
                candle = {
                    "timestamp": int(row["timestamp"]),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"])
                }

                if (
                    candle["open"] <= 0
                    or candle["high"] <= 0
                    or candle["low"] <= 0
                    or candle["close"] <= 0
                    or candle["volume"] < 0
                    or candle["high"] < candle["low"]
                    or candle["high"] < max(
                        candle["open"], candle["close"]
                    )
                    or candle["low"] > min(
                        candle["open"], candle["close"]
                    )
                ):
                    continue

                candles[candle["timestamp"]] = candle

            except (ValueError, KeyError, TypeError):
                continue

    return [
        candles[t]
        for t in sorted(candles)
    ]


# ==========================================
# INDICATORS
# ==========================================

def ema(values, period):

    result = [None] * len(values)

    if len(values) < period:
        return result

    previous = sum(values[:period]) / period
    result[period - 1] = previous

    multiplier = 2 / (period + 1)

    for i in range(period, len(values)):

        previous = (
            values[i] * multiplier
            + previous * (1 - multiplier)
        )

        result[i] = previous

    return result


def sma(values, period):

    result = [None] * len(values)
    total = 0.0

    for i, value in enumerate(values):

        total += value

        if i >= period:
            total -= values[i - period]

        if i >= period - 1:
            result[i] = total / period

    return result


def calculate_adx(candles, period=14):

    n = len(candles)
    result = [None] * n

    if n < period * 2:
        return result

    tr = [0.0] * n
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n

    for i in range(1, n):

        c = candles[i]
        p = candles[i - 1]

        up = c["high"] - p["high"]
        down = p["low"] - c["low"]

        plus_dm[i] = (
            up if up > down and up > 0 else 0
        )

        minus_dm[i] = (
            down if down > up and down > 0 else 0
        )

        tr[i] = max(
            c["high"] - c["low"],
            abs(c["high"] - p["close"]),
            abs(c["low"] - p["close"])
        )

    sm_tr = sum(tr[1:period + 1])
    sm_plus = sum(plus_dm[1:period + 1])
    sm_minus = sum(minus_dm[1:period + 1])

    dx = [None] * n

    for i in range(period, n):

        if i > period:

            sm_tr += tr[i] - sm_tr / period
            sm_plus += plus_dm[i] - sm_plus / period
            sm_minus += minus_dm[i] - sm_minus / period

        if sm_tr <= 0:
            dx[i] = 0
            continue

        plus_di = 100 * sm_plus / sm_tr
        minus_di = 100 * sm_minus / sm_tr

        denominator = plus_di + minus_di

        dx[i] = (
            100 * abs(plus_di - minus_di) / denominator
            if denominator > 0 else 0
        )

    first = period * 2 - 1

    result[first] = (
        sum(dx[period:first + 1]) / period
    )

    for i in range(first + 1, n):

        result[i] = (
            result[i - 1] * (period - 1) + dx[i]
        ) / period

    return result


def prepare(candles):

    closes = [c["close"] for c in candles]
    volumes = [c["volume"] for c in candles]

    return {
        "ema20": ema(closes, 20),
        "ema50": ema(closes, 50),
        "ema200": ema(closes, 200),
        "vol20": sma(volumes, 20),
        "adx": calculate_adx(candles)
    }


# ==========================================
# MARKET REGIME
# ==========================================

def market_regime(indicators, i):

    e50 = indicators["ema50"][i]
    e200 = indicators["ema200"][i]

    if e50 is None or e200 is None:
        return "UNKNOWN"

    difference = (e50 / e200 - 1) * 100

    if difference > 0.5:
        return "BULL"

    if difference < -0.5:
        return "BEAR"

    return "SIDEWAYS"


# ==========================================
# STRATEGY SIGNALS
# ==========================================

def get_signal(strategy, candles, indicators, i):

    if i < 201:
        return None

    c = candles[i]
    p = candles[i - 1]

    e20 = indicators["ema20"]
    e50 = indicators["ema50"]
    e200 = indicators["ema200"]

    vol20 = indicators["vol20"]
    adx = indicators["adx"]

    if strategy == "EMA_CROSS":

        if (
            e20[i - 1] <= e50[i - 1]
            and e20[i] > e50[i]
        ):
            return "LONG"

        if (
            e20[i - 1] >= e50[i - 1]
            and e20[i] < e50[i]
        ):
            return "SHORT"

    elif strategy == "TREND_ADX":

        if adx[i] is None or adx[i] < 25:
            return None

        if (
            e50[i] > e200[i]
            and c["close"] > e50[i]
            and p["close"] <= e50[i - 1]
        ):
            return "LONG"

        if (
            e50[i] < e200[i]
            and c["close"] < e50[i]
            and p["close"] >= e50[i - 1]
        ):
            return "SHORT"

    elif strategy == "VOLUME_BREAKOUT":

        if (
            vol20[i] is None
            or c["volume"] < vol20[i] * 1.5
        ):
            return None

        previous_high = max(
            x["high"] for x in candles[i - 20:i]
        )

        previous_low = min(
            x["low"] for x in candles[i - 20:i]
        )

        if (
            c["close"] > previous_high
            and c["close"] > e200[i]
        ):
            return "LONG"

        if (
            c["close"] < previous_low
            and c["close"] < e200[i]
        ):
            return "SHORT"

    elif strategy == "EMA_PULLBACK":

        if (
            e50[i] > e200[i]
            and c["low"] <= e50[i]
            and c["close"] > e50[i]
            and c["close"] > c["open"]
        ):
            return "LONG"

        if (
            e50[i] < e200[i]
            and c["high"] >= e50[i]
            and c["close"] < e50[i]
            and c["close"] < c["open"]
        ):
            return "SHORT"

    elif strategy == "LIQUIDITY_SWEEP":

        previous_high = max(
            x["high"] for x in candles[i - 10:i]
        )

        previous_low = min(
            x["low"] for x in candles[i - 10:i]
        )

        if (
            c["low"] < previous_low
            and c["close"] > previous_low
            and c["close"] > c["open"]
        ):
            return "LONG"

        if (
            c["high"] > previous_high
            and c["close"] < previous_high
            and c["close"] < c["open"]
        ):
            return "SHORT"

    return None


# ==========================================
# BACKTEST ENGINE
# ==========================================

def run_backtest(
    candles,
    indicators,
    strategy,
    start,
    end
):

    equity = INITIAL_CAPITAL
    peak = equity
    max_drawdown = 0.0

    position = None
    trades = []

    def close_position(position, price, timestamp, reason):

        nonlocal equity

        entry = position["entry"]
        amount = position["amount"]
        side = position["side"]

        if side == "LONG":
            gross_return = price / entry - 1
        else:
            gross_return = entry / price - 1

        fees = amount * FEE_RATE * 2
        pnl = amount * gross_return - fees

        equity += pnl

        trades.append({
            "side": side,
            "regime": position["regime"],
            "entry_time": position["time"],
            "exit_time": timestamp,
            "entry": round(entry, 6),
            "exit": round(price, 6),
            "reason": reason,
            "pnl": round(pnl, 6),
            "trade_return_pct": round(
                pnl / amount * 100, 6
            ) if amount > 0 else 0
        })

    for i in range(start, end):

        candle = candles[i]

        if position is not None:

            entry = position["entry"]
            side = position["side"]

            if side == "LONG":

                stop = entry * (1 - STOP_LOSS)
                target = entry * (1 + TAKE_PROFIT)

                if candle["open"] <= stop:
                    price = candle["open"] * (1 - SLIPPAGE)
                    reason = "SL_GAP"

                elif candle["low"] <= stop:
                    price = stop * (1 - SLIPPAGE)
                    reason = "SL"

                elif candle["open"] >= target:
                    price = target * (1 - SLIPPAGE)
                    reason = "TP"

                elif candle["high"] >= target:
                    price = target * (1 - SLIPPAGE)
                    reason = "TP"

                else:
                    price = None

            else:

                stop = entry * (1 + STOP_LOSS)
                target = entry * (1 - TAKE_PROFIT)

                if candle["open"] >= stop:
                    price = candle["open"] * (1 + SLIPPAGE)
                    reason = "SL_GAP"

                elif candle["high"] >= stop:
                    price = stop * (1 + SLIPPAGE)
                    reason = "SL"

                elif candle["open"] <= target:
                    price = target * (1 + SLIPPAGE)
                    reason = "TP"

                elif candle["low"] <= target:
                    price = target * (1 + SLIPPAGE)
                    reason = "TP"

                else:
                    price = None

            if price is not None:

                close_position(
                    position,
                    price,
                    candle["timestamp"],
                    reason
                )

                position = None

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

                marked_equity = equity + unrealized

                peak = max(peak, marked_equity)

                if peak > 0:
                    max_drawdown = max(
                        max_drawdown,
                        (peak - marked_equity) / peak
                    )

        else:

            if equity <= 0:
                break

            signal = get_signal(
                strategy,
                candles,
                indicators,
                i - 1
            )

            if signal is not None:

                price = candle["open"]

                if signal == "LONG":
                    price *= 1 + SLIPPAGE
                else:
                    price *= 1 - SLIPPAGE

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

        peak = max(peak, equity)

        if peak > 0:
            max_drawdown = max(
                max_drawdown,
                (peak - equity) / peak
            )

    if position is not None:

        last = candles[end - 1]

        if position["side"] == "LONG":
            price = last["close"] * (1 - SLIPPAGE)
        else:
            price = last["close"] * (1 + SLIPPAGE)

        close_position(
            position,
            price,
            last["timestamp"],
            "END"
        )

        peak = max(peak, equity)

        if peak > 0:
            max_drawdown = max(
                max_drawdown,
                (peak - equity) / peak
            )

    return calculate_metrics(
        trades,
        equity,
        max_drawdown
    )


# ==========================================
# PERFORMANCE METRICS
# ==========================================

def calculate_metrics(trades, equity, max_drawdown):

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] < 0]

    total = len(trades)

    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0 else None
    )

    win_rate = (
        len(wins) / total * 100
        if total else 0
    )

    expectancy = (
        sum(t["pnl"] for t in trades) / total
        if total else 0
    )

    average_win = (
        gross_profit / len(wins)
        if wins else 0
    )

    average_loss = (
        gross_loss / len(losses)
        if losses else 0
    )

    payoff_ratio = (
        average_win / average_loss
        if average_loss > 0 else None
    )

    return {
        "trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(win_rate, 4),
        "return_pct": round(
            (equity / INITIAL_CAPITAL - 1) * 100,
            4
        ),
        "profit_factor": (
            round(profit_factor, 4)
            if profit_factor is not None
            else None
        ),
        "max_drawdown_pct": round(
            max_drawdown * 100, 4
        ),
        "expectancy_usd": round(expectancy, 6),
        "average_win_usd": round(average_win, 6),
        "average_loss_usd": round(average_loss, 6),
        "payoff_ratio": (
            round(payoff_ratio, 4)
            if payoff_ratio is not None
            else None
        ),
        "final_equity": round(equity, 4),
        "trade_log": trades
    }


# ==========================================
# WALK-FORWARD WINDOWS
# ==========================================

def walk_forward_windows(n):

    # Expanding training history,
    # followed by non-overlapping
    # out-of-sample validation windows.

    boundaries = [
        int(n * 0.40),
        int(n * 0.55),
        int(n * 0.70),
        int(n * 0.85),
        n
    ]

    windows = []

    for i in range(4):

        train_end = boundaries[i]
        valid_start = boundaries[i]
        valid_end = boundaries[i + 1]

        if (
            train_end >= 300
            and valid_end - valid_start >= 50
        ):
            windows.append({
                "fold": i + 1,
                "train_start": 201,
                "train_end": train_end,
                "valid_start": valid_start,
                "valid_end": valid_end
            })

    return windows


# ==========================================
# REPORT HELPERS
# ==========================================

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


def save_json(path, data):

    os.makedirs(
        os.path.dirname(path),
        exist_ok=True
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )


# ==========================================
# MAIN
# ==========================================

def test_all():

    print("=" * 55)
    print("SPACE BAR AI - TESTER V4.0")
    print("WALK-FORWARD RESEARCH")
    print("=" * 55)

    os.makedirs(
        REPORT_DIR,
        exist_ok=True
    )

    summary = []
    regime_rows = []
    ranking = []

    for symbol in SYMBOLS:

        for timeframe in TIMEFRAMES:

            candles = load_data(
                symbol,
                timeframe
            )

            if len(candles) < MIN_CANDLES:

                print(
                    "Insufficient data:",
                    symbol,
                    timeframe
                )

                continue

            indicators = prepare(candles)
            windows = walk_forward_windows(len(candles))

            for strategy in STRATEGIES:

                validation_results = []

                for window in windows:

                    fold = window["fold"]

                    train = run_backtest(
                        candles,
                        indicators,
                        strategy,
                        window["train_start"],
                        window["train_end"]
                    )

                    valid = run_backtest(
                        candles,
                        indicators,
                        strategy,
                        window["valid_start"],
                        window["valid_end"]
                    )

                    validation_results.append(valid)

                    for period, result in [
                        ("TRAIN", train),
                        ("VALIDATION", valid)
                    ]:

                        row = {
                            "symbol": symbol,
                            "timeframe": timeframe + "m",
                            "strategy": strategy,
                            "fold": fold,
                            "period": period,
                            "trades": result["trades"],
                            "win_rate_pct": result["win_rate_pct"],
                            "return_pct": result["return_pct"],
                            "profit_factor": result["profit_factor"],
                            "max_drawdown_pct": result[
                                "max_drawdown_pct"
                            ],
                            "expectancy_usd": result[
                                "expectancy_usd"
                            ],
                            "payoff_ratio": result[
                                "payoff_ratio"
                            ]
                        }

                        summary.append(row)

                        name = (
                            f"{symbol}_{timeframe}m_"
                            f"{strategy}_F{fold}_{period}"
                        )

                        save_json(
                            f"{REPORT_DIR}/{name}.json",
                            {
                                "created_at": datetime.now(
                                    timezone.utc
                                ).isoformat(),
                                **row,
                                "trade_log": result["trade_log"]
                            }
                        )

                    for regime in [
                        "BULL",
                        "BEAR",
                        "SIDEWAYS"
                    ]:

                        regime_trades = [
                            t for t in valid["trade_log"]
                            if t["regime"] == regime
                        ]

                        regime_rows.append({
                            "symbol": symbol,
                            "timeframe": timeframe + "m",
                            "strategy": strategy,
                            "fold": fold,
                            "regime": regime,
                            "trades": len(regime_trades),
                            "total_pnl_usd": round(
                                sum(
                                    t["pnl"]
                                    for t in regime_trades
                                ),
                                6
                            )
                        })

                if not validation_results:
                    continue

                total_trades = sum(
                    r["trades"]
                    for r in validation_results
                )

                positive_folds = sum(
                    r["return_pct"] > 0
                    for r in validation_results
                )

                all_trades = [
                    trade
                    for result in validation_results
                    for trade in result["trade_log"]
                ]

                gross_profit = sum(
                    t["pnl"]
                    for t in all_trades
                    if t["pnl"] > 0
                )

                gross_loss = abs(sum(
                    t["pnl"]
                    for t in all_trades
                    if t["pnl"] < 0
                ))

                pf = (
                    gross_profit / gross_loss
                    if gross_loss > 0
                    else None
                )

                total_pnl = sum(
                    t["pnl"]
                    for t in all_trades
                )

                total_return = (
                    total_pnl / INITIAL_CAPITAL * 100
                )

                expectancy = (
                    total_pnl / total_trades
                    if total_trades else 0
                )

                max_dd = max(
                    r["max_drawdown_pct"]
                    for r in validation_results
                )

                eligible = (
                    total_trades >= MIN_VALIDATION_TRADES
                    and positive_folds >= 3
                    and total_pnl > 0
                    and pf is not None
                    and pf > 1
                )

                ranking.append({
                    "symbol": symbol,
                    "timeframe": timeframe + "m",
                    "strategy": strategy,
                    "validation_trades": total_trades,
                    "positive_folds": positive_folds,
                    "total_folds": len(validation_results),
                    "validation_return_pct": round(
                        total_return, 4
                    ),
                    "validation_pf": (
                        round(pf, 4)
                        if pf is not None
                        else None
                    ),
                    "expectancy_usd": round(
                        expectancy, 6
                    ),
                    "worst_fold_mdd_pct": max_dd,
                    "eligible": eligible
                })

                print(
                    symbol,
                    timeframe + "m",
                    strategy,
                    "| Trades:", total_trades,
                    "| Positive folds:", positive_folds,
                    "| Return:", round(total_return, 4),
                    "| PF:", round(pf, 4)
                    if pf is not None else None
                )

    summary_fields = [
        "symbol",
        "timeframe",
        "strategy",
        "fold",
        "period",
        "trades",
        "win_rate_pct",
        "return_pct",
        "profit_factor",
        "max_drawdown_pct",
        "expectancy_usd",
        "payoff_ratio"
    ]

    ranking_fields = [
        "symbol",
        "timeframe",
        "strategy",
        "validation_trades",
        "positive_folds",
        "total_folds",
        "validation_return_pct",
        "validation_pf",
        "expectancy_usd",
        "worst_fold_mdd_pct",
        "eligible"
    ]

    regime_fields = [
        "symbol",
        "timeframe",
        "strategy",
        "fold",
        "regime",
        "trades",
        "total_pnl_usd"
    ]

    save_csv(
        f"{REPORT_DIR}/summary.csv",
        summary,
        summary_fields
    )

    save_csv(
        f"{REPORT_DIR}/regime_analysis.csv",
        regime_rows,
        regime_fields
    )

    ranking.sort(
        key=lambda row: (
            row["eligible"],
            row["positive_folds"],
            row["validation_return_pct"]
        ),
        reverse=True
    )

    save_csv(
        f"{REPORT_DIR}/ranking.csv",
        ranking,
        ranking_fields
    )

    print("\n" + "=" * 55)
    print("TOP WALK-FORWARD CANDIDATES")
    print("=" * 55)

    for index, row in enumerate(ranking[:10], 1):

        print(
            index,
            row["symbol"],
            row["timeframe"],
            row["strategy"],
            "| Return:",
            row["validation_return_pct"],
            "| PF:",
            row["validation_pf"],
            "| Positive folds:",
            row["positive_folds"],
            "| Eligible:",
            row["eligible"]
        )

    if not summary:
        raise RuntimeError(
            "No backtest results generated."
        )

    print("\nTESTER V4.0 COMPLETED")
    print("reports/summary.csv")
    print("reports/ranking.csv")
    print("reports/regime_analysis.csv")


if __name__ == "__main__":
    test_all()
