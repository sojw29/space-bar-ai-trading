"""V238 isolated offline mock executor. No external model/network/trading adapter."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from model_output_validator_v237 import validate_outputs, canonical
from model_adapter_contract_v236 import AGENTS

SAFE_SUMMARIES = {
    "ATLAS": "The provided trend classifications are descriptive observations only.",
    "QUANT": "The provided volume ratios are descriptive and not backtested.",
    "GUARDIAN": "No trading authorization exists in this research environment.",
    "COMMANDER": "Research observations were compiled without a trade recommendation.",
}

def execute_offline_fixture(bundle, now=None):
    if not isinstance(bundle, dict) or bundle.get("version") != "V236.0":
        raise ValueError("INVALID_BUNDLE")
    fixture = {
        "version": "V237.MOCK.1", "source": "OFFLINE_FIXTURE_ONLY",
        "request_sha256": hashlib.sha256(canonical(bundle)).hexdigest(),
        "responses": [
            {"agent": agent, "status": "OBSERVATION", "summary": SAFE_SUMMARIES[agent],
             "trade_authorization": "DENIED"} for agent in AGENTS
        ],
    }
    return validate_outputs(bundle, fixture, now)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("request_bundle")
    parser.add_argument("destination")
    args = parser.parse_args()
    target = Path(args.destination)
    try:
        data = json.loads(Path(args.request_bundle).read_text(encoding="utf-8"))
        result = execute_offline_fixture(data)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    except (ValueError, TypeError, KeyError, OSError):
        target.unlink(missing_ok=True)
        raise

if __name__ == "__main__":
    main()
