"""V216 actual per-window dispersion regression tests."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from regime_strategy_metrics_v212 import compare_regime_strategy_metrics
from regime_window_dispersion_v216 import assess_window_dispersion
from publish_scorecard_v203 import publish


class DispersionTests(unittest.TestCase):
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

    def test_actual_windows_and_dispersion(self):
        report=compare_regime_strategy_metrics(self.source)
        self.assertEqual(len(report["window_observations"]),4)
        result=assess_window_dispersion(report)
        self.assertEqual(result["version"],"V216.0")
        for row in result["rows"]:
            self.assertEqual(sum(x["windows"] for x in row["regimes"]),4)
            for group in row["regimes"]:
                if group["windows"]:
                    self.assertGreaterEqual(group["return_dispersion"]["population_stddev_pct"],0)
                    self.assertGreaterEqual(group["drawdown_dispersion"]["population_stddev_pct"],0)
                else:
                    self.assertIsNone(group["return_dispersion"])
        self.assertFalse(result["orders_allowed"])

    def test_tampered_window_count_rejected(self):
        report=compare_regime_strategy_metrics(self.source)
        report["classified_windows"]+=1
        with self.assertRaisesRegex(ValueError,"WINDOW_COUNT_MISMATCH"):
            assess_window_dispersion(report)

    def test_published_report_has_dispersion(self):
        output=Path(self.tmp.name)/"scorecard.json"
        publish(self.source,output)
        report=json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["regime_window_dispersion"]["version"],"V216.0")
        self.assertFalse(report["regime_window_dispersion"]["live_trading_approved"])


if __name__=="__main__":
    unittest.main()
