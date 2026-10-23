"""V61 deterministic, auditable *historical simulated* performance report.

No prediction claims. Null means there is insufficient closed-trade evidence,
not 0% win rate. Observed close-price marks are hypothetical, not broker fills.
"""
import math
from historical_paper_replay_v60 import replay_historical_paper

MIN_CLOSED_TRADES_FOR_RATES = 30


def _finite(value):
    return (type(value) in (int,float) and math.isfinite(value))


def analyze_paper_evidence(replay):
    """Compute descriptive, in-sample stats only from an explicit replay."""
    if (not isinstance(replay,dict) or replay.get("mode")!="EXPLICIT_HISTORICAL_PAPER_REPLAY"
            or replay.get("source")!="historical_csv_snapshot"
            or replay.get("realtime") is not False
            or replay.get("paper_only") is not True
            or replay.get("orders_enabled") is not False
            or replay.get("live_trading_approved") is not False
            or replay.get("independent_oos_verified") is not False):
        raise ValueError("Unsupported or unsafe paper replay")
    marks = replay.get("_completed_candle_equity_observations")
    trades = replay.get("_hypothetical_trade_events")
    if not isinstance(marks,list) or not 1 <= len(marks) <= 26 or not isinstance(trades,list):
        raise ValueError("Missing historical paper evidence")
    if len(marks)!=replay.get("paper_bars_processed") or len(trades)!=replay.get("paper_trade_event_count"):
        raise ValueError("Paper event count disagreement")
    start_cash=replay.get("initial_paper_cash")
    if not _finite(start_cash) or start_cash<=0:
        raise ValueError("Invalid initial paper cash")
    peak=float(start_cash)
    drawdown=0.0
    prev=None
    clean_points=[]
    for item in marks:
        if not isinstance(item,dict):
            raise ValueError("Malformed equity observation")
        ts=item.get("timestamp")
        equity=item.get("equity")
        cash=item.get("cash")
        if (type(ts) is not int or ts<0 or ts%300 or
            (prev is not None and ts!=prev+300) or
            not _finite(equity) or equity<=0 or not _finite(cash)):
            raise ValueError("Unsafe or discontinuous equity history")
        prev=ts
        peak=max(peak,equity)
        drawdown=max(drawdown,(peak-equity)/peak*100)
        clean_points.append({"timestamp":ts,"paper_equity":round(equity,8)})
    if abs(clean_points[-1]["paper_equity"]-replay["paper_equity_mark_to_close"])>1e-6:
        raise ValueError("Final equity does not match the replay")

    # Pair only closed positions; open entry must never count as a winning trade.
    open_entry=None
    closed_nets=[]
    for item in trades:
        if not isinstance(item,dict):
            raise ValueError("Malformed paper trade")
        kind=item.get("type")
        if kind=="ENTRY":
            if open_entry is not None:
                raise ValueError("Overlapping hypothetical positions")
            entry_fee=item.get("entry_fee")
            if not _finite(entry_fee) or entry_fee<0:
                raise ValueError("Invalid entry fee")
            open_entry=item
        elif kind=="EXIT":
            if open_entry is None or open_entry.get("side")!=item.get("side"):
                raise ValueError("Unmatched hypothetical exit")
            net_exit=item.get("net_exit_effect")
            if not _finite(net_exit):
                raise ValueError("Invalid hypothetical exit")
            if (type(item.get("timestamp")) is not int or
                    item["timestamp"]<=open_entry.get("timestamp",-1)):
                raise ValueError("Noncausal hypothetical exit")
            closed_nets.append(net_exit-open_entry["entry_fee"])
            open_entry=None
        else:
            raise ValueError("Unknown simulated trade event")
    entries=sum(t["type"]=="ENTRY" for t in trades)
    exits=len(closed_nets)
    if (entries!=replay.get("paper_entries") or exits!=replay.get("paper_exits")
            or (open_entry is not None)!=(replay.get("paper_position") is not None)):
        raise ValueError("Unbalanced simulated paper ledger")
    winners=sum(net>0 for net in closed_nets)
    losses=sum(net<0 for net in closed_nets)
    # NEVER report a rate based on a handful of fabricated/mock replay results.
    enough=exits>=MIN_CLOSED_TRADES_FOR_RATES
    return {
        "schema_version":"61.0",
        "mode":"DESCRIPTIVE_HISTORICAL_PAPER_PERFORMANCE",
        "source":"historical_csv_snapshot",
        "realtime":False,
        "observed_paper_points":len(clean_points),
        "equity_curve":clean_points,
        "paper_initial_cash":start_cash,
        "paper_latest_marked_equity":clean_points[-1]["paper_equity"],
        "paper_realized_net":replay["paper_net_realized"],
        "paper_max_observed_drawdown_pct":round(drawdown,6),
        "paper_entries":entries,
        "paper_closed_trades":exits,
        "paper_open_position":replay.get("paper_position"),
        "paper_positive_closed_trades":winners,
        "paper_negative_closed_trades":losses,
        "paper_win_rate_pct":round(winners/exits*100,6) if enough else None,
        "paper_profit_factor":(
            round(sum(net for net in closed_nets if net>0)
                  / abs(sum(net for net in closed_nets if net<0)),6)
            if enough and any(net<0 for net in closed_nets) else None),
        "performance_sample_sufficient":enough,
        "performance_sample_minimum_closed_trades":MIN_CLOSED_TRADES_FOR_RATES,
        "oos_validated":False,
        "paper_only":True,
        "orders_enabled":False,
        "live_trading_approved":False,
        "independent_oos_verified":False,
        "warning":"IN-SAMPLE hypothetical close-price accounting only. No actual fills, validated win rate, forward performance, or independent out-of-sample evidence."
    }


def report_historical_paper(history_path):
    """Explicitly request V60 closed-bar replay evidence and generate V61 report."""
    return analyze_paper_evidence(
        replay_historical_paper(history_path, include_evidence=True))
