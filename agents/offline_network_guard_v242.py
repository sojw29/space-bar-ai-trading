"""V242 fail-closed offline execution guardrail.

Blocks common socket connection and send paths during research pipeline execution.
Not a sandbox or protection against malicious code; intended to detect
accidental network dependencies in the offline pipeline.
"""
import socket
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from research_pipeline_smoke_v241 import run_pipeline


class UnexpectedNetworkAccess(RuntimeError):
    pass


def deny_network(*args, **kwargs):
    raise UnexpectedNetworkAccess("OFFLINE_PIPELINE_NETWORK_BLOCKED")


@contextmanager
def network_guard():
    # connect-only guards miss UDP sendto and writes on pre-connected sockets.
    # sendmsg is not available on every Python platform (notably Windows).
    methods = ("connect", "connect_ex", "send", "sendall", "sendto", "sendmsg")
    with ExitStack() as stack:
        stack.enter_context(patch("socket.create_connection", side_effect=deny_network))
        for method in methods:
            if hasattr(socket.socket, method):
                stack.enter_context(
                    patch(f"socket.socket.{method}", side_effect=deny_network)
                )
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
