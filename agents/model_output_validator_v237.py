"""V237 validates untrusted *offline mock* model responses. Never calls models or trades."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from agent_research_runtime_v233 import SYMBOLS, utc_time
from model_adapter_contract_v236 import AGENTS

ALLOWED = {"OBSERVATION", "INSUFFICIENT_DATA", "UNCERTAIN"}
MAX_TEXT = 480
FORBIDDEN = ("buy", "sell", "long", "short", "leverage", "entry", "stop loss",
             "take profit", "매수", "매도", "롱", "숏", "레버리지", "진입", "손절", "익절")

def canonical(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")

def validate_outputs(request_bundle, candidate, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("NAIVE_NOW")
    now = now.astimezone(timezone.utc)
    if not isinstance(request_bundle, dict) or request_bundle.get("version") != "V236.0" or request_bundle.get("type") != "UNEXECUTED_MODEL_ADAPTER_REQUESTS":
        raise ValueError("INVALID_REQUEST")
    for key, expected in (("research_only", True), ("orders_enabled", False),
                          ("model_inference_performed", False), ("ai_agents_running", False),
                          ("trade_signals_available", False), ("network_access_required", False)):
        if request_bundle.get(key) is not expected:
            raise ValueError("UNSAFE_REQUEST")
    source_time = utc_time(request_bundle.get("source_generated_at_utc"))
    request_time = utc_time(request_bundle.get("generated_at_utc"))
    if not source_time <= request_time <= now or not 0 <= (now-source_time).total_seconds() <= 8*3600:
        raise ValueError("STALE_REQUEST")
    requests = request_bundle.get("requests")
    if not isinstance(requests, list) or len(requests) != 4 or [r.get("agent") for r in requests if isinstance(r, dict)] != list(AGENTS):
        raise ValueError("INVALID_AGENTS")
    for request in requests:
        if request.get("mode") != "OFFLINE_INPUT_ONLY" or request.get("trade_authorization") != "DENIED":
            raise ValueError("UNSAFE_ADAPTER")
        facts = request.get("facts")
        if not isinstance(facts, dict) or not isinstance(facts.get("markets"), list) or [m.get("symbol") for m in facts["markets"] if isinstance(m, dict)] != list(SYMBOLS):
            raise ValueError("INVALID_FACTS")
        if type(facts.get("trend_classifications_differ")) is not bool or type(facts.get("volume_data_availability_differs")) is not bool:
            raise ValueError("INVALID_FLAGS")
    if not isinstance(candidate, dict) or candidate.get("version") != "V237.MOCK.1" or candidate.get("source") != "OFFLINE_FIXTURE_ONLY":
        raise ValueError("UNTRUSTED_OUTPUT_SOURCE")
    if candidate.get("request_sha256") != hashlib.sha256(canonical(request_bundle)).hexdigest():
        raise ValueError("REQUEST_HASH_MISMATCH")
    responses = candidate.get("responses")
    if not isinstance(responses, list) or len(responses) != len(AGENTS):
        raise ValueError("INVALID_RESPONSES")
    safe = []
    for agent in AGENTS:
        matching = [r for r in responses if isinstance(r, dict) and r.get("agent") == agent]
        if len(matching) != 1:
            raise ValueError("MISSING_OR_DUPLICATE_RESPONSE")
        response = matching[0]
        if set(response) != {"agent", "status", "summary", "trade_authorization"}:
            raise ValueError("UNKNOWN_RESPONSE_FIELDS")
        summary = response["summary"]
        if (response["status"] not in ALLOWED or response["trade_authorization"] != "DENIED"
            or not isinstance(summary, str) or not 1 <= len(summary) <= MAX_TEXT
            or any(ord(ch) < 32 and ch not in "\n\t" for ch in summary)
            or any(word in summary.casefold() for word in FORBIDDEN)):
            raise ValueError("UNSAFE_RESPONSE")
        safe.append({"agent": agent, "status": response["status"], "summary": summary,
                     "trade_authorization": "DENIED"})
    return {"version": "V237.0", "type": "VALIDATED_OFFLINE_MOCK_RESPONSES",
            "generated_at_utc": now.isoformat(), "source_generated_at_utc": source_time.isoformat(),
            "request_sha256": candidate["request_sha256"],
            "research_only": True, "orders_enabled": False, "ai_agents_running": False,
            "model_inference_performed": False, "trade_signals_available": False,
            "validated_for_trading": False, "responses": safe,
            "warning": "Keyword screening is not a reliable safety filter; no real model outputs are authorized."}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("request_bundle")
    parser.add_argument("mock_response")
    parser.add_argument("destination")
    args = parser.parse_args()
    target = Path(args.destination)
    try:
        bundle = json.loads(Path(args.request_bundle).read_text(encoding="utf-8"))
        candidate = json.loads(Path(args.mock_response).read_text(encoding="utf-8"))
        result = validate_outputs(bundle, candidate)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    except (ValueError, TypeError, KeyError, OSError):
        target.unlink(missing_ok=True)
        raise

if __name__ == "__main__":
    main()
