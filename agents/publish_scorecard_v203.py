"""V203 explicit offline research run -> validated snapshot -> atomic publish.

No background polling, no exchange access, no live orders, no optimization.
"""
import argparse
import csv
import hashlib
from datetime import datetime, timezone
import json
import os
import tempfile
from pathlib import Path

from multi_strategy_holdout_v105 import run
from strategy_scorecard_html_v199 import render

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "reports" / "strategy_scorecard_latest.json"


def _sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def publish(history_csv, output=DEFAULT_OUTPUT, symbol="BTC", timeframe="5m"):
    source = Path(history_csv).resolve(strict=True)
    if not source.is_file() or source.stat().st_size > 200_000_000:
        raise ValueError("INVALID_HISTORY_SOURCE")
    destination = Path(output).resolve()
    if destination.suffix != ".json":
        raise ValueError("INVALID_OUTPUT_EXTENSION")
    if source == destination:
        raise ValueError("SOURCE_OUTPUT_COLLISION")
    initial_digest = _sha256_file(source)
    from history_integrity_gate_v206 import inspect_history
    integrity = inspect_history(source, timeframe=timeframe)
    if integrity["status"] != "PASS":
        raise ValueError("HISTORY_INTEGRITY_BLOCKED: " + str(integrity["errors"]))
    if _sha256_file(source) != initial_digest:
        raise ValueError("HISTORY_CHANGED_DURING_VALIDATION")
    result = run(source, symbol=symbol, timeframe=timeframe)
    result["history_integrity"] = integrity
    render(result)  # V199 strict fail-closed schema and safety gate.
    # Provenance metadata is descriptive, not independent data authenticity.
    if _sha256_file(source) != initial_digest:
        raise ValueError("HISTORY_CHANGED_DURING_BACKTEST")
    with source.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if "timestamp" not in (reader.fieldnames or []):
            raise ValueError("MISSING_HISTORY_TIMESTAMP")
        last_timestamp = None
        for row in reader:
            last_timestamp = row["timestamp"]
    if last_timestamp is None:
        raise ValueError("EMPTY_HISTORY")
    result["snapshot_provenance"] = {
        "version": "V204.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "history_last_timestamp_raw": str(last_timestamp)[:64],
        "history_sha256": initial_digest,
        "source_type": "LOCAL_HISTORICAL_CSV",
        "history_timestamp_verified": False,
        "data_authenticity_verified": False,
        "realtime": False,
        "research_only": True,
    }
    if _sha256_file(source) != initial_digest:
        raise ValueError("HISTORY_CHANGED_DURING_PROVENANCE")
    raw = json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2)
    if len(raw.encode("utf-8")) > 2_000_000:
        raise ValueError("SCORECARD_TOO_LARGE")
    if _sha256_file(source) != initial_digest:
        raise ValueError("HISTORY_CHANGED_BEFORE_PUBLISH")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replace: failed validation must never corrupt the prior snapshot.
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         dir=destination.parent, suffix=".tmp",
                                         prefix=".scorecard-", delete=False) as handle:
            temp_path = Path(handle.name)
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, destination)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return {"version": "V203.0", "status": "OFFLINE_SNAPSHOT_PUBLISHED",
            "output": str(destination), "strategies": len(result["strategy_scorecard"]["rows"]),
            "research_only": True, "orders_enabled": False,
            "live_trading_approved": False}


def main():
    parser = argparse.ArgumentParser(description="V203 explicit offline holdout scorecard publisher")
    parser.add_argument("history_csv", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--symbol", default="BTC")
    parser.add_argument("--timeframe", default="5m")
    args = parser.parse_args()
    print(json.dumps(publish(args.history_csv, args.output, args.symbol, args.timeframe),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
