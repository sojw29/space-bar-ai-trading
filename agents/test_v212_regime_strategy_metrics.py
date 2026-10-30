"""V212 research-only ex-post regime-strategy tests."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from regime_strategy_metrics_v212 import compare_regime_strategy_metrics
from publish_scorecard_v203 import publish


class RegimeStrategyTests(unittest.TestCase):
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

    def test_regime_groups_cover_nonoverlapping_windows(self):
        result=compare_regime_strategy_metrics(self.source)
        self.assertEqual(result["classified_windows"],4)
        self.assertEqual(result["unclassified_tail_candles"],0)
        self.assertEqual(len(result["rows"]),3)
        for row in result["rows"]:
            self.assertEqual(sum(x["windows"] for x in row["regimes"]),4)
            self.assertFalse(any(x["mean_window_return_pct"] is not None
                                 for x in row["regimes"] if x["windows"]==0))
        self.assertFalse(result["strategy_selection_enabled"])
        self.assertFalse(result["orders_allowed"])

    def test_insufficient_holdout_is_not_fabricated(self):
        short=Path(self.tmp.name)/"short.csv"
        with self.source.open(encoding="utf-8") as src,short.open("w",encoding="utf-8") as dst:
            for i,line in enumerate(src):
                if i>250: break
                dst.write(line)
        result=compare_regime_strategy_metrics(short)
        self.assertEqual(result["status"],"INSUFFICIENT_HOLDOUT_CANDLES")
        self.assertEqual(result["classified_windows"],0)

    def test_publisher_attaches_research_only_regime_metrics(self):
        output=Path(self.tmp.name)/"scorecard.json"
        publish(self.source,output)
        report=json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["regime_strategy_metrics"]["version"],"V212.0")
        self.assertFalse(report["regime_strategy_metrics"]["live_trading_approved"])


if __name__=="__main__":
    unittest.main()
