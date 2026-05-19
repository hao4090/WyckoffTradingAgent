from __future__ import annotations

import sys


def test_preview_only_skips_persistence_and_keeps_llm_input_path(monkeypatch, tmp_path):
    import core.batch_report as batch_report
    import core.funnel_pipeline as funnel_pipeline
    import integrations.supabase_signal_pending as signal_pending
    import scripts.daily_job as daily_job

    captured: dict[str, object] = {}

    def forbidden_write(*_args, **_kwargs):
        raise AssertionError("preview-only job must not write persistence tables")

    def fake_run_funnel(webhook_url, *, notify=True, return_details=False):
        captured["step2_webhook"] = webhook_url
        captured["step2_notify"] = notify
        captured["step2_return_details"] = return_details
        return (
            True,
            [{"code": "000001", "name": "平安银行", "tag": "SOS"}],
            {"regime": "NEUTRAL"},
            {
                "triggers": {"sos": [("000002", 1.0)]},
                "all_df_map": {"000002": object()},
                "name_map": {"000002": "万科A"},
                "sector_map": {"000002": "房地产"},
            },
        )

    def fake_run_step2_5(*_args, dry_run=False, **_kwargs):
        captured["signal_dry_run"] = dry_run
        return [{"code": "000002", "name": "万科A", "tag": "pending confirmed"}]

    def fake_run_step3(symbols_info, webhook_url, *_args, **_kwargs):
        captured["step3_symbols"] = [item["code"] for item in symbols_info]
        captured["step3_webhook"] = webhook_url
        return True, "ok_preview", "# Step3 模型输入预演"

    monkeypatch.setenv("STEP3_SKIP_LLM", "1")
    monkeypatch.setenv("DAILY_JOB_SKIP_STEP4", "1")
    monkeypatch.setenv("DAILY_JOB_PREVIEW_ONLY", "1")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.invalid/webhook")
    monkeypatch.setattr(sys, "argv", ["daily_job.py", "--logs", str(tmp_path / "preview.log")])
    monkeypatch.setattr(daily_job, "next_trading_day", lambda today: today)
    monkeypatch.setattr(daily_job, "_latest_trade_date_str", lambda: "2026-05-19")
    monkeypatch.setattr(daily_job, "upsert_market_signal_daily", forbidden_write)
    monkeypatch.setattr(daily_job, "upsert_recommendations", forbidden_write)
    monkeypatch.setattr(daily_job, "mark_ai_recommendations", forbidden_write)
    monkeypatch.setattr(daily_job, "_run_springboard_scoring", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(funnel_pipeline, "run_funnel", fake_run_funnel)
    monkeypatch.setattr(batch_report, "run_step3", fake_run_step3)
    monkeypatch.setattr(batch_report, "extract_operation_pool_codes", lambda **_kwargs: ["000001"])
    monkeypatch.setattr(signal_pending, "run_step2_5", fake_run_step2_5)

    assert daily_job.main() == 0
    assert captured["step2_webhook"] == ""
    assert captured["step2_notify"] is False
    assert captured["step2_return_details"] is True
    assert captured["signal_dry_run"] is True
    assert captured["step3_webhook"] == "https://example.invalid/webhook"
    assert captured["step3_symbols"] == ["000001", "000002"]


def test_signal_confirmation_dry_run_does_not_write(monkeypatch):
    import integrations.supabase_signal_pending as signal_pending

    writes: list[str] = []
    monkeypatch.setattr(signal_pending, "write_pending_signals", lambda *_args, **_kwargs: writes.append("insert"))
    monkeypatch.setattr(signal_pending, "load_pending_signals", lambda: [{"id": 1, "code": 1}])
    monkeypatch.setattr(
        signal_pending,
        "run_confirmation_cycle",
        lambda *_args, **_kwargs: ([{"id": 1, "status": "confirmed"}], [{"code": "000001"}]),
    )
    monkeypatch.setattr(signal_pending, "batch_update_signals", lambda *_args, **_kwargs: writes.append("update"))

    confirmed = signal_pending.run_step2_5(
        signal_date="2026-05-19",
        triggers={"sos": [("000001", 1.0)]},
        df_map={"000001": object()},
        dry_run=True,
    )

    assert confirmed == [{"code": "000001"}]
    assert writes == []
