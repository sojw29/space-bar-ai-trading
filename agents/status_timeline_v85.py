"""V85 read-only status timeline for sanitized V76 diagnostic logs."""
import argparse
import json
from pathlib import Path
from diagnostic_trends_v77 import analyze

def timeline(log_path, limit=1000, recent=20):
    if not 1 <= recent <= 100:
        raise ValueError("INVALID_RECENT_LIMIT")
    log_path = Path(log_path)
    summary = analyze(log_path, limit=limit)
    result = {"version": "V85.0", "status": "REVIEW",
              "events": [], "transitions": [], "total_runs": summary["total_runs"],
              "issues": list(summary["issues"]), "research_only": True,
              "live_trading_approved": False}
    if summary["status"] != "ANALYZED":
        return result
    # V77 validated every record before this file is parsed.
    lines = log_path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines]
    result["events"] = [
        {"timestamp_utc": event["recorded_utc"], "status": event["status"],
         "blocker_codes": event["blocker_codes"], "warning_codes": event["warning_codes"]}
        for event in events[-recent:]
    ]
    result["transitions"] = [
        {"timestamp_utc": current["recorded_utc"], "from": previous["status"],
         "to": current["status"]}
        for previous, current in zip(events, events[1:])
        if previous["status"] != current["status"]
    ][-recent:]
    result["status"] = "ANALYZED"
    return result

def main():
    parser = argparse.ArgumentParser(description="Offline diagnostic status timeline")
    parser.add_argument("--log", type=Path, default=Path("reports/v76/diagnostics.jsonl"))
    parser.add_argument("--recent", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = timeline(args.log, recent=args.recent)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("SPACE BAR AI | DIAGNOSTIC TIMELINE:", result["status"])
        for item in result["events"]:
            print(item["timestamp_utc"], item["status"])
        for item in result["transitions"]:
            print("CHANGE", item["timestamp_utc"], item["from"], "->", item["to"])
        for issue in result["issues"]:
            print("NOTICE", issue)
        print("Live trading: DISABLED")
    return 0 if result["status"] == "ANALYZED" else 1

if __name__ == "__main__":
    raise SystemExit(main())
