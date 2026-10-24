"""V91 offline operational health summary from validated V90 journal."""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

RESULTS = {"SUCCESS", "BLOCKED", "FAILED"}
STATUSES = {"BLOCKED", "REVIEW", "LOCAL_STATUS_PASS", "ERROR"}
KEYS = {"version", "timestamp_utc", "operation", "result", "status",
        "research_only", "live_trading_approved"}

def summarize(path, limit=100):
    if not 1 <= limit <= 100:
        raise ValueError("INVALID_LIMIT")
    summary = {"version": "V91.0", "status": "REVIEW", "total": 0,
               "counts": {key: 0 for key in sorted(RESULTS)},
               "latest_result": None, "latest_utc": None,
               "consecutive_failures": 0, "issues": [],
               "research_only": True, "live_trading_approved": False}
    path = Path(path)
    try:
        if path.stat().st_size > 65536:
            summary["issues"].append("JOURNAL_TOO_LARGE")
            return summary
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        summary["issues"].append("JOURNAL_MISSING_OR_UNREADABLE")
        return summary
    if not lines:
        summary["issues"].append("JOURNAL_EMPTY")
        return summary
    if len(lines) > 100:
        summary["issues"].append("JOURNAL_EXCEEDS_LIMIT")
        return summary
    events = []
    previous = None
    for index, line in enumerate(lines, 1):
        try:
            event = json.loads(line)
            if not isinstance(event, dict) or set(event) != KEYS:
                raise ValueError("schema")
            if (event["version"] != "V90.0" or event["operation"] != "MOBILE_REPORT"
                    or event["result"] not in RESULTS or event["status"] not in STATUSES
                    or event["research_only"] is not True
                    or event["live_trading_approved"] is not False):
                raise ValueError("invalid")
            stamp = datetime.fromisoformat(event["timestamp_utc"].replace("Z", "+00:00"))
            if stamp.tzinfo is None or stamp.utcoffset() != timezone.utc.utcoffset(stamp):
                raise ValueError("timestamp")
            if previous is not None and stamp < previous:
                raise ValueError("out of order")
            previous = stamp
        except (ValueError, TypeError, KeyError, AttributeError):
            summary["issues"].append("INVALID_EVENT_LINE_" + str(index))
            return summary
        events.append(event)
    events = events[-limit:]
    counts = Counter(e["result"] for e in events)
    failures = 0
    for event in reversed(events):
        if event["result"] != "FAILED":
            break
        failures += 1
    latest = events[-1]
    summary.update(total=len(events), counts={k: counts[k] for k in sorted(RESULTS)},
                   latest_result=latest["result"], latest_utc=latest["timestamp_utc"],
                   consecutive_failures=failures,
                   status="BLOCKED" if latest["result"] in ("FAILED", "BLOCKED") else "OPERATIONAL")
    return summary

def main():
    parser = argparse.ArgumentParser(description="Offline operational health from V90 journal")
    parser.add_argument("--journal", type=Path, default=Path("reports/v90/operations.jsonl"))
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    result = summarize(args.journal, args.limit)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "OPERATIONAL" else 1

if __name__ == "__main__":
    raise SystemExit(main())
