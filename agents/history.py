# ============================================================
# SPACE BAR AI TRADING
# HISTORY V6.0 - LONG TERM MARKET DATA
# PAPER RESEARCH ONLY
# ============================================================

import csv
import os
import time
import json
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
TIMEFRAMES = [1, 5, 15]

DATA_DIR = "data/history"

API_URL = "https://api.bybit.com/v5/market/kline"

DAYS_TO_COLLECT = 365
LIMIT = 1000
MAX_RETRIES = 5

# Keep individual GitHub Actions runs manageable.
MAX_REQUESTS_PER_SYMBOL = 60

os.makedirs(DATA_DIR, exist_ok=True)


def request_klines(symbol, end_ms):
    params = (
        f"?category=linear"
        f"&symbol={symbol}"
        f"&interval=1"
        f"&limit={LIMIT}"
        f"&end={end_ms}"
    )

    url = API_URL + params

    for attempt in range(MAX_RETRIES):
        try:
            request = Request(
                url,
                headers={"User-Agent": "Mozilla/5.0"}
            )

            with urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode())

            if data.get("retCode") != 0:
                raise RuntimeError(
                    f"Bybit API error: {data.get('retMsg')}"
                )

            return data["result"]["list"]

        except (HTTPError, URLError, TimeoutError, RuntimeError) as error:
            print(
                f"Retry {attempt + 1}/{MAX_RETRIES}: {error}",
                flush=True
            )

            if attempt < MAX_RETRIES - 1:
                time.sleep(3 * (attempt + 1))

    raise RuntimeError(f"Failed to download {symbol}")


def load_existing(symbol):
    short_symbol = symbol.replace("USDT", "")
    path = f"{DATA_DIR}/{short_symbol}_1m.csv"

    candles = {}

    if not os.path.exists(path):
        return candles

    with open(path, "r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            try:
                timestamp = int(float(row["timestamp"]))

                candles[timestamp] = [
                    timestamp,
                    float(row["open"]),
                    float(row["high"]),
                    float(row["low"]),
                    float(row["close"]),
                    float(row["volume"])
                ]
            except (ValueError, KeyError, TypeError):
                continue

    print(
        f"Loaded existing {symbol}: {len(candles)} candles",
        flush=True
    )

    return candles


def save_csv(symbol, timeframe, candles):
    short_symbol = symbol.replace("USDT", "")
    path = f"{DATA_DIR}/{short_symbol}_{timeframe}m.csv"

    with open(path, "w", newline="") as file:
        writer = csv.writer(file)

        writer.writerow([
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume"
        ])

        writer.writerows(candles)

    print(
        f"Saved {path}: {len(candles)} candles",
        flush=True
    )


def aggregate_candles(one_minute, timeframe):
    result = {}

    for candle in one_minute:
        timestamp, op, hi, lo, cl, vol = candle

        bucket = (
            timestamp // (timeframe * 60)
        ) * (timeframe * 60)

        if bucket not in result:
            result[bucket] = [
                bucket, op, hi, lo, cl, vol
            ]
        else:
            item = result[bucket]
            item[2] = max(item[2], hi)
            item[3] = min(item[3], lo)
            item[4] = cl
            item[5] += vol

    return [result[key] for key in sorted(result)]


def collect_symbol(symbol):
    print(f"\nCollecting {symbol}", flush=True)

    candles = load_existing(symbol)

    now = datetime.now(timezone.utc)
    current_minute = int(now.timestamp() // 60) * 60

    end_ms = current_minute * 1000 - 1

    target_start = int(
        (now - timedelta(days=DAYS_TO_COLLECT)).timestamp()
    )

    requests = 0

    while requests < MAX_REQUESTS_PER_SYMBOL:
        batch = request_klines(symbol, end_ms)

        if not batch:
            break

        oldest_timestamp = None
        new_count = 0

        for item in batch:
            timestamp = int(item[0]) // 1000

            if timestamp >= current_minute:
                continue

            if timestamp < target_start:
                continue

            if timestamp not in candles:
                new_count += 1

            candles[timestamp] = [
                timestamp,
                float(item[1]),
                float(item[2]),
                float(item[3]),
                float(item[4]),
                float(item[5])
            ]

        oldest_timestamp = min(
            int(item[0]) for item in batch
        )

        requests += 1

        print(
            f"{symbol}: request {requests}, "
            f"new={new_count}, total={len(candles)}",
            flush=True
        )

        if oldest_timestamp // 1000 <= target_start:
            break

        end_ms = oldest_timestamp - 1

        time.sleep(0.2)

    one_minute = [
        candles[key]
        for key in sorted(candles)
        if target_start <= key < current_minute
    ]

    if not one_minute:
        raise RuntimeError(f"No data collected for {symbol}")

    save_csv(symbol, 1, one_minute)

    for timeframe in [5, 15]:
        aggregated = aggregate_candles(
            one_minute,
            timeframe
        )

        save_csv(symbol, timeframe, aggregated)

    print(
        f"{symbol} completed: {len(one_minute)} 1m candles",
        flush=True
    )


def main():
    print("SPACE BAR AI HISTORY V6.0", flush=True)

    failures = []

    for symbol in SYMBOLS:
        try:
            collect_symbol(symbol)
        except Exception as error:
            print(
                f"ERROR {symbol}: {error}",
                flush=True
            )
            failures.append(symbol)

    if failures:
        raise RuntimeError(
            "History collection failed: "
            + ", ".join(failures)
        )

    print("\nHistory collection completed!", flush=True)


if __name__ == "__main__":
    main()
