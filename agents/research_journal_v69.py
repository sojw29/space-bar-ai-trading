"""V69 offline, append-only research execution journal.

Never stores credentials, sends orders, or treats diagnostics as profitability proof.
"""
import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

def canonical(record):
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def digest(record):
    return hashlib.sha256(canonical(record).encode("utf-8")).hexdigest()

def read_journal(path):
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]

def verify(entries):
    previous = "0" * 64
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict) or entry.get("sequence") != index:
            return False
        if entry.get("previous_hash") != previous:
            return False
        body = {k: v for k, v in entry.items() if k != "entry_hash"}
        if entry.get("entry_hash") != digest(body):
            return False
        previous = entry["entry_hash"]
    return True

def append_run(journal_path, manifest_path, health_path, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone-aware now required")
    try:
        entries = read_journal(journal_path)
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError("JOURNAL_CORRUPT") from exc
    if not verify(entries):
        raise ValueError("JOURNAL_CHAIN_INVALID")
    try:
        manifest_bytes = manifest_path.read_bytes()
        health_bytes = health_path.read_bytes()
        manifest = json.loads(manifest_bytes)
        health = json.loads(health_bytes)
    except (OSError, ValueError) as exc:
        raise ValueError("REPORTS_MISSING_OR_INVALID") from exc
    if not isinstance(manifest, dict) or manifest.get("version") != "V68.0":
        raise ValueError("INVALID_MANIFEST")
    if not isinstance(health, dict) or health.get("version") != "V66.0":
        raise ValueError("INVALID_HEALTH")
    if manifest.get("live_trading_approved") is not False or health.get("live_trading_approved") is not False:
        raise ValueError("UNSAFE_REPORT")
    status = "BLOCKED" if manifest.get("status") != "CONSISTENT_BUNDLE" else health.get("status")
    if status not in ("BLOCKED", "REVIEW", "RESEARCH_DATA_CHECKS_PASS"):
        raise ValueError("UNKNOWN_HEALTH_STATUS")
    body = {
        "sequence": len(entries) + 1,
        "recorded_utc": now.astimezone(timezone.utc).isoformat(),
        "previous_hash": entries[-1]["entry_hash"] if entries else "0" * 64,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "health_sha256": hashlib.sha256(health_bytes).hexdigest(),
        "status": status,
        "research_only": True,
        "live_trading_approved": False,
    }
    entry = dict(body, entry_hash=digest(body))
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".v69-", dir=journal_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            for old in entries:
                file.write(canonical(old) + "\n")
            file.write(canonical(entry) + "\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp, journal_path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return entry

def main():
    parser = argparse.ArgumentParser(description="Offline append-only research journal")
    parser.add_argument("--reports", type=Path, default=Path("reports"))
    parser.add_argument("--journal", type=Path, default=Path("reports/v69/runs.jsonl"))
    args = parser.parse_args()
    try:
        result = append_run(args.journal, args.reports / "v68/manifest.json",
                            args.reports / "v66/health.json")
    except ValueError as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}))
        return 1
    print(json.dumps(result, indent=2))
    return 0 if result["status"] != "BLOCKED" else 1

if __name__ == "__main__":
    raise SystemExit(main())
