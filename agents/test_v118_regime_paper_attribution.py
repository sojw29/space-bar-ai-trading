import csv
import tempfile
import unittest
from pathlib import Path
from regime_paper_attribution_v118 import REGIMES, analyze, run
from multi_strategy_paper_v117 import STRATEGIES

def sample(n=260):
    rows=[]
    for i in range(n):
        price=100+i*0.15+(2 if i%12<6 else -2)
        rows.append({"timestamp":str(1700000000000+i*300000),
                     "open":str(price-0.2),"high":str(price+1),
                     "low":str(price-1),"close":str(price),
                     "volume":str(1000 if i%17==0 else 100)})
    return rows

class RegimePaperAttributionTests(unittest.TestCase):
    def test_three_strategies(self):
        result=analyze(sample())
        self.assertEqual([x["strategy"] for x in result["strategies"]],list(STRATEGIES))

    def test_all_regimes_present(self):
        for strategy in analyze(sample())["strategies"]:
            self.assertEqual([r["regime"] for r in strategy["by_entry_regime"]],list(REGIMES))

    def test_entries_reconcile_to_buys(self):
        for strategy in analyze(sample())["strategies"]:
            total=sum(x["entries"] for x in strategy["by_entry_regime"])
            self.assertGreaterEqual(strategy["hypothetical_fills"],total)

    def test_no_live_trading(self):
        result=analyze(sample())
        self.assertFalse(result["exchange_connected"])
        self.assertEqual(result["orders_submitted_to_exchange"],0)
        self.assertFalse(result["selection_or_approval"])

    def test_deterministic(self):
        self.assertEqual(analyze(sample()),analyze(sample()))

    def test_insufficient_history(self):
        with self.assertRaisesRegex(ValueError,"INSUFFICIENT_STRATEGY_HISTORY"):
            analyze(sample(201))

    def test_no_unearned_sample_claim(self):
        for strategy in analyze(sample())["strategies"]:
            for regime in strategy["by_entry_regime"]:
                self.assertEqual(regime["sample_sufficient"],regime["closed_trades"]>=30)

    def test_csv_pipeline(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"history.csv"
            rows=sample()
            with path.open("w",newline="",encoding="utf-8") as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            self.assertEqual(run(path)["bars_processed"],260)

if __name__=="__main__":
    unittest.main()
