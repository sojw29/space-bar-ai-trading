import csv
import tempfile
import unittest
from pathlib import Path
from offline_research_report_v123 import build,markdown,run

def sample(n=800):
    rows=[]
    for i in range(n):
        price=100+i*0.08+(4 if i%30<15 else -4)
        rows.append({"timestamp":str(1700000000000+i*300000),
                     "open":str(price-0.2),"high":str(price+1),
                     "low":str(price-1),"close":str(price),
                     "volume":str(1500 if i%11==0 else 100)})
    return rows

class OfflineResearchReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=build(sample())

    def test_scorecard_present(self):
        self.assertEqual(self.report["scorecard"]["version"],"V121.0")

    def test_audit_present(self):
        self.assertEqual(self.report["risk_audit"]["version"],"V122.0")

    def test_folds_present(self):
        self.assertEqual(len(self.report["folds"]),3)

    def test_markdown_heading(self):
        self.assertIn("V123 Offline Research Report",markdown(self.report))

    def test_markdown_warning_section(self):
        self.assertIn("## Risk Warnings",markdown(self.report))

    def test_markdown_folds_section(self):
        self.assertIn("## Chronological Validation Folds",markdown(self.report))

    def test_no_orders(self):
        self.assertFalse(self.report["live_trading_approved"])
        self.assertEqual(self.report["orders_submitted_to_exchange"],0)

    def test_invalid_report(self):
        with self.assertRaisesRegex(ValueError,"INVALID_REPORT"):
            markdown({"version":"V122.0"})

    def test_deterministic(self):
        self.assertEqual(markdown(self.report),markdown(self.report))

    def test_csv_pipeline(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"history.csv"
            rows=sample()
            with path.open("w",newline="",encoding="utf-8") as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            self.assertEqual(run(path)["version"],"V123.0")

if __name__=="__main__":
    unittest.main()
