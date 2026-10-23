"""V59 read-only localhost operations checks for the desktop research launcher.

No remote exchanges, account data, credentials or trading/order endpoints.
All inputs are local research HTTP GET responses; errors fail closed.
"""
from collections import deque
from datetime import datetime, timezone
import json
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

SAFE_PATHS = ("/health", "/api/v1/feed", "/api/v1/agents", "/api/v1/market")
EVENT_LIMIT = 50


def _get_local_json(base_url, path, *, timeout=1.5):
    if not base_url.startswith("http://127.0.0.1:"):
        raise ValueError("Only loopback research URL allowed")
    if path not in SAFE_PATHS:
        raise ValueError("Unknown read-only operations endpoint")
    with urlopen(base_url + path, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError("Research endpoint not ready")
        data = response.read(1_000_001)
        if len(data) > 1_000_000:
            raise ValueError("Oversized local API response")
    parsed = json.loads(data)
    if not isinstance(parsed, dict) or parsed.get("orders_enabled") is not False:
        raise ValueError("Unsafe local API flags")
    return parsed


def probe_local_research(base_url):
    """Report health, historical provenance, completed-bar research, paper absence.

    Never misidentify historical snapshots as a live exchange connection.
    """
    report = {
        "state": "UNAVAILABLE",
        "mode": "UNKNOWN",
        "agent_research": "NOT_VERIFIED",
        "market_board": "NOT_VERIFIED",
        "feed": "UNKNOWN",
        "paper": "NOT_ENABLED",
        "orders_enabled": False,
    }
    try:
        health = _get_local_json(base_url, "/health")
        if health.get("status") != "ok" or health.get("mode") != "local-paper-only":
            raise ValueError("Unexpected research health mode")
        feed = _get_local_json(base_url, "/api/v1/feed")
        if feed.get("state") != "HISTORICAL" or feed.get("ready") is not False:
            raise ValueError("Launcher must remain in historical-only mode")
        report["feed"] = "HISTORICAL"
        agents = _get_local_json(base_url, "/api/v1/agents")
        if (agents.get("realtime") is not False or
                agents.get("source") != "historical_csv_snapshot" or
                agents.get("paper_only") is not True or
                agents.get("live_trading_approved") is not False):
            raise ValueError("Research provenance mismatch")
        envelope = agents.get("events")
        if (not isinstance(envelope, dict) or
                envelope.get("orders_enabled") is not False or
                envelope.get("paper_only") is not True):
            raise ValueError("Unsafe research envelope")
        board = _get_local_json(base_url, "/api/v1/market")
        if (board.get("realtime") is not False or
                board.get("source") != "historical_csv_snapshot" or
                board.get("paper_only") is not True or
                board.get("live_trading_approved") is not False or
                board.get("last_closed_timestamp") is None):
            raise ValueError("Invalid historical market board")
        report.update(state="READY", mode="HISTORICAL_CSV",
                      agent_research="VERIFIED", market_board="VERIFIED")
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, json.JSONDecodeError) as exc:
        report.update(state="UNAVAILABLE",agent_research="NOT_VERIFIED",
                      market_board="NOT_VERIFIED",reason=type(exc).__name__)
    return report


class LocalEventLog:
    """Bounded, redacted event summaries only; no file and no secret material."""
    def __init__(self, max_events=EVENT_LIMIT):
        if isinstance(max_events, bool) or not 1 <= max_events <= 100:
            raise ValueError("Invalid event limit")
        self._items = deque(maxlen=max_events)

    def record(self, event, detail=""):
        if event not in ("STARTED", "STOPPED", "CHECK_OK", "CHECK_FAILED", "START_FAILED"):
            raise ValueError("Unknown local event")
        # No untrusted exception messages, absolute file paths or tokens in logs.
        detail = detail if detail in ("HISTORICAL_CSV","MISSING_DATA","PORT_BUSY","UNAVAILABLE","") else ""
        when = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        message = when + " · " + event + (" · " + detail if detail else "")
        self._items.append(message)
        return message

    def recent(self):
        return tuple(self._items)
