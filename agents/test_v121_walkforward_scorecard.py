import csv
import tempfile
import unittest
from pathlib import Path
from walkforward_scorecard_v121 import scorecard,run

def fixture(folds):
    return {"version":"V120.0","folds":folds}

def fold(strategy,ret="1.0",dd="2.0",buys=3,sells=3):
    return {"selected_strategy":strategy,"validation":({
        "total_return_pct":ret,"max_drawdown_pct":dd,
        "hypothetical_buy_events":buys,"hypothetical_sell_events":sells
    } if strategy is not None else None)}

def sample(n=800):
    rows=[]
    for i in range(n):
        price=100+i*0.08+(4 if i%30<15 else -4)
        rows.append({"timestamp":str(1700000000000+i*300000),
                     "open":str(price-0.2),"high":str(price+1),
                     "low":str(price-1),"close":str(price),
                     "volume":str(1500 if i%11==0 else 100)})
    return rows

class WalkforwardScorecardTests(unittest.TestCase):
    def test_basic_stats(self):
        result=scorecard(fixture([fold("EMA_CROSS","2"),fold("EMA_PULLBACK","-1")]))
        self.assertEqual(result["mean_fold_return_pct"],0.5)
        self.assertEqual(result["positive_fold_rate_pct"],50)
        self.assertEqual(result["strategy_switch_count"],1)

    def test_abstention(self):
        result=scorecard(fixture([fold(None),fold("EMA_CROSS")]))
        self.assertEqual(result["abstained_folds"],1)
        self.assertEqual(result["abstention_rate_pct"],50)

    def test_all_abstain(self):
        result=scorecard(fixture([fold(None)]))
        self.assertIsNone(result["mean_fold_return_pct"])
        self.assertIsNone(result["positive_fold_rate_pct"])

    def test_no_compounding_claim(self):
        result=scorecard(fixture([fold("EMA_CROSS"),fold("EMA_CROSS")]))
        self.assertIsNone(result["compounded_portfolio_return_pct"])
        self.assertFalse(result["live_trading_approved"])

    def test_invalid_version(self):
        with self.assertRaisesRegex(ValueError,"INVALID_WALKFORWARD_REPORT"):
            scorecard({"version":"V119.0","folds":[fold(None)]})

    def test_invalid_negative_drawdown(self):
        with self.assertRaisesRegex(ValueError,"INVALID_VALIDATION_METRICS"):
            scorecard(fixture([fold("EMA_CROSS",dd="-1")]))

    def test_invalid_sell_count(self):
        with self.assertRaisesRegex(ValueError,"INVALID_VALIDATION_METRICS"):
            scorecard(fixture([fold("EMA_CROSS",buys=1,sells=2)]))

    def test_deterministic(self):
        report=fixture([fold("EMA_CROSS"),fold(None)])
        self.assertEqual(scorecard(report),scorecard(report))

    def test_csv_pipeline(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"history.csv"
            rows=sample()
            with path.open("w",newline="",encoding="utf-8") as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            self.assertEqual(run(path)["total_folds"],3)

if __name__=="__main__":
    unittest.main()
