import csv
import tempfile
import unittest
from pathlib import Path
from holdout_strategy_selection_v119 import evaluate, run

def sample(n=900):
    rows=[]
    for i in range(n):
        price=100+i*0.08+(4 if i%30<15 else -4)
        rows.append({"timestamp":str(1700000000000+i*300000),
                     "open":str(price-0.2),"high":str(price+1),
                     "low":str(price-1),"close":str(price),
                     "volume":str(1500 if i%11==0 else 100)})
    return rows

class HoldoutStrategySelectionTests(unittest.TestCase):
    def test_chronological_boundary(self):
        result=evaluate(sample())
        self.assertLess(int(result["train_end_timestamp"]),int(result["validation_start_timestamp"]))

    def test_all_train_candidates(self):
        result=evaluate(sample())
        self.assertEqual(len(result["train_candidates"]),3)

    def test_selected_strategy_from_training_only(self):
        rows=sample()
        first=evaluate(rows)
        modified=[dict(r) for r in rows]
        for i in range(630,len(modified)):
            price=float(modified[i]["close"])*1.1
            modified[i].update({"open":str(price),"high":str(price+1),
                                "low":str(price-1),"close":str(price)})
        second=evaluate(modified)
        self.assertEqual(first["train_candidates"],second["train_candidates"])
        self.assertEqual(first["selected_strategy"],second["selected_strategy"])

    def test_no_orders(self):
        result=evaluate(sample())
        self.assertFalse(result["live_trading_approved"])
        self.assertFalse(result["validated_edge"])
        self.assertEqual(result["orders_submitted_to_exchange"],0)

    def test_repeatable(self):
        self.assertEqual(evaluate(sample()),evaluate(sample()))

    def test_insufficient_holdout(self):
        with self.assertRaisesRegex(ValueError,"INSUFFICIENT_HOLDOUT_BARS"):
            evaluate(sample(450))

    def test_bad_fraction(self):
        with self.assertRaisesRegex(ValueError,"INVALID_TRAIN_FRACTION"):
            evaluate(sample(),0.99)

    def test_csv_pipeline(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"history.csv"
            rows=sample()
            with path.open("w",newline="",encoding="utf-8") as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            self.assertEqual(run(path)["train_bars"],630)

if __name__=="__main__":
    unittest.main()
