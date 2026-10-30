"""V203 explicit offline research run -> validated snapshot -> atomic publish.

No background polling, no exchange access, no live orders, no optimization.
"""
import argparse
import csv
import hashlib
from datetime import datetime, timezone
import json
import os
import shutil
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
    # Freeze a private copy for the full validation/backtest/provenance pipeline.
    # This isolates ordinary concurrent writes to the source path.
    with tempfile.TemporaryDirectory(prefix="spacebar-v208-") as scratch:
        frozen = Path(scratch) / source.name
        source_digest_before = _sha256_file(source)
        shutil.copyfile(source, frozen)
        frozen.chmod(0o400)  # Defense in depth; not an OS-enforced immutable file.
        frozen_digest = _sha256_file(frozen)
        if source_digest_before != frozen_digest or _sha256_file(source) != frozen_digest:
            raise ValueError("HISTORY_CHANGED_DURING_SNAPSHOT")
        from history_integrity_gate_v206 import inspect_history
        integrity = inspect_history(frozen, timeframe=timeframe)
        if integrity["status"] != "PASS":
            raise ValueError("HISTORY_INTEGRITY_BLOCKED: " + str(integrity["errors"]))
        if _sha256_file(frozen) != frozen_digest:
            raise ValueError("FROZEN_HISTORY_CHANGED_DURING_VALIDATION")
        result = run(frozen, symbol=symbol, timeframe=timeframe)
        repeat = run(frozen, symbol=symbol, timeframe=timeframe)
        canonical = lambda report: json.dumps(report, sort_keys=True, ensure_ascii=False,
                                               allow_nan=False, separators=(",", ":"))
        first_result_hash = hashlib.sha256(canonical(result).encode("utf-8")).hexdigest()
        repeat_result_hash = hashlib.sha256(canonical(repeat).encode("utf-8")).hexdigest()
        if first_result_hash != repeat_result_hash:
            raise ValueError("BACKTEST_NOT_REPRODUCIBLE")
        result["reproducibility_check"] = {
            "version": "V209.0", "status": "PASS", "runs": 2,
            "canonical_result_sha256": first_result_hash,
            "history_sha256": frozen_digest, "research_only": True,
            "orders_allowed": False, "live_trading_approved": False,
            "note": "Two identical offline runs; does not prove market-data authenticity or profitability.",
        }
        from chronological_stability_v210 import assess_stability
        result["chronological_stability"] = assess_stability(frozen)
        from market_regime_diagnostics_v211 import inspect_regimes
        result["market_regime_diagnostics"] = inspect_regimes(frozen)
        from regime_strategy_metrics_v212 import compare_regime_strategy_metrics
        result["regime_strategy_metrics"] = compare_regime_strategy_metrics(frozen)
        from regime_sample_adequacy_v213 import assess_regime_sample_adequacy
        result["regime_sample_adequacy"] = assess_regime_sample_adequacy(result["regime_strategy_metrics"])
        from winrate_uncertainty_v214 import attach_winrate_uncertainty
        result["winrate_uncertainty"] = attach_winrate_uncertainty(result["strategy_scorecard"])
        from return_drawdown_stability_v215 import assess_return_drawdown_stability
        result["return_drawdown_stability"] = assess_return_drawdown_stability(result["regime_strategy_metrics"])
        from regime_strategy_attribution_v212 import assess_regime_strategy_performance
        result["regime_strategy_attribution"] = assess_regime_strategy_performance(frozen)
        result["history_integrity"] = integrity
        render(result)
        if _sha256_file(frozen) != frozen_digest:
            raise ValueError("FROZEN_HISTORY_CHANGED_DURING_BACKTEST")
        with frozen.open(newline="", encoding="utf-8") as stream:
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
            "history_sha256": frozen_digest,
            "source_type": "LOCAL_HISTORICAL_CSV_FROZEN_COPY",
            "history_timestamp_verified": False,
            "data_authenticity_verified": False,
            "realtime": False,
            "research_only": True,
        }
        if _sha256_file(frozen) != frozen_digest:
            raise ValueError("FROZEN_HISTORY_CHANGED_DURING_PROVENANCE")
        raw = json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2)
        if len(raw.encode("utf-8")) > 2_000_000:
            raise ValueError("SCORECARD_TOO_LARGE")
        if _sha256_file(frozen) != frozen_digest:
            raise ValueError("FROZEN_HISTORY_CHANGED_BEFORE_PUBLISH")
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
