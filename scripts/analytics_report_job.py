"""Weekly / monthly user activity analytics report."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import timedelta

if __name__ == "__main__" or not __package__:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrations.supabase_analytics import (
    build_analytics_report_markdown,
    build_monthly_snapshot,
    build_weekly_snapshot,
    fetch_daily_activity_rows,
    fetch_excluded_users,
    resolve_report_date,
    resolve_report_month,
    rollup_activity_range,
)
from integrations.supabase_base import create_admin_client
from utils.feishu import send_feishu_notification


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send user activity analytics report")
    parser.add_argument("--mode", choices=["weekly", "monthly"], required=True)
    parser.add_argument("--date", default="", help="Weekly report end date, YYYY-MM-DD. Defaults to yesterday.")
    parser.add_argument("--month", default="", help="Monthly report month, YYYY-MM. Defaults to previous month.")
    parser.add_argument("--no-feishu", action="store_true", help="Print only, do not send Feishu.")
    return parser.parse_args()


def _snapshot(args: argparse.Namespace, client) -> dict:
    if args.mode == "weekly":
        end_date = resolve_report_date(args.date, offset_days=1)
        start_date = end_date - timedelta(days=6)
        rollup_activity_range(start_date, end_date, client=client)
        rows = fetch_daily_activity_rows(client, end_date - timedelta(days=_history_days()), end_date)
        return build_weekly_snapshot(rows, end_date, fetch_excluded_users(client))

    start_date, end_date = resolve_report_month(args.month)
    rollup_activity_range(start_date, end_date, client=client)
    rows = fetch_daily_activity_rows(client, end_date - timedelta(days=_history_days()), end_date)
    return build_monthly_snapshot(rows, start_date, end_date, fetch_excluded_users(client))


def _history_days() -> int:
    return max(int(os.getenv("ANALYTICS_HISTORY_DAYS", "400")), 60)


def _title(snapshot: dict) -> str:
    label = "用户活跃周报" if snapshot.get("mode") == "weekly" else "用户活跃月报"
    return f"{label} {snapshot.get('period_start')}~{snapshot.get('period_end')}"


def main() -> int:
    args = _parse_args()
    client = create_admin_client()
    snapshot = _snapshot(args, client)
    report = build_analytics_report_markdown(snapshot)
    print(report)
    if args.no_feishu:
        return 0
    webhook = os.getenv("FEISHU_WEBHOOK_URL", "").strip()
    if not webhook:
        print("[analytics] FEISHU_WEBHOOK_URL missing, skip send")
        return 0
    return 0 if send_feishu_notification(webhook, _title(snapshot), report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
