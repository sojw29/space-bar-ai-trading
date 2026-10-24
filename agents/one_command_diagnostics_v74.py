"""V74 one-command offline diagnostics; does not start a trading engine."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from windows_smoke_v73 import inspect_environment
from research_operator_v71 import snapshot

def diagnose(repo, reports=None, now=None):
    repo = Path(repo).resolve()
    reports = Path(reports).resolve() if reports else repo / "reports"
    now = now or datetime.now(timezone.utc)
    env = inspect_environment(repo, reports)
    research = snapshot(reports, now=now)
    blockers = []
    warnings = []
    if env["status"] == "BLOCKED":
        blockers.append("ENVIRONMENT_BLOCKED")
    elif env["status"] == "REVIEW":
        warnings.append("ENVIRONMENT_REVIEW")
    if research["status"] == "BLOCKED":
        blockers.append("RESEARCH_BLOCKED")
    elif research["status"] == "REVIEW":
        warnings.append("RESEARCH_REVIEW")
    status = "BLOCKED" if blockers else "REVIEW" if warnings else "LOCAL_DIAGNOSTICS_PASS"
    return {"version": "V74.0", "generated_utc": now.isoformat(),
            "status": status, "blockers": blockers, "warnings": warnings,
            "environment": env, "research": research,
            "research_only": True, "live_trading_approved": False,
            "note": "Local diagnostics are not evidence of profitable trading."}

def main():
    parser = argparse.ArgumentParser(description="One-command offline PC diagnostic")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--reports", type=Path)
    parser.add_argument("--output", type=Path, help="Optional JSON report destination")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = diagnose(args.repo, args.reports)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("SPACE BAR AI | ONE-COMMAND DIAGNOSTICS")
        print("Overall:", result["status"])
        print("Environment:", result["environment"]["status"])
        print("Research:", result["research"]["status"])
        for issue in result["blockers"] + result["warnings"]:
            print("NOTICE:", issue)
        print("Live trading: DISABLED")
    return 1 if result["status"] == "BLOCKED" else 0

if __name__ == "__main__":
    raise SystemExit(main())
