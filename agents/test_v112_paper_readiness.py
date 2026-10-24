import json
import tempfile
import unittest
from pathlib import Path
from paper_readiness_v112 import audit, run

def safe_config():
    return {
        "environment": "SIMULATION",
        "execution_mode": "PAPER_ONLY",
        "live_orders_enabled": False,
        "paper_orders_enabled": True,
        "exchange_api_credentials_present": False,
        "market_data_age_seconds": 5,
        "max_market_data_age_seconds": 60,
        "max_position_fraction": 0.05,
        "max_daily_loss_fraction": 0.02,
        "kill_switch_enabled": True,
        "order_log_enabled": True,
        "risk_limits_enforced": True,
    }

class ReadinessTests(unittest.TestCase):
    def test_pass_is_not_approval(self):
        result = audit(safe_config())
        self.assertEqual(result["status"], "CONFIG_REVIEW_PASS")
        self.assertFalse(result["paper_trading_approved"])
        self.assertFalse(result["live_trading_approved"])
        self.assertFalse(result["orders_enabled"])

    def test_live_order_flag_blocks(self):
        config = safe_config()
        config["live_orders_enabled"] = True
        self.assertEqual(audit(config)["status"], "CONFIG_REVIEW_BLOCKED")

    def test_stale_data_blocks(self):
        config = safe_config()
        config["market_data_age_seconds"] = 61
        self.assertFalse(audit(config)["checks"]["data_fresh"])

    def test_missing_kill_switch_blocks(self):
        config = safe_config()
        config["kill_switch_enabled"] = False
        self.assertEqual(audit(config)["status"], "CONFIG_REVIEW_BLOCKED")

    def test_credentials_block(self):
        config = safe_config()
        config["exchange_api_credentials_present"] = True
        self.assertEqual(audit(config)["status"], "CONFIG_REVIEW_BLOCKED")

    def test_invalid_risk_limits_rejected(self):
        config = safe_config()
        config["max_position_fraction"] = 0.5
        with self.assertRaisesRegex(ValueError, "UNSAFE_RISK"):
            audit(config)

    def test_unexpected_field_rejected(self):
        config = safe_config()
        config["api_key"] = "do-not-store-secrets"
        with self.assertRaisesRegex(ValueError, "INVALID_READINESS_SCHEMA"):
            audit(config)

    def test_file_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"config.json"
            path.write_text(json.dumps(safe_config()), encoding="utf-8")
            self.assertEqual(run(path)["status"], "CONFIG_REVIEW_PASS")

if __name__ == "__main__":
    unittest.main()
