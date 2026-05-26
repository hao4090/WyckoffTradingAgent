from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

SAFE_ENV_PREFIXES = (
    "FUNNEL_",
    "WYCKOFF_FUNNEL_",
    "STEP3_",
    "STEP4_",
    "TAIL_BUY_",
    "MARKET_FUNNEL_",
    "BACKTEST_",
    "REVIEW_",
    "SPRINGBOARD_",
    "SIGNAL_",
)
SECRET_ENV_MARKERS = (
    "API_KEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "WEBHOOK",
    "SUPABASE",
    "CHAT_ID",
    "BOT_TOKEN",
    "COOKIE",
    "AUTH",
    "BASE_URL",
    "URL",
)
ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,96}$")

_APPLY_CACHE_KEY: tuple[str, ...] | None = None
_APPLY_CACHE_RESULT: StrategyConfigApplyResult | None = None


class StrategyConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class StrategyConfigApplyResult:
    source: str
    version: str = ""
    updated_at: str = ""
    cache_path: str = ""
    applied: tuple[str, ...] = field(default_factory=tuple)
    skipped: tuple[str, ...] = field(default_factory=tuple)
    error: str = ""

    @property
    def applied_count(self) -> int:
        return len(self.applied)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)


def _env_bool(name: str, default: bool) -> bool:
    raw = str(os.getenv(name, "") or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _cache_path() -> Path:
    raw = str(os.getenv("WYCKOFF_STRATEGY_CONFIG_CACHE", "") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path(".cache") / "strategy_config" / "strategy_bundle.json"


def _coerce_env_value(value: Any) -> str | None:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int | float | str):
        text = str(value).strip()
        return text if text else None
    return None


def _is_safe_env_key(key: str) -> bool:
    name = str(key or "").strip().upper()
    if not ENV_NAME_RE.match(name):
        return False
    if not name.startswith(SAFE_ENV_PREFIXES):
        return False
    return not any(marker in name for marker in SECRET_ENV_MARKERS)


def _collect_env_values(bundle: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}

    def _add_many(raw: Any) -> None:
        if not isinstance(raw, dict):
            return
        for key, value in raw.items():
            name = str(key or "").strip().upper()
            text = _coerce_env_value(value)
            if name and text is not None:
                values[name] = text

    _add_many(bundle.get("env"))
    sections = bundle.get("sections")
    if isinstance(sections, dict):
        for section in sections.values():
            if isinstance(section, dict):
                _add_many(section.get("env"))
    return values


def _validate_bundle(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise StrategyConfigError("strategy bundle response must be a JSON object")
    if not str(payload.get("version") or "").strip():
        raise StrategyConfigError("strategy bundle missing version")
    if not isinstance(payload.get("env", {}), dict):
        raise StrategyConfigError("strategy bundle env must be an object")
    if not isinstance(payload.get("sections", {}), dict):
        raise StrategyConfigError("strategy bundle sections must be an object")
    return payload


def _write_cache(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def _read_cache(path: Path) -> dict[str, Any]:
    return _validate_bundle(json.loads(path.read_text(encoding="utf-8")))


def fetch_strategy_bundle() -> dict[str, Any]:
    base_url = str(os.getenv("WYCKOFF_STRATEGY_API_URL", "") or "").strip().rstrip("/")
    api_key = str(os.getenv("WYCKOFF_STRATEGY_API_KEY", "") or "").strip()
    if not base_url or not api_key:
        raise StrategyConfigError("strategy API URL/key not configured")

    timeout = _env_float(
        "WYCKOFF_STRATEGY_CONFIG_TIMEOUT",
        _env_float("WYCKOFF_STRATEGY_API_TIMEOUT", 45.0),
    )
    try:
        response = requests.get(
            f"{base_url}/v1/strategy-bundle",
            headers={"X-API-Key": api_key, "Accept": "application/json"},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise StrategyConfigError(f"strategy bundle request failed: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise StrategyConfigError("strategy bundle response is not JSON") from exc
    if response.status_code >= 400:
        detail = payload.get("detail") if isinstance(payload, dict) else response.text[:200]
        raise StrategyConfigError(f"strategy bundle HTTP {response.status_code}: {detail}")
    return _validate_bundle(payload)


def apply_strategy_bundle_to_env(*, force: bool = False) -> StrategyConfigApplyResult:
    global _APPLY_CACHE_KEY, _APPLY_CACHE_RESULT

    enabled = _env_bool("WYCKOFF_STRATEGY_CONFIG_ENABLED", True)
    base_url = str(os.getenv("WYCKOFF_STRATEGY_API_URL", "") or "").strip().rstrip("/")
    api_key = str(os.getenv("WYCKOFF_STRATEGY_API_KEY", "") or "").strip()
    cache_path = _cache_path()
    override_existing = _env_bool("WYCKOFF_STRATEGY_CONFIG_OVERRIDE", True)
    cache_key = (str(enabled), base_url, api_key, str(cache_path), str(override_existing))
    if not force and _APPLY_CACHE_KEY == cache_key and _APPLY_CACHE_RESULT is not None:
        return _APPLY_CACHE_RESULT

    if not enabled:
        result = StrategyConfigApplyResult(source="disabled", cache_path=str(cache_path))
        _APPLY_CACHE_KEY, _APPLY_CACHE_RESULT = cache_key, result
        return result
    if not base_url or not api_key:
        result = StrategyConfigApplyResult(source="disabled", cache_path=str(cache_path))
        _APPLY_CACHE_KEY, _APPLY_CACHE_RESULT = cache_key, result
        return result

    source = "api"
    error = ""
    try:
        bundle = fetch_strategy_bundle()
        _write_cache(cache_path, bundle)
    except Exception as exc:
        error = str(exc)
        try:
            bundle = _read_cache(cache_path)
            source = "cache"
        except Exception as cache_exc:
            result = StrategyConfigApplyResult(
                source="error",
                cache_path=str(cache_path),
                error=f"{error}; cache fallback failed: {cache_exc}",
            )
            _APPLY_CACHE_KEY, _APPLY_CACHE_RESULT = cache_key, result
            return result

    applied: list[str] = []
    skipped: list[str] = []
    for key, value in _collect_env_values(bundle).items():
        if not _is_safe_env_key(key):
            skipped.append(key)
            continue
        if not override_existing and key in os.environ:
            skipped.append(key)
            continue
        os.environ[key] = value
        applied.append(key)

    result = StrategyConfigApplyResult(
        source=source,
        version=str(bundle.get("version") or ""),
        updated_at=str(bundle.get("updated_at") or ""),
        cache_path=str(cache_path),
        applied=tuple(sorted(applied)),
        skipped=tuple(sorted(skipped)),
        error=error,
    )
    _APPLY_CACHE_KEY, _APPLY_CACHE_RESULT = cache_key, result
    return result
