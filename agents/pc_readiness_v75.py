"""V75 read-only PC onboarding readiness and next-step guidance."""
import argparse
import json
from pathlib import Path
from one_command_diagnostics_v74 import diagnose

def checklist(repo, reports=None):
    status = diagnose(repo, reports)
    environment = status["environment"]
    research = status["research"]
    steps = []
    if not environment["checks"]["python_supported"]:
        steps.append("Install Python 3.11+ and rerun diagnostics.")
    if not environment["checks"]["agents_directory_exists"] or not environment["checks"]["v72_cli_exists"]:
        steps.append("Open the full SPACE BAR repository folder.")
    if not environment["checks"]["reports_dir_exists"]:
        steps.append("Generate offline research reports before evaluating research status.")
    if research["status"] == "BLOCKED":
        steps.append("Inspect research blockers; do not assume missing reports mean trading is ready.")
    elif research["status"] == "REVIEW":
        steps.append("Review research warnings and source report freshness.")
    if status["status"] == "LOCAL_DIAGNOSTICS_PASS":
        steps.append("Local observation checks pass. Continue paper-only validation.")
    return {"version": "V75.0", "status": status["status"],
            "environment_status": environment["status"], "research_status": research["status"],
            "next_steps": steps, "diagnostics": status,
            "research_only": True, "live_trading_approved": False}

def main():
    parser = argparse.ArgumentParser(description="Offline PC setup readiness checklist")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--reports", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = checklist(args.repo, args.reports)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("SPACE BAR AI | PC READINESS:", result["status"])
        for i, step in enumerate(result["next_steps"], 1):
            print(str(i) + ".", step)
        print("Live trading: DISABLED")
    return 1 if result["status"] == "BLOCKED" else 0

if __name__ == "__main__":
    raise SystemExit(main())
