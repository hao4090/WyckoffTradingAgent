# -*- coding: utf-8 -*-
"""
ScreenerAgent — 4 层 Wyckoff 漏斗筛选。

当前：整体调用 run_funnel()，同时产出 ScreenResult + benchmark_context。
TODO: 拆解为 run_layer1/2/3/4 独立 Tool 调用。
"""
from __future__ import annotations

import logging

from agents.contracts import AgentSkip, BaseAgent, PipelineStatus, ScreenResult

logger = logging.getLogger(__name__)


class ScreenerAgent(BaseAgent):
    """
    确定性 Agent：执行 4 层 Wyckoff 漏斗筛选。

    Phase 1: 直接调用 core/funnel_pipeline.run_funnel()。
    同时产出:
      - ScreenResult (候选股列表)
      - benchmark_context (大盘环境, 存入 context 供 MarketContextAgent 转换)
    """

    name = "screener"

    def __init__(self, webhook_url: str = "", notify: bool = True):
        self.webhook_url = webhook_url
        self.notify = notify

    def _execute(self, context: dict) -> ScreenResult:
        """执行漏斗筛选。"""
        from core.funnel_pipeline import run_funnel

        ok, symbols_info, benchmark_context = run_funnel(
            self.webhook_url,
            notify=self.notify,
        )

        # 存储 raw benchmark_context 供 MarketContextAgent 使用
        context["_benchmark_context_raw"] = benchmark_context

        if not ok:
            raise AgentSkip("run_funnel returned ok=False")

        screen = ScreenResult.from_legacy(
            symbols_info=symbols_info,
            total_scanned=0,  # TODO: 精确统计需拆解为独立 Tool 后实现
        )
        logger.info(
            "ScreenerAgent: %d candidates selected",
            len(screen.candidates),
        )
        return screen
