"""V225 public OHLCV indicator snapshot; historical, research-only, no orders."""
import json
import argparse
import math
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from market_source_provenance import SOURCES, validate_candle_batch

SYMBOLS=("BTCUSDT","ETHUSDT","SOLUSDT")
API="https://api.bybit.com/v5/market/kline?"
PROVIDERS = {'bybit': 'BYBIT_USDT_PERPETUAL_5M', 'okx': 'OKX_USDT_PERPETUAL_5M'}

def fetch_public(symbol, provider):
    if symbol not in SYMBOLS or provider not in PROVIDERS:
        raise ValueError('UNSUPPORTED_MARKET_SOURCE')
    if provider == 'bybit':
        url = API+urlencode({'category':'linear','symbol':symbol,'interval':'5','limit':'220'})
    else:
        instrument = symbol.removesuffix('USDT')+'-USDT-SWAP'
        url = 'https://www.okx.com/api/v5/market/candles?'+urlencode({'instId':instrument,'bar':'5m','limit':'220'})
    with urlopen(Request(url,headers={'User-Agent':'SPACE-BAR-Research/1.0'}),timeout=15) as response:
        raw = response.read(262145)
    if len(raw)>262144: raise ValueError('OHLCV_RESPONSE_TOO_LARGE')
    return json.loads(raw)

def indicators(symbol, fetch=None, *, provider='bybit', now=None):
    if provider not in PROVIDERS or symbol not in SYMBOLS:
        raise ValueError('UNSUPPORTED_MARKET_SOURCE')
    if fetch is None:
        fetch = lambda s: fetch_public(s, provider)
    response=fetch(symbol)
    if not isinstance(response,dict):
        raise ValueError("OHLCV_SOURCE_UNAVAILABLE")
    if provider == 'bybit':
        if response.get('retCode') != 0: raise ValueError('OHLCV_SOURCE_UNAVAILABLE')
        rows=response.get('result',{}).get('list',[])
    else:
        if response.get('code') != '0': raise ValueError('OHLCV_SOURCE_UNAVAILABLE')
        rows=response.get('data',[])
        if not isinstance(rows,list): raise ValueError('INVALID_OHLCV_ROW')
        converted=[]
        for row in rows:
            if not isinstance(row,list) or len(row)!=9 or row[8] not in ('0','1'):
                raise ValueError('INVALID_OKX_CANDLE')
            # vol is contracts for swaps; volCcy is base-asset volume, matching Bybit units.
            if row[8]=='1': converted.append(row[:5]+[row[6]])
        rows=converted
    if not isinstance(rows,list) or len(rows)<202:
        raise ValueError("INSUFFICIENT_OHLCV")
    bars=[]
    for row in rows:
        if not isinstance(row,list) or len(row)<6:
            raise ValueError("INVALID_OHLCV_ROW")
        stamp = row[0]
        if type(stamp) not in (int, str) or (isinstance(stamp,str) and (not stamp.isascii() or not stamp.isdigit())):
            raise ValueError('INVALID_CANDLE_TIMESTAMP')
        ts=int(stamp)
        if ts<=0 or ts%300000!=0:
            raise ValueError('INVALID_CANDLE_TIMESTAMP')
        o,h,l,c,v=map(float,row[1:6])
        if (not all(math.isfinite(x) for x in (o,h,l,c,v)) or
            min(o,h,l,c)<=0 or v<0 or h<max(o,c,l) or l>min(o,c,h)):
            raise ValueError("INVALID_OHLCV_VALUE")
        bars.append((ts,c,v))
    bars.sort(key=lambda x:x[0])
    if len(set(x[0] for x in bars))!=len(bars):
        raise ValueError("DUPLICATE_CANDLE")
    if any(bars[i+1][0]-bars[i][0]!=300000 for i in range(len(bars)-1)):
        raise ValueError("NON_CONTIGUOUS_CANDLES")
    cutoff = now or datetime.now(timezone.utc)
    if cutoff.tzinfo is None: raise ValueError('NAIVE_CANDLE_CUTOFF')
    now_ms=int(cutoff.timestamp()*1000)
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
def build(fetch=None, *, provider='bybit'):
    if provider not in PROVIDERS: raise ValueError('UNSUPPORTED_MARKET_SOURCE')
    started=datetime.now(timezone.utc)
    markets=[indicators(s,fetch,provider=provider,now=started) for s in SYMBOLS]
    finished=datetime.now(timezone.utc)
    if finished<started:
        raise ValueError('COLLECTION_CLOCK_MOVED_BACKWARD')
    validate_candle_batch(markets, finished)
    return {"version":"V225.0","source":SOURCES[PROVIDERS[provider]],"market_source":PROVIDERS[provider],
            "generated_at_utc":finished.isoformat(),
            "research_only":True,"orders_enabled":False,"realtime":False,
            "trade_signals_available":False,"ai_agents_running":False,
            "markets":markets}
def publish(target, fetch=None, *, provider='bybit'):
    """Replace complete snapshots atomically; discard stale output on feed failure."""
    target = Path(target)
    temporary = None
    try:
        result = build(fetch, provider=provider)
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent,
            prefix=f".{target.name}.", suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(result, handle, ensure_ascii=False, allow_nan=False)
        os.replace(temporary, target)
        return result
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument('destination')
    parser.add_argument('--provider',choices=tuple(PROVIDERS),default='bybit')
    args=parser.parse_args()
    try:
        publish(args.destination,provider=args.provider)
    except HTTPError as error:
        parser.exit(1,'Public OHLCV collection failed for '+args.provider+' (HTTP '+str(error.code)+'); no indicator snapshot published.\n')
    except Exception:
        parser.exit(1,'Public OHLCV collection failed for '+args.provider+'; no indicator snapshot published.\n')
