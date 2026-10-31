"""V243 offline regression matrix for fail-closed pipeline behavior."""
import argparse
import copy
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from offline_network_guard_v242 import run_guarded_pipeline

def evaluate_matrix(source, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("NAIVE_NOW")
    now = now.astimezone(timezone.utc)
    # Fail closed: a baseline failure is not converted into a successful report.
    baseline = run_guarded_pipeline(copy.deepcopy(source), now)
    scenarios = []
    def scenario(name, change):
        altered = copy.deepcopy(source)
        change(altered)
        try:
            run_guarded_pipeline(altered, now)
        except (ValueError, TypeError, KeyError):
            scenarios.append({"scenario": name, "status": "REJECTED_AS_EXPECTED"})
        else:
            raise AssertionError("UNSAFE_SCENARIO_ACCEPTED:" + name)
    scenario("ORDERS_ENABLED", lambda d: d.__setitem__("orders_enabled", True))
    scenario("AI_AGENTS_RUNNING", lambda d: d.__setitem__("ai_agents_running", True))
    scenario("TRADE_SIGNALS_AVAILABLE", lambda d: d.__setitem__("trade_signals_available", True))
    scenario("STALE_SOURCE", lambda d: d.__setitem__("source_generated_at_utc", (now-timedelta(hours=9)).isoformat()))
    scenario("FUTURE_SOURCE", lambda d: d.__setitem__("source_generated_at_utc", (now+timedelta(minutes=1)).isoformat()))
    scenario("MISSING_MARKET", lambda d: d["markets"].pop())
    scenario("DUPLICATE_MARKET", lambda d: d["markets"][1].__setitem__("symbol", d["markets"][0]["symbol"]))
    scenario("UNSAFE_MARKET_AUTHORIZATION", lambda d: d["markets"][0].__setitem__("risk_status", "TRADE_ALLOWED"))
    scenario("NONFINITE_VOLUME", lambda d: d["markets"][0].__setitem__("volume_ratio_20", float("nan")))
    return {"version": "V243.0", "type": "OFFLINE_REGRESSION_MATRIX",
            "generated_at_utc": now.isoformat(), "research_only": True,
            "orders_enabled": False, "network_enabled": False,
            "model_inference_performed": False, "baseline": "PASS",
            "scenarios": scenarios, "rejected_count": len(scenarios),
            "pipeline_request_sha256": baseline["request_sha256"]}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    target = Path(args.destination)
    try:
        data = json.loads(Path(args.source).read_text(encoding="utf-8"))
        result = evaluate_matrix(data)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    except (ValueError, TypeError, KeyError, AssertionError, OSError):
        target.unlink(missing_ok=True)
        raise

if __name__ == "__main__":
    main()
