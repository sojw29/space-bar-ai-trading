"""V215 aggregate dispersion availability audit."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from return_drawdown_stability_v215 import assess_return_drawdown_stability
from publish_scorecard_v203 import publish


class StabilityTests(unittest.TestCase):
    def test_missing_dispersion_not_invented(self):
        report={"version":"V212.0","research_only":True,"orders_allowed":False,
                "live_trading_approved":False,
                "rows":[{"strategy":"EMA_CROSS","regimes":[
                    {"regime":"UP","windows":0,"mean_window_return_pct":None,"mean_window_max_drawdown_pct":None},
                    {"regime":"DOWN","windows":1,"mean_window_return_pct":-3,"mean_window_max_drawdown_pct":4},
                    {"regime":"SIDEWAYS","windows":3,"mean_window_return_pct":2,"mean_window_max_drawdown_pct":6}]}]}
        result=assess_return_drawdown_stability(report)
        groups=result["rows"][0]["regimes"]
        self.assertEqual([x["status"] for x in groups],
                         ["NO_WINDOWS","SINGLE_WINDOW_ONLY","AGGREGATE_MEANS_ONLY"])
        self.assertTrue(all(x["dispersion_available"] is False for x in groups))
        self.assertFalse(result["orders_allowed"])

    def test_invalid_group_mean_fails_closed(self):
        report={"version":"V212.0","research_only":True,"orders_allowed":False,
                "live_trading_approved":False,
                "rows":[{"strategy":"EMA_CROSS","regimes":[
                    {"regime":"UP","windows":0,"mean_window_return_pct":2,"mean_window_max_drawdown_pct":None},
                    {"regime":"DOWN","windows":0,"mean_window_return_pct":None,"mean_window_max_drawdown_pct":None},
                    {"regime":"SIDEWAYS","windows":0,"mean_window_return_pct":None,"mean_window_max_drawdown_pct":None}]}]}
        with self.assertRaisesRegex(ValueError,"INCONSISTENT_EMPTY_GROUP"):
            assess_return_drawdown_stability(report)

    def test_publish_attaches_audit(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"BTC_5m.csv"
            output=Path(folder)/"report.json"
            with source.open("w",newline="",encoding="utf-8") as stream:
                writer=csv.DictWriter(stream,fieldnames=["timestamp","open","high","low","close","volume"])
                writer.writeheader()
                for i in range(1200):
                    p=100+i*.02+(5 if (i//25)%2 else -5)
                    writer.writerow({"timestamp":1700000100+i*300,"open":p,
                                     "high":p+1,"low":p-1,"close":p,
                                     "volume":150 if i%17==0 else 80})
            publish(source,output)
            result=json.loads(output.read_text(encoding="utf-8"))["return_drawdown_stability"]
            self.assertEqual(result["version"],"V215.0")
            self.assertEqual(len(result["rows"]),3)
            self.assertFalse(result["live_trading_approved"])


if __name__=="__main__":
    unittest.main()
