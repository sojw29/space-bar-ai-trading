"""No-network regression tests for composed testnet preflight + durable staging."""
import tempfile
import unittest
from pathlib import Path
from agents.testnet_offline_staging import stage_preflighted_testnet_intent
from agents.bybit_testnet_durable_ledger_v312 import DurableTestnetIntentLedger
from agents.bybit_testnet_order_dryrun_v310 import OrderBlocked
from agents.testnet_order_guard import OrderBlocked as GuardBlocked

SAFE = {
    "SPACE_BAR_ENABLE_TESTNET_ORDERS": "true",
    "SPACE_BAR_CONFIRM_TESTNET_ONLY": "true",
    "SPACE_BAR_EXCHANGE_ENV": "testnet",
    "SPACE_BAR_BYBIT_BASE_URL": "https://api-testnet.bybit.com",
}


def intent():
    return {"symbol": "BTCUSDT", "side": "Sell", "orderType": "Limit",
            "qty": "0.001", "price": "50000", "reduceOnly": True,
            "clientOrderId": "spacebar-stage-0001"}


class OfflineStagingTests(unittest.TestCase):
    def test_stages_once_and_blocks_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intents.db"
            ledger = DurableTestnetIntentLedger(path)
            try:
                result = stage_preflighted_testnet_intent(intent(), settings=SAFE, ledger=ledger, dry_run=True)
                self.assertEqual(result["status"], "STAGED_NOT_SENT")
                self.assertFalse(result["network_enabled"])
                self.assertFalse(result["orders_enabled"])
            finally:
                ledger.close()
            ledger = DurableTestnetIntentLedger(path)
            try:
                with self.assertRaisesRegex(OrderBlocked, "DUPLICATE_CLIENT_ID"):
                    stage_preflighted_testnet_intent(intent(), settings=SAFE, ledger=ledger, dry_run=True)
            finally:
                ledger.close()

    def test_disabled_gate_never_stages(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = DurableTestnetIntentLedger(Path(directory) / "intents.db")
            try:
                with self.assertRaises(GuardBlocked):
                    stage_preflighted_testnet_intent(intent(), settings={}, ledger=ledger, dry_run=True)
                self.assertEqual(ledger.lookup(intent()["clientOrderId"])["status"], "NOT_STAGED")
            finally:
                ledger.close()

    def test_wrong_ledger_or_dry_run_rejected(self):
        with self.assertRaisesRegex(OrderBlocked, "DURABLE_LEDGER_REQUIRED"):
            stage_preflighted_testnet_intent(intent(), settings=SAFE, ledger=None, dry_run=True)
        with self.assertRaisesRegex(OrderBlocked, "DRY_RUN_REQUIRED"):
            stage_preflighted_testnet_intent(intent(), settings=SAFE, ledger=None, dry_run=False)

    def test_reduce_only_required_without_reservation(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = DurableTestnetIntentLedger(Path(directory) / "intents.db")
            try:
                with self.assertRaises(OrderBlocked):
                    stage_preflighted_testnet_intent({**intent(), "reduceOnly": False}, settings=SAFE, ledger=ledger, dry_run=True)
                self.assertEqual(ledger.lookup(intent()["clientOrderId"])["status"], "NOT_STAGED")
            finally:
                ledger.close()


if __name__ == "__main__":
    unittest.main()
