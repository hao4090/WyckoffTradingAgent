from __future__ import annotations

import json
from typing import Any

from integrations import strategy_api_client as legacy_client
from integrations import strategy_config_client as client


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self) -> dict[str, Any]:
        return self._payload


def _configure(monkeypatch, tmp_path):
    monkeypatch.setenv("WYCKOFF_STRATEGY_API_URL", "https://strategy.example")
    monkeypatch.setenv("WYCKOFF_STRATEGY_API_KEY", "secret")
    monkeypatch.setenv("WYCKOFF_STRATEGY_CONFIG_CACHE", str(tmp_path / "bundle.json"))
    monkeypatch.setenv("WYCKOFF_STRATEGY_CONFIG_TIMEOUT", "3")


def test_apply_strategy_bundle_disabled_without_api_config(monkeypatch):
    monkeypatch.delenv("WYCKOFF_STRATEGY_API_URL", raising=False)
    monkeypatch.delenv("WYCKOFF_STRATEGY_API_KEY", raising=False)

    result = client.apply_strategy_bundle_to_env(force=True)

    assert result.source == "disabled"
    assert result.applied_count == 0


def test_apply_strategy_bundle_from_api(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)

    def fake_get(url, headers, timeout):
        assert url == "https://strategy.example/v1/strategy-bundle"
        assert headers["X-API-Key"] == "secret"
        assert timeout == 3
        return FakeResponse(
            200,
            {
                "version": "test-v1",
                "updated_at": "2026-05-26T00:00:00+08:00",
                "env": {
                    "TAIL_BUY_LLM_TOP_N": "7",
                    "TAIL_BUY_USE_BATCH_INTRADAY": True,
                    "BACKTEST_WBT_N_JOBS": 2,
                    "GEMINI_API_KEY": "bad",
                    "SUPABASE_URL": "bad",
                    "unknown_key": "bad",
                },
                "sections": {},
            },
        )

    monkeypatch.setattr(client.requests, "get", fake_get)

    result = client.apply_strategy_bundle_to_env(force=True)

    assert result.source == "api"
    assert result.version == "test-v1"
    assert result.applied_count == 3
    assert "GEMINI_API_KEY" in result.skipped
    assert "SUPABASE_URL" in result.skipped
    assert "UNKNOWN_KEY" in result.skipped
    assert client.os.environ["TAIL_BUY_LLM_TOP_N"] == "7"
    assert client.os.environ["TAIL_BUY_USE_BATCH_INTRADAY"] == "1"
    assert client.os.environ["BACKTEST_WBT_N_JOBS"] == "2"


def test_apply_strategy_bundle_uses_cache_on_fetch_error(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    cache_path = tmp_path / "bundle.json"
    cache_path.write_text(
        json.dumps(
            {
                "version": "cached-v1",
                "updated_at": "2026-05-26T00:00:00+08:00",
                "env": {"STEP4_ATR_PERIOD": "21"},
                "sections": {},
            }
        ),
        encoding="utf-8",
    )

    def fake_get(*_args, **_kwargs):
        raise client.requests.RequestException("timeout")

    monkeypatch.setattr(client.requests, "get", fake_get)

    result = client.apply_strategy_bundle_to_env(force=True)

    assert result.source == "cache"
    assert result.version == "cached-v1"
    assert "timeout" in result.error
    assert client.os.environ["STEP4_ATR_PERIOD"] == "21"


def test_apply_strategy_bundle_can_preserve_existing_env(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    monkeypatch.setenv("WYCKOFF_STRATEGY_CONFIG_OVERRIDE", "0")
    monkeypatch.setenv("TAIL_BUY_LLM_TOP_N", "20")

    def fake_get(*_args, **_kwargs):
        return FakeResponse(
            200,
            {
                "version": "test-v2",
                "updated_at": "2026-05-26T00:00:00+08:00",
                "env": {"TAIL_BUY_LLM_TOP_N": "5"},
                "sections": {},
            },
        )

    monkeypatch.setattr(client.requests, "get", fake_get)

    result = client.apply_strategy_bundle_to_env(force=True)

    assert result.source == "api"
    assert result.applied_count == 0
    assert result.skipped == ("TAIL_BUY_LLM_TOP_N",)
    assert client.os.environ["TAIL_BUY_LLM_TOP_N"] == "20"


def test_legacy_remote_strategy_execution_is_disabled():
    try:
        legacy_client.score_tail_buy_remote(candidates=[], intraday_by_code={})
    except legacy_client.StrategyApiError as exc:
        assert "Remote strategy execution endpoints were removed" in str(exc)
    else:
        raise AssertionError("legacy remote strategy execution should be disabled")
