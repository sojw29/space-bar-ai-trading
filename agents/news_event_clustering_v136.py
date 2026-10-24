"""V136 conservative offline grouping of likely repeated news coverage.

A cluster requires a shared canonical URL or normalized headline AND a
configurable time window. Mere temporal proximity is never sufficient.
Grouping is research metadata, not proof that articles describe one event.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit

def _utc(value):
    if not isinstance(value,str):
        raise ValueError("INVALID_SEEN_TIME")
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("INVALID_SEEN_TIME") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("INVALID_SEEN_TIME")
    return dt.astimezone(timezone.utc)

def _url(value):
    if not isinstance(value,str):
        raise ValueError("INVALID_URL")
    p=urlsplit(value)
    if p.scheme!="https" or not p.hostname or p.username or p.password:
        raise ValueError("INVALID_URL")
    return urlunsplit((p.scheme,p.netloc.lower(),p.path.rstrip("/") or "/",p.query,""))

def cluster(snapshot,window_minutes=60):
    if not isinstance(snapshot,dict) or snapshot.get("version")!="V127.0":
        raise ValueError("INVALID_V127_SNAPSHOT")
    if type(window_minutes) is not int or not 1<=window_minutes<=1440:
        raise ValueError("INVALID_WINDOW")
    articles=snapshot.get("articles")
    if not isinstance(articles,list) or len(articles)>100:
        raise ValueError("INVALID_ARTICLES")
    records=[]
    seen_ids=set()
    for item in articles:
        if not isinstance(item,dict):
            raise ValueError("INVALID_ARTICLE")
        aid=item.get("article_id")
        title=item.get("title")
        if not isinstance(aid,str) or not aid or not isinstance(title,str) or not title.strip():
            raise ValueError("INVALID_ARTICLE")
        if aid in seen_ids:
            raise ValueError("DUPLICATE_ARTICLE_ID")
        seen_ids.add(aid)
        normalized_title=re.sub(r"\s+"," ",title.casefold()).strip()
        records.append({"article_id":aid,"seen":_utc(item.get("gdelt_seen_at_utc")),
                        "url":_url(item.get("url")),"title":normalized_title})
    records.sort(key=lambda x:(x["seen"],x["article_id"]))
    parent=list(range(len(records)))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]]
            i=parent[i]
        return i
    def union(i,j):
        a,b=root(i),root(j)
        if a!=b:
            parent[max(a,b)]=min(a,b)
    # Keep cluster temporal span within the configured window. Complete-link
    # avoids chain-merging articles hours apart via intermediate headlines.
    for i,item in enumerate(records):
        for j in range(i+1,len(records)):
            other=records[j]
            if (other["seen"]-item["seen"]).total_seconds()>window_minutes*60:
                break
            if item["url"]!=other["url"] and item["title"]!=other["title"]:
                continue
            a,b=root(i),root(j)
            if a==b:
                continue
            members=[k for k in range(len(records)) if root(k) in (a,b)]
            span=(records[max(members)]["seen"]-records[min(members)]["seen"]).total_seconds()
            if span<=window_minutes*60:
                union(a,b)
    groups={}
    for index,item in enumerate(records):
        groups.setdefault(root(index),[]).append(item)
    clusters=[]
    for members in groups.values():
        ids=sorted(x["article_id"] for x in members)
        fingerprint=hashlib.sha256("|".join(ids).encode("utf-8")).hexdigest()
        clusters.append({"cluster_id":fingerprint,"article_ids":ids,
                         "article_count":len(ids),
                         "earliest_gdelt_seen_at_utc":min(x["seen"] for x in members).isoformat(),
                         "latest_gdelt_seen_at_utc":max(x["seen"] for x in members).isoformat(),
                         "likely_repeated_coverage":len(ids)>1})
    clusters.sort(key=lambda x:(x["earliest_gdelt_seen_at_utc"],x["cluster_id"]))
    return {"version":"V136.0","status":"HEURISTIC_NEWS_COVERAGE_GROUPS",
            "article_count":len(records),"cluster_count":len(clusters),
            "potentially_repeated_articles":sum(x["article_count"]-1 for x in clusters),
            "window_minutes":window_minutes,"clusters":clusters,
            "event_identity_verified":False,"first_tradable_news_availability_verified":False,
            "research_only":True,"simulation_only":True,
            "exchange_connected":False,"orders_submitted_to_exchange":0,
            "live_trading_approved":False,"validated_edge":False,
            "limitations":"Exact normalized headline or URL plus time proximity are heuristics, not semantic event identity. Different headlines about one event may remain separate; same headline may describe distinct events. No returns are recalculated or trades made."}

def main():
    p=argparse.ArgumentParser(description="V136 offline repeated-news coverage clustering")
    p.add_argument("v127_snapshot_json",type=Path)
    p.add_argument("--window-minutes",type=int,default=60)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    if args.v127_snapshot_json.stat().st_size>2_000_000:
        raise ValueError("INPUT_TOO_LARGE")
    result=cluster(json.loads(args.v127_snapshot_json.read_text(encoding="utf-8")),
                   args.window_minutes)
    output=json.dumps(result,indent=2,ensure_ascii=False)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(output,encoding="utf-8")
    else:
        print(output,end="")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
