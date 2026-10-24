"""V98 end-to-end offline integration verification.

Creates isolated local fixtures; never contacts exchanges or submits orders.
"""
import argparse
import json
import tempfile
from pathlib import Path
from unified_launcher_v97 import execute
from operation_journal_v90 import record_event
from operation_health_v91 import summarize
from mobile_html_report_v88 import convert

def verify():
    checks = []
    def check(name, condition):
        checks.append({"name": name, "status": "PASS" if condition else "FAIL"})
    with tempfile.TemporaryDirectory(prefix="spacebar-v98-") as tmp:
        root = Path(tmp)
        reports = root / "reports"
        # The empty fixture must fail closed; a report may still be generated
        # with BLOCKED/REVIEW diagnostic status.
        ready = execute("readiness", repo=root)
        alerts = execute("alerts", repo=root)
        check("READINESS_FAIL_CLOSED", ready["status"] == "BLOCKED")
        check("ALERTS_FAIL_CLOSED", alerts["status"] == "CRITICAL")
        check("NO_LIVE_TRADING", ready["live_trading_approved"] is False and
              alerts["live_trading_approved"] is False)
        report = execute("report", repo=root)
        output = reports / "v97"
        json_path = output / "mobile_status.json"
        html_path = output / "mobile_status.html"
        check("REPORT_FILES_CREATED", json_path.is_file() and html_path.is_file())
        if json_path.is_file() and html_path.is_file():
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            html = html_path.read_text(encoding="utf-8")
            check("REPORT_SANITIZED", payload.get("transport") == "LOCAL_FILE_ONLY" and
                  payload.get("live_trading_approved") is False and
                  "LIVE TRADING DISABLED" in html)
            check("REPORT_STATUS_NOT_PROMOTED",
                  payload.get("overall_status") in ("BLOCKED", "REVIEW") and
                  report["status"] in ("BLOCKED", "REVIEW"))
        else:
            check("REPORT_SANITIZED", False)
            check("REPORT_STATUS_NOT_PROMOTED", False)
        journal = reports / "v90" / "operations.jsonl"
        event = {"version": "V90.0", "timestamp_utc": "2026-10-24T00:00:00+00:00",
                 "operation": "MOBILE_REPORT", "result": "FAILED",
                 "status": "ERROR", "research_only": True,
                 "live_trading_approved": False}
        record_event(journal, event)
        health = summarize(journal)
        check("FAILED_OPERATION_BLOCKS", health["status"] == "BLOCKED")
        check("NO_AUTOMATED_ORDERS", all(
            item["live_trading_approved"] is False
            for item in (ready, alerts, report)))
    return {"version": "V98.0",
            "status": "INTEGRATION_PASS" if all(x["status"] == "PASS" for x in checks)
                      else "INTEGRATION_FAIL",
            "checks": checks, "passed": sum(x["status"] == "PASS" for x in checks),
            "total": len(checks), "research_only": True,
            "live_trading_approved": False,
            "scope": "OFFLINE_LOCAL_REPORTING_ONLY"}

def main():
    parser = argparse.ArgumentParser(description="V98 isolated offline integration verification")
    parser.parse_args()
    result = verify()
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "INTEGRATION_PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
