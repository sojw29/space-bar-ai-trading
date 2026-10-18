import json
import os
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.parse import urlencode

# =====================================
# SPACE BAR AI TRADING
# ATLAS V2.0 MARKET ANALYSIS ENGINE
# =====================================

BASE_URL = "https://api.bybit.com"

SYMBOLS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT"
}

TIMEFRAMES = ["1", "5", "15"]

CANDLE_LIMIT = 250


# =====================================
# 1. BYBIT API
# =====================================

def api_request(endpoint, params):

    query = urlencode(params)

    url = f"{BASE_URL}{endpoint}?{query}"

    request = Request(
        url,
        headers={"User-Agent": "SpaceBarAI/2.0"}
    )

    with urlopen(request, timeout=15) as response:
        data = json.load(response)

    if data.get("retCode") != 0:
        raise RuntimeError(
            data.get("retMsg", "Bybit API error")
        )

    return data["result"]


# =====================================
# 2. MARKET DATA COLLECTION
# =====================================

def get_candles(symbol, interval):

    result = api_request(
        "/v5/market/kline",
        {
            "category": "linear",
            "symbol": symbol,
            "interval": interval,
            "limit": CANDLE_LIMIT
        }
    )

    raw = result.get("list", [])

    candles = []

    for item in reversed(raw):

        candle = {
            "time": int(item[0]),
            "open": float(item[1]),
            "high": float(item[2]),
            "low": float(item[3]),
            "close": float(item[4]),
            "volume": float(item[5])
        }

        candles.append(candle)

    # Remove the latest candle if it is unfinished.
    if candles:

        interval_ms = int(interval) * 60 * 1000

        now_ms = int(
            datetime.now(timezone.utc).timestamp() * 1000
        )

        last_start = candles[-1]["time"]

        if now_ms < last_start + interval_ms:
            candles.pop()

    return candles


# =====================================
# 3. EMA INDICATOR
# =====================================

def calculate_ema(values, period):

    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    ema = sum(values[:period]) / period

    for price in values[period:]:
        ema = (
            price * multiplier
            + ema * (1 - multiplier)
        )

    return ema


# =====================================
# 4. RSI INDICATOR
# =====================================

def calculate_rsi(values, period=14):

    if len(values) <= period:
        return None

    changes = [
        values[i] - values[i - 1]
        for i in range(1, len(values))
    ]

    gains = [
        max(change, 0)
        for change in changes
    ]

    losses = [
        max(-change, 0)
        for change in changes
    ]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(changes)):

        avg_gain = (
            avg_gain * (period - 1) + gains[i]
        ) / period

        avg_loss = (
            avg_loss * (period - 1) + losses[i]
        ) / period

    if avg_gain == 0 and avg_loss == 0:
        return 50.0

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


# =====================================
# 5. ATR INDICATOR
# =====================================

def calculate_atr(candles, period=14):

    if len(candles) <= period:
        return None

    true_ranges = []

    for i in range(1, len(candles)):

        current = candles[i]
        previous = candles[i - 1]

        tr = max(
            current["high"] - current["low"],
            abs(
                current["high"] - previous["close"]
            ),
            abs(
                current["low"] - previous["close"]
            )
        )

        true_ranges.append(tr)

    atr = sum(true_ranges[:period]) / period

    for tr in true_ranges[period:]:

        atr = (
            atr * (period - 1) + tr
        ) / period

    return atr


# =====================================
# 6. VOLUME ANALYSIS
# =====================================

def analyze_volume(candles):

    if len(candles) < 21:
        return None

    current_volume = candles[-1]["volume"]

    previous_volumes = [
        candle["volume"]
        for candle in candles[-21:-1]
    ]

    average_volume = (
        sum(previous_volumes) / 20
    )

    if average_volume == 0:
        return None

    return current_volume / average_volume


# =====================================
# 7. MARKET ANALYSIS
# =====================================

def analyze_candles(candles):

    if len(candles) < 200:
        raise ValueError(
            "Not enough candles for EMA200"
        )

    closes = [
        candle["close"]
        for candle in candles
    ]

    price = closes[-1]

    ema50 = calculate_ema(closes, 50)
    ema200 = calculate_ema(closes, 200)

    rsi = calculate_rsi(closes, 14)
    atr = calculate_atr(candles, 14)

    volume_ratio = analyze_volume(candles)

    if price > ema50 > ema200:
        trend = "BULLISH"

    elif price < ema50 < ema200:
        trend = "BEARISH"

    else:
        trend = "NEUTRAL"

    return {
        "price": price,
        "ema50": round(ema50, 6),
        "ema200": round(ema200, 6),
        "rsi14": round(rsi, 2),
        "atr14": round(atr, 6),
        "volume_ratio": (
            round(volume_ratio, 3)
            if volume_ratio is not None
            else None
        ),
        "trend": trend,
        "last_candle_time": candles[-1]["time"]
    }


# =====================================
# 8. SAVE RESULTS
# =====================================

def save_results(results):

    os.makedirs("data", exist_ok=True)

    filename = "data/atlas_report.json"

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            indent=4,
            ensure_ascii=False
        )

    print(f"\nReport saved: {filename}")


# =====================================
# 9. ATLAS MAIN ENGINE
# =====================================

def analyze_market():

    print("\n================================")
    print("SPACE BAR AI - ATLAS V2.0")
    print("================================")

    results = {
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "markets": {}
    }

    for coin, symbol in SYMBOLS.items():

        results["markets"][coin] = {}

        for timeframe in TIMEFRAMES:

            try:

                candles = get_candles(
                    symbol,
                    timeframe
                )

                analysis = analyze_candles(
                    candles
                )

                results["markets"][coin][
                    timeframe
                ] = analysis

                print(
                    f"{coin} {timeframe}M | "
                    f"{analysis['trend']} | "
                    f"RSI: {analysis['rsi14']}"
                )

            except Exception as error:

                print(
                    f"{coin} {timeframe}M ERROR: "
                    f"{error}"
                )

                results["markets"][coin][
                    timeframe
                ] = {
                    "error": str(error)
                }

    save_results(results)

    return results


if __name__ == "__main__":
    analyze_market()
