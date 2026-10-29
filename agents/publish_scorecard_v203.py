"""V203 explicit offline research run -> validated snapshot -> atomic publish.

No background polling, no exchange access, no live orders, no optimization.
"""
import argparse
import json
import os
import tempfile
from pathlib import Path

from multi_strategy_holdout_v105 import run
from strategy_scorecard_html_v199 import render

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "reports" / "strategy_scorecard_latest.json"


def publish(history_csv, output=DEFAULT_OUTPUT, symbol="BTC", timeframe="5m"):
    source = Path(history_csv).resolve(strict=True)
    if not source.is_file() or source.stat().st_size > 200_000_000:
        raise ValueError("INVALID_HISTORY_SOURCE")
    destination = Path(output).resolve()
    if destination.suffix != ".json":
        raise ValueError("INVALID_OUTPUT_EXTENSION")
    if source == destination:
        raise ValueError("SOURCE_OUTPUT_COLLISION")
    result = run(source, symbol=symbol, timeframe=timeframe)
    render(result)  # V199 strict fail-closed schema and safety gate.
    raw = json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2)
    if len(raw.encode("utf-8")) > 2_000_000:
        raise ValueError("SCORECARD_TOO_LARGE")
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
