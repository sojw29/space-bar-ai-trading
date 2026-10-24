"""V137 descriptive news statistics with one representative per heuristic cluster.

Representative = earliest GDELT-observed article, ties by article ID.
The clustering heuristic is NOT proof of unique real-world event identity.
No tradable news timestamp, causal inference or order execution.
"""
import argparse
import json
import math
import statistics
from pathlib import Path

HORIZONS=("5m","15m","60m")

def _valid_number(value):
    return type(value) in (float,int) and math.isfinite(value)

def adjust(taxonomy,event_study,clusters,min_samples=5):
    if type(min_samples) is not int or min_samples<1:
        raise ValueError("INVALID_MIN_SAMPLES")
    if not isinstance(taxonomy,dict) or taxonomy.get("version")!="V128.0":
        raise ValueError("INVALID_TAXONOMY")
    if not isinstance(event_study,dict) or event_study.get("version")!="V129.0":
        raise ValueError("INVALID_EVENT_STUDY")
    if not isinstance(clusters,dict) or clusters.get("version")!="V136.0":
        raise ValueError("INVALID_CLUSTERS")
    articles=taxonomy.get("articles")
    events=event_study.get("events")
    groups=clusters.get("clusters")
    if not isinstance(articles,list) or not isinstance(events,list) or not isinstance(groups,list):
        raise ValueError("INVALID_INPUT_LISTS")
    if max(len(articles),len(events),len(groups))>100:
        raise ValueError("INPUT_TOO_LARGE")
    def indexed(rows):
        out={}
        for item in rows:
            if not isinstance(item,dict) or not isinstance(item.get("article_id"),str):
                raise ValueError("INVALID_ARTICLE_ID")
            aid=item["article_id"]
            if aid in out:
                raise ValueError("DUPLICATE_ARTICLE_ID")
            out[aid]=item
        return out
    classified=indexed(articles)
    studied=indexed(events)
    if set(classified)!=set(studied):
        raise ValueError("ARTICLE_EVENT_MISMATCH")
    representatives=[]
    covered=set()
    for group in groups:
        if not isinstance(group,dict) or not isinstance(group.get("article_ids"),list) or not group["article_ids"]:
            raise ValueError("INVALID_CLUSTER")
        ids=group["article_ids"]
        if any(not isinstance(aid,str) or aid not in classified or aid in covered for aid in ids):
            raise ValueError("INVALID_CLUSTER_MEMBERSHIP")
        covered.update(ids)
        # V136 emits earliest seen time ordering, but only IDs in the cluster.
        # V129 events carry the same GDELT observation timestamps.
        def key(aid):
            value=studied[aid].get("gdelt_seen_at_utc")
            if not isinstance(value,str):
                raise ValueError("MISSING_EVENT_TIMESTAMP")
            return (value,aid)
        representatives.append(min(ids,key=key))
    if covered!=set(classified):
        raise ValueError("UNCOVERED_ARTICLES")
    by_category={}
    for aid in representatives:
        categories=classified[aid].get("categories")
        forward=studied[aid].get("forward")
        if not isinstance(categories,list) or not isinstance(forward,dict):
            raise ValueError("INVALID_EVENT_CONTENT")
        for category in set(categories):
            if not isinstance(category,str):
                raise ValueError("INVALID_CATEGORY")
            for horizon in HORIZONS:
                observation=forward.get(horizon)
                if observation is None:
                    continue
                if not isinstance(observation,dict):
                    raise ValueError("INVALID_FORWARD")
                value=observation.get("return_pct")
                if not _valid_number(value):
                    raise ValueError("INVALID_RETURN")
                by_category.setdefault(category,{}).setdefault(horizon,[]).append(value)
    output=[]
    for category,by_horizon in sorted(by_category.items()):
        horizons={}
        for horizon in HORIZONS:
            values=by_horizon.get(horizon,[])
            enough=len(values)>=min_samples
            horizons[horizon]={
                "samples":len(values),
                "mean_return_pct":round(statistics.mean(values),8) if enough else None,
                "median_return_pct":round(statistics.median(values),8) if enough else None,
                "mean_absolute_move_pct":round(statistics.mean(abs(x) for x in values),8) if enough else None,
                "positive_observation_rate_pct":round(100*sum(x>0 for x in values)/len(values),8) if enough else None,
                "insufficient_samples":not enough}
        output.append({"category":category,"horizons":horizons})
    return {"version":"V137.0","status":"HEURISTIC_CLUSTER_REPRESENTATIVE_DESCRIPTIVE_STATISTICS",
            "article_count":len(articles),"heuristic_cluster_count":len(groups),
            "representative_article_ids":sorted(representatives),
            "excluded_potential_duplicate_articles":len(articles)-len(representatives),
            "minimum_samples_to_display":min_samples,"categories":output,
            "unique_real_world_events_verified":False,
            "independent_observations_verified":False,
            "point_in_time_news_availability_verified":False,
            "causal_effect_established":False,"validated_edge":False,
            "research_only":True,"simulation_only":True,
            "exchange_connected":False,"orders_submitted_to_exchange":0,
            "live_trading_approved":False,
            "limitations":"Uses earliest GDELT-observed article per heuristic V136 group, not verified unique events. Remaining correlated stories and incomplete market horizons may bias estimates. No tradable timestamp, statistical significance or causal inference."}

def main():
    p=argparse.ArgumentParser(description="V137 offline cluster-adjusted news descriptive statistics")
    p.add_argument("v128_taxonomy_json",type=Path)
    p.add_argument("v129_event_study_json",type=Path)
    p.add_argument("v136_clusters_json",type=Path)
    p.add_argument("--min-samples",type=int,default=5)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    inputs=[]
    for path in (args.v128_taxonomy_json,args.v129_event_study_json,args.v136_clusters_json):
        if path.stat().st_size>4_000_000:
            raise ValueError("INPUT_TOO_LARGE")
        inputs.append(json.loads(path.read_text(encoding="utf-8")))
    result=adjust(*inputs,min_samples=args.min_samples)
    encoded=json.dumps(result,indent=2,ensure_ascii=False)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(encoded,encoding="utf-8")
    else:
        print(encoded,end="")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
