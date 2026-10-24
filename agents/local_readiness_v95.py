"""V95 local readiness gate for diagnostics and report generation.

A PASS is a *local reporting readiness* result, never permission to trade.
"""
import argparse
import json
from pathlib import Path
from alerts_dashboard_v94 import dashboard_with_alerts
from mobile_html_report_v88 import render

def assess(repo=None, reports=None, log=None, journal=None):
    data = dashboard_with_alerts(repo=repo, reports=reports, log=log, journal=journal)
    checks = []
    def check(code, ok, detail):
        checks.append({"code": code, "status": "PASS" if ok else "BLOCKED",
                       "detail": detail})
    check("LOCAL_DIAGNOSTICS", data["status"] == "LOCAL_STATUS_PASS",
          "Local diagnostics and report operation checks must pass.")
    check("NO_CRITICAL_ALERTS", data["severity"] != "CRITICAL",
          "No critical local operational alerts may be present.")
    check("OPERATION_JOURNAL", data["operations"]["status"] == "OPERATIONAL",
          "At least one valid local report operation must be recorded.")
    check("NO_RECENT_FAILURE_STREAK", data["operations"]["consecutive_failures"] == 0,
          "Latest local operation sequence must not end in failures.")
    sample = {"schema": "spacebar.local-status.v87",
              "generated_utc": "2026-10-24T00:00:00+00:00",
              "overall_status": "REVIEW", "pc_status": "REVIEW",
              "audit_status": "REVIEW", "history_status": "REVIEW",
              "recent_statuses": [], "status_transitions": [],
              "research_only": True, "live_trading_approved": False,
              "transport": "LOCAL_FILE_ONLY"}
    try:
        html = render(sample)
        html_ok = isinstance(html, str) and "<html" in html.lower()
    except (ValueError, TypeError, KeyError):
        html_ok = False
    check("OFFLINE_HTML_RENDER", html_ok,
          "Sanitized offline mobile HTML rendering must work.")
    overall = "LOCAL_REPORT_READY" if all(x["status"] == "PASS" for x in checks) else "BLOCKED"
    return {"version": "V95.0", "status": overall, "checks": checks,
            "passed": sum(x["status"] == "PASS" for x in checks),
            "total": len(checks), "research_only": True,
            "live_trading_approved": False, "scope": "LOCAL_REPORTING_ONLY"}

def main():
    parser = argparse.ArgumentParser(description="Offline local reporting readiness gate")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--reports", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--journal", type=Path)
    args = parser.parse_args()
    result = assess(args.repo, args.reports, args.log, args.journal)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "LOCAL_REPORT_READY" else 1

if __name__ == "__main__":
    raise SystemExit(main())
