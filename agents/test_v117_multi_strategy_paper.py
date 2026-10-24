import csv
import tempfile
import unittest
from pathlib import Path
from multi_strategy_paper_v117 import STRATEGIES, compare, generate, run

def sample(n=260):
    rows=[]
    for i in range(n):
        price=100+i*0.15+(2 if i%12<6 else -2)
        rows.append({"timestamp":str(1700000000000+i*300000),
                     "open":str(price-0.2),"high":str(price+1),
                     "low":str(price-1),"close":str(price),
                     "volume":str(1000 if i%17==0 else 100)})
    return rows

class MultiStrategyPaperTests(unittest.TestCase):
    def test_all_strategies_present(self):
        result=compare(sample())
        self.assertEqual([x["strategy"] for x in result["strategies"]],list(STRATEGIES))

    def test_warmup(self):
        for strategy in STRATEGIES:
            signals=generate(sample(),strategy)
            self.assertTrue(all(x["signal"]=="HOLD" for x in signals[:50]))

    def test_repeatability(self):
        self.assertEqual(compare(sample()),compare(sample()))

    def test_no_live_orders(self):
        result=compare(sample())
        self.assertFalse(result["exchange_connected"])
        self.assertEqual(result["orders_submitted_to_exchange"],0)
        self.assertFalse(result["selection_or_approval"])

    def test_unknown_strategy(self):
        with self.assertRaisesRegex(ValueError,"UNKNOWN_STRATEGY"):
            generate(sample(),"LIVE_TRADING")

    def test_short_history(self):
        with self.assertRaisesRegex(ValueError,"INSUFFICIENT_STRATEGY_HISTORY"):
            generate(sample(201),"EMA_PULLBACK")

    def test_all_have_metrics(self):
        for result in compare(sample())["strategies"]:
            self.assertIn("max_drawdown_pct",result)
            self.assertIn("fees_paid",result)
            self.assertIn("total_return_pct",result)

    def test_csv_pipeline(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"history.csv"
            rows=sample()
            with path.open("w",newline="",encoding="utf-8") as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            self.assertEqual(run(path)["bars_processed"],260)

if __name__ == "__main__":
    unittest.main()
