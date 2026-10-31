"""V241 end-to-end offline research integration smoke. Never invokes models or orders."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from agent_research_runtime_v233 import build_research
from agent_handoff_audit_v234 import compile_handoff
from research_consistency_review_v235 import review
from model_adapter_contract_v236 import build_adapter_requests
from provider_transport_preflight_v240 import preflight
from offline_model_execution_harness_v238 import execute_offline_fixture

def run_pipeline(source, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("NAIVE_NOW")
    now = now.astimezone(timezone.utc)
    v233 = build_research(source, now)
    v234 = compile_handoff(v233, now)
    v235 = review(v234, now)
    v236 = build_adapter_requests(v235, now)
    v240 = preflight(v236, dry_run=True, now=now)
    v238 = execute_offline_fixture(v236, now=now)
    if v238["request_sha256"] != v240["request_sha256"]:
        raise ValueError("REQUEST_HASH_MISMATCH")
    if any(v.get("orders_enabled") is not False for v in (v233, v234, v235, v236, v240, v238)):
        raise ValueError("ORDER_AUTHORIZATION_DETECTED")
    return {"version": "V241.0", "mode": "OFFLINE_FIXTURE_INTEGRATION_SMOKE",
            "generated_at_utc": now.isoformat(), "source_generated_at_utc": v233["source_generated_at_utc"],
            "research_only": True, "orders_enabled": False, "ai_agents_running": False,
            "model_inference_performed": False, "network_enabled": False,
            "trade_signals_available": False, "validated_for_trading": False,
            "steps": [
                {"version": "V233", "status": "PASS"},
                {"version": "V234", "status": "PASS", "event_count": v234["event_count"]},
                {"version": "V235", "status": "PASS"},
                {"version": "V236", "status": "PASS", "request_count": len(v236["requests"])},
                {"version": "V240", "status": v240["status"]},
                {"version": "V238/V237", "status": "VALIDATED_OFFLINE_MOCK_ONLY",
                 "response_count": len(v238["responses"])}
            ], "request_sha256": v240["request_sha256"]}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    target = Path(args.destination)
    try:
        source = json.loads(Path(args.source).read_text(encoding="utf-8"))
        result = run_pipeline(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    except (ValueError, TypeError, KeyError, OSError):
        target.unlink(missing_ok=True)
        raise

if __name__ == "__main__":
    main()
