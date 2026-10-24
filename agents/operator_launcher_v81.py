"""V81 safe offline operator launcher for Windows and Linux.

Only allowlisted read-only commands. No shell, no subprocess, no trading.
"""
import argparse
import json
from pathlib import Path
from integration_contract_v80 import verify
from integrated_local_audit_v79 import audit
from pc_readiness_v75 import checklist

ALLOWED = ("self-test", "pc-check", "audit")

def launch(action, repo=None, reports=None, log=None):
    if action not in ALLOWED:
        raise ValueError("ACTION_NOT_ALLOWED")
    repo = Path(repo).resolve() if repo else Path(__file__).resolve().parent.parent
    if action == "self-test":
        result = verify()
    elif action == "pc-check":
        result = checklist(repo, reports)
    else:
        result = audit(repo, reports, log)
    return {"version": "V81.0", "action": action, "status": result["status"],
            "result": result, "research_only": True,
            "live_trading_approved": False,
            "note": "Offline inspection only; no orders, remote server or automatic repairs."}

def main():
    parser = argparse.ArgumentParser(description="SPACE BAR safe local operator launcher")
    parser.add_argument("action", choices=ALLOWED, nargs="?", default="pc-check")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--reports", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.log and args.action != "audit":
        parser.error("--log is only supported with audit")
    result = launch(args.action, args.repo, args.reports, args.log)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("SPACE BAR AI | OFFLINE OPERATOR")
        print("Action:", result["action"])
        print("Status:", result["status"])
        if result["action"] == "pc-check":
            for step in result["result"]["next_steps"]:
                print("NEXT:", step)
        if result["action"] == "audit":
            for issue in result["result"]["issues"]:
                print("NOTICE:", issue)
        print("Live trading: DISABLED")
    return 1 if result["status"] in ("BLOCKED", "FAIL", "INSUFFICIENT_DATA") else 0

if __name__ == "__main__":
    raise SystemExit(main())
