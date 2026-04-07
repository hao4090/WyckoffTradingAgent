# -*- coding: utf-8 -*-
"""
智能管线 — 一键运行完整 Wyckoff 量化管线。

5 阶段流水线：漏斗筛选 → 大盘环境 → AI 研报 → 持仓策略 → 通知汇总。
实时展示每阶段进度，自动轮询刷新，用户无需手动点击"刷新"。
"""
from __future__ import annotations

import os
import time
from typing import Any

import streamlit as st

from app.background_jobs import (
    background_jobs_ready_for_current_user,
    submit_background_job,
    sync_background_job_state,
)
from app.layout import setup_page
from app.navigation import show_right_nav
from app.pipeline_renderers import render_pipeline_progress, render_pipeline_summary
from integrations.llm_client import (
    DEFAULT_GEMINI_MODEL,
    GEMINI_MODELS,
    OPENAI_COMPATIBLE_BASE_URLS,
    PROVIDER_LABELS,
    SUPPORTED_PROVIDERS,
    get_provider_credentials,
)

setup_page(page_title="智能管线", page_icon="🚀")

STATE_KEY = "full_pipeline_job"


def _is_running(state: dict[str, Any] | None) -> bool:
    """判断 pipeline 是否仍在运行。"""
    if not isinstance(state, dict):
        return False
    run = state.get("run")
    if run is None:
        # 刚提交，还没有 run 对象
        request_id = state.get("request_id", "")
        return bool(request_id)
    status = getattr(run, "status", "")
    return status in ("queued", "in_progress")


def _is_completed(state: dict[str, Any] | None) -> bool:
    """判断 pipeline 是否已完成（成功或失败）。"""
    if not isinstance(state, dict):
        return False
    run = state.get("run")
    if run is None:
        return False
    return getattr(run, "status", "") == "completed"


# ---------------------------------------------------------------------------
# 页面主体
# ---------------------------------------------------------------------------
content_col = show_right_nav()
with content_col:
    st.title("🚀 智能管线")
    st.markdown(
        "一键运行完整量化流水线：**漏斗筛选 → 大盘环境 → AI 研报 → 持仓策略 → 通知汇总**。"
    )

    # ── 权限检查 ──
    ready, reason = background_jobs_ready_for_current_user()
    if not ready:
        st.warning(f"后台任务不可用：{reason}")
        st.stop()

    # ── 模型配置区 ──
    with st.expander("模型配置", expanded=False):
        col_provider, col_model = st.columns(2)
        with col_provider:
            provider = st.selectbox(
                "API 供应商",
                options=list(SUPPORTED_PROVIDERS),
                format_func=lambda x: PROVIDER_LABELS.get(x, x),
                key="pipeline_provider",
            )
        with col_model:
            if provider == "gemini":
                model = st.selectbox(
                    "Gemini 模型",
                    options=GEMINI_MODELS,
                    index=GEMINI_MODELS.index(DEFAULT_GEMINI_MODEL) if DEFAULT_GEMINI_MODEL in GEMINI_MODELS else 0,
                    key="pipeline_model_gemini",
                )
            else:
                model = st.text_input(
                    "模型名称",
                    value=get_provider_credentials(provider)[1],
                    key="pipeline_model_other",
                )

        api_key, default_model, base_url = get_provider_credentials(provider)
        if not model:
            model = default_model

        api_key_input = st.text_input(
            f"{PROVIDER_LABELS.get(provider, provider)} API Key",
            value=api_key,
            type="password",
            key="pipeline_api_key",
        )
        if api_key_input:
            api_key = api_key_input

    # ── 高级配置 ──
    with st.expander("高级配置"):
        col_a, col_b = st.columns(2)
        with col_a:
            webhook_url = st.text_input(
                "飞书 Webhook (可选)",
                value=st.session_state.get("feishu_webhook", "") or "",
                key="pipeline_feishu_webhook",
            )
        with col_b:
            skip_step4 = st.checkbox(
                "跳过持仓策略 (Step4)",
                value=False,
                key="pipeline_skip_step4",
            )
        notify_enabled = bool(webhook_url.strip())

    # ── 提交按钮 ──
    submitted = False
    state = st.session_state.get(STATE_KEY)
    running = _is_running(state)

    if running:
        st.button(
            "🔄 管线运行中...",
            disabled=True,
            use_container_width=True,
        )
    else:
        if not api_key:
            st.warning(f"请配置 {PROVIDER_LABELS.get(provider, provider)} API Key 后运行管线。")

        submitted = st.button(
            "🚀 一键运行完整管线",
            type="primary",
            disabled=not api_key,
            use_container_width=True,
        )

    if submitted and api_key:
        user = st.session_state.get("user") or {}
        user_id = str(user.get("id", "") or "").strip() if isinstance(user, dict) else ""

        payload = {
            "user_id": user_id,
            "provider": provider,
            "model": model,
            "api_key": api_key,
            "base_url": base_url,
            "webhook_url": webhook_url.strip(),
            "skip_step4": skip_step4,
        }

        submit_background_job("full_pipeline", payload, state_key=STATE_KEY)
        st.rerun()

    # ── 同步状态 + 渲染进度 ──
    state = sync_background_job_state(state_key=STATE_KEY)

    if isinstance(state, dict) and state.get("request_id"):
        request_id = state.get("request_id", "")
        stages = state.get("stages", [])
        current_stage = state.get("current_stage", "")
        current_stage_status = state.get("current_stage_status", "")
        is_running_now = _is_running(state)

        st.divider()
        st.subheader("管线进度")
        st.caption(f"任务 ID: `{request_id}`")

        render_pipeline_progress(
            stages=stages,
            current_stage=current_stage,
            current_stage_status=current_stage_status,
            is_running=is_running_now,
        )

        # 完成后渲染结果
        if _is_completed(state):
            result = state.get("result")
            if isinstance(result, dict):
                conclusion = getattr(state.get("run"), "conclusion", "")
                if conclusion == "success" and result.get("ok"):
                    st.success("管线运行完成!")
                elif conclusion == "success":
                    st.warning("管线部分完成，部分阶段失败。")
                else:
                    st.error("管线运行失败。")
                    error_msg = result.get("error", "")
                    if error_msg:
                        st.error(error_msg)

                st.divider()
                st.subheader("运行结果")
                render_pipeline_summary(result)

        # 自动轮询：运行中时每 2 秒刷新
        if is_running_now:
            time.sleep(2)
            st.rerun()
