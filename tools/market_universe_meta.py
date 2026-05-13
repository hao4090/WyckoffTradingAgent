"""Structured metadata helpers for market universe files."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

UNIVERSE_DIR = Path(__file__).resolve().parent.parent / "data" / "market_universes"
META_FILES = {
    "us": "us_meta.json",
    "hk": "hk_meta.json",
    "etf_cn": "etf_cn_meta.json",
}


def _read_meta(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


@lru_cache(maxsize=1)
def load_all_market_meta() -> dict[str, list[dict[str, Any]]]:
    """Load all generated market metadata files."""
    return {market: _read_meta(UNIVERSE_DIR / filename) for market, filename in META_FILES.items()}


def load_market_meta(markets: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    """Load metadata entries for selected markets."""
    all_meta = load_all_market_meta()
    selected = markets or tuple(all_meta.keys())
    rows: list[dict[str, Any]] = []
    for market in selected:
        rows.extend(all_meta.get(market, []))
    return rows


def load_symbol_name_map(markets: tuple[str, ...] = ()) -> dict[str, str]:
    """Return code/symbol to display-name map where metadata has a name."""
    out: dict[str, str] = {}
    for row in load_market_meta(markets):
        name = str(row.get("name", "") or "").strip()
        if not name:
            continue
        symbol = str(row.get("symbol", "") or "").strip().upper()
        code = str(row.get("code", "") or "").strip().upper()
        if symbol:
            out[symbol] = name
        if code:
            out[code] = name
    return out


def search_market_meta(query: str, *, limit: int = 10) -> list[dict[str, Any]]:
    """Search generated market metadata by symbol, code, or name."""
    q = str(query or "").strip().upper()
    if not q:
        return []
    matches: list[dict[str, Any]] = []
    for row in load_market_meta():
        haystack = " ".join(str(row.get(key, "") or "").upper() for key in ("symbol", "code", "name", "sector_tag"))
        if q in haystack:
            matches.append(row)
            if len(matches) >= limit:
                break
    return matches
