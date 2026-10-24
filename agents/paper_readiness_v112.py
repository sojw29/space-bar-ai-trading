"""V112 fail-closed offline paper-trading readiness audit.

This module never sends orders, connects to an exchange, or enables live mode.
A PASS is only configuration readiness for further human review.
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

REQUIRED = frozenset({
    "environment", "execution_mode", "live_orders_enabled", "paper_orders_enabled",
    "exchange_api_credentials_present", "market_data_age_seconds",
    "max_market_data_age_seconds", "max_position_fraction",
    "max_daily_loss_fraction", "kill_switch_enabled",
    "order_log_enabled", "risk_limits_enforced",
})
MAX_BYTES = 65536

def audit(config):
    if not isinstance(config, dict) or set(config) != REQUIRED:
        raise ValueError("INVALID_READINESS_SCHEMA")
    if config["environment"] != "SIMULATION":
        raise ValueError("INVALID_ENVIRONMENT")
    if config["execution_mode"] != "PAPER_ONLY":
        raise ValueError("INVALID_EXECUTION_MODE")
    boolean_keys = ("live_orders_enabled", "paper_orders_enabled",
                    "exchange_api_credentials_present", "kill_switch_enabled",
                    "order_log_enabled", "risk_limits_enforced")
    if any(type(config[k]) is not bool for k in boolean_keys):
        raise ValueError("INVALID_BOOLEAN")
    numeric_keys = ("market_data_age_seconds", "max_market_data_age_seconds",
                    "max_position_fraction", "max_daily_loss_fraction")
    if any(type(config[k]) not in (int, float) or not math.isfinite(config[k])
           for k in numeric_keys):
        raise ValueError("INVALID_NUMBER")
    if (config["market_data_age_seconds"] < 0 or
            not 0 < config["max_market_data_age_seconds"] <= 3600 or
            not 0 < config["max_position_fraction"] <= 0.1 or
            not 0 < config["max_daily_loss_fraction"] <= 0.05):
        raise ValueError("UNSAFE_RISK_OR_DATA_LIMIT")
    checks = {
        "live_orders_disabled": not config["live_orders_enabled"],
        "paper_orders_enabled": config["paper_orders_enabled"],
        "exchange_credentials_absent": not config["exchange_api_credentials_present"],
        "data_fresh": config["market_data_age_seconds"] <= config["max_market_data_age_seconds"],
        "kill_switch_enabled": config["kill_switch_enabled"],
        "order_log_enabled": config["order_log_enabled"],
        "risk_limits_enforced": config["risk_limits_enforced"],
    }
    passed = all(checks.values())
    return {
        "version": "V112.0",
        "status": "CONFIG_REVIEW_PASS" if passed else "CONFIG_REVIEW_BLOCKED",
        "checks": checks,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "paper_trading_approved": False,
        "paper_orders_submitted": 0,
        "live_trading_approved": False,
        "live_orders_enabled": False,
        "orders_enabled": False,
        "research_only": True,
        "limitations": ("Configuration assertions are not proof of running infrastructure, "
                        "market-data connectivity, operational kill-switch behavior or "
                        "enforced risk controls. Requires separate integration tests and "
                        "human review before paper execution."),
    }

def run(path):
    source = Path(path)
    if not source.is_file() or source.stat().st_size > MAX_BYTES:
        raise ValueError("MISSING_OR_OVERSIZED_CONFIG")
    try:
        config = json.loads(source.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("INVALID_CONFIG_JSON") from exc
    return audit(config)

def main():
    parser = argparse.ArgumentParser(description="V112 paper-only config readiness audit")
    parser.add_argument("config_json")
    args = parser.parse_args()
    print(json.dumps(run(args.config_json), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
