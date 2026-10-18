import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen

SYMBOLS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
}

BASE_URL = "https://api.bybit.com"


def get_market_price(symbol):
    url = (
        f"{BASE_URL}/v5/market/tickers"
        f"?category=linear&symbol={symbol}"
    )

    request = Request(
        url,
        headers={"User-Agent": "SpaceBarAI/1.0"}
    )

    with urlopen(request, timeout=10) as response:
        data = json.load(response)

    if data.get("retCode") != 0:
        raise RuntimeError(data.get("retMsg", "API 오류"))

    items = data.get("result", {}).get("list", [])

    if not items:
        raise RuntimeError("가격 데이터가 없습니다.")

    return float(items[0]["lastPrice"])


def analyze_market():
    print("\n===== ATLAS MARKET REPORT =====")

    print(
        "UTC:",
        datetime.now(timezone.utc).isoformat()
    )

    results = {}

    for coin, symbol in SYMBOLS.items():
        try:
            price = get_market_price(symbol)
            results[coin] = price
            print(f"{coin}: {price:,.4f} USDT")

        except Exception as error:
            print(f"{coin}: 데이터 수집 실패 - {error}")

    print("================================")

    return results


if __name__ == "__main__":
    analyze_market()
