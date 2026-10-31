"""V223 read-only public market snapshot, no orders or agent decisions."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

SYMBOLS=("BTCUSDT","ETHUSDT","SOLUSDT")
ENDPOINT="https://api.bybit.com/v5/market/tickers?category=linear&symbol="
def build(fetch=None):
    if fetch is None:
        def fetch(symbol):
            req=Request(ENDPOINT+symbol,headers={"User-Agent":"SPACE-BAR-Research/1.0"})
            with urlopen(req,timeout=12) as response:
                return json.load(response)
    rows=[]
    for symbol in SYMBOLS:
        response=fetch(symbol)
        if not isinstance(response,dict) or response.get("retCode")!=0:
            raise ValueError("PUBLIC_MARKET_FEED_UNAVAILABLE")
        entries=response.get("result",{}).get("list",[])
        if len(entries)!=1 or entries[0].get("symbol")!=symbol:
            raise ValueError("PUBLIC_MARKET_SYMBOL_MISMATCH")
        item=entries[0]
        price=float(item["lastPrice"])
        volume=float(item["volume24h"])
        if not (0<price<1e12 and 0<=volume<1e15):
            raise ValueError("INVALID_MARKET_VALUE")
        rows.append({"symbol":symbol,"last_price":price,"volume_24h":volume})
    return {"version":"V223.0","source":"Bybit public linear ticker API",
            "captured_at_utc":datetime.now(timezone.utc).isoformat(),
            "research_only":True,"orders_enabled":False,
            "realtime":False,"agent_analysis_available":False,"markets":rows}
if __name__=="__main__":
    result=build()
    target=Path(sys.argv[1])
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),encoding="utf-8")
