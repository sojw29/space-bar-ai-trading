"""V131 offline news research quality guardrails; never produces orders.

Risk warnings concern data adequacy and provenance, not directional forecasts.
"""
import argparse
import json
from pathlib import Path

def assess(collector, taxonomy, event_study, impact, min_articles=10, min_matched=5):
    versions=((collector,"V127.0"),(taxonomy,"V128.0"),(event_study,"V129.0"),(impact,"V130.0"))
    if any(not isinstance(x,dict) or x.get("version")!=v for x,v in versions):
        raise ValueError("INVALID_PIPELINE_VERSION")
    if any(type(x) is not int or x<1 for x in (min_articles,min_matched)):
        raise ValueError("INVALID_THRESHOLDS")
    articles=collector.get("articles")
    classified=taxonomy.get("articles")
    events=event_study.get("events")
    categories=impact.get("categories")
    if any(not isinstance(x,list) or len(x)>100 for x in (articles,classified,events)):
        raise ValueError("INVALID_ARTICLE_RECORDS")
    if not isinstance(categories,list):
        raise ValueError("INVALID_CATEGORY_RECORDS")
    ids=[]
    for group in (articles,classified,events):
        item_ids=[]
        for x in group:
            if not isinstance(x,dict) or not isinstance(x.get("article_id"),str):
                raise ValueError("INVALID_ARTICLE_ID")
            item_ids.append(x["article_id"])
        if len(set(item_ids))!=len(item_ids):
            raise ValueError("DUPLICATE_ARTICLE_ID")
        ids.append(set(item_ids))
    if ids[0]!=ids[1] or ids[0]!=ids[2]:
        raise ValueError("PIPELINE_ARTICLE_MISMATCH")
    if impact.get("matched_articles")!=len(ids[0]):
        raise ValueError("PIPELINE_MATCH_COUNT_MISMATCH")
    flags=[]
    def flag(code,detail):
        flags.append({"code":code,"detail":detail})
    if len(articles)<min_articles:
        flag("LOW_NEWS_SAMPLE","News article count below configured review threshold.")
    if len(ids[0])<min_matched:
        flag("LOW_MATCHED_EVENTS","Matched event count below configured review threshold.")
    missing=0
    for event in events:
        forward=event.get("forward")
        if not isinstance(forward,dict):
            raise ValueError("INVALID_FORWARD_MEASUREMENTS")
        if all(forward.get(k) is None for k in ("5m","15m","60m")):
            missing+=1
    if missing:
        flag("MISSING_FORWARD_RETURNS",str(missing)+" events lack any measured forward close.")
    flag("UNVERIFIED_NEWS_AVAILABILITY","GDELT observed time is not verified first tradable publication time.")
    flag("UNVERIFIED_CAUSALITY","Market moves cannot be attributed to headlines without controls.")
    return {"version":"V131.0","status":"RESEARCH_REVIEW_REQUIRED",
            "articles":len(articles),"matched_events":len(ids[0]),
            "missing_forward_events":missing,"warnings":flags,"warning_count":len(flags),
            "risk_signal_type":"DATA_QUALITY_AND_RESEARCH_LIMITATIONS",
            "trade_action":"NONE","automatic_strategy_changes":False,
            "news_availability_verified":False,"causality_established":False,
            "research_only":True,"simulation_only":True,
            "exchange_connected":False,"orders_submitted_to_exchange":0,
            "live_trading_approved":False,"validated_edge":False,
            "limitations":"No realtime calendar or breaking-news monitoring, directional news signal, market volatility forecast or execution decision. Requires matched V127-V130 snapshot inputs."}

def main():
    p=argparse.ArgumentParser(description="V131 offline news research quality guardian")
    for name in ("v127_collector","v128_taxonomy","v129_event_study","v130_impact"):
        p.add_argument(name,type=Path)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    result=assess(*(json.loads(getattr(args,k).read_text(encoding="utf-8"))
                    for k in ("v127_collector","v128_taxonomy","v129_event_study","v130_impact")))
    output=json.dumps(result,indent=2,ensure_ascii=False)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(output,encoding="utf-8")
    else:
        print(output,end="")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
