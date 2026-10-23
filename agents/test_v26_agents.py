"""V26 offline contract tests: no network, exchange or model dependencies."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import multi_agent_v26 as v26


def candles():
    start = 1700000100
    result = []
    for i in range(60):
        p = 100 + i * 0.12
        result.append({"timestamp": start + i * 300, "open": p - 0.04,
                       "high": p + 0.15, "low": p - 0.15,
                       "close": p, "volume": 10.0})
    return result


class MultiAgentTests(unittest.TestCase):
    def test_contract_and_no_execution(self):
        result = v26.analyze(candles())
        self.assertEqual(len(result["agents"]), 6)
        self.assertEqual({a["agent"] for a in result["agents"]}, set(v26.AGENTS))
        self.assertIn(result["commander"]["decision"], v26.DECISIONS)
        self.assertFalse(result["orders_enabled"])
        self.assertFalse(result["live_trading_approved"])
        self.assertFalse(result["independent_oos_verified"])
        self.assertEqual(result["agents"][4]["decision"], "WAIT")

    def test_rejects_missing_bar(self):
        data = candles()
        data[30]["timestamp"] += 300
        with self.assertRaises(ValueError):
            v26.analyze(data)

    def test_rejects_future_and_bad_ohlcv(self):
        data = candles()
        data[-1]["timestamp"] = int(datetime.now(timezone.utc).timestamp()) + 300
        with self.assertRaises(ValueError):
            v26.analyze(data)
        data = candles()
        data[4]["low"] = data[4]["high"] + 1
        with self.assertRaises(ValueError):
            v26.analyze(data)

    def test_deterministic(self):
        self.assertEqual(v26.analyze(candles()), v26.analyze(candles()))

    def test_no_signal_on_flat_market(self):
        data = candles()
        for row in data:
            row.update(open=100, high=100, low=100, close=100, volume=10)
        result = v26.analyze(data)
        self.assertEqual(result["commander"]["decision"], "WAIT")


if __name__ == "__main__":
    unittest.main(verbosity=2)
