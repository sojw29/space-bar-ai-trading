"""V125 conservative offline performance-drift warnings from V124 history.

Only descriptive snapshot deltas; no trading decisions, online monitoring,
automatic strategy changes or claim of comparable experiments.
"""
import argparse
import json
import math
from pathlib import Path

from report_history_v124 import METRICS

def _number(value, key):
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value):
        raise ValueError("INVALID_"+key.upper())
    return float(value)

def detect(history, return_drop_pp=2.0, drawdown_increase_pp=3.0,
           positive_rate_drop_pp=15.0, min_evaluated_folds=5):
    if (not isinstance(history,list) or len(history)>100 or
            any(not isinstance(x,dict) for x in history)):
        raise ValueError("INVALID_HISTORY")
    if type(min_evaluated_folds) is not int or min_evaluated_folds<1:
        raise ValueError("INVALID_MIN_FOLDS")
    thresholds={
        "return_drop_pp":_number(return_drop_pp,"RETURN_DROP_THRESHOLD"),
        "drawdown_increase_pp":_number(drawdown_increase_pp,"DRAWDOWN_THRESHOLD"),
        "positive_rate_drop_pp":_number(positive_rate_drop_pp,"POSITIVE_RATE_THRESHOLD"),
    }
    if any(v<=0 or v>100 for v in thresholds.values()):
        raise ValueError("INVALID_THRESHOLDS")
    warnings=[]
    def warn(code, detail):
        warnings.append({"code":code,"detail":detail})
    if len(history)<2:
        warn("INSUFFICIENT_HISTORY","At least two report snapshots are required.")
        changes=None
    else:
        prev,current=history[-2:]
        if not isinstance(prev.get("metrics"),dict) or not isinstance(current.get("metrics"),dict):
            raise ValueError("INVALID_HISTORY_METRICS")
        a,b=prev["metrics"],current["metrics"]
        changes={}
        for key in METRICS:
            x,y=a.get(key),b.get(key)
            if x is None or y is None:
                changes[key]=None
            else:
                changes[key]=round(_number(y,key)-_number(x,key),8)
        old_folds=a.get("evaluated_folds")
        new_folds=b.get("evaluated_folds")
        if (type(old_folds) is not int or type(new_folds) is not int or
                old_folds<0 or new_folds<0):
            raise ValueError("INVALID_FOLD_COUNTS")
        if min(old_folds,new_folds)<min_evaluated_folds:
            warn("INSUFFICIENT_FOLDS","One or both snapshots have too few evaluated folds.")
        if changes["mean_fold_return_pct"] is not None and changes["mean_fold_return_pct"]<=-thresholds["return_drop_pp"]:
            warn("MEAN_FOLD_RETURN_DETERIORATION","Mean hypothetical fold return fell by configured threshold.")
        if changes["worst_fold_max_drawdown_pct"] is not None and changes["worst_fold_max_drawdown_pct"]>=thresholds["drawdown_increase_pp"]:
            warn("DRAWDOWN_DETERIORATION","Worst sampled fold drawdown rose by configured threshold.")
        if changes["positive_fold_rate_pct"] is not None and changes["positive_fold_rate_pct"]<=-thresholds["positive_rate_drop_pp"]:
            warn("POSITIVE_FOLD_RATE_DETERIORATION","Positive fold rate fell by configured threshold.")
        if prev.get("report_sha256")==current.get("report_sha256"):
            warn("SAME_REPORT_RECORDED","Latest snapshots refer to the same report contents.")
    return {"version":"V125.0","status":"DESCRIPTIVE_OFFLINE_DRIFT_WARNINGS",
            "snapshots_seen":len(history),"changes":changes,
            "warning_count":len(warnings),"warnings":warnings,
            "performance_drift_proven":False,
            "comparable_configuration_verified":False,
            "automatic_strategy_changes":False,
            "research_only":True,"simulation_only":True,
            "exchange_connected":False,"orders_submitted_to_exchange":0,
            "live_trading_approved":False,"validated_edge":False,
            "limitations":"Only compares latest two summary snapshots. Different datasets, parameters, regimes or periods can explain differences. Thresholds are heuristics, not statistically validated change detection. No live monitoring."}

def run(path,**kwargs):
    path=Path(path)
    if path.stat().st_size>2_000_000:
        raise ValueError("HISTORY_TOO_LARGE")
    try:
        history=json.loads(path.read_text(encoding="utf-8"))
    except (ValueError,UnicodeError) as exc:
        raise ValueError("INVALID_HISTORY") from exc
    return detect(history,**kwargs)

def main():
    parser=argparse.ArgumentParser(description="V125 offline performance change warnings")
    parser.add_argument("history_json")
    parser.add_argument("--return-drop-pp",type=float,default=2.0)
    parser.add_argument("--drawdown-increase-pp",type=float,default=3.0)
    parser.add_argument("--positive-rate-drop-pp",type=float,default=15.0)
    args=parser.parse_args()
    print(json.dumps(run(args.history_json,return_drop_pp=args.return_drop_pp,
                         drawdown_increase_pp=args.drawdown_increase_pp,
                         positive_rate_drop_pp=args.positive_rate_drop_pp),indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
