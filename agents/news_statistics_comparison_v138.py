"""V138 descriptive comparison of article-level and heuristic cluster-adjusted news stats.

Only differences in supplied aggregates are reported. No causal attribution,
independence proof, news-time validation, or trading recommendations.
"""
import argparse
import json
import math
from pathlib import Path

HORIZONS=("5m","15m","60m")
METRICS=("mean_return_pct","median_return_pct","mean_absolute_move_pct",
         "positive_observation_rate_pct")

def _finite(value):
    return type(value) in (int,float) and math.isfinite(value)

def compare(article_stats,adjusted_stats):
    if not isinstance(article_stats,dict) or article_stats.get("version")!="V130.0":
        raise ValueError("INVALID_ARTICLE_STATISTICS")
    if not isinstance(adjusted_stats,dict) or adjusted_stats.get("version")!="V137.0":
        raise ValueError("INVALID_ADJUSTED_STATISTICS")
    def index(stats):
        groups=stats.get("categories")
        if not isinstance(groups,list) or len(groups)>100:
            raise ValueError("INVALID_CATEGORIES")
        out={}
        for item in groups:
            if not isinstance(item,dict) or not isinstance(item.get("category"),str) or not isinstance(item.get("horizons"),dict):
                raise ValueError("INVALID_CATEGORY")
            name=item["category"]
            if name in out:
                raise ValueError("DUPLICATE_CATEGORY")
            out[name]=item["horizons"]
        return out
    before=index(article_stats)
    after=index(adjusted_stats)
    rows=[]
    for category in sorted(set(before)|set(after)):
        for horizon in HORIZONS:
            old=before.get(category,{}).get(horizon,{})
            new=after.get(category,{}).get(horizon,{})
            if not isinstance(old,dict) or not isinstance(new,dict):
                raise ValueError("INVALID_HORIZON")
            old_count=old.get("samples",0)
            new_count=new.get("samples",0)
            if type(old_count) is not int or type(new_count) is not int or min(old_count,new_count)<0:
                raise ValueError("INVALID_SAMPLE_COUNT")
            if new_count>old_count:
                raise ValueError("ADJUSTED_SAMPLE_COUNT_EXCEEDS_ARTICLE_COUNT")
            changes={}
            for metric in METRICS:
                a,b=old.get(metric),new.get(metric)
                if a is not None and not _finite(a) or b is not None and not _finite(b):
                    raise ValueError("INVALID_METRIC")
                changes[metric]=round(b-a,8) if a is not None and b is not None else None
            rows.append({"category":category,"horizon":horizon,
                         "article_samples":old_count,"cluster_adjusted_samples":new_count,
                         "potentially_repeated_samples_removed":old_count-new_count,
                         "changes":changes,
                         "metrics_comparable":all(v is not None for v in changes.values())})
    return {"version":"V138.0","status":"DESCRIPTIVE_ARTICLE_VS_HEURISTIC_CLUSTER_COMPARISON",
            "article_count":article_stats.get("matched_articles"),
            "cluster_count":adjusted_stats.get("heuristic_cluster_count"),
            "rows":rows,"rows_with_all_metrics":sum(x["metrics_comparable"] for x in rows),
            "same_input_provenance_verified":False,
            "real_world_event_identity_verified":False,
            "causal_effect_established":False,"validated_edge":False,
            "research_only":True,"simulation_only":True,"exchange_connected":False,
            "orders_submitted_to_exchange":0,"live_trading_approved":False,
            "limitations":"Comparison assumes both inputs describe the same source snapshot, but provenance is not cryptographically verified. Deltas are descriptive percentage-point differences, not causal corrections or trading signals."}

def main():
    p=argparse.ArgumentParser(description="V138 offline article vs cluster-adjusted statistics")
    p.add_argument("v130_article_statistics_json",type=Path)
    p.add_argument("v137_adjusted_statistics_json",type=Path)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    inputs=[]
    for path in (args.v130_article_statistics_json,args.v137_adjusted_statistics_json):
        if path.stat().st_size>4_000_000:
            raise ValueError("INPUT_TOO_LARGE")
        inputs.append(json.loads(path.read_text(encoding="utf-8")))
    result=compare(*inputs)
    output=json.dumps(result,indent=2,ensure_ascii=False)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(output,encoding="utf-8")
    else:
        print(output,end="")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
