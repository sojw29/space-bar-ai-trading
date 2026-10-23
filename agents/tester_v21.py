"""V21 retrospective trade reconciliation across paper snapshots.

Compares prior and current V17 snapshots. This is NOT an immutable forward
execution ledger: retrospective replays may revise historical outcomes.
"""
import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import tester_v20 as v20

OUT = Path("reports/v21")
CURRENT = Path("reports/v17/trades.csv")
PREVIOUS = Path(os.environ.get("V21_PREVIOUS_TRADES", "previous_v21/trades.csv"))
FIELDS = ("candidate", "scenario", "side", "entry_time", "entry_price")
OUTCOME = ("exit_time", "exit_price", "net_pnl_usd", "reason")


def read(path):
    if not path.exists():
        return None
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fingerprint(row):
    raw = json.dumps([row.get(k, "") for k in FIELDS], separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def closed(rows):
    result, duplicate = {}, []
    for row in rows:
        # V10's END exit is a forced end-of-data mark, not a finalized trade.
        if row.get("reason", "").upper() == "END":
            continue
        key = fingerprint(row)
        if key in result:
            duplicate.append(key)
        result[key] = row
    return result, duplicate


def reconcile(previous, current):
    now, duplicate_now = closed(current)
    if previous is None:
        return {
            "previous_snapshot_available": False,
            "current_finalized_trades": len(now),
            "previous_finalized_trades": None,
            "new_finalized_trades": None,
            "missing_previous_trades": [],
            "revised_previous_trades": [],
            "duplicate_current_ids": duplicate_now,
            "duplicate_previous_ids": [],
            "status": "BASELINE_ONLY",
        }
    old, duplicate_old = closed(previous)
    missing = sorted(set(old) - set(now))
    revised = sorted(
        k for k in set(old) & set(now)
        if any(old[k].get(field) != now[k].get(field) for field in OUTCOME)
    )
    new = sorted(set(now) - set(old))
    return {
        "previous_snapshot_available": True,
        "current_finalized_trades": len(now),
        "previous_finalized_trades": len(old),
        "new_finalized_trades": len(new),
        "missing_previous_trades": missing,
        "revised_previous_trades": revised,
        "duplicate_current_ids": duplicate_now,
        "duplicate_previous_ids": duplicate_old,
        "status": "RECONCILIATION_WARNING" if (missing or revised or duplicate_now or duplicate_old) else "OBSERVATION_ONLY",
    }


def previous_trades_path():
    """Resolve GitHub artifact layouts without silently using current-run trades.

    Multi-path upload-artifact archives normally extract as v17/trades.csv,
    while older archives may include reports/v17/trades.csv.
    An explicit override is treated strictly, with no fallback.
    """
    if PREVIOUS.exists() or os.environ.get("V21_PREVIOUS_TRADES"):
        return PREVIOUS
    for candidate in (PREVIOUS.parent / "v17" / "trades.csv",
                      PREVIOUS.parent / "reports" / "v17" / "trades.csv"):
        if candidate.exists():
            return candidate
    return PREVIOUS


def finalized_by_scenario(finalized):
    counts = {}
    for trade in finalized.values():
        candidate, scenario = trade["candidate"], trade["scenario"]
        counts.setdefault(candidate, {})
        counts[candidate][scenario] = counts[candidate].get(scenario, 0) + 1
    return counts


def run():
    v20.audit()
    current = read(CURRENT)
    if current is None:
        raise RuntimeError("Missing V17 current trade report")
    prior_path = previous_trades_path()
    result = reconcile(read(prior_path), current)
    result["current_finalized_by_candidate_scenario"] = finalized_by_scenario(closed(current)[0])
    result["previous_snapshot_source"] = str(prior_path) if prior_path.exists() else None
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        "version": "V21.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        **result,
        "snapshot_sha256": hashlib.sha256(CURRENT.read_bytes()).hexdigest(),
        "independent_oos_verified": False,
        "live_trading_approved": False,
        "caveats": [
            "Trade identities use candidate/scenario/side/entry time/price, not exchange execution IDs.",
            "END forced-close rows are excluded from finalized-trade counts.",
            "Previous artifacts may be unavailable or have overlapping retrospective observations.",
            "Stable retrospective trade records do not establish independent OOS validity.",
        ],
    }
    (OUT / "reconciliation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("V21", result["status"], "finalized", result["current_finalized_trades"],
          "new", result["new_finalized_trades"], "revised", len(result["revised_previous_trades"]))
    if result["duplicate_current_ids"]:
        raise RuntimeError("Duplicate trade IDs in current snapshot")


if __name__ == "__main__":
    run()
