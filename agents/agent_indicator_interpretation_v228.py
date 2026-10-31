"""V228 deterministic agent-labeled indicator interpretations; not AI inference."""
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

SYMBOLS=("BTCUSDT","ETHUSDT","SOLUSDT")
def interpret(snapshot, now=None):
    now=now or datetime.now(timezone.utc)
    if (not isinstance(snapshot,dict) or snapshot.get("version")!="V225.0"
        or snapshot.get("research_only") is not True or snapshot.get("orders_enabled") is not False
        or snapshot.get("realtime") is not False or snapshot.get("trade_signals_available") is not False
        or snapshot.get("ai_agents_running") is not False):
        raise ValueError("UNSAFE_INDICATOR_SNAPSHOT")
    generated=datetime.fromisoformat(snapshot["generated_at_utc"].replace("Z","+00:00"))
    if generated.tzinfo is None or not 0<=(now-generated).total_seconds()<=8*3600:
        raise ValueError("STALE_INDICATORS")
    markets=snapshot.get("markets")
    if not isinstance(markets,list) or len(markets)!=3:
        raise ValueError("MISSING_INDICATORS")
    out=[]
    for symbol in SYMBOLS:
        matches=[m for m in markets if isinstance(m,dict) and m.get("symbol")==symbol]
        if len(matches)!=1:raise ValueError("DUPLICATE_OR_MISSING_SYMBOL")
        m=matches[0]
        for key in ("close","sma50","sma200","volume20","volume_latest"):
            v=m.get(key)
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0:
                raise ValueError("INVALID_INDICATOR_VALUE")
        if min(m["close"],m["sma50"],m["sma200"])<=0:raise ValueError("INVALID_PRICE")
        label=("SMA50_ABOVE_SMA200" if m["sma50"]>m["sma200"] else
               "SMA50_BELOW_SMA200" if m["sma50"]<m["sma200"] else "SMA_EQUAL")
        if m.get("trend_label")!=label:raise ValueError("INCONSISTENT_TREND_LABEL")
        ratio=m["volume_latest"]/m["volume20"] if m["volume20"]>0 else None
        out.append({"symbol":symbol,"ATLAS":{"sma_relationship":label,
            "interpretation":"50-period mean above 200-period mean" if label=="SMA50_ABOVE_SMA200" else
                "50-period mean below 200-period mean" if label=="SMA50_BELOW_SMA200" else "moving averages equal"},
            "QUANT":{"volume_ratio_20":round(ratio,4) if ratio is not None else None,
                     "status":"DESCRIPTIVE_ONLY_NO_BACKTEST"},
            "GUARDIAN":{"status":"NO_TRADE_AUTHORIZATION","orders_enabled":False}})
    return {"version":"V228.0","generated_at_utc":now.isoformat(),
            "source_generated_at_utc":snapshot["generated_at_utc"],
            "research_only":True,"orders_enabled":False,"realtime":False,
            "ai_agents_running":False,"trade_signals_available":False,
            "analysis_type":"DETERMINISTIC_INDICATOR_DESCRIPTION","markets":out}
if __name__=="__main__":
    source=Path(sys.argv[1]);target=Path(sys.argv[2])
    result=interpret(json.loads(source.read_text(encoding="utf-8")))
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),encoding="utf-8")
