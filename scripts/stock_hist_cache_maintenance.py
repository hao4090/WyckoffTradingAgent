# -*- coding: utf-8 -*-
"""
stock_hist_cache 维护任务：
- 统一 source 字段为 cache（去业务意义化）
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.constants import TABLE_STOCK_HIST_CACHE
from core.stock_cache import _get_stock_cache_client


def normalize_source_value(context: str = "admin") -> tuple[bool, str]:
    client = _get_stock_cache_client(context=context)
    if client is None:
        return False, "Supabase client unavailable"

    total_updated = 0
    try:
        resp = (
            client.table(TABLE_STOCK_HIST_CACHE)
            .update({"source": "cache"})
            .neq("source", "cache")
            .execute()
        )
        total_updated += len(resp.data or [])
    except Exception as e:
        return False, f"normalize non-cache source failed: {e}"

    try:
        resp_null = (
            client.table(TABLE_STOCK_HIST_CACHE)
            .update({"source": "cache"})
            .is_("source", None)
            .execute()
        )
        total_updated += len(resp_null.data or [])
    except Exception:
        # 某些 PostgREST 版本对 is_ 行为不同，不作为致命失败
        pass

    return True, f"updated_rows={total_updated}"


def main() -> int:
    parser = argparse.ArgumentParser(description="stock_hist_cache maintenance")
    parser.add_argument(
        "--normalize-source",
        action="store_true",
        default=True,
        help="统一 source 为 cache（默认开启）",
    )
    args = parser.parse_args()

    if args.normalize_source:
        ok, msg = normalize_source_value(context="admin")
        print(f"[stock_hist_cache_maintenance] normalize_source ok={ok}, {msg}")
        return 0 if ok else 1

    print("[stock_hist_cache_maintenance] no-op")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
