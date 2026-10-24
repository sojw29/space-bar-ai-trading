"""V79 single-command read-only PC diagnostics and historical issue audit."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from one_command_diagnostics_v74 import diagnose
from diagnostic_trends_v77 import analyze
from diagnostic_triage_v78 import triage

def audit(repo, reports=None, log=None, now=None):
    repo = Path(repo).resolve()
    reports = Path(reports).resolve() if reports else repo / "reports"
    log = Path(log).resolve() if log else reports / "v76" / "diagnostics.jsonl"
    now = now or datetime.now(timezone.utc)
    current = diagnose(repo, reports, now=now)
    history = analyze(log)
    priorities = triage(log)
    issues = []
    if current["status"] != "LOCAL_DIAGNOSTICS_PASS":
        issues.append("CURRENT_DIAGNOSTICS_" + current["status"])
    if history["status"] != "ANALYZED" or priorities["status"] == "INSUFFICIENT_DATA":
        issues.append("HISTORY_NOT_AVAILABLE")
    if priorities["status"] == "REVIEW_PRIORITIES":
        issues.append("HISTORICAL_ISSUES_RECORDED")
    if current["status"] == "BLOCKED":
        status = "BLOCKED"
    elif current["status"] == "REVIEW" or issues:
        status = "REVIEW"
    else:
        status = "LOCAL_AUDIT_PASS"
    return {"version": "V79.0", "generated_utc": now.isoformat(),
            "status": status, "issues": issues, "current": current,
            "history": history, "triage": priorities,
            "research_only": True, "automatic_repair": False,
            "live_trading_approved": False,
            "note": "Passing local audit does not validate a trading strategy."}

def main():
    parser = argparse.ArgumentParser(description="Offline local research system audit")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--reports", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = audit(args.repo, args.reports, args.log)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("SPACE BAR AI | INTEGRATED LOCAL AUDIT")
        print("Current:", result["current"]["status"])
        print("History:", result["history"]["status"])
        print("Priorities:", result["triage"]["status"])
        print("Overall:", result["status"])
        for issue in result["issues"]:
            print("NOTICE:", issue)
        print("Live trading: DISABLED")
    return 1 if result["status"] == "BLOCKED" else 0

if __name__ == "__main__":
    raise SystemExit(main())
