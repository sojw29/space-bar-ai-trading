"""V134 bounded, offline, append-only-by-replacement news research snapshots.

Tracks descriptive V132 category metrics across runs; no causal or trading
claims. Report IDs hash canonical content and preserve provenance.
"""
import argparse
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path

MAX_RECORDS=100
MAX_INPUT_BYTES=4_000_000
HORIZONS=("5m","15m","60m")
METRICS=("samples","mean_return_pct","median_return_pct",
         "mean_absolute_move_pct","positive_observation_rate_pct")

def _time(value):
    if not isinstance(value,str):
        raise ValueError("INVALID_RECORDED_AT")
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("INVALID_RECORDED_AT") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("INVALID_RECORDED_AT")
    return dt.astimezone(timezone.utc).isoformat()

def summarize(report):
    if not isinstance(report,dict) or report.get("version")!="V132.0":
        raise ValueError("INVALID_V132_REPORT")
    impact=report.get("impact")
    if not isinstance(impact,dict) or impact.get("version")!="V130.0" or not isinstance(impact.get("categories"),list):
        raise ValueError("INVALID_IMPACT")
    categories={}
    for group in impact["categories"]:
        if not isinstance(group,dict) or not isinstance(group.get("category"),str) or not isinstance(group.get("horizons"),dict):
            raise ValueError("INVALID_CATEGORY")
        category=group["category"]
        if category in categories:
            raise ValueError("DUPLICATE_CATEGORY")
        values={}
        for horizon in HORIZONS:
            row=group["horizons"].get(horizon,{})
            if not isinstance(row,dict):
                raise ValueError("INVALID_HORIZON")
            values[horizon]={metric:row.get(metric) for metric in METRICS}
        categories[category]=values
    return {"matched_articles":impact.get("matched_articles"),"categories":categories}

def record(report,history,recorded_at,label=""):
    when=_time(recorded_at)
    if not isinstance(label,str) or len(label)>120:
        raise ValueError("INVALID_LABEL")
    if not isinstance(history,list) or len(history)>MAX_RECORDS:
        raise ValueError("INVALID_HISTORY")
    snapshot=summarize(report)
    digest=hashlib.sha256(json.dumps(report,sort_keys=True,ensure_ascii=False,
        separators=(",",":"),allow_nan=False).encode("utf-8")).hexdigest()
    ids=[]
    for item in history:
        if not isinstance(item,dict) or not isinstance(item.get("report_sha256"),str):
            raise ValueError("INVALID_HISTORY_ENTRY")
        ids.append(item["report_sha256"])
    if len(set(ids))!=len(ids):
        raise ValueError("DUPLICATE_HISTORY_ENTRY")
    if digest in ids:
        return {"version":"V134.0","appended":False,"history":history,
                "comparison":compare(history),"research_only":True,
                "orders_submitted_to_exchange":0,"live_trading_approved":False}
    entry={"report_sha256":digest,"recorded_at_utc":when,"label":label,
           "summary":snapshot}
    updated=(history+[entry])[-MAX_RECORDS:]
    return {"version":"V134.0","appended":True,"history":updated,
            "comparison":compare(updated),"research_only":True,
            "orders_submitted_to_exchange":0,"live_trading_approved":False,
            "limitations":"Different datasets, time windows and news availability may not be comparable. Observed-time news is not proven tradable; descriptive changes are not predictive."}

def compare(history):
    if len(history)<2:
        return {"comparable":False,"reason":"NEED_TWO_DISTINCT_REPORTS"}
    older,newer=history[-2:]
    before=older.get("summary",{}).get("categories",{})
    after=newer.get("summary",{}).get("categories",{})
    shared=sorted(set(before)&set(after))
    changes=[]
    for category in shared:
        for horizon in HORIZONS:
            a=before[category].get(horizon,{})
            b=after[category].get(horizon,{})
            x,y=a.get("mean_return_pct"),b.get("mean_return_pct")
            if isinstance(x,(int,float)) and not isinstance(x,bool) and isinstance(y,(int,float)) and not isinstance(y,bool):
                changes.append({"category":category,"horizon":horizon,
                                "mean_return_change_percentage_points":round(y-x,8),
                                "old_samples":a.get("samples"),"new_samples":b.get("samples")})
    return {"comparable":False,"reason":"DATASET_AND_EVENT_OVERLAP_NOT_VERIFIED",
            "shared_categories":shared,"descriptive_changes_only":changes}

def main():
    p=argparse.ArgumentParser(description="V134 offline news research report history")
    p.add_argument("v132_report_json",type=Path)
    p.add_argument("history_json",type=Path)
    p.add_argument("--recorded-at",required=True)
    p.add_argument("--label",default="")
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    for path in (args.v132_report_json,args.history_json):
        if path.exists() and path.stat().st_size>MAX_INPUT_BYTES:
            raise ValueError("INPUT_TOO_LARGE")
    report=json.loads(args.v132_report_json.read_text(encoding="utf-8"))
    history=json.loads(args.history_json.read_text(encoding="utf-8")) if args.history_json.exists() else []
    result=record(report,history,args.recorded_at,args.label)
    encoded=json.dumps(result,indent=2,ensure_ascii=False)+"\n"
    destination=args.output or args.history_json
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(encoded,encoding="utf-8")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
