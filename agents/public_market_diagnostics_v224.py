"""V224 deterministic public ticker diagnostics; not AI decisions or trade signals."""
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

SYMBOLS=("BTCUSDT","ETHUSDT","SOLUSDT")
MAX_AGE_SECONDS=8*3600

def assess(snapshot, now=None):
    now=now or datetime.now(timezone.utc)
    if (not isinstance(snapshot,dict) or snapshot.get("version")!="V223.0"
        or snapshot.get("research_only") is not True
        or snapshot.get("orders_enabled") is not False
        or snapshot.get("realtime") is not False
        or snapshot.get("agent_analysis_available") is not False):
        raise ValueError("UNTRUSTED_MARKET_SNAPSHOT")
    stamp=datetime.fromisoformat(snapshot["captured_at_utc"].replace("Z","+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("NAIVE_TIMESTAMP")
    age=(now-stamp).total_seconds()
    if not 0<=age<=MAX_AGE_SECONDS:
        raise ValueError("STALE_OR_FUTURE_MARKET_SNAPSHOT")
    markets=snapshot.get("markets")
    if not isinstance(markets,list) or len(markets)!=len(SYMBOLS):
        raise ValueError("INCOMPLETE_MARKET_SNAPSHOT")
    by_symbol={}
    for row in markets:
        if not isinstance(row,dict) or row.get("symbol") not in SYMBOLS or row["symbol"] in by_symbol:
            raise ValueError("DUPLICATE_OR_UNKNOWN_SYMBOL")
        price=row.get("last_price"); volume=row.get("volume_24h")
        if (isinstance(price,bool) or not isinstance(price,(int,float))
            or not math.isfinite(price) or not 0<price<1e12
            or isinstance(volume,bool) or not isinstance(volume,(int,float))
            or not math.isfinite(volume) or not 0<=volume<1e15):
            raise ValueError("INVALID_MARKET_METRIC")
        by_symbol[row["symbol"]]=row
    if set(by_symbol)!=set(SYMBOLS):
        raise ValueError("MISSING_SYMBOL")
    return {"version":"V224.0","captured_at_utc":snapshot["captured_at_utc"],
        "assessed_at_utc":now.isoformat(),"source":"V223 public ticker snapshot",
        "research_only":True,"orders_enabled":False,"realtime":False,
        "ai_agents_running":False,"trade_signals_available":False,
        "ATLAS":{"status":"DATA_PRESENT","note":"Three public ticker prices only; no trend or prediction."},
        "QUANT":{"status":"INSUFFICIENT_HISTORY","note":"One ticker snapshot cannot validate a strategy."},
        "GUARDIAN":{"status":"NO_TRADE_AUTHORIZATION","note":"No orders; snapshot is delayed and not a risk model."},
        "symbols":list(SYMBOLS)}

def publish(source, destination, now=None):
    """Fail closed: never leave a previous public diagnostic after invalid input."""
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError("DIAGNOSTIC_SOURCE_DESTINATION_SAME")
    destination.unlink(missing_ok=True)
    data = assess(json.loads(source.read_text(encoding="utf-8")), now=now)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(data, ensure_ascii=False, allow_nan=False), encoding="utf-8"
    )
    return data


if __name__=="__main__":
    publish(sys.argv[1], sys.argv[2])
