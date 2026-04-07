# -*- coding: utf-8 -*-
"""
Wyckoff Agent 层 — LiteLLM 统一适配 + 自研 OrchestratorAgent 编排。

5 Agent 管线：ScreenerAgent → MarketContextAgent → WyckoffAnalystAgent
→ StrategyAgent → NotifierAgent，由 OrchestratorAgent 协调执行顺序与重试。
"""
