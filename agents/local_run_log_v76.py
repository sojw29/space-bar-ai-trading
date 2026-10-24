"""V76 offline diagnostic execution log, sanitized and non-trading."""
import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from one_command_diagnostics_v74 import diagnose

ALLOWED_STATUSES = {"BLOCKED", "REVIEW", "LOCAL_DIAGNOSTICS_PASS"}

def record_run(repo, log_path, reports=None, now=None):
    now = now or datetime.now(timezone.utc)
    result = diagnose(repo, reports, now=now)
    if result["status"] not in ALLOWED_STATUSES:
        raise ValueError("UNKNOWN_DIAGNOSTIC_STATUS")
    # Only write a narrow allowlist; do not copy arbitrary report payloads,
    # API keys, user paths, or environment variables into the log.
    event = {"version": "V76.0", "recorded_utc": now.astimezone(timezone.utc).isoformat(),
             "status": result["status"],
             "environment_status": result["environment"]["status"],
             "research_status": result["research"]["status"],
             "blocker_codes": result["blockers"], "warning_codes": result["warnings"],
             "research_only": True, "live_trading_approved": False}
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    existing = log_path.read_bytes() if log_path.exists() else b""
    if existing and not existing.endswith(b"\n"):
        raise ValueError("EXISTING_LOG_INCOMPLETE")
    # Atomic replace protects against a partial write, but not concurrent writers.
    fd, tmp = tempfile.mkstemp(prefix=".v76-", dir=log_path.parent)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(existing)
            file.write((json.dumps(event, sort_keys=True) + "\n").encode("utf-8"))
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp, log_path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return event

def main():
    parser = argparse.ArgumentParser(description="Offline diagnostic log; no trading")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--reports", type=Path)
    parser.add_argument("--log", type=Path, default=Path("reports/v76/diagnostics.jsonl"))
    args = parser.parse_args()
    try:
        result = record_run(args.repo, args.log, args.reports)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}))
        return 1
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "BLOCKED" else 0

if __name__ == "__main__":
    raise SystemExit(main())
