"""V77 read-only offline diagnostic history trends; no exchange access."""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

STATUSES = {"BLOCKED", "REVIEW", "LOCAL_DIAGNOSTICS_PASS"}

def analyze(path, limit=1000):
    if limit < 1:
        raise ValueError("INVALID_LIMIT")
    summary = {"version": "V77.0", "status": "INSUFFICIENT_DATA",
               "total_runs": 0, "counts": {k: 0 for k in sorted(STATUSES)},
               "latest_status": None, "status_changes": 0,
               "top_blockers": [], "top_warnings": [], "issues": [],
               "research_only": True, "live_trading_approved": False}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        summary["issues"].append("LOG_MISSING_OR_UNREADABLE")
        return summary
    if not lines:
        summary["issues"].append("LOG_EMPTY")
        return summary
    if len(lines) > limit:
        summary["issues"].append("LOG_EXCEEDS_LIMIT")
        return summary
    events = []
    for number, line in enumerate(lines, 1):
        try:
            item = json.loads(line)
            if not isinstance(item, dict) or item.get("version") != "V76.0":
                raise ValueError("wrong version")
            if item.get("status") not in STATUSES or item.get("live_trading_approved") is not False:
                raise ValueError("unsafe status")
            if not isinstance(item.get("blocker_codes"), list) or not isinstance(item.get("warning_codes"), list):
                raise ValueError("invalid codes")
            if not all(isinstance(x, str) and x.isupper() and len(x) <= 80 for x in item["blocker_codes"] + item["warning_codes"]):
                raise ValueError("invalid code contents")
            timestamp = datetime.fromisoformat(item["recorded_utc"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                raise ValueError("naive timestamp")
        except (ValueError, TypeError, KeyError, AttributeError):
            summary["issues"].append("INVALID_EVENT_LINE_" + str(number))
            return summary
        events.append(item)
    counts = Counter(x["status"] for x in events)
    summary["total_runs"] = len(events)
    summary["counts"] = {key: counts[key] for key in sorted(STATUSES)}
    summary["latest_status"] = events[-1]["status"]
    summary["status_changes"] = sum(a["status"] != b["status"] for a, b in zip(events, events[1:]))
    blockers = Counter(x for event in events for x in event["blocker_codes"])
    warnings = Counter(x for event in events for x in event["warning_codes"])
    summary["top_blockers"] = [{"code": k, "count": v} for k, v in blockers.most_common(5)]
    summary["top_warnings"] = [{"code": k, "count": v} for k, v in warnings.most_common(5)]
    summary["status"] = "ANALYZED"
    return summary

def main():
    parser = argparse.ArgumentParser(description="Offline local diagnostic trend summary")
    parser.add_argument("--log", type=Path, default=Path("reports/v76/diagnostics.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("reports/v77/trends.json"))
    args = parser.parse_args()
    result = analyze(args.log)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "ANALYZED" else 1

if __name__ == "__main__":
    raise SystemExit(main())
