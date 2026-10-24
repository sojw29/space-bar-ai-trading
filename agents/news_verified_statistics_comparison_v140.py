"""V140 fail-closed news statistics comparison with input-manifest checks.

Matching V139 manifests confirm byte-identical supplied inputs and declared
settings only. They do NOT establish original news availability or causality.
"""
import argparse
import json
from pathlib import Path

from news_data_provenance_v139 import compare as compare_manifests
from news_statistics_comparison_v138 import compare as compare_statistics

MAX_INPUT_BYTES=4_000_000

def verified_compare(article_stats,adjusted_stats,article_manifest,adjusted_manifest):
    provenance=compare_manifests(article_manifest,adjusted_manifest)
    if not provenance["exact_input_and_settings_match"]:
        raise ValueError("INPUT_PROVENANCE_MISMATCH")
    # Input manifests match, but the caller could still supply aggregates
    # generated from unrelated data. Explicitly avoid claiming output linkage.
    statistics=compare_statistics(article_stats,adjusted_stats)
    return {
        "version":"V140.0",
        "status":"MATCHING_INPUT_MANIFESTS_DESCRIPTIVE_COMPARISON",
        "provenance":provenance,
        "comparison":statistics,
        "input_bytes_and_declared_settings_match":True,
        "statistics_derived_from_manifest_inputs_verified":False,
        "news_first_market_availability_verified":False,
        "causal_effect_established":False,
        "validated_edge":False,
        "research_only":True,
        "simulation_only":True,
        "exchange_connected":False,
        "orders_submitted_to_exchange":0,
        "live_trading_approved":False,
        "limitations":"Matching V139 input manifests do not prove that the supplied V130/V137 aggregate outputs were computed from those files. For stronger lineage, calculate and bind output hashes in one reproducible pipeline. No original publication timing, causal effect or tradable edge is verified."
    }

def main():
    p=argparse.ArgumentParser(description="V140 offline manifest-gated descriptive comparison")
    p.add_argument("v130_statistics_json",type=Path)
    p.add_argument("v137_statistics_json",type=Path)
    p.add_argument("v130_input_manifest_json",type=Path)
    p.add_argument("v137_input_manifest_json",type=Path)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    items=[]
    for path in (args.v130_statistics_json,args.v137_statistics_json,
                 args.v130_input_manifest_json,args.v137_input_manifest_json):
        if path.stat().st_size>MAX_INPUT_BYTES:
            raise ValueError("INPUT_TOO_LARGE")
        items.append(json.loads(path.read_text(encoding="utf-8")))
    result=verified_compare(*items)
    encoded=json.dumps(result,indent=2,ensure_ascii=False)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(encoded,encoding="utf-8")
    else:
        print(encoded,end="")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
