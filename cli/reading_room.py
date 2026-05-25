"""Shared Reading Room runtime for TUI, headless CLI, and native clients."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from typing import Any

logger = logging.getLogger(__name__)


def create_reading_room_tools():
    from cli.tools import ToolRegistry

    tools = ToolRegistry()
    session_expired = _restore_session_state(tools)
    return tools, session_expired


def initialize_local_agent_storage() -> None:
    try:
        from integrations.local_db import init_db, prune_memories

        init_db()
        prune_memories()
        from integrations.sync import sync_all_background

        sync_all_background()
    except Exception:
        logger.warning("local db init or sync failed", exc_info=True)


def load_data_source_env() -> None:
    try:
        from cli.auth import load_config

        cfg = load_config()
        env_keys = [("tushare_token", "TUSHARE_TOKEN"), ("tickflow_api_key", "TICKFLOW_API_KEY")]
        for key, env_key in env_keys:
            value = str(cfg.get(key, "") or "").strip()
            if value:
                os.environ.setdefault(env_key, value)
    except Exception:
        logger.debug("config env vars load failed", exc_info=True)


def build_reading_room_runtime() -> tuple[Any, dict[str, Any], bool]:
    tools, session_expired = create_reading_room_tools()
    initialize_local_agent_storage()
    state = load_provider_state()
    if state["provider"]:
        tools.set_provider(state["provider"])
    return tools, state, session_expired


def load_provider_state() -> dict[str, Any]:
    state: dict[str, Any] = {"provider": None, "provider_name": "", "model": "", "api_key": "", "base_url": ""}
    load_data_source_env()
    try:
        from cli.auth import load_default_model_id, load_fallback_model_id, load_model_configs
        from cli.providers.fallback import FallbackProvider

        configs = load_model_configs()
        default_id = load_default_model_id()
        if not configs or not default_id:
            return state
        _seed_provider_env(configs)
        default_cfg = next((c for c in configs if c["id"] == default_id), configs[0])
        state.update(default_cfg)
        if len(configs) == 1:
            state["provider"] = _provider_from_config(default_cfg)
        else:
            state["provider"] = FallbackProvider(configs, default_id, fallback_id=load_fallback_model_id())
    except Exception:
        logger.warning("model provider init failed", exc_info=True)
    _wrap_routing_provider(state)
    return state


def parse_history_json(raw: str) -> list[dict[str, str]]:
    if not raw.strip():
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"history-json 不是合法 JSON: {exc}") from exc
    if not isinstance(parsed, list):
        raise ValueError("history-json 必须是消息数组")
    return [_normalize_history_message(item) for item in parsed]


def run_reading_room_stream(
    user_text: str,
    history: list[dict[str, str]] | None = None,
) -> Iterator[dict[str, Any]]:
    from cli.runtime import AgentRuntime
    from core.prompts import CHAT_AGENT_SYSTEM_PROMPT, with_current_time

    tools, state, _session_expired = build_reading_room_runtime()
    provider = state["provider"]
    if not provider:
        yield {"type": "error", "error": "未配置读盘室模型。请先运行 wyckoff model add 或在设置中配置模型。"}
        return
    messages: list[dict[str, Any]] = list(history or [])
    messages.append({"role": "user", "content": user_text})
    runtime = AgentRuntime(provider, tools)
    yield from runtime.run_stream(messages, with_current_time(CHAT_AGENT_SYSTEM_PROMPT))


def _restore_session_state(tools) -> bool:
    try:
        from cli.auth import _load_session, restore_session

        had_session = _load_session() is not None
        session = restore_session()
        if not session:
            return had_session
        tools.state.update(
            {
                "user_id": session["user_id"],
                "email": session["email"],
                "access_token": session.get("access_token", ""),
                "refresh_token": session.get("refresh_token", ""),
            }
        )
    except Exception:
        logger.warning("session restore failed", exc_info=True)
    return False


def _seed_provider_env(configs: list[dict[str, Any]]) -> None:
    env_map = {"gemini": "GEMINI_API_KEY", "claude": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
    for cfg in configs:
        env_key = env_map.get(cfg.get("provider_name", ""))
        if env_key and cfg.get("api_key"):
            os.environ.setdefault(env_key, cfg["api_key"])


def _provider_from_config(config: dict[str, Any]) -> Any | None:
    from cli._provider_factory import _create_provider

    provider, err = _create_provider(
        config["provider_name"],
        config["api_key"],
        config.get("model", ""),
        config.get("base_url", ""),
    )
    return None if err else provider


def _wrap_routing_provider(state: dict[str, Any]) -> None:
    try:
        from cli.auth import load_light_model_id, load_model_configs
        from cli.model_router import RoutingProvider

        light_id = load_light_model_id()
        if not light_id or not state.get("provider"):
            return
        light_cfg = next((c for c in load_model_configs() if c["id"] == light_id), None)
        light_provider = _provider_from_config(light_cfg) if light_cfg else None
        if light_provider:
            state["provider"] = RoutingProvider(state["provider"], light_provider)
    except Exception:
        logger.debug("routing provider setup failed", exc_info=True)


def _normalize_history_message(item: Any) -> dict[str, str]:
    if not isinstance(item, dict):
        raise ValueError("history-json 中每条消息必须是对象")
    role = str(item.get("role", ""))
    content = str(item.get("content", ""))
    if role not in {"user", "assistant"}:
        raise ValueError("history-json 消息 role 只支持 user/assistant")
    if not content.strip():
        raise ValueError("history-json 消息 content 不能为空")
    return {"role": role, "content": content}
