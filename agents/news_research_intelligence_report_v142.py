"""V142 offline Markdown report for V141 reproducible news research bundles."""
import argparse
import json
import math
from pathlib import Path
from news_research_reproducibility_v141 import ARTIFACTS, verify_bundle

MAX_JSON_BYTES=4_000_000

def _cell(value):
    return str(value).replace("|","\\|").replace("\n"," ").replace("\r"," ").replace("<","&lt;").replace(">","&gt;")

def _metric(value):
    if value is None:
        return "N/A"
    if type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError("INVALID_METRIC")
    return f"{value:+.4f}"

def render(bundle,artifacts,verification=None):
    if not isinstance(bundle,dict) or bundle.get("version")!="V141.0":
        raise ValueError("INVALID_BUNDLE")
    if not isinstance(artifacts,dict) or set(artifacts)!=set(ARTIFACTS):
        raise ValueError("INVALID_ARTIFACTS")
    pipeline=artifacts["pipeline"]
    groups=artifacts["clusters"]
    adjusted=artifacts["adjusted_statistics"]
    comparison=artifacts["comparison"]
    if (pipeline.get("version")!="V132.0" or groups.get("version")!="V136.0"
        or adjusted.get("version")!="V137.0" or comparison.get("version")!="V138.0"):
        raise ValueError("INVALID_STAGES")
    rows=comparison.get("rows")
    if not isinstance(rows,list) or len(rows)>300:
        raise ValueError("INVALID_COMPARISON")
    manifest=bundle.get("input_manifest",{})
    settings=manifest.get("settings",{})
    if not isinstance(settings,dict):
        raise ValueError("INVALID_SETTINGS")
    verified=bool(verification and verification.get("reproducible") is True)
    lines=[
        "# SPACE BAR — News Research Intelligence Report (V142)",
        "",
        "> **OFFLINE RESEARCH ONLY.** No trading advice or validated edge.",
        "",
        "## Reproducibility",
        "",
        "- Exact offline replay verified in this invocation: **"+("YES" if verified else "NOT CHECKED")+"**",
        "- Topic: **"+_cell(settings.get("topic","UNKNOWN"))+"**",
        "- Declared observation time: **"+_cell(settings.get("observed_at","UNKNOWN"))+"**",
        "- Input manifest SHA-256: "+_cell(manifest.get("manifest_sha256","UNKNOWN")),
        "- Historical first tradable news availability: **UNVERIFIED**",
        "- Event identity and causal impact: **UNVERIFIED**",
        "",
        "## News Coverage",
        "",
        "- Normalized articles: **"+str(groups.get("article_count",0))+"**",
        "- Heuristic coverage groups: **"+str(groups.get("cluster_count",0))+"**",
        "- Potentially repeated entries: **"+str(groups.get("potentially_repeated_articles",0))+"**",
        "",
        "## Article vs Cluster-Adjusted Descriptive Statistics",
        "",
        "| Category | Horizon | Article samples | Group samples | Removed | Mean delta (pp) | Positive-rate delta (pp) |",
        "|---|---|---:|---:|---:|---:|---:|"
    ]
    for row in sorted(rows,key=lambda x:(str(x.get("category","")),str(x.get("horizon","")))):
        if not isinstance(row,dict) or not isinstance(row.get("changes"),dict):
            raise ValueError("INVALID_ROW")
        changes=row["changes"]
        lines.append("| "+" | ".join([
            _cell(row.get("category","UNKNOWN")),_cell(row.get("horizon","UNKNOWN")),
            _cell(row.get("article_samples","?")),_cell(row.get("cluster_adjusted_samples","?")),
            _cell(row.get("potentially_repeated_samples_removed","?")),
            _metric(changes.get("mean_return_pct")),_metric(changes.get("positive_observation_rate_pct"))
        ])+" |")
    warnings=pipeline.get("guardian",{}).get("warnings",[])
    if not isinstance(warnings,list):
        raise ValueError("INVALID_WARNINGS")
    lines.extend(["","## Research Warnings",""])
    if not warnings:
        lines.append("- No additional pipeline warnings recorded; research limitations remain.")
    for warning in warnings[:100]:
        lines.append("- "+_cell(warning.get("code","UNKNOWN") if isinstance(warning,dict) else warning))
    lines.extend(["","## Interpretation Limits","",
        "- Grouping by URL/headline and time is heuristic, not verified event identity.",
        "- GDELT seen time does not prove original publication or first market availability.",
        "- Correlated observations may remain; descriptive returns do not imply causality.",
        "- Reproducible outputs do not establish significance or executable performance.",
        "- No exchange orders, live trading approval or verified trading edge.",""])
    return "\n".join(lines)

def load_bundle(directory):
    directory=Path(directory)
    items={}
    for name in ARTIFACTS:
        path=directory/(name+".json")
        if path.stat().st_size>MAX_JSON_BYTES:
            raise ValueError("INPUT_TOO_LARGE")
        items[name]=json.loads(path.read_text(encoding="utf-8"))
    path=directory/"bundle.json"
    if path.stat().st_size>MAX_JSON_BYTES:
        raise ValueError("INPUT_TOO_LARGE")
    return json.loads(path.read_text(encoding="utf-8")),items

def main():
    p=argparse.ArgumentParser(description="V142 offline Markdown news research report")
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
    markdown=render(bundle,artifacts,verification)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(markdown,encoding="utf-8")
    else:
        print(markdown)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
