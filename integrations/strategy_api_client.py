from __future__ import annotations

import os
from dataclasses import dataclass

from integrations.strategy_config_client import apply_strategy_bundle_to_env, fetch_strategy_bundle


class StrategyApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class StrategyApiConfig:
    base_url: str
    api_key: str
    mode: str


def get_strategy_api_config() -> StrategyApiConfig:
    return StrategyApiConfig(
        base_url=str(os.getenv("WYCKOFF_STRATEGY_API_URL", "") or "").strip().rstrip("/"),
        api_key=str(os.getenv("WYCKOFF_STRATEGY_API_KEY", "") or "").strip(),
        mode=str(os.getenv("WYCKOFF_STRATEGY_API_MODE", "config") or "config").strip().lower(),
    )


def is_strategy_api_configured(config: StrategyApiConfig | None = None) -> bool:
    cfg = config or get_strategy_api_config()
    return bool(cfg.base_url and cfg.api_key)


def is_strategy_api_required(config: StrategyApiConfig | None = None) -> bool:
    cfg = config or get_strategy_api_config()
    return cfg.mode in {"config", "remote", "required"}


def is_strategy_api_enabled(config: StrategyApiConfig | None = None) -> bool:
    return is_strategy_api_configured(config)


def _remote_strategy_execution_disabled(*_args, **_kwargs):
    raise StrategyApiError(
        "Remote strategy execution endpoints were removed. "
        "Use integrations.strategy_config_client to fetch /v1/strategy-bundle, then run strategies locally."
    )


analyze_stock_legacy = _remote_strategy_execution_disabled
screen_stocks_legacy = _remote_strategy_execution_disabled
run_backtest_legacy = _remote_strategy_execution_disabled
score_tail_buy_remote = _remote_strategy_execution_disabled
prepare_tail_buy_remote = _remote_strategy_execution_disabled
finalize_tail_buy_remote = _remote_strategy_execution_disabled
analyze_tail_buy_holdings_remote = _remote_strategy_execution_disabled
run_step4_rebalance_remote = _remote_strategy_execution_disabled


__all__ = [
    "StrategyApiConfig",
    "StrategyApiError",
    "apply_strategy_bundle_to_env",
    "fetch_strategy_bundle",
    "get_strategy_api_config",
    "is_strategy_api_configured",
    "is_strategy_api_enabled",
    "is_strategy_api_required",
]
