"""V205 conservative research snapshot freshness classification.

Freshness refers ONLY to snapshot generation, never market-data freshness or
data authenticity. No orders, rankings, trading approval or strategy selection.
"""
from datetime import datetime, timezone

FRESH_HOURS = 24
STALE_HOURS = 72


def assess(report, now=None):
    if not isinstance(report, dict) or report.get("version") != "V105.0":
        raise ValueError("INVALID_RESEARCH_REPORT")
    if report.get("research_only") is not True or report.get("orders_enabled") is not False or report.get("live_trading_approved") is not False:
        raise ValueError("UNSAFE_RESEARCH_REPORT")
    p = report.get("snapshot_provenance")
    status = "UNKNOWN"
    reason = "MISSING_OR_UNVERIFIED_GENERATION_TIME"
    age_hours = None
    if isinstance(p, dict) and p.get("version") == "V204.0" and p.get("research_only") is True and p.get("realtime") is False and p.get("data_authenticity_verified") is False and p.get("history_timestamp_verified") is False:
        value = p.get("generated_at_utc")
        if isinstance(value, str) and value.endswith("Z"):
            try:
                generated = datetime.fromisoformat(value.replace("Z", "+00:00"))
                clock = now or datetime.now(timezone.utc)
                if clock.tzinfo is None:
                    raise ValueError("NAIVE_CLOCK")
                age = (clock.astimezone(timezone.utc) - generated).total_seconds() / 3600
                if 0 <= age <= 24 * 3650:
                    age_hours = round(age, 2)
                    if age <= FRESH_HOURS:
                        status, reason = "RECENT_SNAPSHOT", "GENERATED_WITHIN_24_HOURS"
                    elif age <= STALE_HOURS:
                        status, reason = "AGING_SNAPSHOT", "GENERATED_24_TO_72_HOURS_AGO"
                    else:
                        status, reason = "STALE_SNAPSHOT", "GENERATED_OVER_72_HOURS_AGO"
                elif age < 0:
                    status, reason = "UNKNOWN", "FUTURE_GENERATION_TIME"
                else:
                    status, reason = "UNKNOWN", "IMPLAUSIBLY_OLD_GENERATION_TIME"
            except (ValueError, OverflowError):
                status, reason = "UNKNOWN", "INVALID_GENERATION_TIME"
    return {"version": "V205.0", "status": status, "reason": reason,
            "age_hours": age_hours, "scope": "SNAPSHOT_GENERATION_ONLY",
            "market_data_freshness_verified": False,
            "data_authenticity_verified": False,
            "research_only": True, "orders_allowed": False,
            "live_trading_approved": False}
