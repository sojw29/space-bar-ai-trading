"""V222 opt-in public historical scorecard staging; never generates data or orders."""
import json
import sys
from pathlib import Path

MAX_BYTES=2_000_000

def stage(source, destination):
    source,destination=Path(source),Path(destination)
    if not source.is_file():
        destination.unlink(missing_ok=True)
        return False
    if source.stat().st_size>MAX_BYTES:
        raise ValueError("SNAPSHOT_TOO_LARGE")
    data=json.loads(source.read_text(encoding="utf-8"))
    card=data.get("strategy_scorecard") if isinstance(data,dict) else None
    provenance=data.get("snapshot_provenance") if isinstance(data,dict) else None
    if (data.get("version")!="V105.0" or data.get("research_only") is not True
        or data.get("orders_enabled") is not False
        or data.get("live_trading_approved") is not False
        or not isinstance(card,dict)
        or card.get("version")!="V197.0"
        or card.get("status")!="RESEARCH_COMPARISON_ONLY"
        or card.get("research_only") is not True
        or card.get("ranking_enabled") is not False
        or card.get("strategy_selection_enabled") is not False
        or card.get("orders_allowed") is not False
        or card.get("live_trading_approved") is not False
        or not isinstance(card.get("rows"),list)
        or not 1<=len(card["rows"])<=30
        or not isinstance(provenance,dict)
        or provenance.get("source_type")!="LOCAL_HISTORICAL_CSV_FROZEN_COPY"
        or provenance.get("realtime") is not False
        or provenance.get("research_only") is not True
        or provenance.get("data_authenticity_verified") is not False):
        raise ValueError("UNSAFE_OR_UNPROVEN_RESEARCH_SNAPSHOT")
    raw=json.dumps(data,ensure_ascii=False,allow_nan=False).encode("utf-8")
    if len(raw)>MAX_BYTES:
        raise ValueError("SNAPSHOT_TOO_LARGE")
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_bytes(raw)
    return True

if __name__=="__main__":
    print("historical_snapshot_staged="+str(stage(sys.argv[1],sys.argv[2])).lower())
