# -*- coding: utf-8 -*-
"""
Agent 间数据契约 — 所有 Agent 的输入输出类型定义。

每个 dataclass 提供 from_legacy_dict() / to_legacy_dict() 实现
新旧格式互转，Phase 1 期间保持与现有 pipeline 的完全兼容。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Regime(str, Enum):
    """大盘水温 regime。"""
    RISK_ON = "RISK_ON"
    NEUTRAL = "NEUTRAL"
    RISK_OFF = "RISK_OFF"
    CRASH = "CRASH"
    PANIC_REPAIR = "PANIC_REPAIR"
    BLACK_SWAN = "BLACK_SWAN"

    @classmethod
    def from_str(cls, s: str) -> "Regime":
        s = (s or "").strip().upper()
        try:
            return cls(s)
        except ValueError:
            return cls.NEUTRAL


class PipelineStatus(str, Enum):
    """Pipeline / Agent 执行状态。"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


# ---------------------------------------------------------------------------
# MarketContext — MarketContextAgent 的输出
# ---------------------------------------------------------------------------

@dataclass
class MarketContext:
    """大盘环境上下文。"""
    date: str                                       # YYYY-MM-DD
    regime: Regime = Regime.NEUTRAL
    benchmark_metrics: dict = field(default_factory=dict)  # close, ma50, ma200, 3d ...
    sector_rotation: dict = field(default_factory=dict)
    breadth: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)           # 完整 benchmark_context 原始 dict

    @classmethod
    def from_legacy_dict(cls, d: dict) -> "MarketContext":
        """从现有 benchmark_context dict 构造。"""
        from utils.trading_clock import resolve_end_calendar_day
        date = d.get("date") or resolve_end_calendar_day().isoformat()
        return cls(
            date=str(date),
            regime=Regime.from_str(str(d.get("regime", "NEUTRAL"))),
            benchmark_metrics={
                k: d.get(k) for k in (
                    "close", "ma50", "ma200",
                    "recent3_cum_pct", "main_today_pct",
                    "main_code", "smallcap_code",
                    "smallcap_close", "smallcap_recent3_cum_pct",
                )
            },
            sector_rotation=d.get("sector_rotation") or {},
            breadth=d.get("breadth") or {},
            raw=dict(d),
        )

    def to_legacy_dict(self) -> dict:
        """还原为现有 benchmark_context dict 格式。"""
        out = dict(self.raw) if self.raw else {}
        out["regime"] = self.regime.value
        out["date"] = self.date
        out.update(self.benchmark_metrics)
        if self.sector_rotation:
            out["sector_rotation"] = self.sector_rotation
        if self.breadth:
            out["breadth"] = self.breadth
        return out


# ---------------------------------------------------------------------------
# StockCandidate — 单只候选股信息
# ---------------------------------------------------------------------------

_CANDIDATE_FIELDS = (
    "code", "name", "tag", "track", "stage", "score", "priority_score",
    "industry", "sector_state", "exit_signal",
)


@dataclass
class StockCandidate:
    """漏斗筛出的候选股。"""
    code: str = ""
    name: str = ""
    tag: str = ""
    track: str = ""                      # Trend | Accum | ""
    stage: str = ""                      # Markup | Accum_A | Accum_B | Accum_C | ""
    score: float = 0.0
    priority_score: float = 0.0
    industry: str = ""
    sector_state: str = ""
    exit_signal: str = ""
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_legacy_dict(cls, d: dict) -> "StockCandidate":
        kwargs = {k: d.get(k, "") for k in _CANDIDATE_FIELDS}
        kwargs["score"] = float(kwargs.get("score") or 0)
        kwargs["priority_score"] = float(kwargs.get("priority_score") or 0)
        kwargs["raw"] = dict(d)
        return cls(**kwargs)

    def to_legacy_dict(self) -> dict:
        if self.raw:
            return dict(self.raw)
        return {k: getattr(self, k) for k in _CANDIDATE_FIELDS}


# ---------------------------------------------------------------------------
# ScreenResult — ScreenerAgent 的输出
# ---------------------------------------------------------------------------

@dataclass
class ScreenResult:
    """漏斗筛选结果。"""
    candidates: list[StockCandidate] = field(default_factory=list)
    total_scanned: int = 0
    funnel_stats: dict = field(default_factory=dict)

    @classmethod
    def from_legacy(
        cls,
        symbols_info: list[dict],
        total_scanned: int = 0,
        funnel_stats: dict | None = None,
    ) -> "ScreenResult":
        return cls(
            candidates=[StockCandidate.from_legacy_dict(d) for d in symbols_info],
            total_scanned=total_scanned,
            funnel_stats=funnel_stats or {},
        )

    def to_legacy_symbols_info(self) -> list[dict]:
        return [c.to_legacy_dict() for c in self.candidates]


# ---------------------------------------------------------------------------
# AnalysisReport — WyckoffAnalystAgent 的输出
# ---------------------------------------------------------------------------

@dataclass
class AnalysisReport:
    """AI 三阵营研报结果。"""
    report_text: str = ""                # 完整 Markdown
    springboard_codes: list[str] = field(default_factory=list)
    model_used: str = ""
    token_usage: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# StrategyDecision — StrategyAgent 的输出
# ---------------------------------------------------------------------------

@dataclass
class StrategyDecision:
    """OMS 决策结果。"""
    market_view: str = ""
    decisions: list[dict] = field(default_factory=list)
    model_used: str = ""
    reason: str = "ok"


# ---------------------------------------------------------------------------
# AgentResult — 所有 Agent 的统一输出包装
# ---------------------------------------------------------------------------

@dataclass
class AgentResult:
    """Agent 执行结果的通用包装。"""
    agent_name: str = ""
    status: PipelineStatus = PipelineStatus.PENDING
    payload: Any = None
    error: str | None = None
    duration_ms: int = 0
    retries: int = 0

    @property
    def ok(self) -> bool:
        return self.status == PipelineStatus.COMPLETED

    def to_checkpoint_dict(self) -> dict:
        """序列化为可存入 Supabase JSON 的 dict。"""
        return {
            "agent_name": self.agent_name,
            "status": self.status.value,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "retries": self.retries,
        }


# ---------------------------------------------------------------------------
# AgentSkip — _execute 内提前中止（非异常失败，而是逻辑跳过/前置缺失）
# ---------------------------------------------------------------------------

class AgentSkip(Exception):
    """Agent 内部主动跳过，carry FAILED 结果。"""

    def __init__(self, error: str, *, status: PipelineStatus = PipelineStatus.FAILED, payload: Any = None):
        super().__init__(error)
        self.status = status
        self.payload = payload


# ---------------------------------------------------------------------------
# BaseAgent — 公共 run() 模板（计时 + try/except + AgentResult 包装）
# ---------------------------------------------------------------------------

class BaseAgent:
    """
    所有 Agent 的基类，提供 ``run()`` 模板方法。

    子类只需实现 ``_execute(context) -> payload``：
    - 正常返回 payload → ``AgentResult(COMPLETED, payload)``
    - raise ``AgentSkip(error)`` → ``AgentResult(FAILED/COMPLETED, error=...)``
    - raise 其他异常 → ``AgentResult(FAILED, error=str(e))``
    """

    name: str = ""

    def run(self, context: dict) -> AgentResult:
        logger = logging.getLogger(self.__class__.__name__)
        t0 = time.monotonic()
        try:
            payload = self._execute(context)
            return AgentResult(
                agent_name=self.name,
                status=PipelineStatus.COMPLETED,
                payload=payload,
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
        except AgentSkip as skip:
            return AgentResult(
                agent_name=self.name,
                status=skip.status,
                payload=skip.payload,
                error=str(skip),
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
        except Exception as e:
            logger.exception("%s failed", self.__class__.__name__)
            return AgentResult(
                agent_name=self.name,
                status=PipelineStatus.FAILED,
                error=str(e),
                duration_ms=int((time.monotonic() - t0) * 1000),
            )

    def _execute(self, context: dict) -> Any:
        """子类实现：返回 payload，或 raise AgentSkip / 异常。"""
        raise NotImplementedError
