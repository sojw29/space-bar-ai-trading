import csv
import json
import os
from datetime import datetime, timezone

# ==========================================
# SPACE BAR AI TRADING
# TESTER V1.0 - BACKTEST ENGINE
# ==========================================

INITIAL_CAPITAL = 10000.0

# Fee per side: 0.055%
FEE_RATE = 0.00055

# Slippage per side: 0.02%
SLIPPAGE = 0.0002

# Fraction of equity used per trade
POSITION_SIZE = 0.10

# Price-based stop loss and take profit
STOP_LOSS = 0.006
TAKE_PROFIT = 0.012

# EMA crossover strategy (baseline only)
FAST_EMA = 20
SLOW_EMA = 50

DATA_DIR = "data/history"
REPORT_DIR = "reports"

SYMBOLS = ["BTC", "ETH", "SOL"]
TIMEFRAMES = ["1", "5", "15"]


# ==========================================
# 1. LOAD DATA
# ==========================================

def load_data(coin, interval):

    filename = (
        f"{DATA_DIR}/{coin}_{interval}m.csv"
    )

    if not os.path.exists(filename):
        print(f"Missing data: {filename}")
        return []

    candles = []

    with open(
        filename,
        "r",
        encoding="utf-8"
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

                candles.append(candle)

            except (ValueError, KeyError):
                continue

    candles.sort(
        key=lambda x: x["timestamp"]
    )

    return candles


# ==========================================
# 2. EMA CALCULATION
# ==========================================

def calculate_ema(prices, period):

    if len(prices) < period:
        return [None] * len(prices)

    result = [None] * len(prices)

    multiplier = 2 / (period + 1)

    initial = sum(
        prices[:period]
    ) / period

    result[period - 1] = initial

    previous = initial

    for i in range(period, len(prices)):

        previous = (
            prices[i] * multiplier
            + previous * (1 - multiplier)
        )

        result[i] = previous

    return result


# ==========================================
# 3. BACKTEST
# ==========================================

def run_backtest(candles):

    if len(candles) < SLOW_EMA + 2:
        return None

    closes = [
        candle["close"]
        for candle in candles
    ]

    fast = calculate_ema(
        closes,
        FAST_EMA
    )

    slow = calculate_ema(
        closes,
        SLOW_EMA
    )

    equity = INITIAL_CAPITAL
    peak_equity = equity
    max_drawdown = 0.0

    position = None
    trades = []

    for i in range(SLOW_EMA + 1, len(candles)):

        candle = candles[i]

        # Existing position:
        # check stop and target first.
        if position is not None:

            side = position["side"]
            entry = position["entry"]
            amount = position["amount"]

            if side == "LONG":

                stop = entry * (1 - STOP_LOSS)
                target = entry * (1 + TAKE_PROFIT)

                hit_stop = candle["low"] <= stop
                hit_target = candle["high"] >= target

                # Conservative assumption:
                # if both hit, stop executes first.
                if hit_stop:
                    exit_price = stop * (1 - SLIPPAGE)
                    reason = "SL"

                elif hit_target:
                    exit_price = target * (1 - SLIPPAGE)
                    reason = "TP"

                else:
                    continue

                gross_return = (
                    exit_price / entry - 1
                )

            else:

                stop = entry * (1 + STOP_LOSS)
                target = entry * (1 - TAKE_PROFIT)

                hit_stop = candle["high"] >= stop
                hit_target = candle["low"] <= target

                if hit_stop:
                    exit_price = stop * (1 + SLIPPAGE)
                    reason = "SL"

                elif hit_target:
                    exit_price = target * (1 + SLIPPAGE)
                    reason = "TP"

                else:
                    continue

                gross_return = (
                    entry / exit_price - 1
                )

            fees = amount * FEE_RATE * 2
            pnl = amount * gross_return - fees

            equity += pnl

            trades.append({
                "side": side,
                "entry_time": position["time"],
                "exit_time": candle["timestamp"],
                "entry": round(entry, 6),
                "exit": round(exit_price, 6),
                "reason": reason,
                "pnl": round(pnl, 4)
            })

            position = None

            peak_equity = max(
                peak_equity,
                equity
            )

            drawdown = (
                (peak_equity - equity)
                / peak_equity
            )

            max_drawdown = max(
                max_drawdown,
                drawdown
            )

            continue

        # EMA crossover confirmed on
        # previous completed candle.
        previous = i - 1
        before = i - 2

        if (
            fast[before] is None
            or slow[before] is None
        ):
            continue

        bullish_cross = (
            fast[before] <= slow[before]
            and fast[previous] > slow[previous]
        )

        bearish_cross = (
            fast[before] >= slow[before]
            and fast[previous] < slow[previous]
        )

        if not bullish_cross and not bearish_cross:
            continue

        if equity <= 0:
            break

        side = (
            "LONG"
            if bullish_cross
            else "SHORT"
        )

        entry_price = candle["open"]

        if side == "LONG":
            entry_price *= (1 + SLIPPAGE)
        else:
            entry_price *= (1 - SLIPPAGE)

        position = {
            "side": side,
            "entry": entry_price,
            "amount": equity * POSITION_SIZE,
            "time": candle["timestamp"]
        }

    # ======================================
    # 4. PERFORMANCE METRICS
    # ======================================

    wins = [
        trade for trade in trades
        if trade["pnl"] > 0
    ]

    losses = [
        trade for trade in trades
        if trade["pnl"] < 0
    ]

    total_trades = len(trades)

    win_rate = (
        len(wins) / total_trades * 100
        if total_trades
        else 0
    )

    gross_profit = sum(
        trade["pnl"] for trade in wins
    )

    gross_loss = abs(sum(
        trade["pnl"] for trade in losses
    ))

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else None
    )

    total_return = (
        (equity / INITIAL_CAPITAL - 1)
        * 100
    )

    return {
        "initial_capital": INITIAL_CAPITAL,
        "final_equity": round(equity, 2),
        "total_return_pct": round(
            total_return, 2
        ),
        "total_trades": total_trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(win_rate, 2),
        "profit_factor": (
            round(profit_factor, 3)
            if profit_factor is not None
            else None
        ),
        "max_drawdown_pct": round(
            max_drawdown * 100, 2
        ),
        "trades": trades
    }


# ==========================================
# 5. SAVE REPORT
# ==========================================

def save_report(coin, interval, result):

    os.makedirs(
        REPORT_DIR,
        exist_ok=True
    )

    filename = (
        f"{REPORT_DIR}/"
        f"{coin}_{interval}m_backtest.json"
    )

    report = {
        "symbol": coin,
        "timeframe": f"{interval}m",
        "strategy": "EMA_CROSSOVER_20_50",
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        **result
    }

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            indent=2,
            ensure_ascii=False
        )

    print(
        f"Saved report: {filename}"
    )


# ==========================================
# 6. MAIN
# ==========================================

def test_all():

    print("=" * 45)
    print("SPACE BAR AI - TESTER V1.0")
    print("=" * 45)

    for coin in SYMBOLS:

        for interval in TIMEFRAMES:

            candles = load_data(
                coin,
                interval
            )

            if not candles:
                continue

            result = run_backtest(candles)

            if result is None:
                print(
                    f"Insufficient data: "
                    f"{coin} {interval}m"
                )
                continue

            save_report(
                coin,
                interval,
                result
            )

            print(
                f"{coin} {interval}m | "
                f"Trades: {result['total_trades']} | "
                f"Win: {result['win_rate_pct']}% | "
                f"Return: {result['total_return_pct']}%"
            )

    print("\nBacktest finished.")


if __name__ == "__main__":
    test_all()
