"""CLI entrypoint for the daily Wyckoff job."""

from __future__ import annotations

import argparse
<<<<<<< Updated upstream
import logging

import _bootstrap  # noqa: F401
=======
import atexit
import gc
import os
import sys
import warnings
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def _cleanup_network_resources() -> None:
    """退出时清理未关闭的 socket / SSL 连接，抑制 ResourceWarning 噪音。

    GitHub Actions daily_job 跑完后，服务端（飞书/Supabase/Cloudflare）会
    主动关闭 keep-alive 连接，客户端读到 ECONNRESET 是预期行为，Python
    退出时扫描到这些未关闭 socket 会打印 sys:1: ResourceWarning。
    这里主动触发 gc 并忽略退出阶段的 ResourceWarning。
    """
    warnings.filterwarnings(
        "ignore",
        category=ResourceWarning,
        message=r".*unclosed.*",
    )
    gc.collect()


atexit.register(_cleanup_network_resources)

# Ensure project root is on sys.path for direct script invocation
if __name__ == "__main__" or not __package__:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from integrations._llm_types import OPENAI_COMPATIBLE_BASE_URLS
from integrations.fetch_a_share_csv import _resolve_trading_window
from integrations.llm_client import get_provider_credentials, provider_fallbacks, resolve_provider_name
from integrations.supabase_market_signal import upsert_market_signal_daily
from integrations.supabase_recommendation import (
    mark_ai_recommendations,
    prepare_recommendation_payload,
    upsert_recommendation_payload,
    write_recommendation_backup_artifact,
)
from utils.trading_clock import next_trading_day, resolve_end_calendar_day
>>>>>>> Stashed changes

from workflows.daily_job import run_daily_job

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="每日定时任务：Wyckoff Funnel -> 批量研报")
    parser.add_argument("--dry-run", action="store_true", help="仅校验配置，不执行任务")
    parser.add_argument("--logs", default=None, help="日志文件路径，默认 logs/daily_job_YYYYMMDD_HHMMSS.log")
    return parser.parse_args()


def main() -> int:
    return run_daily_job(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
