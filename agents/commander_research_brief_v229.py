"""V229 deterministic COMMANDER research briefing; no AI, orders or recommendations."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SYMBOLS=("BTCUSDT","ETHUSDT","SOLUSDT")
RELATIONS=("SMA50_ABOVE_SMA200","SMA50_BELOW_SMA200","SMA_EQUAL")
def summarize(data,now=None):
    now=now or datetime.now(timezone.utc)
    if (not isinstance(data,dict) or data.get("version")!="V228.0"
        or data.get("analysis_type")!="DETERMINISTIC_INDICATOR_DESCRIPTION"
        or data.get("research_only") is not True or data.get("orders_enabled") is not False
        or data.get("realtime") is not False or data.get("ai_agents_running") is not False
        or data.get("trade_signals_available") is not False):
        raise ValueError("UNTRUSTED_RESEARCH")
    ts=datetime.fromisoformat(data["source_generated_at_utc"].replace("Z","+00:00"))
    if ts.tzinfo is None or not 0<=(now-ts).total_seconds()<=8*3600:
        raise ValueError("STALE_RESEARCH")
    markets=data.get("markets")
    if not isinstance(markets,list) or len(markets)!=3:raise ValueError("INCOMPLETE_RESEARCH")
    summary=[]
    for symbol in SYMBOLS:
        matches=[x for x in markets if isinstance(x,dict) and x.get("symbol")==symbol]
        if len(matches)!=1:raise ValueError("DUPLICATE_OR_MISSING_SYMBOL")
        item=matches[0];atlas=item.get("ATLAS");quant=item.get("QUANT");guardian=item.get("GUARDIAN")
        if not isinstance(atlas,dict) or atlas.get("sma_relationship") not in RELATIONS:
            raise ValueError("BAD_ATLAS")
        if not isinstance(quant,dict) or quant.get("status")!="DESCRIPTIVE_ONLY_NO_BACKTEST":
            raise ValueError("BAD_QUANT")
        ratio=quant.get("volume_ratio_20")
        if ratio is not None and (isinstance(ratio,bool) or not isinstance(ratio,(int,float)) or not 0<=ratio<1e12):
            raise ValueError("BAD_VOLUME_RATIO")
        if not isinstance(guardian,dict) or guardian.get("status")!="NO_TRADE_AUTHORIZATION" or guardian.get("orders_enabled") is not False:
            raise ValueError("BAD_GUARDIAN")
        summary.append({"symbol":symbol,"trend_observation":atlas["sma_relationship"],
                        "volume_ratio_20":ratio,"risk_status":"NO_TRADE_AUTHORIZATION",
                        "research_conclusion":"DESCRIPTIVE_ONLY"})
    return {"version":"V229.0","report_type":"DETERMINISTIC_COMMANDER_RESEARCH_BRIEF",
            "generated_at_utc":now.isoformat(),"source_generated_at_utc":data["source_generated_at_utc"],
            "research_only":True,"orders_enabled":False,"realtime":False,
            "ai_agents_running":False,"trade_signals_available":False,
            "backtest_verified":False,"commander":{"status":"COMPILED_NOT_AI",
                "note":"Descriptive indicator aggregation only; no strategy validation or trade decision."},
            "markets":summary}
if __name__=="__main__":
    source=Path(sys.argv[1]);target=Path(sys.argv[2])
    report=summarize(json.loads(source.read_text(encoding="utf-8")))
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,allow_nan=False),encoding="utf-8")
