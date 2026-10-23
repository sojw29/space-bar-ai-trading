"""V44 read-only analytics for V43 simulated-paper journal sessions.

Only observed historical paper snapshots are used. Never computes an actual
exchange P&L, validated win rate, or broker execution metrics.
"""
import math
from paper_journal_v43 import session_events, verify_session

def _finite(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))

def analyze_session(db_path, session_id, *, limit=500):
    audit = verify_session(db_path, session_id)
    rows = list(reversed(session_events(db_path, session_id, limit=limit)))
    if not rows:
        return {
            "schema_version": "44.0", "mode": "SIMULATED_PAPER_ANALYTICS",
            "session_id": session_id, "journal_entries": 0,
            "sampled_entries": 0, "sample_complete": True,
            "observed_equity_max_drawdown_pct": None,
            "latest_paper_cash": None, "latest_paper_realized_net": None,
            "paper_trade_events": 0, "halt_count_in_sample": 0,
            "paper_only": True, "orders_enabled": False,
            "live_trading_approved": False, "independent_oos_verified": False,
        }
    high = None
    max_dd = 0.0
    observed = 0
    halts = 0
    last_trade_count = None
    previous_trade_count = None
    for item in rows:
        data = item["paper_data"]
        if (data.get("paper_only") is not True or
            data.get("orders_enabled") is not False or
            data.get("live_trading_approved") is not False or
            data.get("mode") != "LOCAL_PAPER_SIMULATION"):
            raise ValueError("Invalid simulated journal event")
        if item["kind"] == "feed_halt":
            halts += 1
        count = data.get("paper_trade_event_count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("Invalid paper trade event counter")
        if previous_trade_count is not None and count < previous_trade_count:
            raise ValueError("Paper trade event counter decreased")
        previous_trade_count = count
        last_trade_count = count
        equity = data.get("paper_mark_to_close_equity")
        if data.get("mark_is_stale") is False and _finite(equity) and equity > 0:
            high = equity if high is None else max(high, equity)
            max_dd = max(max_dd, (high - equity) / high * 100)
            observed += 1
    last = rows[-1]["paper_data"]
    cash = last.get("paper_cash")
    realized = last.get("paper_realized_net")
    if not _finite(cash) or not _finite(realized):
        raise ValueError("Invalid simulated cash or P&L")
    return {
        "schema_version": "44.0",
        "mode": "SIMULATED_PAPER_ANALYTICS",
        "session_id": session_id,
        "journal_entries": audit["entries"],
        "sampled_entries": len(rows),
        "sample_complete": audit["entries"] <= len(rows),
        "observed_equity_points": observed,
        "observed_equity_max_drawdown_pct": round(max_dd, 6) if observed >= 2 else None,
        "latest_paper_cash": round(cash, 6),
        "latest_paper_realized_net": round(realized, 6),
        "paper_trade_events": last_trade_count,
        "halt_count_in_sample": halts,
        "latest_state": last.get("state"),
        "warning": "Observed simulated marks only; no validated returns, win rate or real fills.",
        "paper_only": True,
        "orders_enabled": False,
        "live_trading_approved": False,
        "independent_oos_verified": False,
    }
