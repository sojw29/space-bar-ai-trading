"""V141 reproducible offline news research bundle with input/output SHA256.

A replay recomputes all derived artifacts and checks byte-identical results.
This is reproducibility of supplied inputs, NOT historical market availability.
"""
import argparse
import hashlib
import json
from pathlib import Path

from news_intelligence_pipeline_v132 import run as run_pipeline
from news_event_clustering_v136 import cluster
from news_event_adjusted_statistics_v137 import adjust
from news_statistics_comparison_v138 import compare
from news_data_provenance_v139 import manifest,ROLES

ARTIFACTS=("pipeline","taxonomy","event_study","clusters","article_statistics",
           "adjusted_statistics","comparison")
MAX_INPUT_BYTES=20_000_000

def _bytes(value):
    return (json.dumps(value,sort_keys=True,separators=(",",":"),
                       ensure_ascii=False,allow_nan=False)+"\n").encode("utf-8")

def _hash(value):
    return hashlib.sha256(_bytes(value)).hexdigest()

def build(raw_news_path,ohlcv_path,topic,observed_at,min_samples=5,cluster_window_minutes=60):
    if type(min_samples) is not int or min_samples<1:
        raise ValueError("INVALID_MIN_SAMPLES")
    if type(cluster_window_minutes) is not int or not 1<=cluster_window_minutes<=1440:
        raise ValueError("INVALID_CLUSTER_WINDOW")
    for path in (raw_news_path,ohlcv_path):
        if Path(path).stat().st_size>MAX_INPUT_BYTES:
            raise ValueError("INPUT_TOO_LARGE")
    pipeline=run_pipeline(raw_news_path,ohlcv_path,topic,observed_at,min_samples)
    taxonomy=pipeline["taxonomy"]
    study=pipeline["event_study"]
    grouped=cluster(pipeline["collector"],cluster_window_minutes)
    adjusted=adjust(taxonomy,study,grouped,min_samples)
    article_stats=pipeline["impact"]
    comparison=compare(article_stats,adjusted)
    artifacts={"pipeline":pipeline,"taxonomy":taxonomy,"event_study":study,
               "clusters":grouped,"article_statistics":article_stats,
               "adjusted_statistics":adjusted,"comparison":comparison}
    return artifacts

def write_bundle(directory,raw_news_path,ohlcv_path,topic,observed_at,
                 min_samples=5,cluster_window_minutes=60):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    if any((directory/(name+".json")).exists() for name in (*ARTIFACTS,"bundle")):
        raise ValueError("OUTPUT_ALREADY_EXISTS")
    artifacts=build(raw_news_path,ohlcv_path,topic,observed_at,min_samples,cluster_window_minutes)
    for name in ARTIFACTS:
        (directory/(name+".json")).write_bytes(_bytes(artifacts[name]))
    settings={"topic":topic,"observed_at":observed_at,
              "min_samples":min_samples,"cluster_window_minutes":cluster_window_minutes}
    files={"raw_news":raw_news_path,"ohlcv_csv":ohlcv_path,
           "taxonomy":directory/"taxonomy.json",
           "event_study":directory/"event_study.json",
           "clusters":directory/"clusters.json"}
    provenance=manifest(files,settings)
    bundle={"version":"V141.0","status":"OFFLINE_REPRODUCIBLE_NEWS_RESEARCH_BUNDLE",
            "input_manifest":provenance,
            "output_sha256":{name:_hash(artifacts[name]) for name in ARTIFACTS},
            "output_encoding":"canonical_sorted_json_utf8_newline",
            "source_raw_news_path":str(Path(raw_news_path).resolve()),
            "source_ohlcv_path":str(Path(ohlcv_path).resolve()),
            "first_tradable_news_availability_verified":False,
            "causal_effect_established":False,"validated_edge":False,
            "research_only":True,"simulation_only":True,"exchange_connected":False,
            "orders_submitted_to_exchange":0,"live_trading_approved":False,
            "limitations":"Reproducibility proves deterministic computations for available inputs; not authentic data, first publication, tradable availability, causality or a profitable strategy."}
    (directory/"bundle.json").write_bytes(_bytes(bundle))
    return bundle

def verify_bundle(directory,raw_news_path,ohlcv_path):
    directory=Path(directory)
    bundle=json.loads((directory/"bundle.json").read_text(encoding="utf-8"))
    if bundle.get("version")!="V141.0" or set(bundle.get("output_sha256",{}))!=set(ARTIFACTS):
        raise ValueError("INVALID_BUNDLE")
    settings=bundle["input_manifest"]["settings"]
    artifacts=build(raw_news_path,ohlcv_path,settings["topic"],settings["observed_at"],
                    settings["min_samples"],settings["cluster_window_minutes"])
    for name in ARTIFACTS:
        path=directory/(name+".json")
        if not path.is_file() or path.read_bytes()!=_bytes(artifacts[name]):
            raise ValueError("OUTPUT_REPLAY_MISMATCH:"+name)
        if _hash(artifacts[name])!=bundle["output_sha256"][name]:
            raise ValueError("OUTPUT_HASH_MISMATCH:"+name)
    files={"raw_news":raw_news_path,"ohlcv_csv":ohlcv_path,
           "taxonomy":directory/"taxonomy.json","event_study":directory/"event_study.json",
           "clusters":directory/"clusters.json"}
    expected=manifest(files,settings)
    if expected!=bundle["input_manifest"]:
        raise ValueError("INPUT_MANIFEST_MISMATCH")
    return {"version":"V141.0","status":"REPLAY_MATCHED_EXACT_INPUTS_AND_OUTPUTS",
            "reproducible":True,"artifact_count":len(ARTIFACTS),
            "first_tradable_news_availability_verified":False,
            "orders_submitted_to_exchange":0,"live_trading_approved":False,
            "validated_edge":False}

def main():
    p=argparse.ArgumentParser(description="V141 offline reproducible news research")
    sub=p.add_subparsers(dest="command",required=True)
    create=sub.add_parser("create")
    create.add_argument("raw_news",type=Path)
    create.add_argument("ohlcv",type=Path)
    create.add_argument("output_dir",type=Path)
    create.add_argument("--topic",required=True,choices=["BTC","ETH","SOL","MACRO"])
    create.add_argument("--observed-at",required=True)
    create.add_argument("--min-samples",type=int,default=5)
    create.add_argument("--cluster-window-minutes",type=int,default=60)
    verify=sub.add_parser("verify")
    verify.add_argument("output_dir",type=Path)
    verify.add_argument("raw_news",type=Path)
    verify.add_argument("ohlcv",type=Path)
    args=p.parse_args()
    if args.command=="create":
        result=write_bundle(args.output_dir,args.raw_news,args.ohlcv,args.topic,
                            args.observed_at,args.min_samples,args.cluster_window_minutes)
    else:
        result=verify_bundle(args.output_dir,args.raw_news,args.ohlcv)
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
