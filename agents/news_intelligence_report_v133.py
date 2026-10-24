"""V133 human-readable, offline V132 news research report generator.

Reports descriptive statistics and limitations, never trading recommendations.
"""
import argparse
import json
from pathlib import Path

def _fmt(value,suffix=""):
    if value is None:
        return "N/A (insufficient samples)"
    if not isinstance(value,(int,float)) or isinstance(value,bool):
        raise ValueError("INVALID_REPORT_METRIC")
    return f"{value:.4f}{suffix}"

def render(report):
    if not isinstance(report,dict) or report.get("version")!="V132.0":
        raise ValueError("INVALID_V132_REPORT")
    collector=report.get("collector")
    taxonomy=report.get("taxonomy")
    event_study=report.get("event_study")
    impact=report.get("impact")
    guardian=report.get("guardian")
    if any(not isinstance(item,dict) for item in (collector,taxonomy,event_study,impact,guardian)):
        raise ValueError("INCOMPLETE_PIPELINE_REPORT")
    if any(part.get("version")!=version for part,version in (
        (collector,"V127.0"),(taxonomy,"V128.0"),(event_study,"V129.0"),
        (impact,"V130.0"),(guardian,"V131.0"))):
        raise ValueError("INCOMPATIBLE_PIPELINE_REPORT")
    counts=taxonomy.get("category_counts")
    groups=impact.get("categories")
    warnings=guardian.get("warnings")
    if not isinstance(counts,dict) or not isinstance(groups,list) or not isinstance(warnings,list):
        raise ValueError("INVALID_REPORT_CONTENT")
    lines=[
        "# SPACE BAR AI TRADING — V133 News Intelligence Research Report",
        "",
        "> **OFFLINE RESEARCH ONLY.** No verified first-tradable news availability,",
        "> causal attribution, predictive edge, exchange connectivity or order execution.",
        "",
        "## Pipeline overview",
        "",
        f"- News topic: {collector.get('topic','UNKNOWN')}",
        f"- Collected article records: {collector.get('count',0)}",
        f"- Descriptive market events: {event_study.get('event_count',0)}",
        f"- Matched articles: {impact.get('matched_articles',0)}",
        f"- Guardian warnings: {guardian.get('warning_count',len(warnings))}",
        "",
        "## Headline categories",
        "",
        "| Category | Article count |",
        "| --- | ---: |",
    ]
    for category,count in sorted(counts.items()):
        if not isinstance(category,str) or not isinstance(count,int) or isinstance(count,bool):
            raise ValueError("INVALID_CATEGORY_COUNTS")
        lines.append(f"| {category.replace('|','/')} | {count} |")
    lines.extend(["","## Descriptive forward returns by category","","| Category | Horizon | Samples | Mean return | Median return | Mean absolute move | Positive observations |",
                  "| --- | --- | ---: | ---: | ---: | ---: | ---: |"])
    for group in sorted(groups,key=lambda x:str(x.get("category",""))):
        if not isinstance(group,dict) or not isinstance(group.get("horizons"),dict):
            raise ValueError("INVALID_CATEGORY_GROUP")
        name=str(group.get("category","UNKNOWN")).replace("|","/")
        for horizon in ("5m","15m","60m"):
            entry=group["horizons"].get(horizon,{})
            if not isinstance(entry,dict):
                raise ValueError("INVALID_HORIZON_METRICS")
            lines.append(f"| {name} | {horizon} | {entry.get('samples',0)} | "
                         f"{_fmt(entry.get('mean_return_pct'),'%')} | "
                         f"{_fmt(entry.get('median_return_pct'),'%')} | "
                         f"{_fmt(entry.get('mean_absolute_move_pct'),'%')} | "
                         f"{_fmt(entry.get('positive_observation_rate_pct'),'%')} |")
    lines.extend(["","## Research risk warnings",""])
    if not warnings:
        lines.append("- No additional warnings reported; general limitations still apply.")
    for warning in warnings:
        if not isinstance(warning,dict):
            raise ValueError("INVALID_WARNING")
        code=str(warning.get("code","UNKNOWN")).replace("\n"," ").replace("|","/")
        detail=str(warning.get("detail","")).replace("\n"," ").replace("|","/")
        lines.append(f"- **{code}**: {detail}")
    lines.extend(["","## Interpretation limits","",
                  "- GDELT seen time is not proven original publication or first market availability.",
                  "- Overlapping headlines may describe one event; observations are not independent.",
                  "- These are descriptive forward candle-close returns, not executable returns.",
                  "- No control group, causal inference, out-of-sample validation or trading edge.",
                  "- The report cannot trigger orders or change risk settings.",""])
    return "\n".join(lines)

def main():
    parser=argparse.ArgumentParser(description="V133 offline V132 news research markdown report")
    parser.add_argument("v132_report_json",type=Path)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    source=args.v132_report_json
    if source.stat().st_size>4_000_000:
        raise ValueError("REPORT_INPUT_TOO_LARGE")
    report=json.loads(source.read_text(encoding="utf-8"))
    result=render(report)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(result,encoding="utf-8")
    else:
        print(result,end="")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
