"""V135 offline news research validator for duplicated and overlapping events.

Produces descriptive quality warnings only, never trading signals or approval.
"""
import argparse
import json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit

MAX_EVENTS=100

def _utc(value):
    if not isinstance(value,str):
        raise ValueError("INVALID_TIME")
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("INVALID_TIME") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("INVALID_TIME")
    return dt.astimezone(timezone.utc)

def validate(pipeline,overlap_minutes=60):
    if not isinstance(pipeline,dict) or pipeline.get("version")!="V132.0":
        raise ValueError("INVALID_PIPELINE")
    if type(overlap_minutes) is not int or not 1<=overlap_minutes<=1440:
        raise ValueError("INVALID_OVERLAP_WINDOW")
    collector=pipeline.get("collector")
    event_study=pipeline.get("event_study")
    if not isinstance(collector,dict) or collector.get("version")!="V127.0" or not isinstance(event_study,dict) or event_study.get("version")!="V129.0":
        raise ValueError("INVALID_PIPELINE_STAGES")
    articles=collector.get("articles")
    events=event_study.get("events")
    if not isinstance(articles,list) or not isinstance(events,list) or len(articles)>MAX_EVENTS or len(events)>MAX_EVENTS:
        raise ValueError("INVALID_EVENT_COUNT")
    by_id={}
    url_keys=defaultdict(list)
    headline_keys=defaultdict(list)
    for article in articles:
        if not isinstance(article,dict) or not isinstance(article.get("article_id"),str):
            raise ValueError("INVALID_ARTICLE")
        aid=article["article_id"]
        if aid in by_id:
            raise ValueError("DUPLICATE_ARTICLE_ID")
        url=article.get("url")
        title=article.get("title")
        if not isinstance(url,str) or not isinstance(title,str):
            raise ValueError("INVALID_ARTICLE")
        parsed=urlsplit(url)
        if parsed.scheme!="https" or not parsed.hostname:
            raise ValueError("INVALID_ARTICLE_URL")
        seen=_utc(article.get("gdelt_seen_at_utc"))
        by_id[aid]=seen
        # V127 canonicalizes scheme/host but deliberately preserves
        # case-sensitive paths, queries and trailing slashes.
        url_keys[url].append(aid)
        headline_keys[" ".join(title.casefold().split())].append(aid)
    event_ids=[]
    for event in events:
        if not isinstance(event,dict) or not isinstance(event.get("article_id"),str):
            raise ValueError("INVALID_EVENT")
        aid=event["article_id"]
        if aid not in by_id:
            raise ValueError("UNKNOWN_EVENT_ID")
        event_ids.append(aid)
    if len(event_ids)!=len(set(event_ids)):
        raise ValueError("DUPLICATE_EVENT_ID")
    if set(event_ids)!=set(by_id):
        raise ValueError("MISSING_EVENT_ID")
    repeated_urls=[sorted(ids) for ids in url_keys.values() if len(ids)>1]
    repeated_titles=[sorted(ids) for ids in headline_keys.values() if len(ids)>1]
    ordered=sorted(by_id.items(),key=lambda pair:(pair[1],pair[0]))
    overlaps=[]
    for index,(aid,at) in enumerate(ordered):
        for bid,bt in ordered[index+1:]:
            minutes=(bt-at).total_seconds()/60
            if minutes>overlap_minutes:
                break
            overlaps.append({"article_ids":[aid,bid],"minutes_apart":round(minutes,4)})
    warnings=[]
    if repeated_urls:
        warnings.append("REPEATED_URL")
    if repeated_titles:
        warnings.append("REPEATED_NORMALIZED_TITLE")
    if overlaps:
        warnings.append("TEMPORALLY_OVERLAPPING_ARTICLES")
    warnings.extend(["FIRST_TRADABLE_NEWS_AVAILABILITY_UNVERIFIED",
                     "EVENT_INDEPENDENCE_UNVERIFIED",
                     "CAUSAL_MARKET_IMPACT_UNVERIFIED"])
    return {"version":"V135.0","status":"RESEARCH_VALIDATION_WARNINGS",
            "article_count":len(articles),"event_count":len(events),
            "overlap_window_minutes":overlap_minutes,
            "repeated_url_groups":sorted(repeated_urls),
            "repeated_title_groups":sorted(repeated_titles),
            "overlapping_article_pairs":overlaps,
            "warnings":warnings,
            "historical_point_in_time_validated":False,
            "event_independence_validated":False,
            "causal_effect_established":False,
            "research_only":True,"simulation_only":True,
            "exchange_connected":False,"orders_submitted_to_exchange":0,
            "live_trading_approved":False,"validated_edge":False,
            "limitations":"Time proximity and matching headlines are heuristic duplicate/overlap warnings; neither proves identical stories. Different runs cannot be compared without shared dataset and window provenance."}

def main():
    parser=argparse.ArgumentParser(description="V135 offline news research event validator")
    parser.add_argument("v132_report_json",type=Path)
    parser.add_argument("--overlap-minutes",type=int,default=60)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    if args.v132_report_json.stat().st_size>4_000_000:
        raise ValueError("REPORT_INPUT_TOO_LARGE")
    report=json.loads(args.v132_report_json.read_text(encoding="utf-8"))
    result=validate(report,args.overlap_minutes)
    encoded=json.dumps(result,indent=2,ensure_ascii=False)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(encoded,encoding="utf-8")
    else:
        print(encoded,end="")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
