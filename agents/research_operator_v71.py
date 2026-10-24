"""V71 offline operator status snapshot; no server, network, or order execution."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from research_recovery_v70 import inspect_journal
from research_manifest_v68 import inspect_bundle

def read_json(path):
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except (OSError, ValueError, UnicodeError):
        return None

def snapshot(reports, now=None, max_age_hours=24):
    now = now or datetime.now(timezone.utc)
    manifest = inspect_bundle(reports)
    journal = inspect_journal(reports / "v69/runs.jsonl")
    health = read_json(reports / "v66/health.json")
    blockers, warnings = [], []
    if manifest["status"] != "CONSISTENT_BUNDLE":
        blockers.append("REPORT_BUNDLE_INCONSISTENT")
    if journal["status"] != "CHAIN_VALID":
        blockers.append("JOURNAL_INVALID_OR_MISSING")
    if health is None or health.get("version") != "V66.0":
        blockers.append("HEALTH_REPORT_MISSING")
    else:
        if health.get("live_trading_approved") is not False:
            blockers.append("UNSAFE_HEALTH_REPORT")
        if health.get("status") == "BLOCKED":
            blockers.append("RESEARCH_HEALTH_BLOCKED")
        elif health.get("status") == "REVIEW":
            warnings.append("RESEARCH_HEALTH_REVIEW")
        elif health.get("status") != "RESEARCH_DATA_CHECKS_PASS":
            blockers.append("UNKNOWN_HEALTH_STATUS")
        try:
            stamp = datetime.fromisoformat(health["generated_utc"].replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                raise ValueError("naive timestamp")
            age = (now - stamp.astimezone(timezone.utc)).total_seconds()
            if age < -300 or age > max_age_hours * 3600:
                blockers.append("HEALTH_REPORT_STALE_OR_FUTURE")
        except (KeyError, AttributeError, TypeError, ValueError):
            blockers.append("INVALID_HEALTH_TIMESTAMP")
    status = "BLOCKED" if blockers else "REVIEW" if warnings else "OBSERVATION_READY"
    return {"version": "V71.0", "generated_utc": now.isoformat(), "status": status,
            "blockers": sorted(set(blockers)), "warnings": sorted(set(warnings)),
            "journal_valid_entries": journal["valid_prefix_entries"],
            "journal_issue": journal["issue"],
            "report_hashes": {k: v["sha256"] for k, v in manifest["reports"].items()},
            "research_only": True, "independent_oos_verified": False,
            "live_trading_approved": False,
            "note": "Observation readiness is not strategy validation or trading approval."}

def main():
    parser = argparse.ArgumentParser(description="Offline operator status summary")
    parser.add_argument("--reports", type=Path, default=Path("reports"))
    parser.add_argument("--output", type=Path, default=Path("reports/v71/operator_status.json"))
    args = parser.parse_args()
    result = snapshot(args.reports)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "BLOCKED" else 0

if __name__ == "__main__":
    raise SystemExit(main())
