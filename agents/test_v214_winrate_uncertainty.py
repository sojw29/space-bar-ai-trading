"""V214 Wilson interval validation and offline publishing."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from winrate_uncertainty_v214 import attach_winrate_uncertainty, wilson_interval
from publish_scorecard_v203 import publish


class UncertaintyTests(unittest.TestCase):
    def test_wilson_extremes_and_empty(self):
        self.assertIsNone(wilson_interval(0,0))
        self.assertEqual(wilson_interval(0,10)[0],0)
        self.assertEqual(wilson_interval(10,10)[1],100)
        low,high=wilson_interval(5,10)
        self.assertLess(low,50)
        self.assertGreater(high,50)

    def test_inconsistent_win_rate_rejected(self):
        card={"version":"V197.0","research_only":True,"orders_allowed":False,
              "live_trading_approved":False,
              "rows":[{"strategy":"EMA_CROSS","holdout_trades":10,
                       "holdout_win_rate_pct":55.0}]}
        with self.assertRaisesRegex(ValueError,"INCONSISTENT"):
            attach_winrate_uncertainty(card)

    def test_publish_contains_uncertainty_without_approval(self):
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
            result=report["winrate_uncertainty"]
            self.assertEqual(result["version"],"V214.0")
            self.assertEqual(len(result["rows"]),3)
            self.assertFalse(result["live_trading_approved"])


if __name__=="__main__":
    unittest.main()
