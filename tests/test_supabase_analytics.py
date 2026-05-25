from __future__ import annotations

from datetime import date

from integrations.supabase_analytics import (
    aggregate_daily_activity,
    build_analytics_report_markdown,
    build_monthly_snapshot,
    build_weekly_snapshot,
)


def test_aggregate_daily_activity_excludes_action_and_heartbeat():
    rows = aggregate_daily_activity(
        [
            {"user_id": "u1", "source": "web", "event_name": "page_view", "session_id": "s1", "feature": "chat"},
            {"user_id": "u1", "source": "web", "event_name": "tool_run", "session_id": "s1", "feature": "screen"},
            {"user_id": "u2", "source": "action", "event_name": "scheduled_job", "session_id": "s2"},
            {"user_id": "u3", "source": "cli", "event_name": "heartbeat", "session_id": "s3"},
        ],
        date(2026, 5, 24),
    )

    assert len(rows) == 1
    assert rows[0]["user_id"] == "u1"
    assert rows[0]["event_count"] == 2
    assert rows[0]["feature_counts"] == {"chat": 1, "screen": 1}


def test_weekly_snapshot_reports_daily_dau_and_wau():
    rows = [
        {"activity_date": "2026-05-18", "user_id": "u1", "sources": ["web"], "event_count": 2},
        {"activity_date": "2026-05-19", "user_id": "u1", "sources": ["web"], "event_count": 1},
        {"activity_date": "2026-05-19", "user_id": "u2", "sources": ["cli"], "event_count": 3},
        {"activity_date": "2026-05-24", "user_id": "u3", "sources": ["web"], "event_count": 1},
    ]

    snapshot = build_weekly_snapshot(rows, date(2026, 5, 24))
    report = build_analytics_report_markdown(snapshot)

    assert snapshot["active_users"] == 3
    assert snapshot["daily"][1]["dau"] == 2
    assert "用户活跃周报" in report
    assert "2026-05-19: DAU=2" in report


def test_monthly_snapshot_excludes_internal_user():
    rows = [
        {"activity_date": "2026-05-01", "user_id": "internal", "sources": ["web"], "event_count": 2},
        {"activity_date": "2026-05-02", "user_id": "u1", "sources": ["web"], "event_count": 1},
        {"activity_date": "2026-05-03", "user_id": "u2", "sources": ["cli"], "event_count": 1},
    ]

    snapshot = build_monthly_snapshot(rows, date(2026, 5, 1), date(2026, 5, 31), {"internal"})

    assert snapshot["active_users"] == 2
    assert snapshot["new_users"] == 2
