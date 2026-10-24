"""V87 offline privacy-minimized status export for future mobile viewing.

Local JSON only. Does not start a server, sync files or transmit data.
"""
import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from timeline_dashboard_v86 import dashboard_data

ALLOWED = {"BLOCKED", "REVIEW", "LOCAL_STATUS_PASS", "ANALYZED",
           "INSUFFICIENT_DATA", "LOCAL_DIAGNOSTICS_PASS"}

def create_payload(repo=None, reports=None, log=None, now=None):
    now = now or datetime.now(timezone.utc)
    data = dashboard_data(repo=repo, reports=reports, log=log)
    history = data["timeline"]
    status = data["status"]
    if status not in ("BLOCKED", "REVIEW", "LOCAL_STATUS_PASS"):
        status = "REVIEW"
    return {"schema": "spacebar.local-status.v87", "generated_utc": now.isoformat(),
            "overall_status": status,
            "pc_status": data["current"]["pc_status"],
            "audit_status": data["current"]["audit_status"],
            "history_status": history["status"],
            "recent_statuses": [
                {"timestamp_utc": item["timestamp_utc"], "status": item["status"]}
                for item in history["events"][-10:]],
            "status_transitions": [
                {"timestamp_utc": item["timestamp_utc"], "from": item["from"], "to": item["to"]}
                for item in history["transitions"][-10:]],
            "research_only": True, "live_trading_approved": False,
            "transport": "LOCAL_FILE_ONLY"}

def export(path, repo=None, reports=None, log=None, now=None):
    payload = create_payload(repo=repo, reports=reports, log=log, now=now)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".v87-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(payload, output, indent=2, ensure_ascii=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return payload

def main():
    parser = argparse.ArgumentParser(description="Offline mobile-ready status JSON export")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--reports", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/v87/mobile_status.json"))
    args = parser.parse_args()
    result = export(args.output, repo=args.repo, reports=args.reports, log=args.log)
    print("SPACE BAR AI | LOCAL STATUS EXPORT")
    print("File:", args.output)
    print("Overall:", result["overall_status"])
    print("No network transmission. Live trading: DISABLED")
    return 1 if result["overall_status"] == "BLOCKED" else 0

if __name__ == "__main__":
    raise SystemExit(main())
