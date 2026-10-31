"""V225 public OHLCV indicator snapshot; historical, research-only, no orders."""
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SYMBOLS=("BTCUSDT","ETHUSDT","SOLUSDT")
API="https://api.bybit.com/v5/market/kline?"
def indicators(symbol, fetch=None):
    if fetch is None:
        def fetch(s):
            query=urlencode({"category":"linear","symbol":s,"interval":"5","limit":"220"})
            with urlopen(Request(API+query,headers={"User-Agent":"SPACE-BAR-Research/1.0"}),timeout=15) as response:
                return json.load(response)
    response=fetch(symbol)
    if not isinstance(response,dict) or response.get("retCode")!=0:
        raise ValueError("OHLCV_SOURCE_UNAVAILABLE")
    rows=response.get("result",{}).get("list",[])
    if not isinstance(rows,list) or len(rows)<202:
        raise ValueError("INSUFFICIENT_OHLCV")
    bars=[]
    for row in rows:
        if not isinstance(row,list) or len(row)<6:
            raise ValueError("INVALID_OHLCV_ROW")
        ts=int(row[0]); o,h,l,c,v=map(float,row[1:6])
        if (not all(math.isfinite(x) for x in (o,h,l,c,v)) or
            min(o,h,l,c)<=0 or v<0 or h<max(o,c,l) or l>min(o,c,h)):
            raise ValueError("INVALID_OHLCV_VALUE")
        bars.append((ts,c,v))
    bars.sort(key=lambda x:x[0])
    if len(set(x[0] for x in bars))!=len(bars):
        raise ValueError("DUPLICATE_CANDLE")
    if any(bars[i+1][0]-bars[i][0]!=300000 for i in range(len(bars)-1)):
        raise ValueError("NON_CONTIGUOUS_CANDLES")
    now_ms=int(datetime.now(timezone.utc).timestamp()*1000)
    completed=[x for x in bars if x[0]+300000<=now_ms]
    if len(completed)<200 or now_ms-(completed[-1][0]+300000)>3600000:
        raise ValueError("STALE_OR_INSUFFICIENT_CANDLES")
    closes=[x[1] for x in completed];volumes=[x[2] for x in completed]
    sma50=sum(closes[-50:])/50
    sma200=sum(closes[-200:])/200
    volume20=sum(volumes[-20:])/20
    return {"symbol":symbol,"last_completed_candle_utc":datetime.fromtimestamp(
        completed[-1][0]/1000,timezone.utc).isoformat(),
        "close":round(closes[-1],8),"sma50":round(sma50,8),
        "sma200":round(sma200,8),"volume20":round(volume20,8),
        "volume_latest":round(volumes[-1],8),
        "trend_label":"SMA50_ABOVE_SMA200" if sma50>sma200 else
            "SMA50_BELOW_SMA200" if sma50<sma200 else "SMA_EQUAL"}
def build(fetch=None):
    return {"version":"V225.0","source":"Bybit public linear 5m historical OHLCV",
            "generated_at_utc":datetime.now(timezone.utc).isoformat(),
            "research_only":True,"orders_enabled":False,"realtime":False,
            "trade_signals_available":False,"ai_agents_running":False,
            "markets":[indicators(s,fetch) for s in SYMBOLS]}
if __name__=="__main__":
    output=Path(sys.argv[1]);result=build()
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),encoding="utf-8")
