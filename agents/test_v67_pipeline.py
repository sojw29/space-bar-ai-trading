import csv
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from research_pipeline_v67 import run

NOW = datetime(2026, 10, 23, 12, tzinfo=timezone.utc)
LAST = int(datetime(2026, 10, 19, 23, 55, tzinfo=timezone.utc).timestamp())

class PipelineTests(unittest.TestCase):
    def test_missing_inputs_fail_closed_and_write_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            result = run(base / "data", base / "reports", NOW)
            self.assertEqual(result["status"], "BLOCKED")
            for name in ("v63/diagnostics.json", "v64/archive_lag.json",
                         "v65/quality.json", "v66/health.json"):
                self.assertTrue((base / "reports" / name).exists())
            self.assertFalse(result["live_trading_approved"])

    def test_complete_candles_still_block_without_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data = base / "data"
            data.mkdir()
            for coin in ("BTC", "ETH", "SOL"):
                for tf in (1, 5, 15):
                    stamp = LAST - (LAST % (tf * 60))
                    with (data / f"{coin}_{tf}m.csv").open("w", newline="") as f:
                        w = csv.writer(f)
                        w.writerow(["timestamp", "open", "high", "low", "close", "volume"])
                        w.writerow([stamp-tf*60, 1, 2, 0.5, 1.5, 10])
                        w.writerow([stamp, 1, 2, 0.5, 1.5, 10])
            result = run(data, base / "reports", NOW)
            self.assertEqual(result["status"], "BLOCKED")
            v65 = json.loads((base / "reports/v65/quality.json").read_text())
            self.assertEqual(len(v65["results"]), 9)

if __name__ == "__main__":
    unittest.main()
