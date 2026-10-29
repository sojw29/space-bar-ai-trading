"""V203 pipeline-to-snapshot integration and atomic failure behavior."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from publish_scorecard_v203 import publish
from strategy_scorecard_html_v199 import render


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "BTC_5m.csv"
        self.target = Path(self.tmp.name) / "reports" / "strategy_scorecard_latest.json"
        with self.source.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["timestamp","open","high","low","close","volume"])
            writer.writeheader()
            for i in range(600):
                price = 100 + 0.02*i + (4 if (i//25)%2 else -4)
                writer.writerow({"timestamp":1700000000000+i*300000,
                                 "open":price,"high":price+1,"low":price-1,
                                 "close":price,"volume":120 if i%13==0 else 70})

    def test_real_pipeline_publishes_renderable_snapshot(self):
        summary = publish(self.source, self.target)
        self.assertEqual(summary["status"], "OFFLINE_SNAPSHOT_PUBLISHED")
        self.assertFalse(summary["orders_enabled"])
        data = json.loads(self.target.read_text(encoding="utf-8"))
        self.assertEqual(data["version"], "V105.0")
        self.assertEqual(len(data["strategy_scorecard"]["rows"]), 3)
        self.assertIn("NO LIVE ORDERS", render(data))

    def test_failed_validation_preserves_previous_snapshot(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_text('{"existing":true}', encoding="utf-8")
        with patch("publish_scorecard_v203.render", side_effect=ValueError("REJECTED")):
            with self.assertRaises(ValueError):
                publish(self.source, self.target)
        self.assertEqual(self.target.read_text(encoding="utf-8"), '{"existing":true}')

    def test_refuses_non_json_output(self):
        with self.assertRaises(ValueError):
            publish(self.source, Path(self.tmp.name)/"out.txt")


if __name__ == "__main__":
    unittest.main()
