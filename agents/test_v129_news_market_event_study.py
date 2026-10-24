import csv
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from news_market_event_study_v129 import study,load_candles

START=datetime(2026,10,24,9,tzinfo=timezone.utc)
def candles(n=100):
    return [{"time":START+timedelta(minutes=i),"open":100+i,"high":101+i,
             "low":99+i,"close":100+i,"volume":10} for i in range(n)]
def snapshot(time="2026-10-24T09:10:30+00:00"):
    return {"version":"V127.0","articles":[{"article_id":"x","gdelt_seen_at_utc":time}]}

class NewsMarketEventStudyTests(unittest.TestCase):
    def test_baseline_only_completed_candle(self):
        r=study(snapshot(),candles(),60)["events"][0]
        self.assertEqual(r["baseline_close"],109)
        self.assertEqual(r["baseline_close_time_utc"],"2026-10-24T09:10:00+00:00")
    def test_forward_five_minute(self):
        r=study(snapshot(),candles(),60)["events"][0]
        self.assertAlmostEqual(r["forward"]["5m"]["return_pct"],100*(114/109-1),6)
    def test_all_horizons(self):
        r=study(snapshot(),candles(),60)["events"][0]
        self.assertEqual(set(r["forward"]),{"5m","15m","60m"})
    def test_no_future_candles(self):
        r=study(snapshot(),candles(12),60)["events"][0]
        self.assertIsNone(r["forward"]["5m"])
    def test_missing_baseline(self):
        r=study(snapshot("2026-10-24T09:00:30+00:00"),candles(),60)["events"][0]
        self.assertIsNone(r["baseline_close"])
    def test_invalid_version(self):
        with self.assertRaisesRegex(ValueError,"INVALID_V127_SNAPSHOT"):
            study({"version":"V128.0","articles":[]},candles(),60)
    def test_no_backtest_approval(self):
        r=study(snapshot(),candles(),60)
        self.assertFalse(r["historical_backtest_eligibility"])
        self.assertFalse(r["live_trading_approved"])
        self.assertEqual(r["orders_submitted_to_exchange"],0)
    def test_no_events(self):
        self.assertEqual(study({"version":"V127.0","articles":[]},candles(),60)["event_count"],0)
    def test_invalid_event_time(self):
        with self.assertRaisesRegex(ValueError,"TIMESTAMP_WITHOUT_TIMEZONE"):
            study(snapshot("2026-10-24T09:10:30"),candles(),60)
    def test_deterministic(self):
        self.assertEqual(study(snapshot(),candles(),60),study(snapshot(),candles(),60))
    def test_load_csv(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"data.csv"
            with p.open("w",newline="",encoding="utf-8") as f:
                w=csv.DictWriter(f,fieldnames=["timestamp","open","high","low","close","volume"])
                w.writeheader()
                for row in candles(3):
                    w.writerow({"timestamp":int(row["time"].timestamp()*1000),**{k:row[k] for k in ("open","high","low","close","volume")}})
            rows,step=load_candles(p)
            self.assertEqual(len(rows),3)
            self.assertEqual(step,60)
    def test_reject_irregular_csv(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"data.csv"
            with p.open("w",newline="",encoding="utf-8") as f:
                w=csv.DictWriter(f,fieldnames=["timestamp","open","high","low","close","volume"])
                w.writeheader()
                for i in (0,1,3):
                    w.writerow({"timestamp":int((START+timedelta(minutes=i)).timestamp()*1000),
                                "open":100,"high":101,"low":99,"close":100,"volume":10})
            with self.assertRaisesRegex(ValueError,"IRREGULAR_CANDLE_INTERVAL"):
                load_candles(p)

if __name__=="__main__":
    unittest.main()
