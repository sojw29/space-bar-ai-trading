"""V62 chronology-safe development/holdout paper-research evaluation.

Runs the existing FIXED V26/V27 decision rules without fitting or optimizing
them. The 70/30 split is descriptive only: it is NOT independently OOS-
verified, a trading signal, or evidence of predictive ability.
"""
import csv
import math
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from agent_events_v27 import analyze_and_emit
from market_board_v52 import market_board
from multi_agent_v26 import validate as validate_candles
from paper_portfolio_v41 import PaperPortfolio

BAR_SECONDS = 300
MAX_BARS = 5000
MIN_BARS = 200
WARMUP = 55
DEV_FRACTION = 0.70
INITIAL_CASH = 10000.0
MIN_CLOSED_TRADES = 30


def read_btc_history(path):
    """Reject invalid/gapped history and avoid silently truncating a file."""
    file = Path(path).expanduser().resolve()
    if not file.is_file():
        raise FileNotFoundError("No historical BTC 5m CSV available")
    if file.stat().st_size > 20_000_000:
        raise ValueError("Historical CSV exceeds safety size cap")
    with file.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        keys = {"timestamp", "open", "high", "low", "close", "volume"}
        if not keys.issubset(reader.fieldnames or []):
            raise ValueError("Missing historical OHLCV columns")
        rows = []
        for row in reader:
            if len(rows) >= MAX_BARS:
                raise ValueError("Too many candles; split inputs explicitly")
            try:
                ts = int(row["timestamp"])
                if str(row["timestamp"]).strip() != str(ts):
                    raise ValueError("Not integer epoch seconds")
                candle = {"timestamp":ts}
                candle.update({k:float(row[k]) for k in
                               ("open","high","low","close","volume")})
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise ValueError("Invalid historical CSV candle") from exc
            rows.append(candle)
    if len(rows) < MIN_BARS:
        raise ValueError("At least 200 complete BTC 5m bars are needed for split evaluation")
    # V26 validates every OHLCV and chronological continuity (and close finality).
    validate_candles(rows)
    if rows[0]["timestamp"] % BAR_SECONDS != 0:
        raise ValueError("Incorrect 5-minute candle grid")
    return rows


def _segment(rows, first_index, after_last):
    """First trade at first_index; warmup only uses PAST candles."""
    if not (WARMUP - 1 <= first_index < after_last <= len(rows)):
        raise ValueError("Invalid evaluation window")
    now = rows[-1]["timestamp"] + BAR_SECONDS
    portfolio = PaperPortfolio(initial_cash=INITIAL_CASH, clock=lambda: now)
    peak=INITIAL_CASH
    mdd=0.0
    equity_points=[]
    halted=False
    for i in range(first_index, after_last):
        candle = rows[i]
        lookback = rows[max(0, i-119):i+1]
        if len(lookback)<WARMUP:
            raise ValueError("Missing prior-only signal warmup")
        event = analyze_and_emit(lookback)
        snapshot = portfolio.on_completed_candle({**candle, "closed":True},event)
        equity = snapshot["mark_to_close_equity"]
        if (not isinstance(equity,(int,float)) or isinstance(equity,bool)
                or not math.isfinite(equity) or equity<=0):
            raise ValueError("Invalid hypothetical paper mark")
        peak=max(peak,equity)
        mdd=max(mdd,(peak-equity)/peak*100)
        equity_points.append({"bar_open_utc":datetime.fromtimestamp(
            candle["timestamp"], timezone.utc).isoformat(),
            "paper_marked_equity":round(equity,8)})
        if snapshot["halted"]:
            halted=True
            break
    if not equity_points:
        raise ValueError("No completed-bar valuation")
    final=portfolio.snapshot(rows[first_index+len(equity_points)-1]["close"])
    entries=sum(t["type"]=="ENTRY" for t in final["trades"])
    exits=sum(t["type"]=="EXIT" for t in final["trades"])
    # Count and pair CLOSED paper outcomes, never an unclosed position.
    open_entry=None
    nets=[]
    for trade in final["trades"]:
        if trade["type"]=="ENTRY":
            if open_entry is not None:
                raise ValueError("Overlapping paper entries")
            open_entry=trade
        elif trade["type"]=="EXIT":
            if open_entry is None or open_entry["side"]!=trade["side"]:
                raise ValueError("Unpaired paper exit")
            nets.append(trade["net_exit_effect"]-open_entry["entry_fee"])
            open_entry=None
        else:
            raise ValueError("Unrecognized paper ledger event")
    if len(nets)!=exits or entries!=exits+int(open_entry is not None):
        raise ValueError("Paper trade ledger mismatch")
    enough=len(nets)>=MIN_CLOSED_TRADES
    positive=sum(n>0 for n in nets)
    negative=sum(n<0 for n in nets)
    total_loss=abs(sum(n for n in nets if n<0))
    return {
        "first_evaluated_bar_utc":datetime.fromtimestamp(rows[first_index]["timestamp"],timezone.utc).isoformat(),
        "last_evaluated_bar_utc":equity_points[-1]["bar_open_utc"],
        "scheduled_bars":after_last-first_index,
        "evaluated_bars":len(equity_points),
        "equity_curve":equity_points,
        "paper_initial_cash":INITIAL_CASH,
        "paper_final_marked_equity":equity_points[-1]["paper_marked_equity"],
        "paper_cash":final["cash"],
        "paper_net_realized":final["total_paper_net_realized"],
        "paper_max_observed_drawdown_pct":round(mdd,6),
        "paper_entries":entries,
        "paper_closed_trades":exits,
        "paper_open_position":final["position"],
        "paper_win_rate_pct":round(positive/len(nets)*100,6) if enough else None,
        "paper_profit_factor":round(sum(n for n in nets if n>0)/total_loss,6)
                             if enough and total_loss>0 else None,
        "insufficient_closed_trade_sample":not enough,
        "halted":halted,
        "halt_reason":final["halt_reason"],
    }


def evaluate_chronological_holdout(path):
    rows = read_btc_history(path)
    total=len(rows)
    split=int(total*DEV_FRACTION)
    if split<=WARMUP or total-split<40:
        raise ValueError("Chronological holdout too short")
    # No strategy fitting takes place: rules are predefined. The split simply
    # prevents the HOLDOUT portfolio from ingesting earlier trades/marks.
    dev = _segment(rows, WARMUP-1, split)
    holdout = _segment(rows, split, total)
    if dev["last_evaluated_bar_utc"]>=holdout["first_evaluated_bar_utc"]:
        raise ValueError("Development/holdout timestamps overlap")
    return {
        "schema_version":"62.0",
        "mode":"CHRONOLOGICAL_DESCRIPTIVE_PAPER_HOLDOUT",
        "symbol":"BTCUSDT",
        "timeframe":"5m",
        "source":"historical_csv_snapshot",
        "data_candles":total,
        "split_index":split,
        "development_fraction":DEV_FRACTION,
        "warmup_bars":WARMUP,
        "model_fitting_performed":False,
        "rule_parameters_frozen":True,
        "holdout_was_reserved_from_paper_portfolio":True,
        "development":dev,
        "holdout":holdout,
        "oos_validated":False,
        "independent_oos_verified":False,
        "paper_only":True,
        "orders_enabled":False,
        "live_trading_approved":False,
        "realtime":False,
        "warning":"FIXED deterministic rules, in-file chronological holdout, hypothetical close-price fills. Not untouched independent OOS after iterative development; no live fills, profitability or generalization claim."
    }
