"""V213 sample adequacy diagnostics regression tests."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from regime_sample_adequacy_v213 import assess_regime_sample_adequacy
from publish_scorecard_v203 import publish


class AdequacyTests(unittest.TestCase):
    def test_low_sample_and_empty_regime_cautions(self):
        report={"version":"V212.0","research_only":True,"orders_allowed":False,
                "live_trading_approved":False,
                "rows":[{"strategy":"EMA_CROSS","regimes":[
                    {"regime":"UP","windows":0,"total_hypothetical_trades":0},
                    {"regime":"DOWN","windows":5,"total_hypothetical_trades":20},
                    {"regime":"SIDEWAYS","windows":4,"total_hypothetical_trades":30}]}]}
        result=assess_regime_sample_adequacy(report)
        self.assertEqual(result["limited_groups"],2)
        self.assertEqual(result["checks"][0]["sample_status"],"LIMITED_SAMPLE")
        self.assertEqual(result["checks"][1]["sample_status"],"DESCRIPTIVE_SAMPLE_THRESHOLD_MET")
        self.assertFalse(result["orders_allowed"])

    def test_rejects_unsafe_or_malformed_inputs(self):
        report={"version":"V212.0","research_only":True,"orders_allowed":True,
                "live_trading_approved":False,"rows":[]}
        with self.assertRaisesRegex(ValueError,"INVALID_OR_UNSAFE"):
            assess_regime_sample_adequacy(report)

    def test_published_snapshot_contains_cautions(self):
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
            data=json.loads(output.read_text(encoding="utf-8"))
            check=data["regime_sample_adequacy"]
            self.assertEqual(check["version"],"V213.0")
            self.assertEqual(len(check["checks"]),9)
            self.assertFalse(check["strategy_selection_enabled"])


if __name__=="__main__":
    unittest.main()
