"""CLI activity telemetry with silent failure."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

SESSION_FILE = Path.home() / ".wyckoff" / "telemetry_session"


def _session_id() -> str:
    try:
        if SESSION_FILE.exists():
            existing = SESSION_FILE.read_text(encoding="utf-8").strip()
            if existing:
                return existing
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        sid = uuid.uuid4().hex
        SESSION_FILE.write_text(sid, encoding="utf-8")
        return sid
    except Exception:
        return uuid.uuid4().hex


def track_cli_activity(
    event_name: str,
    *,
    feature: str = "",
    success: bool = True,
    duration_ms: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    if os.getenv("WYCKOFF_TELEMETRY", "1").strip() == "0":
        return
    try:
        from cli.auth import restore_session
        from integrations.supabase_analytics import track_activity_event

        session = restore_session()
        if not session or not session.get("user_id"):
            return
        track_activity_event(
            user_id=str(session.get("user_id") or ""),
            event_name=event_name,
            source="cli",
            session_id=_session_id(),
            feature=feature or event_name,
            success=success,
            duration_ms=duration_ms,
            metadata=metadata,
            access_token=str(session.get("access_token") or ""),
        )
    except Exception:
        return


def track_cli_command(command: str, *, success: bool, duration_ms: int, subcommand: str = "") -> None:
    track_cli_activity(
        "cli_command",
        feature=command or "tui",
        success=success,
        duration_ms=duration_ms,
        metadata={"subcommand": subcommand},
    )
