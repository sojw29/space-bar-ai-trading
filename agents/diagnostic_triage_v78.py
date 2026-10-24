"""V78 deterministic, offline diagnostic triage; suggestions only, no repair."""
import argparse
import json
from pathlib import Path
from diagnostic_trends_v77 import analyze

GUIDANCE = {
    "RESEARCH_BLOCKED": ("HIGH", "Inspect V71 research blockers and missing reports."),
    "ENVIRONMENT_BLOCKED": ("HIGH", "Check Python version and repository layout with V73."),
    "JOURNAL_INVALID_OR_MISSING": ("HIGH", "Inspect V70 journal diagnosis; preserve original."),
    "REPORT_BUNDLE_INCONSISTENT": ("HIGH", "Regenerate offline reports as one consistent run."),
    "ENVIRONMENT_REVIEW": ("MEDIUM", "Review local setup warnings from V73."),
    "RESEARCH_REVIEW": ("MEDIUM", "Review data freshness and V66 health warnings."),
}
ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

def triage(log_path, limit=1000):
    trends = analyze(log_path, limit=limit)
    result = {"version": "V78.0", "status": "INSUFFICIENT_DATA",
              "total_runs": trends["total_runs"], "priorities": [],
              "issues": list(trends["issues"]), "research_only": True,
              "automatic_repair": False, "live_trading_approved": False}
    if trends["status"] != "ANALYZED":
        return result
    candidates = {}
    for category in ("top_blockers", "top_warnings"):
        for item in trends[category]:
            code = item["code"]
            severity, guidance = GUIDANCE.get(code, ("LOW", "Inspect the original diagnostic report manually."))
            old = candidates.get(code)
            if old is None or item["count"] > old["count"]:
                candidates[code] = {"code": code, "severity": severity,
                                    "count": item["count"], "suggested_action": guidance}
    result["priorities"] = sorted(candidates.values(),
                                  key=lambda x: (ORDER[x["severity"]], -x["count"], x["code"]))
    result["status"] = "REVIEW_PRIORITIES" if result["priorities"] else "NO_RECORDED_ISSUES"
    return result

def main():
    parser = argparse.ArgumentParser(description="Offline issue prioritization")
    parser.add_argument("--log", type=Path, default=Path("reports/v76/diagnostics.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("reports/v78/triage.json"))
    args = parser.parse_args()
    result = triage(args.log)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "INSUFFICIENT_DATA" else 0

if __name__ == "__main__":
    raise SystemExit(main())
