"""User activity analytics helpers for Web / CLI / scheduled reports."""

from __future__ import annotations

import os
import uuid
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from core.constants import TABLE_ANALYTICS_EXCLUDED_USERS, TABLE_USER_ACTIVITY_EVENTS, TABLE_USER_DAILY_ACTIVITY
from integrations.supabase_base import create_admin_client, create_user_client, is_admin_configured

TZ = ZoneInfo("Asia/Shanghai")
IGNORED_EVENT_NAMES = {"heartbeat", "auth_refresh"}
IGNORED_SOURCES = {"action"}


def resolve_report_date(raw_date: str = "", offset_days: int = 1) -> date:
    text = str(raw_date or "").strip()
    if text:
        return datetime.strptime(text, "%Y-%m-%d").date()
    return datetime.now(TZ).date() - timedelta(days=max(int(offset_days), 0))


def resolve_report_month(raw_month: str = "") -> tuple[date, date]:
    text = str(raw_month or "").strip()
    if text:
        start = datetime.strptime(f"{text}-01", "%Y-%m-%d").date()
    else:
        today = datetime.now(TZ).date()
        this_month = today.replace(day=1)
        start = (this_month - timedelta(days=1)).replace(day=1)
    next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start, next_month - timedelta(days=1)


def iter_dates(start_date: date, end_date: date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _day_bounds_utc(activity_date: date) -> tuple[str, str]:
    start = datetime.combine(activity_date, time.min, TZ)
    end = start + timedelta(days=1)
    return start.astimezone(UTC).isoformat(), end.astimezone(UTC).isoformat()


def _safe_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in dict(metadata or {}).items():
        if value is None:
            continue
        text_key = str(key)[:64]
        if isinstance(value, str):
            out[text_key] = value[:256]
        elif isinstance(value, bool | int | float):
            out[text_key] = value
        else:
            out[text_key] = str(value)[:256]
    return out


def track_activity_event(
    *,
    user_id: str,
    event_name: str,
    source: str,
    session_id: str = "",
    feature: str = "",
    route: str = "",
    success: bool = True,
    duration_ms: int | None = None,
    metadata: dict[str, Any] | None = None,
    access_token: str = "",
    refresh_token: str = "",
) -> bool:
    if not user_id or not event_name or os.getenv("WYCKOFF_TELEMETRY", "1").strip() == "0":
        return False
    payload = {
        "event_id": uuid.uuid4().hex,
        "user_id": user_id,
        "source": source,
        "session_id": session_id or uuid.uuid4().hex,
        "event_name": event_name,
        "feature": feature,
        "route": route,
        "success": bool(success),
        "duration_ms": duration_ms,
        "metadata": _safe_metadata(metadata),
        "client_ts": datetime.now(UTC).isoformat(),
    }
    try:
        client = create_user_client(access_token, refresh_token) if access_token else create_admin_client()
        client.table(TABLE_USER_ACTIVITY_EVENTS).insert(payload).execute()
        return True
    except Exception:
        return False


def _fetch_paged(query, page_size: int = 1000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    page = max(min(int(page_size), 1000), 1)
    while True:
        batch = query.range(start, start + page - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < page:
            return rows
        start += page


def fetch_activity_events(client, activity_date: date) -> list[dict[str, Any]]:
    start_utc, end_utc = _day_bounds_utc(activity_date)
    query = (
        client.table(TABLE_USER_ACTIVITY_EVENTS)
        .select("*")
        .gte("created_at", start_utc)
        .lt("created_at", end_utc)
        .order("created_at", desc=False)
    )
    return _fetch_paged(query)


def aggregate_daily_activity(events: list[dict[str, Any]], activity_date: date) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for event in events or []:
        user_id = str(event.get("user_id") or "").strip()
        source = str(event.get("source") or "").strip()
        event_name = str(event.get("event_name") or "").strip()
        if not user_id or source in IGNORED_SOURCES or event_name in IGNORED_EVENT_NAMES:
            continue
        row = grouped.setdefault(
            user_id,
            {"sources": set(), "sessions": set(), "features": Counter(), "first": "", "last": "", "events": 0},
        )
        row["events"] += 1
        row["sources"].add(source)
        row["sessions"].add(str(event.get("session_id") or ""))
        row["features"][str(event.get("feature") or event_name)] += 1
        created = str(event.get("created_at") or event.get("client_ts") or "")
        row["first"] = min(row["first"], created) if row["first"] and created else created or row["first"]
        row["last"] = max(row["last"], created) if row["last"] and created else created or row["last"]
    return [_daily_payload(activity_date, user_id, row) for user_id, row in sorted(grouped.items())]


def _daily_payload(activity_date: date, user_id: str, row: dict[str, Any]) -> dict[str, Any]:
    sessions = {x for x in row["sessions"] if x}
    return {
        "activity_date": activity_date.isoformat(),
        "user_id": user_id,
        "sources": sorted(row["sources"]),
        "event_count": int(row["events"]),
        "session_count": len(sessions),
        "first_seen_at": row["first"] or None,
        "last_seen_at": row["last"] or None,
        "feature_counts": dict(row["features"]),
        "updated_at": datetime.now(UTC).isoformat(),
    }


def rollup_daily_activity(activity_date: date, client=None) -> int:
    if client is None:
        if not is_admin_configured():
            raise RuntimeError("Supabase service credentials are required for analytics rollup")
        client = create_admin_client()
    rows = aggregate_daily_activity(fetch_activity_events(client, activity_date), activity_date)
    if not rows:
        return 0
    client.table(TABLE_USER_DAILY_ACTIVITY).upsert(rows, on_conflict="activity_date,user_id").execute()
    return len(rows)


def rollup_activity_range(start_date: date, end_date: date, client=None) -> int:
    if client is None:
        if not is_admin_configured():
            raise RuntimeError("Supabase service credentials are required for analytics rollup")
        client = create_admin_client()
    return sum(rollup_daily_activity(day, client=client) for day in iter_dates(start_date, end_date))


def fetch_daily_activity_rows(client, start_date: date, end_date: date) -> list[dict[str, Any]]:
    query = (
        client.table(TABLE_USER_DAILY_ACTIVITY)
        .select("*")
        .gte("activity_date", start_date.isoformat())
        .lte("activity_date", end_date.isoformat())
        .order("activity_date", desc=False)
    )
    return _fetch_paged(query)


def fetch_excluded_users(client) -> set[str]:
    try:
        rows = client.table(TABLE_ANALYTICS_EXCLUDED_USERS).select("user_id").execute().data or []
        return {str(row.get("user_id") or "").strip() for row in rows if row.get("user_id")}
    except Exception:
        return set()


def _group_daily_rows(
    rows: list[dict[str, Any]], excluded_users: set[str] | None = None
) -> tuple[dict[date, list[dict[str, Any]]], dict[str, date]]:
    excluded = set(excluded_users or set())
    by_date: dict[date, list[dict[str, Any]]] = defaultdict(list)
    first_seen: dict[str, date] = {}
    for row in rows or []:
        user_id = str(row.get("user_id") or "").strip()
        if not user_id or user_id in excluded:
            continue
        d = _parse_date(row.get("activity_date"))
        if d is None:
            continue
        by_date[d].append(row)
        first_seen[user_id] = min(first_seen.get(user_id, d), d)
    return by_date, first_seen


def build_weekly_snapshot(rows: list[dict[str, Any]], end_date: date, excluded_users: set[str] | None = None) -> dict:
    start_date = end_date - timedelta(days=6)
    by_date, first_seen = _group_daily_rows(rows, excluded_users)
    daily = [_daily_stat(by_date, day) for day in iter_dates(start_date, end_date)]
    period_rows = _period_rows(by_date, start_date, end_date)
    return _period_snapshot("weekly", start_date, end_date, daily, period_rows, by_date, first_seen)


def build_monthly_snapshot(
    rows: list[dict[str, Any]], start_date: date, end_date: date, excluded_users: set[str] | None = None
) -> dict:
    by_date, first_seen = _group_daily_rows(rows, excluded_users)
    daily = [_daily_stat(by_date, day) for day in iter_dates(start_date, end_date)]
    period_rows = _period_rows(by_date, start_date, end_date)
    return _period_snapshot("monthly", start_date, end_date, daily, period_rows, by_date, first_seen)


def _daily_stat(by_date: dict[date, list[dict[str, Any]]], day: date) -> dict[str, Any]:
    rows = by_date.get(day, [])
    return {
        "date": day.isoformat(),
        "dau": len(_users_on(by_date, day)),
        "events": sum(int(row.get("event_count") or 0) for row in rows),
        "sessions": sum(int(row.get("session_count") or 0) for row in rows),
    }


def _period_snapshot(
    mode: str,
    start_date: date,
    end_date: date,
    daily: list[dict[str, Any]],
    period_rows: list[dict[str, Any]],
    by_date: dict[date, list[dict[str, Any]]],
    first_seen: dict[str, date],
) -> dict:
    active_users = _users_between(by_date, start_date, end_date)
    dau_values = [int(row["dau"]) for row in daily]
    return {
        "mode": mode,
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "active_users": len(active_users),
        "avg_dau": round(sum(dau_values) / len(dau_values), 2) if dau_values else 0.0,
        "peak_dau": max(dau_values) if dau_values else 0,
        "new_users": sum(1 for d in first_seen.values() if start_date <= d <= end_date),
        "daily": daily,
        "source_counts": _source_counts(period_rows),
        "feature_counts": _feature_counts(period_rows),
        "retention": _retention_stats(by_date, first_seen, end_date),
    }


def _parse_date(raw: Any) -> date | None:
    try:
        return datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _users_on(by_date: dict[date, list[dict[str, Any]]], d: date) -> set[str]:
    return {str(row.get("user_id")) for row in by_date.get(d, []) if row.get("user_id")}


def _users_between(by_date: dict[date, list[dict[str, Any]]], start: date, end: date) -> set[str]:
    users: set[str] = set()
    current = start
    while current <= end:
        users.update(_users_on(by_date, current))
        current += timedelta(days=1)
    return users


def _period_rows(by_date: dict[date, list[dict[str, Any]]], start: date, end: date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for day in iter_dates(start, end):
        rows.extend(by_date.get(day, []))
    return rows


def _source_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        for source in row.get("sources") or []:
            counts[str(source)] += 1
    return dict(counts.most_common())


def _feature_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        counts.update(dict(row.get("feature_counts") or {}))
    return dict(counts.most_common(10))


def _retention_stats(
    by_date: dict[date, list[dict[str, Any]]], first_seen: dict[str, date], target: date
) -> dict[str, dict]:
    out: dict[str, dict] = {}
    active_today = _users_on(by_date, target)
    for days in (1, 7, 30):
        cohort_date = target - timedelta(days=days)
        cohort = {user for user, d in first_seen.items() if d == cohort_date}
        retained = cohort & active_today
        rate = round(len(retained) / len(cohort) * 100, 2) if cohort else 0.0
        out[f"d{days}"] = {
            "cohort_date": cohort_date.isoformat(),
            "cohort": len(cohort),
            "retained": len(retained),
            "rate": rate,
        }
    return out


def build_analytics_report_markdown(snapshot: dict) -> str:
    title = "用户活跃周报" if snapshot.get("mode") == "weekly" else "用户活跃月报"
    active_label = "WAU" if snapshot.get("mode") == "weekly" else "MAU"
    lines = [
        f"# {title} {snapshot.get('period_start')} ~ {snapshot.get('period_end')}",
        "",
        f"- {active_label}: {snapshot.get('active_users', 0)}",
        f"- 平均 DAU: {snapshot.get('avg_dau', 0)}",
        f"- 峰值 DAU: {snapshot.get('peak_dau', 0)}",
        f"- 新增活跃用户: {snapshot.get('new_users', 0)}",
        "",
        "## 每日 DAU",
        _format_daily(snapshot.get("daily", [])),
        "",
        "## 留存",
    ]
    for key, label in (("d1", "D1"), ("d7", "D7"), ("d30", "D30")):
        row = snapshot.get("retention", {}).get(key, {})
        lines.append(
            f"- {label}({row.get('cohort_date', '-')}): "
            f"{row.get('retained', 0)}/{row.get('cohort', 0)} ({row.get('rate', 0)}%)"
        )
    lines.extend(
        [
            "",
            "## 来源分布",
            _format_counts(snapshot.get("source_counts", {})),
            "",
            "## 功能 Top10",
            _format_counts(snapshot.get("feature_counts", {})),
        ]
    )
    return "\n".join(lines).strip()


def _format_daily(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "- 无"
    return "\n".join(
        f"- {row['date']}: DAU={row['dau']} events={row['events']} sessions={row['sessions']}" for row in rows
    )


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "- 无"
    return "\n".join(f"- {name}: {count}" for name, count in counts.items())
