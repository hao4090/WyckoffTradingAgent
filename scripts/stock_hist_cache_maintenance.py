# -*- coding: utf-8 -*-
"""
stock_hist_cache 维护任务：
- 按交易日期 date 清理滑动窗口外的历史记录
"""
from __future__ import annotations

import argparse
import os
import sys


# Ensure project root is on sys.path for direct script invocation
if __name__ == "__main__" or not __package__:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.stock_cache import cleanup_cache
from core.constants import TABLE_STOCK_HIST_CACHE


def cleanup_expired_cache(ttl_days: int, context: str = "admin") -> tuple[bool, str]:
    try:
        cleanup_cache(ttl_days=ttl_days, context=context)
        return True, f"cleanup_done ttl_days={ttl_days}"
    except Exception as e:
        return False, f"cleanup failed: {e}"


def cleanup_unadjusted_cache(context: str = "admin") -> tuple[bool, str]:
    """删除 adjust='none'（不复权）的存量缓存数据。"""
    try:
        from integrations.supabase_base import create_admin_client
        client = create_admin_client()
        client.table(TABLE_STOCK_HIST_CACHE).delete().eq("adjust", "none").execute()
        return True, "cleaned adjust=none rows"
    except Exception as e:
        return False, f"cleanup adjust=none failed: {e}"


def main() -> int:
    parser = argparse.ArgumentParser(description="stock_hist_cache maintenance")
    parser.add_argument(
        "--ttl-days",
        type=int,
        default=400,
        help="按 date 清理早于该天数的缓存记录（默认 400）",
    )
    args = parser.parse_args()

    ttl_days = max(int(args.ttl_days or 365), 1)
    ok, msg = cleanup_expired_cache(ttl_days=ttl_days, context="admin")
    print(f"[stock_hist_cache_maintenance] cleanup ok={ok}, {msg}")

    ok2, msg2 = cleanup_unadjusted_cache(context="admin")
    print(f"[stock_hist_cache_maintenance] unadjusted ok={ok2}, {msg2}")

    return 0 if (ok and ok2) else 1


if __name__ == "__main__":
    raise SystemExit(main())
