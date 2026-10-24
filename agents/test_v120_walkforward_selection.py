import csv
import tempfile
import unittest
from pathlib import Path
from walkforward_selection_v120 import walkforward,run

def sample(n=800):
    rows=[]
    for i in range(n):
        price=100+i*0.08+(4 if i%30<15 else -4)
        rows.append({"timestamp":str(1700000000000+i*300000),
                     "open":str(price-0.2),"high":str(price+1),
                     "low":str(price-1),"close":str(price),
                     "volume":str(1500 if i%11==0 else 100)})
    return rows

class WalkforwardSelectionTests(unittest.TestCase):
    def test_fold_count(self):
        result=walkforward(sample())
        self.assertEqual(result["fold_count"],3)

    def test_strict_time_order(self):
        for fold in walkforward(sample())["folds"]:
            self.assertLess(int(fold["train_end_timestamp"]),int(fold["test_start_timestamp"]))

    def test_no_overlapping_test_windows(self):
        folds=walkforward(sample())["folds"]
        for previous,current in zip(folds,folds[1:]):
            self.assertLess(int(previous["test_end_timestamp"]),int(current["test_start_timestamp"]))

    def test_future_change_does_not_change_earlier_fold(self):
        original=sample()
        modified=[dict(x) for x in original]
        for i in range(600,len(modified)):
            p=float(modified[i]["close"])*1.1
            modified[i].update({"open":str(p),"high":str(p+1),"low":str(p-1),"close":str(p)})
        self.assertEqual(walkforward(original)["folds"][0],walkforward(modified)["folds"][0])

    def test_repeatability(self):
        self.assertEqual(walkforward(sample()),walkforward(sample()))

    def test_reject_small_window(self):
        with self.assertRaisesRegex(ValueError,"INVALID_TEST_BARS"):
            walkforward(sample(),test_bars=20)

    def test_reject_insufficient_history(self):
        with self.assertRaisesRegex(ValueError,"INSUFFICIENT_WALKFORWARD_HISTORY"):
            walkforward(sample(400))

    def test_no_orders(self):
        result=walkforward(sample())
        self.assertFalse(result["live_trading_approved"])
        self.assertEqual(result["orders_submitted_to_exchange"],0)
        self.assertFalse(result["continuous_portfolio_return_available"])

    def test_csv_pipeline(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"history.csv"
            rows=sample()
            with path.open("w",newline="",encoding="utf-8") as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            self.assertEqual(run(path)["fold_count"],3)

if __name__=="__main__":
    unittest.main()
