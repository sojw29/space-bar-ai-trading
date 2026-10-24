"""V127 opt-in GDELT news metadata collector for offline research.

Network is disabled by default. GDELT seendate is observation/ingestion time,
NOT proven original publication time or the time a trader could see the story.
No sentiment predictions, orders, live trading or look-ahead-safe backtest claim.
"""
import argparse
import hashlib
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
QUERIES = {
    "BTC": '(bitcoin OR "bitcoin ETF")',
    "ETH": '(ethereum OR "ether ETF")',
    "SOL": '(solana OR "SOL token")',
    "MACRO": '("Federal Reserve" OR "interest rates" OR inflation)',
}
MAX_RESPONSE_BYTES = 2_000_000
MAX_ARTICLES = 100

def _seen(value):
    if not isinstance(value,str) or not re.fullmatch(r"\d{14}",value):
        raise ValueError("INVALID_GDELT_SEENDATE")
    try:
        return datetime.strptime(value,"%Y%m%d%H%M%S").replace(
            tzinfo=timezone.utc).isoformat()
    except ValueError as exc:
        raise ValueError("INVALID_GDELT_SEENDATE") from exc

def _url(value):
    if not isinstance(value,str) or len(value)>2048:
        raise ValueError("INVALID_ARTICLE_URL")
    parsed=urllib.parse.urlsplit(value)
    if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("INVALID_ARTICLE_URL")
    return urllib.parse.urlunsplit((parsed.scheme,parsed.netloc.lower(),
                                    parsed.path,parsed.query,""))

def normalize(payload,topic,observed_at):
    if topic not in QUERIES:
        raise ValueError("INVALID_TOPIC")
    if not isinstance(observed_at,str):
        raise ValueError("INVALID_OBSERVATION_TIME")
    try:
        observed=datetime.fromisoformat(observed_at.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("INVALID_OBSERVATION_TIME") from exc
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("INVALID_OBSERVATION_TIME")
    if not isinstance(payload,dict) or not isinstance(payload.get("articles"),list):
        raise ValueError("INVALID_GDELT_RESPONSE")
    items={}
    for article in payload["articles"][:MAX_ARTICLES]:
        if not isinstance(article,dict):
            continue
        try:
            url=_url(article.get("url"))
            seen=_seen(article.get("seendate"))
        except ValueError:
            continue
        # Reject articles whose GDELT observation is later than this snapshot.
        if datetime.fromisoformat(seen)>observed:
            continue
        title=article.get("title","")
        if not isinstance(title,str) or not title.strip():
            continue
        uid=hashlib.sha256(url.encode("utf-8")).hexdigest()
        record={"article_id":uid,"topic":topic,"title":title.strip()[:500],
                "url":url,"source_domain":str(article.get("domain",""))[:200],
                "gdelt_seen_at_utc":seen,"collector_observed_at_utc":observed.astimezone(
                    timezone.utc).isoformat(),
                "original_publication_time_verified":False,
                "earliest_tradable_availability_verified":False,
                "source":"GDELT_DOC_2"}
        if uid not in items or seen<items[uid]["gdelt_seen_at_utc"]:
            items[uid]=record
    return {"version":"V127.0","topic":topic,"count":len(items),
            "articles":sorted(items.values(),key=lambda x:(x["gdelt_seen_at_utc"],x["article_id"])),
            "research_only":True,"simulation_only":True,
            "exchange_connected":False,"orders_submitted_to_exchange":0,
            "live_trading_approved":False,"validated_edge":False,
            "limitations":"GDELT seendate is not guaranteed original publication or first market availability. No historical point-in-time backtest eligibility without separate availability proof."}

def fetch(topic,timespan="24h",maxrecords=50,timeout=15):
    if topic not in QUERIES:
        raise ValueError("INVALID_TOPIC")
    if not isinstance(timespan,str) or not re.fullmatch(r"(?:[1-9]|[1-9][0-9])(?:h|hours|d|days)",timespan):
        raise ValueError("INVALID_TIMESPAN")
    if type(maxrecords) is not int or not 1<=maxrecords<=MAX_ARTICLES:
        raise ValueError("INVALID_MAXRECORDS")
    if not isinstance(timeout,(int,float)) or isinstance(timeout,bool) or not 1<=timeout<=30:
        raise ValueError("INVALID_TIMEOUT")
    params=urllib.parse.urlencode({"query":QUERIES[topic],"mode":"ArtList",
                                    "format":"json","timespan":timespan,
                                    "maxrecords":maxrecords})
    request=urllib.request.Request(ENDPOINT+"?"+params,headers={
        "User-Agent":"SpaceBarResearchCollector/1.0 (offline research)"})
    with urllib.request.urlopen(request,timeout=timeout) as response:
        raw=response.read(MAX_RESPONSE_BYTES+1)
    if len(raw)>MAX_RESPONSE_BYTES:
        raise ValueError("GDELT_RESPONSE_TOO_LARGE")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeError,ValueError) as exc:
        raise ValueError("INVALID_GDELT_RESPONSE") from exc

def main():
    parser=argparse.ArgumentParser(description="V127 opt-in GDELT news metadata collector")
    parser.add_argument("--topic",choices=sorted(QUERIES),required=True)
    parser.add_argument("--input-json",type=Path,help="Offline fixture (default; no network)")
    parser.add_argument("--allow-network",action="store_true",
                        help="Explicitly opt into external GDELT request")
    parser.add_argument("--timespan",default="24h")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    if args.allow_network and args.input_json:
        parser.error("Choose either --allow-network or --input-json")
    if not args.allow_network and not args.input_json:
        parser.error("No network by default: provide --input-json or --allow-network")
    observed=datetime.now(timezone.utc).isoformat()
    payload=fetch(args.topic,args.timespan) if args.allow_network else json.loads(
        args.input_json.read_text(encoding="utf-8"))
    result=normalize(payload,args.topic,observed)
    encoded=json.dumps(result,indent=2,ensure_ascii=False)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(encoded,encoding="utf-8")
    else:
        print(encoded,end="")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
