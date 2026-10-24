"""V90 sanitized local operation result journal for offline reporting.

Never stores exception messages, local paths, secrets or report payloads.
"""
import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from one_click_report_v89 import generate

ALLOWED = {"SUCCESS", "BLOCKED", "FAILED"}
MAX_EVENTS = 100

def record_event(path, event):
    if not isinstance(event, dict) or set(event) != {
        "version", "timestamp_utc", "operation", "result", "status",
        "research_only", "live_trading_approved"
    }:
        raise ValueError("INVALID_EVENT_SCHEMA")
    if (event["version"] != "V90.0" or event["operation"] != "MOBILE_REPORT"
            or event["result"] not in ALLOWED or
            event["status"] not in ("BLOCKED", "REVIEW", "LOCAL_STATUS_PASS", "ERROR")
            or event["research_only"] is not True
            or event["live_trading_approved"] is not False):
        raise ValueError("UNSAFE_EVENT")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 65536:
        raise ValueError("JOURNAL_TOO_LARGE")
    events = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            old = json.loads(line)
            if not isinstance(old, dict) or old.get("version") != "V90.0" or old.get("live_trading_approved") is not False:
                raise ValueError("INVALID_EXISTING_JOURNAL")
            events.append(old)
    events = (events + [event])[-MAX_EVENTS:]
    fd, temporary = tempfile.mkstemp(prefix=".v90-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            for item in events:
                file.write(json.dumps(item, sort_keys=True) + "\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return event

def run_logged(repo=None, reports=None, log=None, output_dir=None, journal=None, now=None):
    now = now or datetime.now(timezone.utc)
    repo = Path(repo).resolve() if repo else Path(__file__).resolve().parent.parent
    reports = Path(reports).resolve() if reports else repo / "reports"
    journal = Path(journal) if journal else reports / "v90" / "operations.jsonl"
    result = "FAILED"
    status = "ERROR"
    try:
        output = generate(repo=repo, reports=reports, log=log, output_dir=output_dir)
        status = output["status"]
        result = "BLOCKED" if status == "BLOCKED" else "SUCCESS"
    except Exception:
        # Deliberately omit exception text and potentially sensitive paths.
        pass
    event = {"version": "V90.0", "timestamp_utc": now.astimezone(timezone.utc).isoformat(),
             "operation": "MOBILE_REPORT", "result": result, "status": status,
             "research_only": True, "live_trading_approved": False}
    record_event(journal, event)
    return event

def recent_events(path, limit=20):
    if not 1 <= limit <= MAX_EVENTS:
        raise ValueError("INVALID_LIMIT")
    path = Path(path)
    if not path.exists():
        return []
    if path.stat().st_size > 65536:
        raise ValueError("JOURNAL_TOO_LARGE")
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        if not isinstance(item, dict) or item.get("version") != "V90.0" or item.get("live_trading_approved") is not False:
            raise ValueError("INVALID_JOURNAL_EVENT")
        events.append(item)
    return events[-limit:]

def main():
    parser = argparse.ArgumentParser(description="Offline report generation with safe operation journal")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--reports", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--journal", type=Path)
    args = parser.parse_args()
    event = run_logged(args.repo, args.reports, args.log, args.output_dir, args.journal)
    print(json.dumps(event, indent=2))
    return 0 if event["result"] == "SUCCESS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
