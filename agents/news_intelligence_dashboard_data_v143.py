"""V143 offline JSON view model for SPACE BAR news research dashboard.

This is static dashboard DATA, not a live dashboard or market feed.
"""
import argparse
import json
import math
from pathlib import Path

from news_research_intelligence_report_v142 import load_bundle
from news_research_reproducibility_v141 import verify_bundle

MAX_ROWS=300

def _number(value):
    if value is None:
        return None
    if type(value) not in (float,int) or not math.isfinite(value):
        raise ValueError("INVALID_DASHBOARD_METRIC")
    return round(value,8)

def build(bundle,artifacts,verification=None):
    if not isinstance(bundle,dict) or bundle.get("version")!="V141.0":
        raise ValueError("INVALID_BUNDLE")
    if not isinstance(artifacts,dict):
        raise ValueError("INVALID_ARTIFACTS")
    pipeline=artifacts.get("pipeline")
    groups=artifacts.get("clusters")
    adjusted=artifacts.get("adjusted_statistics")
    comparison=artifacts.get("comparison")
    if not all(isinstance(x,dict) for x in (pipeline,groups,adjusted,comparison)):
        raise ValueError("INVALID_STAGES")
    if (pipeline.get("version")!="V132.0" or groups.get("version")!="V136.0"
        or adjusted.get("version")!="V137.0" or comparison.get("version")!="V138.0"):
        raise ValueError("INVALID_STAGES")
    rows=comparison.get("rows")
    if not isinstance(rows,list) or len(rows)>MAX_ROWS:
        raise ValueError("INVALID_ROWS")
    cards=[]
    for key,label in (
        ("article_count","Normalized articles"),
        ("cluster_count","Heuristic coverage groups"),
        ("potentially_repeated_articles","Potentially repeated articles")):
        value=groups.get(key)
        if type(value) is not int or value<0:
            raise ValueError("INVALID_COUNT")
        cards.append({"id":key,"label":label,"value":value})
    if cards[1]["value"]>cards[0]["value"] or cards[2]["value"]!=cards[0]["value"]-cards[1]["value"]:
        raise ValueError("INCONSISTENT_COUNTS")
    charts=[]
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get("changes"),dict):
            raise ValueError("INVALID_ROW")
        category=row.get("category")
        horizon=row.get("horizon")
        if not isinstance(category,str) or horizon not in ("5m","15m","60m"):
            raise ValueError("INVALID_ROW")
        before=row.get("article_samples")
        after=row.get("cluster_adjusted_samples")
        if type(before) is not int or type(after) is not int or not 0<=after<=before:
            raise ValueError("INVALID_SAMPLE_COUNTS")
        changes=row["changes"]
        charts.append({
            "category":category,"horizon":horizon,
            "article_samples":before,"adjusted_samples":after,
            "removed_samples":before-after,
            "mean_return_delta_percentage_points":_number(changes.get("mean_return_pct")),
            "positive_rate_delta_percentage_points":_number(changes.get("positive_observation_rate_pct")),
            "missing_comparable_metrics":any(changes.get(k) is None for k in (
                "mean_return_pct","positive_observation_rate_pct"))})
    charts.sort(key=lambda x:(x["category"],{"5m":0,"15m":1,"60m":2}[x["horizon"]]))
    warnings=pipeline.get("guardian",{}).get("warnings",[])
    if not isinstance(warnings,list):
        raise ValueError("INVALID_WARNINGS")
    warning_codes=[]
    for warning in warnings[:100]:
        if not isinstance(warning,dict) or not isinstance(warning.get("code"),str):
            raise ValueError("INVALID_WARNING")
        warning_codes.append(warning["code"])
    settings=bundle.get("input_manifest",{}).get("settings",{})
    if not isinstance(settings,dict):
        raise ValueError("INVALID_SETTINGS")
    return {
        "version":"V143.0","status":"OFFLINE_NEWS_DASHBOARD_VIEW_MODEL",
        "cards":cards,"charts":charts,"warning_codes":warning_codes,
        "metadata":{"topic":settings.get("topic"),"observed_at":settings.get("observed_at"),
                    "manifest_sha256":bundle.get("input_manifest",{}).get("manifest_sha256"),
                    "replay_verified_this_run":bool(verification and verification.get("reproducible") is True)},
        "data_freshness":"STATIC_OFFLINE_SNAPSHOT",
        "first_tradable_news_availability_verified":False,
        "event_identity_verified":False,"causal_effect_established":False,
        "validated_edge":False,"research_only":True,"simulation_only":True,
        "exchange_connected":False,"orders_submitted_to_exchange":0,
        "live_trading_approved":False,
        "limitations":"This JSON is a view model for an offline historical news study, not a live market dashboard. Heuristic coverage grouping and descriptive statistics do not prove causality, original news availability or profitable trading."}

def main():
    p=argparse.ArgumentParser(description="V143 offline news dashboard JSON data")
    p.add_argument("bundle_dir",type=Path)
    p.add_argument("--verify-raw-news",type=Path)
    p.add_argument("--verify-ohlcv",type=Path)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    if bool(args.verify_raw_news)!=bool(args.verify_ohlcv):
        raise ValueError("VERIFY_REQUIRES_BOTH_INPUTS")
    verification=(verify_bundle(args.bundle_dir,args.verify_raw_news,args.verify_ohlcv)
                  if args.verify_raw_news else None)
    bundle,artifacts=load_bundle(args.bundle_dir)
    output=json.dumps(build(bundle,artifacts,verification),indent=2,ensure_ascii=False)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(output,encoding="utf-8")
    else:
        print(output,end="")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
