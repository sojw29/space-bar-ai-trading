"""V72 Windows-friendly, read-only local operator CLI. No network or trading."""
import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from research_operator_v71 import snapshot

def render(status):
    names = {"OBSERVATION_READY": "RESEARCH OBSERVATION READY",
             "REVIEW": "MANUAL REVIEW NEEDED", "BLOCKED": "BLOCKED"}
    lines = ["SPACE BAR AI TRADING | LOCAL STATUS",
             "Research status: " + names.get(status["status"], "UNKNOWN"),
             "Journal valid entries: " + str(status["journal_valid_entries"]),
             "Live trading: DISABLED (research only)"]
    if status["blockers"]:
        lines.append("Blockers: " + ", ".join(status["blockers"]))
    if status["warnings"]:
        lines.append("Warnings: " + ", ".join(status["warnings"]))
    return "\n".join(lines)

def run(reports, now=None):
    result = snapshot(reports, now=now)
    return {"version": "V72.0", "generated_utc": (now or datetime.now(timezone.utc)).isoformat(),
            "platform": platform.system(), "python_version": platform.python_version(),
            "research_status": result, "research_only": True,
            "live_trading_approved": False}

def main():
    parser = argparse.ArgumentParser(description="Offline local status; no exchange access")
    parser.add_argument("--reports", type=Path, default=Path("reports"))
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--output", type=Path, help="Optional output JSON file")
    args = parser.parse_args()
    result = run(args.reports)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(render(result["research_status"]))
    return 1 if result["research_status"]["status"] == "BLOCKED" else 0

if __name__ == "__main__":
    sys.exit(main())
