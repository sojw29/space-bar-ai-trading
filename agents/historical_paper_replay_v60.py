"""V60 explicitly triggered, historical-only paper replay for local launcher.

This is a deterministic hypothetical paper simulation, NOT future performance,
real fills, autonomous execution, broker order placement or a live account.
No external network or private credentials used.
"""
import math
from datetime import datetime,timezone

from dashboard_api_v28 import load_candles
from market_board_v52 import market_board
from agent_events_v27 import analyze_and_emit
from paper_portfolio_v41 import PaperPortfolio

INITIAL_SIM_CASH=10_000.0
MIN_WARMUP_BARS=55
REPLAY_BARS=80


def replay_historical_paper(history_path):
    """Replay max 80 real supplied historical candles, after 55-bar warmup.

    A new portfolio is constructed for every explicit invocation; historical
    snapshot never mutates the local server or submits any orders.
    """
    rows=load_candles(history_path,limit=REPLAY_BARS)
    if len(rows)<MIN_WARMUP_BARS:
        raise ValueError("Need 55 completed historical bars for paper replay")
    validated=market_board(rows,realtime=False,source="historical_csv_snapshot")
    bars=validated["candles"]
    # V52 market board intentionally returns only last 60; use full validated
    # 80 OHLCV rows after checking the 60-bar suffix.
    for index in range(1,len(rows)):
        if rows[index]["timestamp"] != rows[index-1]["timestamp"]+300:
            raise ValueError("Historical replay contains missing or repeated candles")
    end=rows[-1]["timestamp"]+300
    portfolio=PaperPortfolio(initial_cash=INITIAL_SIM_CASH,clock=lambda: end)
    count=0
    state=None
    for end_index in range(MIN_WARMUP_BARS,len(rows)+1):
        candle=rows[end_index-1]
        result=analyze_and_emit(rows[:end_index])
        state=portfolio.on_completed_candle({**candle,"closed":True},result)
        count+=1
        if state["halted"]:
            break
    if state is None:
        raise ValueError("Unable to produce historical paper results")
    close_price=rows[MIN_WARMUP_BARS+count-2]["close"]
    final=portfolio.snapshot(close_price)
    equity=final["mark_to_close_equity"]
    if isinstance(equity,bool) or not isinstance(equity,(int,float)) or not math.isfinite(equity):
        raise ValueError("Invalid simulated equity")
    position=final["position"]
    # No historical trade records fabricated. Keep totals separate from live.
    return {
        "schema_version":"60.0",
        "mode":"EXPLICIT_HISTORICAL_PAPER_REPLAY",
        "source":"historical_csv_snapshot",
        "realtime":False,
        "bars_used":len(rows),
        "warmup_bars":MIN_WARMUP_BARS,
        "paper_bars_processed":count,
        "last_processed_bar_utc":datetime.fromtimestamp(
            final["closed_candles_processed_until"],timezone.utc).isoformat(),
        "initial_paper_cash":INITIAL_SIM_CASH,
        "paper_cash":final["cash"],
        "paper_equity_mark_to_close":equity,
        "paper_net_realized":final["total_paper_net_realized"],
        "paper_position":position,
        "paper_trade_event_count":len(final["trades"]),
        "paper_entries":sum(t["type"]=="ENTRY" for t in final["trades"]),
        "paper_exits":sum(t["type"]=="EXIT" for t in final["trades"]),
        "halted":bool(final["halted"]),
        "halt_reason":final["halt_reason"],
        "paper_only":True,
        "orders_enabled":False,
        "live_trading_approved":False,
        "independent_oos_verified":False,
        "warning":"HYPOTHETICAL historical close-price fills with fees/slippage; no real execution, intrabar stops, or predictive-performance validation."
    }
