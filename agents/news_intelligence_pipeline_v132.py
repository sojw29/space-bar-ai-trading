"""V132 deterministic offline V127-V131 news intelligence research pipeline.

Uses explicit observation timestamp, a supplied GDELT fixture and historical
OHLCV CSV. No automatic network access, news trading or causal claims.
"""
import argparse
import json
from pathlib import Path

from news_collector_v127 import normalize
from news_taxonomy_v128 import classify_snapshot
from news_market_event_study_v129 import load_candles, study
from news_impact_research_v130 import aggregate
from news_risk_guardian_v131 import assess

def build(raw_news,topic,observed_at,candles,step_seconds,min_samples=5):
    collector=normalize(raw_news,topic,observed_at)
    taxonomy=classify_snapshot(collector)
    event_study=study(collector,candles,step_seconds)
    impact=aggregate(taxonomy,event_study,min_samples=min_samples)
    guardian=assess(collector,taxonomy,event_study,impact)
    return {
        "version":"V132.0","status":"OFFLINE_NEWS_RESEARCH_PIPELINE_COMPLETE",
        "collector":collector,"taxonomy":taxonomy,
        "event_study":event_study,"impact":impact,"guardian":guardian,
        "pipeline_stages":["V127","V128","V129","V130","V131"],
        "historical_news_availability_verified":False,
        "causal_effect_established":False,
        "validated_edge":False,"research_only":True,
        "simulation_only":True,"exchange_connected":False,
        "orders_submitted_to_exchange":0,"live_trading_approved":False,
        "limitations":"Offline historical observation study, not a point-in-time tradable news backtest. GDELT seendate does not prove first publication or availability. Category aggregates may include correlated events; no causal or predictive inference."
    }

def run(raw_news_path,ohlcv_path,topic,observed_at,min_samples=5):
    path=Path(raw_news_path)
    if path.stat().st_size>2_000_000:
        raise ValueError("NEWS_INPUT_TOO_LARGE")
    try:
        raw=json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError,ValueError) as exc:
        raise ValueError("INVALID_NEWS_JSON") from exc
    candles,step=load_candles(ohlcv_path)
    return build(raw,topic,observed_at,candles,step,min_samples)

def main():
    parser=argparse.ArgumentParser(description="V132 offline end-to-end news research pipeline")
    parser.add_argument("gdelt_raw_json",type=Path)
    parser.add_argument("ohlcv_csv",type=Path)
    parser.add_argument("--topic",choices=["BTC","ETH","SOL","MACRO"],required=True)
    parser.add_argument("--observed-at",required=True,
                        help="Explicit timezone-aware collection timestamp (UTC recommended)")
    parser.add_argument("--min-samples",type=int,default=5)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    result=run(args.gdelt_raw_json,args.ohlcv_csv,args.topic,args.observed_at,args.min_samples)
    encoded=json.dumps(result,indent=2,ensure_ascii=False)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(encoded,encoding="utf-8")
    else:
        print(encoded,end="")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
