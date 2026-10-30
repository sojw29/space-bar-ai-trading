"""V217 consecutive negative-window stress tests."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from losing_window_streaks_v217 import assess_losing_window_streaks
from publish_scorecard_v203 import publish


class LosingWindowTests(unittest.TestCase):
    def test_known_streak_and_worst_window(self):
        values=[1,-2,-3,0,-4,-5,-6,2]
        windows=[{"start_validation_index":i*90,
                  "end_validation_index_exclusive":(i+1)*90,
                  "strategy_metrics":{"EMA_CROSS":{"return":value}}}
                 for i,value in enumerate(values)]
        report={"version":"V212.0","research_only":True,"orders_allowed":False,
                "live_trading_approved":False,"window_candles":90,
                "classified_windows":len(windows),"window_observations":windows,
                "rows":[{"strategy":"EMA_CROSS"}]}
        result=assess_losing_window_streaks(report)["rows"][0]
        self.assertEqual(result["longest_consecutive_negative_windows"],3)
        self.assertEqual(result["longest_streak_start_window_index"],4)
        self.assertEqual(result["longest_streak_end_window_index"],6)
        self.assertEqual(result["worst_single_window_return_pct"],-6)
        self.assertEqual(result["negative_return_windows"],5)

    def test_rejects_noncontiguous_windows(self):
        report={"version":"V212.0","research_only":True,"orders_allowed":False,
                "live_trading_approved":False,"window_candles":90,
                "classified_windows":1,"window_observations":[
                    {"start_validation_index":2,"end_validation_index_exclusive":92}],
                "rows":[{"strategy":"EMA_CROSS"}]}
        with self.assertRaisesRegex(ValueError,"NONCONTIGUOUS"):
            assess_losing_window_streaks(report)

    def test_publish_attaches_stress(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"BTC_5m.csv"
            output=Path(folder)/"scorecard.json"
            with source.open("w",newline="",encoding="utf-8") as stream:
                writer=csv.DictWriter(stream,fieldnames=["timestamp","open","high","low","close","volume"])
                writer.writeheader()
                for i in range(1200):
                    p=100+i*.02+(5 if (i//25)%2 else -5)
                    writer.writerow({"timestamp":1700000100+i*300,"open":p,
                                     "high":p+1,"low":p-1,"close":p,
                                     "volume":150 if i%17==0 else 80})
            publish(source,output)
            report=json.loads(output.read_text(encoding="utf-8"))
            result=report["losing_window_streaks"]
            self.assertEqual(result["version"],"V217.0")
            self.assertEqual(len(result["rows"]),3)
            self.assertFalse(result["orders_allowed"])


if __name__=="__main__":
    unittest.main()
