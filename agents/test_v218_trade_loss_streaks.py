"""V218 trade-level losing streak tests."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from trade_loss_streaks_v218 import summarize_trade_losses, assess_trade_loss_streaks
from publish_scorecard_v203 import publish


class TradeLossTests(unittest.TestCase):
    def test_known_trade_streak(self):
        result=summarize_trade_losses([5,-2,-3,0,-4,-5,-6,1])
        self.assertEqual(result["longest_consecutive_losing_trades"],3)
        self.assertEqual(result["longest_streak_start_trade_index"],4)
        self.assertEqual(result["longest_streak_end_trade_index"],6)
        self.assertEqual(result["worst_consecutive_loss_sum_cash"],-15)
        self.assertEqual(result["losing_trades"],5)

    def test_empty_and_nonfinite(self):
        self.assertEqual(summarize_trade_losses([])["status"],"NO_TRADES")
        with self.assertRaisesRegex(ValueError,"NONFINITE"):
            summarize_trade_losses([float("nan")])

    def test_publish_trade_streaks(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"BTC_5m.csv"
            output=Path(folder)/"report.json"
            with source.open("w",newline="",encoding="utf-8") as stream:
                writer=csv.DictWriter(stream,fieldnames=["timestamp","open","high","low","close","volume"])
                writer.writeheader()
                for i in range(1200):
                    p=100+i*.02+(5 if (i//25)%2 else -5)
                    writer.writerow({"timestamp":1700000100+i*300,"open":p,
                                     "high":p+1,"low":p-1,"close":p,
                                     "volume":150 if i%17==0 else 80})
            publish(source,output)
            result=json.loads(output.read_text(encoding="utf-8"))["trade_loss_streaks"]
            self.assertEqual(result["version"],"V218.0")
            self.assertEqual(len(result["rows"]),3)
            self.assertFalse(result["orders_allowed"])


if __name__=="__main__":
    unittest.main()
