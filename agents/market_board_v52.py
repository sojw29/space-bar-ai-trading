"""V52 read-only completed BTCUSDT 5m market chart contract.

Market-board data is validated but never used to place orders.
"""
import math
import time

FIELDS = ("open","high","low","close","volume")

def market_board(rows, *, realtime, source, now=None):
    if not isinstance(rows, (tuple,list)) or not 1 <= len(rows) <= 80:
        raise ValueError("Market chart requires 1..80 bars")
    if not isinstance(realtime,bool) or source not in (
        "historical_csv_snapshot","public_binance_usdm_ws"):
        raise ValueError("Unknown market data provenance")
    if realtime != (source == "public_binance_usdm_ws"):
        raise ValueError("Inconsistent market source")
    current = float(time.time() if now is None else now)
    if not math.isfinite(current): raise ValueError("Invalid local clock")
    cleaned=[]
    for bar in rows:
        if not isinstance(bar,dict): raise ValueError("Invalid candle")
        ts=bar.get("timestamp")
        if isinstance(ts,bool) or not isinstance(ts,int) or ts<0 or ts%300:
            raise ValueError("Invalid timestamp")
        if cleaned and ts != cleaned[-1]["timestamp"]+300:
            raise ValueError("Gapped, duplicated or unordered chart")
        if ts+300>current: raise ValueError("Chart includes unclosed candle")
        try: data={key:float(bar[key]) for key in FIELDS}
        except (TypeError,ValueError,KeyError,OverflowError) as exc:
            raise ValueError("Invalid price or volume") from exc
        o,h,l,c,v=(data[key] for key in FIELDS)
        if (not all(math.isfinite(n) for n in data.values()) or
            min(o,h,l,c)<=0 or h<max(o,c) or l>min(o,c) or v<0):
            raise ValueError("Invalid candle OHLCV")
        cleaned.append({"timestamp":ts,**data})
    if realtime and not 0<=current-(cleaned[-1]["timestamp"]+300)<=420:
        raise ValueError("Live chart too old")
    return {
        "schema_version":"52.0","mode":"COMPLETED_CANDLE_MARKET_BOARD",
        "symbol":"BTCUSDT","timeframe":"5m",
        "source":source,"realtime":realtime,
        "candles":cleaned[-60:],
        "last_closed_timestamp":cleaned[-1]["timestamp"],
        "paper_only":True,"orders_enabled":False,
        "live_trading_approved":False,"independent_oos_verified":False,
    }
