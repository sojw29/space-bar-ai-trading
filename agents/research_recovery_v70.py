"""V70 read-only journal recovery diagnosis. Never modifies or repairs records.

A valid prefix is evidence for manual review, NOT permission to truncate.
"""
import argparse
import json
from pathlib import Path
from research_journal_v69 import digest

def inspect_journal(path):
    result = {"version": "V70.0", "status": "REVIEW_REQUIRED",
              "valid_prefix_entries": 0, "total_lines": 0,
              "first_invalid_line": None, "issue": None,
              "manual_recovery_only": True, "auto_repair_performed": False,
              "live_trading_approved": False}
    try:
        with path.open("r", encoding="utf-8") as file:
            lines = file.readlines()
    except (OSError, UnicodeError) as exc:
        result["issue"] = "JOURNAL_UNREADABLE"
        return result
    result["total_lines"] = len(lines)
    if not lines:
        result["issue"] = "EMPTY_JOURNAL"
        return result
    previous = "0" * 64
    for i, line in enumerate(lines, 1):
        try:
            item = json.loads(line)
        except ValueError:
            result["issue"] = "INVALID_JSON"
            result["first_invalid_line"] = i
            return result
        if not isinstance(item, dict) or type(item.get("sequence")) is not int or item["sequence"] != i:
            result["issue"] = "INVALID_SEQUENCE"
        elif item.get("previous_hash") != previous:
            result["issue"] = "BROKEN_HASH_CHAIN"
        elif item.get("entry_hash") != digest({k: v for k, v in item.items() if k != "entry_hash"}):
            result["issue"] = "ENTRY_HASH_MISMATCH"
        else:
            result["valid_prefix_entries"] = i
            previous = item["entry_hash"]
            continue
        result["first_invalid_line"] = i
        return result
    result["status"] = "CHAIN_VALID"
    result["issue"] = None
    return result

def main():
    parser = argparse.ArgumentParser(description="Read-only journal corruption diagnosis")
    parser.add_argument("--journal", type=Path, default=Path("reports/v69/runs.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("reports/v70/recovery_diagnosis.json"))
    args = parser.parse_args()
    result = inspect_journal(args.journal)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "CHAIN_VALID" else 1

if __name__ == "__main__":
    raise SystemExit(main())
