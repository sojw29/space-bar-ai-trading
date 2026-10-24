"""V128 deterministic, conservative news taxonomy over V127 metadata.

Classification is keyword-based and explicitly NOT predictive sentiment,
causal market impact, publication-time proof, or an order signal.
"""
import argparse
import json
import re
from pathlib import Path

CATEGORIES={
    "MONETARY_POLICY":(r"\bfederal reserve\b",r"\bfomc\b",r"\brate (?:hike|cut|decision)\b",r"\bcentral bank\b"),
    "INFLATION":(r"\binflation\b",r"\bcpi\b",r"\bppi\b",r"\bconsumer price index\b"),
    "REGULATION":(r"\bsec\b",r"\bregulat(?:ion|or|ory)\b",r"\blawsuit\b",r"\bcrypto ban\b"),
    "ETF":(r"\betf\b",r"\bexchange.traded fund\b"),
    "EXCHANGE_SECURITY":(r"\bexchange hack\b",r"\bhack(?:ed|ing)?\b",r"\bexploit\b",r"\bwithdrawal suspension\b"),
    "TOKEN_SUPPLY":(r"\btoken unlock\b",r"\btoken burn\b",r"\bcirculating supply\b"),
    "NETWORK":(r"\bmainnet\b",r"\bnetwork upgrade\b",r"\bhard fork\b",r"\bblockchain outage\b"),
}
ASSETS={
    "BTC":(r"\bbitcoin\b",r"\bbtc\b"),
    "ETH":(r"\bethereum\b",r"\bether\b",r"\beth\b"),
    "SOL":(r"\bsolana\b",r"\bsol\b"),
}
# Avoid treating ambiguous standalone SOL as Solana.
ASSETS["SOL"]=(r"\bsolana\b",)

def classify_article(article):
    if not isinstance(article,dict) or not isinstance(article.get("title"),str):
        raise ValueError("INVALID_ARTICLE")
    title=article["title"][:500]
    categories=[key for key,patterns in CATEGORIES.items()
                if any(re.search(pattern,title,re.IGNORECASE) for pattern in patterns)]
    assets=[key for key,patterns in ASSETS.items()
            if any(re.search(pattern,title,re.IGNORECASE) for pattern in patterns)]
    # Broad market macro stories may be relevant to all assets but do not
    # assert a directional impact or force explicit ticker mentions.
    topic=article.get("topic")
    if topic not in ("BTC","ETH","SOL","MACRO"):
        raise ValueError("INVALID_TOPIC")
    return {
        "article_id":article.get("article_id"),
        "title":title,"topic":topic,
        "categories":categories or ["OTHER_UNCLASSIFIED"],
        "explicit_title_asset_mentions":assets,
        "macro_market_context":bool(set(categories)&{"MONETARY_POLICY","INFLATION"}),
        "headline_only":True,
        "impact_direction":"UNKNOWN",
        "importance_score":None,
        "market_effect_verified":False,
        "original_publication_time_verified":False,
        "tradable_availability_verified":False,
    }

def classify_snapshot(snapshot):
    if not isinstance(snapshot,dict) or snapshot.get("version")!="V127.0":
        raise ValueError("INVALID_V127_SNAPSHOT")
    articles=snapshot.get("articles")
    if not isinstance(articles,list) or len(articles)>100:
        raise ValueError("INVALID_ARTICLES")
    classified=[classify_article(a) for a in articles]
    counts={key:sum(key in a["categories"] for a in classified) for key in CATEGORIES}
    counts["OTHER_UNCLASSIFIED"]=sum("OTHER_UNCLASSIFIED" in a["categories"] for a in classified)
    return {
        "version":"V128.0","status":"HEADLINE_ONLY_RESEARCH_TAXONOMY",
        "source_snapshot_version":"V127.0",
        "article_count":len(classified),"category_counts":counts,
        "articles":classified,
        "classification_is_heuristic":True,
        "sentiment_inferred":False,"price_direction_predicted":False,
        "market_impact_verified":False,
        "research_only":True,"simulation_only":True,
        "exchange_connected":False,"orders_submitted_to_exchange":0,
        "live_trading_approved":False,"validated_edge":False,
        "limitations":"English headline keyword rules only. Ambiguous terms, satire, negation and multilingual stories may be misclassified. No article-body reading, causal inference, original publication-time verification or tradable news availability."
    }

def main():
    parser=argparse.ArgumentParser(description="V128 offline news headline taxonomy")
    parser.add_argument("snapshot_json",type=Path)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    result=classify_snapshot(json.loads(args.snapshot_json.read_text(encoding="utf-8")))
    encoded=json.dumps(result,indent=2,ensure_ascii=False)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(encoded,encoding="utf-8")
    else:
        print(encoded,end="")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
