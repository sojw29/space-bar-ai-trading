"""V242 fail-closed offline execution guardrail.

Blocks socket connection attempts during research pipeline execution.
Not a sandbox or protection against malicious code; intended to detect
accidental network dependencies in the offline pipeline.
"""
from contextlib import contextmanager
from unittest.mock import patch

from research_pipeline_smoke_v241 import run_pipeline

class UnexpectedNetworkAccess(RuntimeError):
    pass

def deny_network(*args, **kwargs):
    raise UnexpectedNetworkAccess("OFFLINE_PIPELINE_NETWORK_BLOCKED")

@contextmanager
def network_guard():
    with patch("socket.socket.connect", side_effect=deny_network), \
         patch("socket.socket.connect_ex", side_effect=deny_network), \
         patch("socket.create_connection", side_effect=deny_network):
        yield

def run_guarded_pipeline(source, now=None):
    with network_guard():
        result = run_pipeline(source, now)
    if (result.get("network_enabled") is not False
        or result.get("orders_enabled") is not False
        or result.get("model_inference_performed") is not False
        or result.get("validated_for_trading") is not False):
        raise ValueError("UNSAFE_PIPELINE_OUTPUT")
    return result
