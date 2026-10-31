"""V240 research provider preflight: no HTTP, credentials, inference, or orders.

Produces a provider-agnostic dry-run envelope only. Deliberately excludes
secrets and URLs to avoid accidental network execution.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from model_output_validator_v237 import canonical
from model_adapter_contract_v236 import AGENTS
from agent_research_runtime_v233 import SYMBOLS, utc_time

class ProviderNotEnabled(RuntimeError):
    pass

def preflight(bundle, *, dry_run=False, now=None):
    if dry_run is not True:
        raise ProviderNotEnabled("DRY_RUN_REQUIRED")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("NAIVE_NOW")
    now = now.astimezone(timezone.utc)
    if not isinstance(bundle, dict) or bundle.get("version") != "V236.0" or bundle.get("type") != "UNEXECUTED_MODEL_ADAPTER_REQUESTS":
        raise ValueError("INVALID_BUNDLE")
    for key, expected in (("research_only", True), ("orders_enabled", False),
                          ("model_inference_performed", False), ("ai_agents_running", False),
                          ("trade_signals_available", False), ("network_access_required", False)):
        if bundle.get(key) is not expected:
            raise ValueError("UNSAFE_FLAGS")
    source = utc_time(bundle.get("source_generated_at_utc"))
    created = utc_time(bundle.get("generated_at_utc"))
    if not source <= created <= now or not 0 <= (now-source).total_seconds() <= 8*3600:
        raise ValueError("INVALID_PROVENANCE")
    requests = bundle.get("requests")
    if not isinstance(requests, list) or len(requests) != 4:
        raise ValueError("INVALID_REQUESTS")
    common_facts = None
    for expected_agent, request in zip(AGENTS, requests):
        if not isinstance(request, dict) or request.get("agent") != expected_agent or request.get("mode") != "OFFLINE_INPUT_ONLY" or request.get("trade_authorization") != "DENIED":
            raise ValueError("UNSAFE_AGENT")
        instruction = request.get("instruction")
        if not isinstance(instruction, str) or not 1 <= len(instruction) <= 800 or "Do not recommend trades" not in instruction:
            raise ValueError("INVALID_INSTRUCTION")
        facts = request.get("facts")
        if not isinstance(facts, dict) or not isinstance(facts.get("markets"), list) or len(facts["markets"]) != 3:
            raise ValueError("INVALID_FACTS")
        if type(facts.get("trend_classifications_differ")) is not bool or type(facts.get("volume_data_availability_differs")) is not bool:
            raise ValueError("INVALID_COMPARISON")
        import math
        for symbol, market in zip(SYMBOLS, facts["markets"]):
            if not isinstance(market, dict) or market.get("symbol") != symbol or market.get("trend") not in ("SMA50_ABOVE_SMA200", "SMA50_BELOW_SMA200", "SMA_EQUAL"):
                raise ValueError("INVALID_MARKET")
            ratio = market.get("volume_ratio_20")
            if ratio is not None and (type(ratio) not in (int, float) or not math.isfinite(ratio) or not 0 <= ratio < 1e12):
                raise ValueError("INVALID_RATIO")
        if common_facts is None:
            common_facts = canonical(facts)
        elif canonical(facts) != common_facts:
            raise ValueError("INCONSISTENT_AGENT_FACTS")
    return {"version": "V240.0", "type": "PROVIDER_TRANSPORT_DRY_RUN_PREFLIGHT",
            "created_at_utc": now.isoformat(), "source_generated_at_utc": source.isoformat(),
            "request_sha256": hashlib.sha256(canonical(bundle)).hexdigest(),
            "agent_order": list(AGENTS), "request_count": len(requests),
            "research_only": True, "orders_enabled": False, "network_enabled": False,
            "model_inference_performed": False, "trade_signals_available": False,
            "provider_configured": False, "credentials_included": False,
            "status": "VALIDATED_NOT_DISPATCHED"}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("request_bundle")
    parser.add_argument("destination")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    target = Path(args.destination)
    try:
        bundle = json.loads(Path(args.request_bundle).read_text(encoding="utf-8"))
        output = preflight(bundle, dry_run=args.dry_run)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(output, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    except (ValueError, TypeError, KeyError, OSError, ProviderNotEnabled):
        target.unlink(missing_ok=True)
        raise

if __name__ == "__main__":
    main()
