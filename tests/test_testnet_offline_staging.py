"""No-network regression tests for composed testnet preflight + durable staging."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from agents.testnet_offline_staging import stage_preflighted_testnet_intent, stage_preflighted_testnet_intent_status
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

    def test_conflicting_payload_preserves_original_record(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intents.db"
            ledger = DurableTestnetIntentLedger(path)
            try:
                original = stage_preflighted_testnet_intent(intent(), settings=SAFE, ledger=ledger, dry_run=True)
                with self.assertRaisesRegex(OrderBlocked, "CLIENT_ID_CONFLICT"):
                    stage_preflighted_testnet_intent(
                        {**intent(), "price": "49000"}, settings=SAFE, ledger=ledger, dry_run=True
                    )
                self.assertEqual(
                    ledger.lookup(intent()["clientOrderId"])["payload_sha256"],
                    original["payload_sha256"],
                )
            finally:
                ledger.close()

    def test_preflight_quantity_failure_never_reserves_client_id(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = DurableTestnetIntentLedger(Path(directory) / "intents.db")
            try:
                with self.assertRaises(GuardBlocked):
                    stage_preflighted_testnet_intent(
                        {**intent(), "qty": "0.02", "price": "100"},
                        settings=SAFE, ledger=ledger, dry_run=True,
                    )
                self.assertEqual(ledger.lookup(intent()["clientOrderId"])["status"], "NOT_STAGED")
                result = stage_preflighted_testnet_intent(intent(), settings=SAFE, ledger=ledger, dry_run=True)
                self.assertEqual(result["status"], "STAGED_NOT_SENT")
            finally:
                ledger.close()

    def test_missing_dry_run_does_not_reserve_client_id(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = DurableTestnetIntentLedger(Path(directory) / "intents.db")
            try:
                with self.assertRaisesRegex(OrderBlocked, "DRY_RUN_REQUIRED"):
                    stage_preflighted_testnet_intent(intent(), settings=SAFE, ledger=ledger)
                self.assertEqual(ledger.lookup(intent()["clientOrderId"])["status"], "NOT_STAGED")
            finally:
                ledger.close()

    def test_locked_database_fails_without_staging_and_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intents.db"
            ledger = DurableTestnetIntentLedger(path)
            blocker = sqlite3.connect(str(path), isolation_level=None)
            try:
                ledger.db.execute("PRAGMA busy_timeout=100")
                blocker.execute("BEGIN IMMEDIATE")
                with self.assertRaises(sqlite3.OperationalError):
                    stage_preflighted_testnet_intent(intent(), settings=SAFE, ledger=ledger, dry_run=True)
                blocker.execute("ROLLBACK")
                self.assertEqual(ledger.lookup(intent()["clientOrderId"])["status"], "NOT_STAGED")
                staged = stage_preflighted_testnet_intent(intent(), settings=SAFE, ledger=ledger, dry_run=True)
                self.assertEqual(staged["status"], "STAGED_NOT_SENT")
            finally:
                if blocker.in_transaction:
                    blocker.execute("ROLLBACK")
                blocker.close()
                ledger.close()

    def test_closed_database_fails_without_success_result(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = DurableTestnetIntentLedger(Path(directory) / "intents.db")
            ledger.close()
            with self.assertRaises(sqlite3.ProgrammingError):
                stage_preflighted_testnet_intent(intent(), settings=SAFE, ledger=ledger, dry_run=True)

    def test_status_adapter_reports_success_without_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = DurableTestnetIntentLedger(Path(directory) / "intents.db")
            try:
                result = stage_preflighted_testnet_intent_status(
                    intent(), settings=SAFE, ledger=ledger, dry_run=True
                )
                self.assertEqual(result["status"], "STAGED_NOT_SENT")
                self.assertEqual(result["reason"], "OFFLINE_ONLY")
                self.assertFalse(result["orders_enabled"])
                self.assertFalse(result["network_enabled"])
            finally:
                ledger.close()

    def test_status_adapter_masks_validation_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = DurableTestnetIntentLedger(Path(directory) / "intents.db")
            try:
                for settings, expected in (({}, "PREFLIGHT_BLOCKED"), (SAFE, "ORDER_VALIDATION_BLOCKED")):
                    bad = intent() if not settings else {**intent(), "reduceOnly": False}
                    result = stage_preflighted_testnet_intent_status(
                        bad, settings=settings, ledger=ledger, dry_run=True
                    )
                    self.assertEqual(result["status"], "BLOCKED")
                    self.assertEqual(result["reason"], expected)
                    self.assertFalse(result["network_enabled"])
                    self.assertNotIn("client_order_id", result)
                self.assertEqual(ledger.lookup(intent()["clientOrderId"])["status"], "NOT_STAGED")
            finally:
                ledger.close()

    def test_status_adapter_masks_closed_database_error(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = DurableTestnetIntentLedger(Path(directory) / "intents.db")
            ledger.close()
            result = stage_preflighted_testnet_intent_status(
                intent(), settings=SAFE, ledger=ledger, dry_run=True
            )
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["reason"], "LEDGER_UNAVAILABLE")
            self.assertFalse(result["orders_enabled"])

    def test_status_adapter_reports_duplicate_without_leaking_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = DurableTestnetIntentLedger(Path(directory) / "intents.db")
            try:
                first = stage_preflighted_testnet_intent_status(
                    intent(), settings=SAFE, ledger=ledger, dry_run=True
                )
                self.assertEqual(first["status"], "STAGED_NOT_SENT")
                second = stage_preflighted_testnet_intent_status(
                    intent(), settings=SAFE, ledger=ledger, dry_run=True
                )
                self.assertEqual(second["status"], "BLOCKED")
                self.assertEqual(second["reason"], "ORDER_VALIDATION_BLOCKED")
                self.assertFalse(second["orders_enabled"])
                self.assertNotIn("client_order_id", second)
                self.assertNotIn("payload", second)
            finally:
                ledger.close()

    def test_status_adapter_masks_sqlite_lock_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intents.db"
            ledger = DurableTestnetIntentLedger(path)
            blocker = sqlite3.connect(str(path), isolation_level=None)
            try:
                ledger.db.execute("PRAGMA busy_timeout=100")
                blocker.execute("BEGIN IMMEDIATE")
                status = stage_preflighted_testnet_intent_status(
                    intent(), settings=SAFE, ledger=ledger, dry_run=True
                )
                self.assertEqual(status["status"], "BLOCKED")
                self.assertEqual(status["reason"], "LEDGER_UNAVAILABLE")
                self.assertFalse(status["network_enabled"])
                self.assertNotIn("client_order_id", status)
                blocker.execute("ROLLBACK")
                self.assertEqual(ledger.lookup(intent()["clientOrderId"])["status"], "NOT_STAGED")
            finally:
                if blocker.in_transaction:
                    blocker.execute("ROLLBACK")
                blocker.close()
                ledger.close()

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
