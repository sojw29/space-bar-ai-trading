"""V129 strictly descriptive offline news-observation vs OHLCV event study.

Events use V127 GDELT seen-at timestamps, NOT verified original publication or
first tradable availability. Uses only fully closed candle boundaries, never
claims backtest eligibility or predictive news signals.
"""
import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

HORIZONS_MIN=(5,15,60)
MAX_CANDLES=200_000

def _utc(value):
    if not isinstance(value,str):
        raise ValueError("INVALID_TIMESTAMP")
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("INVALID_TIMESTAMP") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("TIMESTAMP_WITHOUT_TIMEZONE")
    return dt.astimezone(timezone.utc)

def _float(value):
    if isinstance(value,bool):
        raise ValueError("INVALID_OHLCV")
    try:
        v=float(value)
    except (TypeError,ValueError) as exc:
        raise ValueError("INVALID_OHLCV") from exc
    if not math.isfinite(v):
        raise ValueError("INVALID_OHLCV")
    return v

def load_candles(path):
    rows=[]
    with Path(path).open(newline="",encoding="utf-8") as stream:
        reader=csv.DictReader(stream)
        if not reader.fieldnames or not {"timestamp","open","high","low","close","volume"}.issubset(reader.fieldnames):
            raise ValueError("INVALID_CSV_COLUMNS")
        for row in reader:
            if len(rows)>=MAX_CANDLES:
                raise ValueError("TOO_MANY_CANDLES")
            raw=row["timestamp"]
            try:
                number=int(raw)
            except (ValueError,TypeError):
                ts=_utc(raw)
            else:
                ts=datetime.fromtimestamp(number/(1000 if abs(number)>10**11 else 1),tz=timezone.utc)
            candle={k:_float(row[k]) for k in ("open","high","low","close","volume")}
            if min(candle["open"],candle["high"],candle["low"],candle["close"])<=0 or candle["volume"]<0:
                raise ValueError("INVALID_OHLCV")
            if candle["high"]<max(candle["open"],candle["close"],candle["low"]) or candle["low"]>min(candle["open"],candle["close"],candle["high"]):
                raise ValueError("INVALID_OHLCV")
            rows.append({"time":ts,**candle})
    if len(rows)<2 or any(a["time"]>=b["time"] for a,b in zip(rows,rows[1:])):
        raise ValueError("UNSORTED_OR_INSUFFICIENT_CANDLES")
    step=(rows[1]["time"]-rows[0]["time"]).total_seconds()
    if step<=0 or any(abs((b["time"]-a["time"]).total_seconds()-step)>0.001 for a,b in zip(rows,rows[1:])):
        raise ValueError("IRREGULAR_CANDLE_INTERVAL")
    return rows,step

def study(snapshot,candles,step_seconds):
    if not isinstance(snapshot,dict) or snapshot.get("version")!="V127.0" or not isinstance(snapshot.get("articles"),list):
        raise ValueError("INVALID_V127_SNAPSHOT")
    if len(snapshot["articles"])>100 or not isinstance(candles,list) or len(candles)<2 or step_seconds<=0:
        raise ValueError("INVALID_STUDY_INPUT")
    import bisect
    from datetime import timedelta
    times=[x["time"] for x in candles]
    events=[]
    for article in snapshot["articles"]:
        if not isinstance(article,dict):
            raise ValueError("INVALID_ARTICLE")
        seen=_utc(article.get("gdelt_seen_at_utc"))
        # OHLCV timestamp denotes candle OPEN; base is the last candle whose
        # CLOSE is no later than the GDELT observation time.
        idx=bisect.bisect_right(times,seen-timedelta(seconds=step_seconds))-1
        record={"article_id":article.get("article_id"),"gdelt_seen_at_utc":seen.isoformat(),
                "baseline_close_time_utc":None,"baseline_close":None,"forward":{},
                "point_in_time_news_availability_verified":False}
        if idx>=0:
            record["baseline_close_time_utc"]=(times[idx]+timedelta(seconds=step_seconds)).isoformat()
            record["baseline_close"]=candles[idx]["close"]
            for horizon in HORIZONS_MIN:
                target=seen+timedelta(minutes=horizon)
                end_idx=bisect.bisect_right(times,target-timedelta(seconds=step_seconds))-1
                if end_idx<=idx or end_idx>=len(candles):
                    record["forward"][str(horizon)+"m"]=None
                    continue
                end_close_time=times[end_idx]+timedelta(seconds=step_seconds)
                # A distant previous candle must not masquerade as a horizon
                # measurement when history is stale or ends early.
                if target-end_close_time>=timedelta(seconds=step_seconds):
                    record["forward"][str(horizon)+"m"]=None
                    continue
                ret=100*(candles[end_idx]["close"]/candles[idx]["close"]-1)
                record["forward"][str(horizon)+"m"]={"return_pct":round(ret,8),
                    "close_time_utc":end_close_time.isoformat()}
        else:
            record["forward"]={str(h)+"m":None for h in HORIZONS_MIN}
        events.append(record)
    return {"version":"V129.0","status":"DESCRIPTIVE_NEWS_OBSERVATION_EVENT_STUDY",
            "events":events,"event_count":len(events),
            "horizons_minutes":list(HORIZONS_MIN),
            "candle_interval_seconds":step_seconds,
            "point_in_time_news_availability_verified":False,
            "historical_backtest_eligibility":False,
            "predictive_signal":False,"research_only":True,
            "simulation_only":True,"exchange_connected":False,
            "orders_submitted_to_exchange":0,"live_trading_approved":False,
            "validated_edge":False,
            "limitations":"GDELT seen time may lag actual publication; no first-availability proof. Forward descriptive returns use completed candles and may differ from executable entry returns. No causal attribution, controls, volatility normalization or execution cost model."}

def main():
    parser=argparse.ArgumentParser(description="V129 offline GDELT observation event study")
    parser.add_argument("v127_snapshot_json",type=Path)
    parser.add_argument("ohlcv_csv",type=Path)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    snapshot=json.loads(args.v127_snapshot_json.read_text(encoding="utf-8"))
    candles,step=load_candles(args.ohlcv_csv)
    encoded=json.dumps(study(snapshot,candles,step),indent=2,ensure_ascii=False)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(encoded,encoding="utf-8")
    else:
        print(encoded,end="")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
