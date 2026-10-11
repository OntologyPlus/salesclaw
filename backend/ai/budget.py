"""Phase B：动态 ToolLoop / 延迟预算

按 intent / skill 元数据 / 工作流标记解析 max_rounds 与 latency budget，
替代全局写死的 max_rounds=2。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

from config import settings

# 需要更深工具链的意图（分析 / 规划 / 跨域）
_COMPLEX_INTENTS = frozenset({
    "visit", "coverage", "roi", "kpi", "attribution", "what_if", "what-if",
    "diagnose", "attribute", "suggest", "insight", "kol", "territory",
    "exam", "scenario", "academic", "onboarding", "report",
})


@dataclass
class TurnBudget:
    max_rounds: int
    max_latency_ms: int
    max_tool_calls: int
    reason: str = "default"

    def to_dict(self) -> dict:
        return asdict(self)


def resolve_budget(
    *,
    intent: str = "",
    skill_meta: Optional[dict] = None,
    is_workflow: bool = False,
    collaboration: bool = False,
) -> TurnBudget:
    """解析本轮执行预算。"""
    skill_meta = skill_meta or {}
    meta = skill_meta.get("metadata") or skill_meta
    nested = meta.get("metadata") or {}

    # 工作流：优先 SKILL.md max_rounds_per_step
    if is_workflow or meta.get("is_workflow") or nested.get("is_workflow"):
        rounds = int(
            meta.get("max_rounds_per_step")
            or nested.get("max_rounds_per_step")
            or settings.AI_WORKFLOW_MAX_ROUNDS
        )
        return TurnBudget(
            max_rounds=max(1, rounds),
            max_latency_ms=settings.AI_COMPLEX_MAX_LATENCY_MS,
            max_tool_calls=max(1, rounds),
            reason="workflow",
        )

    if collaboration:
        return TurnBudget(
            max_rounds=min(3, settings.AI_COMPLEX_MAX_ROUNDS),
            max_latency_ms=settings.AI_COMPLEX_MAX_LATENCY_MS,
            max_tool_calls=3,
            reason="collaboration",
        )

    intent_l = (intent or "").lower()
    if intent_l in _COMPLEX_INTENTS or any(k in intent_l for k in ("analy", "plan", "simulat")):
        return TurnBudget(
            max_rounds=settings.AI_COMPLEX_MAX_ROUNDS,
            max_latency_ms=settings.AI_COMPLEX_MAX_LATENCY_MS,
            max_tool_calls=settings.AI_COMPLEX_MAX_ROUNDS,
            reason="complex_intent",
        )

    return TurnBudget(
        max_rounds=settings.AI_DEFAULT_MAX_ROUNDS,
        max_latency_ms=settings.AI_DEFAULT_MAX_LATENCY_MS,
        max_tool_calls=settings.AI_DEFAULT_MAX_ROUNDS,
        reason="default",
    )


def budget_exceeded(started_monotonic: float, budget: TurnBudget, *, now: Optional[float] = None) -> bool:
    """是否已超过 latency 预算。"""
    import time
    t = now if now is not None else time.monotonic()
    elapsed_ms = int((t - started_monotonic) * 1000)
    return elapsed_ms >= budget.max_latency_ms


__all__ = ["TurnBudget", "resolve_budget", "budget_exceeded"]
