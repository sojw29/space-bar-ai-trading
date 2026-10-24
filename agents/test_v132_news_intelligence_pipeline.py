import csv
import json
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

from news_intelligence_pipeline_v132 import build,run

START=datetime(2026,10,24,9,tzinfo=timezone.utc)
OBSERVED="2026-10-24T12:00:00+00:00"
def news(n=10):
    return {"articles":[{"url":"https://example.org/story/"+str(i),
        "seendate":"20261024091000","title":"Bitcoin ETF update "+str(i),
        "domain":"example.org"} for i in range(n)]}
def candles(n=240):
    return [{"time":START+timedelta(minutes=i),
             "open":100+i,"high":101+i,"low":99+i,
             "close":100+i,"volume":10} for i in range(n)]
def pipeline(n=10):
    return build(news(n),"BTC",OBSERVED,candles(),60)

class NewsPipelineTests(unittest.TestCase):
    def test_all_stages_present(self):
        r=pipeline()
        self.assertEqual(r["pipeline_stages"],["V127","V128","V129","V130","V131"])
    def test_all_versions(self):
        r=pipeline()
        self.assertEqual([r[x]["version"] for x in
            ("collector","taxonomy","event_study","impact","guardian")],
            ["V127.0","V128.0","V129.0","V130.0","V131.0"])
    def test_collector_count(self):
        self.assertEqual(pipeline()["collector"]["count"],10)
    def test_taxonomy(self):
        self.assertEqual(pipeline()["taxonomy"]["category_counts"]["ETF"],10)
    def test_event_study(self):
        self.assertEqual(pipeline()["event_study"]["event_count"],10)
    def test_guardian_matches(self):
        self.assertEqual(pipeline()["guardian"]["matched_events"],10)
    def test_guardian_warns_on_availability(self):
        codes=[w["code"] for w in pipeline()["guardian"]["warnings"]]
        self.assertIn("UNVERIFIED_NEWS_AVAILABILITY",codes)
    def test_no_trading(self):
        r=pipeline()
        self.assertFalse(r["live_trading_approved"])
        self.assertEqual(r["orders_submitted_to_exchange"],0)
        self.assertFalse(r["historical_news_availability_verified"])
    def test_low_samples(self):
        self.assertEqual(pipeline(2)["impact"]["categories"][0]["horizons"]["5m"]["samples"],2)
    def test_deterministic(self):
        self.assertEqual(pipeline(),pipeline())
    def test_invalid_topic(self):
        with self.assertRaisesRegex(ValueError,"INVALID_TOPIC"):
            build(news(),"DOGE",OBSERVED,candles(),60)
    def test_invalid_timestamp(self):
        with self.assertRaisesRegex(ValueError,"INVALID_OBSERVATION_TIME"):
            build(news(),"BTC","2026-10-24T12:00:00",candles(),60)
    def test_json_csv_pipeline(self):
        with tempfile.TemporaryDirectory() as temp:
            raw=Path(temp)/"news.json"
            data=Path(temp)/"ohlcv.csv"
            raw.write_text(json.dumps(news()),encoding="utf-8")
            with data.open("w",newline="",encoding="utf-8") as stream:
                writer=csv.DictWriter(stream,fieldnames=["timestamp","open","high","low","close","volume"])
                writer.writeheader()
                for row in candles():
                    writer.writerow({"timestamp":int(row["time"].timestamp()*1000),
                        **{key:row[key] for key in ("open","high","low","close","volume")}})
            self.assertEqual(run(raw,data,"BTC",OBSERVED)["version"],"V132.0")

if __name__=="__main__":
    unittest.main()
