"""V239: injectable research-only provider boundary, disabled by default.

No provider SDK, HTTP requests, credentials, orders, or model calls are implemented.
An injected callable can be used in local tests only; its output is validated as
an OFFLINE_FIXTURE_ONLY response and must not be described as real inference.
"""
import argparse
import json
from pathlib import Path
from model_output_validator_v237 import validate_outputs

class ProviderDisabledError(RuntimeError):
    pass

def execute_with_injected_fixture(bundle, fixture_provider=None, *, allow_offline_fixture=False, now=None):
    if not allow_offline_fixture:
        raise ProviderDisabledError("PROVIDER_DISABLED_BY_DEFAULT")
    if fixture_provider is None or not callable(fixture_provider):
        raise ProviderDisabledError("NO_OFFLINE_FIXTURE_PROVIDER")
    if not isinstance(bundle, dict):
        raise ValueError("INVALID_REQUEST_BUNDLE")
    # Validate the request before any callback is allowed to run. The existing
    # validator checks the bundle before inspecting candidate response fields.
    placeholder = {"version": "V237.MOCK.1", "source": "OFFLINE_FIXTURE_ONLY",
                   "request_sha256": "0" * 64, "responses": []}
    try:
        validate_outputs(bundle, placeholder, now)
    except ValueError as exc:
        if str(exc) != "REQUEST_HASH_MISMATCH":
            raise
    # Callback is a local fixture generator, never a provider/network adapter.
    candidate = fixture_provider(bundle)
    return validate_outputs(bundle, candidate, now)

def main():
    parser = argparse.ArgumentParser(description="V239 fail-closed provider boundary")
    parser.add_argument("request_bundle")
    parser.add_argument("destination")
    args = parser.parse_args()
    target = Path(args.destination)
    # CLI intentionally never enables a fixture or provider. Delete stale output.
    target.unlink(missing_ok=True)
    raise ProviderDisabledError("PROVIDER_DISABLED: no live AI provider configured")

if __name__ == "__main__":
    main()
