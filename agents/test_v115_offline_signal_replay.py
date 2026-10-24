import csv
import tempfile
import unittest
from pathlib import Path
from offline_signal_replay_v115 import read_signals, replay, run

def bars(signals=("BUY","HOLD","SELL","HOLD")):
    return [{"timestamp":str(1700000000000+i*300000),
             "open":str(100+i*2),"high":str(101+i*2),
             "low":str(99+i*2),"close":str(100+i*2),
             "volume":"100","signal":signal}
            for i,signal in enumerate(signals)]

class OfflineSignalReplayTests(unittest.TestCase):
    def test_signal_executes_next_bar(self):
        result = replay(bars())
        self.assertEqual(result["hypothetical_fills"][0],
                         {"signal_bar_index":0,"fill_bar_index":1,"side":"BUY"})
        self.assertEqual(result["hypothetical_fills"][1],
                         {"signal_bar_index":2,"fill_bar_index":3,"side":"SELL"})
        self.assertEqual(result["performance"]["hypothetical_buy_events"],1)
        self.assertEqual(result["performance"]["hypothetical_sell_events"],1)

    def test_final_bar_signal_not_filled(self):
        result = replay(bars(("HOLD","HOLD","HOLD","BUY")))
        self.assertEqual(result["hypothetical_fills"],[])

    def test_repeated_buy_does_not_pyramid(self):
        result = replay(bars(("BUY","BUY","BUY","HOLD")))
        self.assertEqual(result["performance"]["hypothetical_buy_events"],1)

    def test_no_exchange_orders(self):
        result = replay(bars())
        self.assertFalse(result["exchange_connected"])
        self.assertEqual(result["orders_submitted_to_exchange"],0)
        self.assertFalse(result["live_trading_approved"])

    def test_replay_is_deterministic(self):
        self.assertEqual(replay(bars()),replay(bars()))

    def test_invalid_fraction(self):
        with self.assertRaisesRegex(ValueError,"INVALID_BUDGET_FRACTION"):
            replay(bars(),0.5)

    def test_strict_csv(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"signals.csv"
            with path.open("w",newline="",encoding="utf-8") as f:
                writer=csv.DictWriter(f,fieldnames=list(bars()[0]))
                writer.writeheader()
                writer.writerows(bars())
            self.assertEqual(len(read_signals(path)),4)
            self.assertEqual(run(path)["bars_processed"],4)

    def test_invalid_signal_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"signals.csv"
            invalid=bars()
            invalid[0]["signal"]="LIVE_BUY"
            with path.open("w",newline="",encoding="utf-8") as f:
                writer=csv.DictWriter(f,fieldnames=list(invalid[0]))
                writer.writeheader()
                writer.writerows(invalid)
            with self.assertRaisesRegex(ValueError,"INVALID_SIGNAL"):
                run(path)

if __name__ == "__main__":
    unittest.main()
