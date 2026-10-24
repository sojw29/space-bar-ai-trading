"""V80 offline integration contract verification for V73-V79.

Uses real modules and isolated temporary directories. Never connects to exchanges.
"""
import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from integrated_local_audit_v79 import audit
from diagnostic_trends_v77 import analyze
from diagnostic_triage_v78 import triage
from local_run_log_v76 import record_run

NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)

def verify():
    checks = {}
    with tempfile.TemporaryDirectory(prefix="spacebar-v80-") as temp:
        repo = Path(temp)
        log = repo / "reports" / "v76" / "diagnostics.jsonl"
        initial = audit(repo, log=log, now=NOW)
        checks["missing_repo_blocks"] = initial["status"] == "BLOCKED"
        checks["missing_history_review_flag"] = "HISTORY_NOT_AVAILABLE" in initial["issues"]
        first = record_run(repo, log, now=NOW)
        second = record_run(repo, log, now=NOW)
        checks["recorded_events_remain_blocked"] = first["status"] == second["status"] == "BLOCKED"
        history = analyze(log)
        checks["history_two_events"] = history["status"] == "ANALYZED" and history["total_runs"] == 2
        priorities = triage(log)
        checks["triage_detects_blocker"] = (priorities["status"] == "REVIEW_PRIORITIES"
                                           and any(x["code"] == "RESEARCH_BLOCKED"
                                                   for x in priorities["priorities"]))
        final = audit(repo, log=log, now=NOW)
        checks["history_now_available"] = "HISTORY_NOT_AVAILABLE" not in final["issues"]
        checks["blocked_remains_blocked"] = final["status"] == "BLOCKED"
        checks["live_trading_never_approved"] = all(
            x["live_trading_approved"] is False for x in
            (initial, first, second, history, priorities, final))
        checks["no_automatic_repair"] = final["automatic_repair"] is False
    return {"version": "V80.0", "status": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks, "research_only": True, "live_trading_approved": False}

def main():
    parser = argparse.ArgumentParser(description="Offline V80 integration contract checks")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = verify()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("SPACE BAR AI | V80 INTEGRATION:", result["status"])
        for name, passed in result["checks"].items():
            print("PASS" if passed else "FAIL", name)
        print("Live trading: DISABLED")
    return 0 if result["status"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
