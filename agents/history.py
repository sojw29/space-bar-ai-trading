import csv
import os
import json
import time

from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# =====================================
# SPACE BAR AI TRADING
# HISTORY V1.1
# =====================================

BASE_URL = "https://api.bybit.com"

SYMBOLS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT"
}

TIMEFRAMES = ["1", "5", "15"]

TARGET_CANDLES = 10000
PAGE_LIMIT = 1000
REQUEST_DELAY = 0.25

DATA_DIR = "data/history"


# =====================================
# API REQUEST
# =====================================

def api_request(params):

    url = (
        BASE_URL
        + "/v5/market/kline?"
        + urlencode(params)
    )

    request = Request(
        url,
        headers={
            "User-Agent": "SpaceBarAI/1.1"
        }
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

        except Exception as error:

            print(
                f"API attempt {attempt + 1} "
                f"failed: {error}"
            )

            if attempt == 2:
                raise

            time.sleep(2 ** attempt)


# =====================================
# DOWNLOAD HISTORY
# =====================================

def download_history(symbol, interval):

    candles = {}

    interval_ms = int(interval) * 60000

    end_time = int(
        datetime.now(timezone.utc).timestamp()
        * 1000
    )

    print(
        f"\nDownloading {symbol} "
        f"{interval}M..."
    )

    while len(candles) < TARGET_CANDLES:

        remaining = TARGET_CANDLES - len(candles)

        raw = api_request({
            "category": "linear",
            "symbol": symbol,
            "interval": interval,
            "limit": min(
                PAGE_LIMIT,
                remaining
            ),
            "end": end_time
        })

        if not raw:
            break

        oldest = None

        now_ms = int(time.time() * 1000)

        for item in raw:

            timestamp = int(item[0])

            if timestamp + interval_ms > now_ms:
                continue

            candles[timestamp] = {
                "timestamp": timestamp,
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5])
            }

            if oldest is None or timestamp < oldest:
                oldest = timestamp

        if oldest is None:
            raise RuntimeError(
                "No completed candles received"
            )

        end_time = oldest - 1

        print(
            f"{symbol} {interval}M: "
            f"{len(candles)} candles"
        )

        if len(raw) < min(
            PAGE_LIMIT,
            remaining
        ):
            break

        time.sleep(REQUEST_DELAY)

    result = [
        candles[key]
        for key in sorted(candles)
    ]

    if len(result) < TARGET_CANDLES:
        raise RuntimeError(
            f"Insufficient candles: "
            f"{len(result)}/{TARGET_CANDLES}"
        )

    return result[-TARGET_CANDLES:]


# =====================================
# SAVE CSV
# =====================================

def save_csv(coin, interval, candles):

    os.makedirs(
        DATA_DIR,
        exist_ok=True
    )

    filename = (
        f"{DATA_DIR}/"
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
        f"SAVED: {filename} "
        f"({len(candles)} candles)"
    )


# =====================================
# MAIN
# =====================================

def collect_all_history():

    print("=" * 45)
    print("SPACE BAR AI - HISTORY V1.1")
    print("=" * 45)

    failures = []

    for coin, symbol in SYMBOLS.items():

        for interval in TIMEFRAMES:

            try:

                candles = download_history(
                    symbol,
                    interval
                )

                save_csv(
                    coin,
                    interval,
                    candles
                )

            except Exception as error:

                message = (
                    f"{coin} {interval}M: {error}"
                )

                print("ERROR:", message)

                failures.append(message)

    if failures:

        raise RuntimeError(
            "History collection failed:\n"
            + "\n".join(failures)
        )

    print("\nALL HISTORY DATA COLLECTED")


if __name__ == "__main__":
    collect_all_history()
