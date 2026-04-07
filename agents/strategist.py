# -*- coding: utf-8 -*-
"""
StrategyAgent — LLM 驱动的 OMS 决策。

当前：整体调用 core.strategy.run_step4()。
TODO: 拆分为 build_prompt → call_llm → parse_json → run_oms 独立 Tool。
"""
from __future__ import annotations

import logging

from agents.contracts import (
    AgentResult,
    AgentSkip,
    AnalysisReport,
    BaseAgent,
    MarketContext,
    PipelineStatus,
    ScreenResult,
    StrategyDecision,
)

logger = logging.getLogger(__name__)


class StrategyAgent(BaseAgent):
    """
    LLM Agent：生成持仓去留决策 + 新标的买入策略。

    使用 PRIVATE_PM_DECISION_JSON_PROMPT 让 LLM 以威科夫视角
    对持仓和候选标的做结构化 JSON 决策。
    """

    name = "strategist"

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
        portfolio_id: str = "",
        tg_bot_token: str = "",
        tg_chat_id: str = "",
    ):
        self.api_key = api_key
        self.model = model
        self.portfolio_id = portfolio_id
        self.tg_bot_token = tg_bot_token
        self.tg_chat_id = tg_chat_id

    def _execute(self, context: dict) -> StrategyDecision:
        """Phase 1: 调用 step4_rebalancer.run() 做持仓再平衡。"""
        if not self.portfolio_id:
            raise AgentSkip(
                "skipped_no_portfolio",
                status=PipelineStatus.COMPLETED,
                payload=StrategyDecision(reason="skipped_no_portfolio"),
            )

        if not self.tg_bot_token or not self.tg_chat_id:
            raise AgentSkip(
                "skipped_telegram_unconfigured",
                status=PipelineStatus.COMPLETED,
                payload=StrategyDecision(reason="skipped_telegram_unconfigured"),
            )

        analyst_result: AgentResult = context.get("analyst")
        market_result: AgentResult = context.get("market_context")
        screen_result: AgentResult = context.get("screener")

        # 构建 step4 输入
        report_text = ""
        if analyst_result and analyst_result.payload:
            report: AnalysisReport = analyst_result.payload
            report_text = report.report_text

        benchmark_context = None
        if market_result and market_result.ok:
            mctx: MarketContext = market_result.payload
            benchmark_context = mctx.to_legacy_dict()

        # 构建 candidate_meta: 仅起跳板代码
        candidate_meta: list[dict] = []
        if (
            analyst_result
            and analyst_result.payload
            and screen_result
            and screen_result.ok
        ):
            springboard_set = set(analyst_result.payload.springboard_codes)
            screen: ScreenResult = screen_result.payload
            for c in screen.candidates:
                if c.code in springboard_set:
                    candidate_meta.append(c.to_legacy_dict())

        from core.strategy import run_step4

        ok, reason = run_step4(
            external_report=report_text,
            benchmark_context=benchmark_context,
            api_key=self.api_key,
            model=self.model,
            candidate_meta=candidate_meta or None,
            portfolio_id=self.portfolio_id,
            tg_bot_token=self.tg_bot_token,
            tg_chat_id=self.tg_chat_id,
        )

        logger.info("StrategyAgent: ok=%s reason=%s", ok, reason)
        decision = StrategyDecision(model_used=self.model, reason=reason)

        if not ok:
            raise AgentSkip(reason, payload=decision)

        return decision
