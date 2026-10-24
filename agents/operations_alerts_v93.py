"""V93 deterministic offline operational alerts with safe remediation hints.

Read-only, no notification transport, exchange actions, or auto-remediation.
"""
import argparse
import json
from pathlib import Path
from operations_dashboard_v92 import combined_status

def evaluate(data):
    if not isinstance(data, dict):
        raise ValueError("INVALID_INPUT")
    diagnostics = data.get("diagnostics")
    operations = data.get("operations")
    if not isinstance(diagnostics, dict) or not isinstance(operations, dict):
        raise ValueError("INVALID_COMPONENTS")
    alerts = []
    def add(code, level, message, action):
        alerts.append({"code": code, "level": level, "message": message,
                       "suggested_action": action})
    d = diagnostics.get("status")
    o = operations.get("status")
    streak = operations.get("consecutive_failures")
    if not isinstance(streak, int) or isinstance(streak, bool) or streak < 0:
        streak = 0
        add("INVALID_FAILURE_COUNT", "WARNING", "Failure counter is invalid.",
            "Inspect the local operation journal manually.")
    if d == "BLOCKED":
        add("DIAGNOSTICS_BLOCKED", "CRITICAL", "Local diagnostics are blocked.",
            "Review local PC and audit diagnostics before further research.")
    elif d != "LOCAL_STATUS_PASS":
        add("DIAGNOSTICS_REVIEW", "WARNING", "Local diagnostics require review.",
            "Refresh the local dashboard and inspect diagnostic history.")
    if o == "BLOCKED":
        add("OPERATIONS_BLOCKED", "CRITICAL", "Last local report operation failed or was blocked.",
            "Review the offline report generation workflow.")
    elif o != "OPERATIONAL":
        add("OPERATIONS_REVIEW", "WARNING", "Operation journal is missing or invalid.",
            "Run a local report generation and inspect the journal.")
    if streak >= 3:
        add("REPEATED_FAILURES", "CRITICAL", "Three or more consecutive report failures.",
            "Stop repeated attempts and inspect the local environment.")
    elif streak >= 1:
        add("RECENT_FAILURES", "WARNING", "Recent report generation failures detected.",
            "Check the report output directory and local dependencies.")
    if not alerts:
        add("LOCAL_CHECKS_CLEAR", "INFO", "No local diagnostic or report-operation alerts.",
            "Continue offline research checks; this is not trading approval.")
    severity = "CRITICAL" if any(a["level"] == "CRITICAL" for a in alerts) else (
        "WARNING" if any(a["level"] == "WARNING" for a in alerts) else "INFO")
    return {"version": "V93.0", "severity": severity, "alerts": alerts,
            "research_only": True, "live_trading_approved": False,
            "auto_remediation": False, "notification_transport": "NONE"}

def inspect(repo=None, reports=None, log=None, journal=None):
    return evaluate(combined_status(repo=repo, reports=reports, log=log, journal=journal))

def main():
    parser = argparse.ArgumentParser(description="Offline operational alert assessment")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--reports", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--journal", type=Path)
    args = parser.parse_args()
    result = inspect(args.repo, args.reports, args.log, args.journal)
    print(json.dumps(result, indent=2))
    return 1 if result["severity"] == "CRITICAL" else 0

if __name__ == "__main__":
    raise SystemExit(main())
