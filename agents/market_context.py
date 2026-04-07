# -*- coding: utf-8 -*-
"""
MarketContextAgent — 大盘水温 + regime 计算。

Phase 1: 调用现有 run_funnel() 的大盘分析部分（拆分自 wyckoff_funnel.run()）。
         由于 run_funnel() 内部大盘分析与股票筛选耦合，Phase 1 不拆分，
         只在 OrchestratorAgent 层面做数据传递。

实际逻辑：接收 benchmark_context dict（由 ScreenerAgent 一并产出），
         转换为 MarketContext dataclass。
"""
from __future__ import annotations

import logging

from agents.contracts import AgentSkip, BaseAgent, MarketContext

logger = logging.getLogger(__name__)


class MarketContextAgent(BaseAgent):
    """
    确定性 Agent：从 benchmark_context 原始 dict 构建 MarketContext。

    设计说明：
    当前 run_funnel() 内部同时产出 benchmark_context 和 symbols_info，
    无法独立调用大盘分析。因此 MarketContextAgent 的 run()
    接收已有的 benchmark_context dict 做转换即可。
    大盘分析 Tool 已提取至 tools/market_regime.py；
    TODO: MarketContextAgent 应直接调用 tools/market_regime 而非依赖 ScreenerAgent 传入。
    """

    name = "market_context"

    def _execute(self, context: dict) -> MarketContext:
        """Phase 1: 从 context["_benchmark_context_raw"] 转换为 MarketContext。"""
        raw = context.get("_benchmark_context_raw")
        if not raw or not isinstance(raw, dict):
            raise AgentSkip("benchmark_context not provided")

        market_ctx = MarketContext.from_legacy_dict(raw)
        logger.info(
            "MarketContextAgent: date=%s regime=%s",
            market_ctx.date, market_ctx.regime.value,
        )
        return market_ctx
