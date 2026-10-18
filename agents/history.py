import csv
import os
import json
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# =====================================
# SPACE BAR AI TRADING
# HISTORY V1.0
# =====================================

BASE_URL = "https://api.bybit.com"

SYMBOLS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT"
}

TIMEFRAMES = ["1", "5", "15"]

# Number of historical candles per market
TARGET_CANDLES = 10000

# Bybit API maximum per request
PAGE_LIMIT = 1000

# Delay between requests
REQUEST_DELAY = 0.25


# =====================================
# 1. API REQUEST
# =====================================

def api_request(params):

    endpoint = "/v5/market/kline"

    url = (
        BASE_URL
        + endpoint
        + "?"
        + urlencode(params)
    )

    request = Request(
        url,
        headers={"User-Agent": "SpaceBarAI/1.0"}
    )

    for attempt in range(3):

        try:
            with urlopen(
                request,
                timeout=20
            ) as response:
                data = json.load(response)

            if data.get("retCode") != 0:
                raise RuntimeError(
                    data.get("retMsg", "API error")
                )

            return data["result"]["list"]

        except Exception:
            if attempt == 2:
                raise

            time.sleep(2 ** attempt)


# =====================================
# 2. DOWNLOAD HISTORICAL DATA
# =====================================

def download_history(symbol, interval):

    all_candles = {}

    end_time = int(
        datetime.now(timezone.utc).timestamp()
        * 1000
    )

    interval_ms = int(interval) * 60 * 1000

    print(
        f"\nDownloading {symbol} "
        f"{interval}M history..."
    )

    while len(all_candles) < TARGET_CANDLES:

        remaining = (
            TARGET_CANDLES - len(all_candles)
        )

        limit = min(PAGE_LIMIT, remaining)

        raw = api_request({
            "category": "linear",
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
            "end": end_time
        })

        if not raw:
            break

        oldest_time = None

        for item in raw:

            candle_time = int(item[0])

            # Exclude unfinished candles
            now_ms = int(time.time() * 1000)

            if candle_time + interval_ms > now_ms:
                continue

            all_candles[candle_time] = {
                "timestamp": candle_time,
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5])
            }

            if (
                oldest_time is None
                or candle_time < oldest_time
            ):
                oldest_time = candle_time

        if oldest_time is None:
            break

        next_end = oldest_time - 1

        if next_end >= end_time:
            break

        end_time = next_end

        print(
            f"{symbol} {interval}M: "
            f"{len(all_candles)} candles"
        )

        if len(raw) < limit:
            break

        time.sleep(REQUEST_DELAY)

    candles = [
        all_candles[key]
        for key in sorted(all_candles)
    ]

    return candles[-TARGET_CANDLES:]


# =====================================
# 3. SAVE CSV
# =====================================

def save_csv(coin, interval, candles):

    os.makedirs("data/history", exist_ok=True)

    filename = (
        f"data/history/"
        f"{coin}_{interval}m.csv"
    )

    columns = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    with open(
        filename,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=columns
        )

        writer.writeheader()
        writer.writerows(candles)

    print(
        f"Saved: {filename} "
        f"({len(candles)} candles)"
    )


# =====================================
# 4. MAIN
# =====================================

def collect_all_history():

    print("=" * 40)
    print("SPACE BAR AI - HISTORY V1.0")
    print("=" * 40)

    for coin, symbol in SYMBOLS.items():

        for interval in TIMEFRAMES:

            try:
                candles = download_history(
                    symbol,
                    interval
                )

                if not candles:
                    print(
                        f"No data: {coin} {interval}M"
                    )
                    continue

                save_csv(
                    coin,
                    interval,
                    candles
                )

            except Exception as error:
                print(
                    f"ERROR {coin} {interval}M: "
                    f"{error}"
                )

    print("\nHistory collection finished.")


if __name__ == "__main__":
    collect_all_history()
