"""V211 market regime diagnostics tests."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from market_regime_diagnostics_v211 import inspect_regimes
from publish_scorecard_v203 import publish


class RegimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source=Path(self.tmp.name)/"BTC_5m.csv"
        with self.source.open("w",newline="",encoding="utf-8") as stream:
            writer=csv.DictWriter(stream,fieldnames=["timestamp","open","high","low","close","volume"])
            writer.writeheader()
            for i in range(1200):
                p=100+i*.02+(5 if (i//25)%2 else -5)
                writer.writerow({"timestamp":1700000100+i*300,"open":p,
                                 "high":p+1,"low":p-1,"close":p,
                                 "volume":150 if i%17==0 else 80})

    def test_counts_cover_complete_nonoverlapping_windows(self):
        report=inspect_regimes(self.source)
        self.assertEqual(report["status"],"DESCRIPTIVE_ONLY")
        self.assertEqual(sum(report["counts"].values()),12)
        self.assertEqual(len(report["observations"]),12)
        self.assertEqual(report["unclassified_tail_candles"],0)
        self.assertTrue(all(x["candles"]==30 for x in report["observations"]))
        self.assertFalse(report["orders_allowed"])

    def test_publish_includes_regimes(self):
        output=Path(self.tmp.name)/"report.json"
        publish(self.source,output)
        data=json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(data["market_regime_diagnostics"]["version"],"V211.0")
        self.assertFalse(data["market_regime_diagnostics"]["strategy_selection_enabled"])


if __name__=="__main__":
    unittest.main()
