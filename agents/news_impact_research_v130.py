"""V130 descriptive category-level news observation event statistics.

Aggregates V128 headline tags with V129 observed-event returns; does NOT
infer causation, tradable news availability, independence, or predictive edge.
"""
import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

HORIZONS=("5m","15m","60m")

def aggregate(taxonomy,event_study,min_samples=5):
    if not isinstance(taxonomy,dict) or taxonomy.get("version")!="V128.0":
        raise ValueError("INVALID_V128_TAXONOMY")
    if not isinstance(event_study,dict) or event_study.get("version")!="V129.0":
        raise ValueError("INVALID_V129_STUDY")
    if type(min_samples) is not int or min_samples<1:
        raise ValueError("INVALID_MIN_SAMPLES")
    articles=taxonomy.get("articles")
    events=event_study.get("events")
    if not isinstance(articles,list) or not isinstance(events,list) or len(articles)>100 or len(events)>100:
        raise ValueError("INVALID_ARTICLES_OR_EVENTS")
    indexed={}
    for event in events:
        if not isinstance(event,dict) or not isinstance(event.get("article_id"),str) or not isinstance(event.get("forward"),dict):
            raise ValueError("INVALID_EVENT")
        key=event["article_id"]
        if key in indexed:
            raise ValueError("DUPLICATE_EVENT_ID")
        indexed[key]=event
    groups=defaultdict(lambda:defaultdict(list))
    seen=set()
    for article in articles:
        if not isinstance(article,dict) or not isinstance(article.get("article_id"),str):
            raise ValueError("INVALID_ARTICLE")
        key=article["article_id"]
        if key in seen:
            raise ValueError("DUPLICATE_ARTICLE_ID")
        seen.add(key)
        categories=article.get("categories")
        if not isinstance(categories,list) or not categories or any(not isinstance(x,str) or not x for x in categories):
            raise ValueError("INVALID_CATEGORIES")
        event=indexed.get(key)
        if event is None:
            continue
        for horizon in HORIZONS:
            measurement=event["forward"].get(horizon)
            if measurement is None:
                continue
            if not isinstance(measurement,dict):
                raise ValueError("INVALID_RETURN")
            value=measurement.get("return_pct")
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
                raise ValueError("INVALID_RETURN")
            for category in set(categories):
                groups[category][horizon].append(float(value))
    results=[]
    for category in sorted(groups):
        horizons={}
        for horizon in HORIZONS:
            values=groups[category].get(horizon,[])
            n=len(values)
            horizons[horizon]={
                "samples":n,
                "mean_return_pct":round(statistics.mean(values),8) if n>=min_samples else None,
                "median_return_pct":round(statistics.median(values),8) if n>=min_samples else None,
                "mean_absolute_move_pct":round(statistics.mean(abs(x) for x in values),8) if n>=min_samples else None,
                "positive_observation_rate_pct":round(100*sum(x>0 for x in values)/n,8) if n>=min_samples else None,
                "insufficient_samples":n<min_samples,
            }
        results.append({"category":category,"horizons":horizons})
    return {
        "version":"V130.0","status":"DESCRIPTIVE_CATEGORY_EVENT_STATISTICS",
        "matched_articles":len(seen.intersection(indexed)),
        "minimum_samples_to_display":min_samples,
        "categories":results,
        "news_availability_verified":False,
        "independent_events_verified":False,
        "causal_effect_established":False,
        "statistical_significance_tested":False,
        "predictive_edge_established":False,
        "research_only":True,"simulation_only":True,
        "exchange_connected":False,"orders_submitted_to_exchange":0,
        "live_trading_approved":False,"validated_edge":False,
        "limitations":"Overlapping events and repeated coverage violate independence assumptions. Only headline categories and observed forward closes; missing horizons omitted. Small samples suppressed. No controls, counterfactuals, market beta adjustment, verified first availability or executable-entry modeling."
    }

def main():
    parser=argparse.ArgumentParser(description="V130 offline news category market response statistics")
    parser.add_argument("v128_taxonomy_json",type=Path)
    parser.add_argument("v129_event_study_json",type=Path)
    parser.add_argument("--min-samples",type=int,default=5)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    result=aggregate(json.loads(args.v128_taxonomy_json.read_text(encoding="utf-8")),
                     json.loads(args.v129_event_study_json.read_text(encoding="utf-8")),
                     args.min_samples)
    encoded=json.dumps(result,indent=2,ensure_ascii=False)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(encoded,encoding="utf-8")
    else:
        print(encoded,end="")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
