"""LogicPlan — 把目标解析为有序 Action 序列（Logic 平面的规划层）。

复用 ontology.actions 的元数据中心（recommend_actions_for_diagnosis /
list_actions），不重复定义动作，只做「目标 → 可执行序列」的编排。

规划策略：
    - 若目标是诊断结论（含 level 字段）→ 复用 recommend_actions_for_diagnosis
    - 否则按 domain/risk_level 检索候选 action，按风险升序排成安全优先序列
本模块零第三方依赖。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# risk 排序权重（L1 最安全，前置执行）
_RISK_ORDER = {"L1": 0, "L2": 1, "L3": 2, "L4": 3}


@dataclass
class PlanStep:
    action_name: str
    display_name: str
    risk_level: str
    description: str
    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "action": self.action_name,
            "display_name": self.display_name,
            "risk_level": self.risk_level,
            "description": self.description,
            "payload": self.payload,
        }


@dataclass
class LogicPlan:
    goal: str
    domain: Optional[str]
    steps: list[PlanStep] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "domain": self.domain,
            "steps": [s.to_dict() for s in self.steps],
            "notes": self.notes,
            "step_count": len(self.steps),
        }


def build_plan(goal: str, *, domain: Optional[str] = None,
               level: Optional[str] = None,
               tenant_id: Optional[str] = None,
               payload: dict = None) -> LogicPlan:
    """构建执行计划。

    Args:
        goal: 自然语言目标（用于备注，不参与规则匹配）
        domain: 业务域（coverage/visit/adoption/...）
        level: 诊断等级（RED/BLACK/YELLOW/GREEN），存在时走诊断推荐
        tenant_id: 租户隔离
        payload: 默认注入到每个 step 的载荷
    """
    payload = payload or {}
    plan = LogicPlan(goal=goal, domain=domain)

    from ontology.actions import recommend_actions_for_diagnosis, list_actions

    if level:
        # 诊断驱动：复用既有 Layer 5 推荐
        recs = recommend_actions_for_diagnosis(level, domain)
        for r in recs:
            plan.steps.append(PlanStep(
                action_name=r["action"],
                display_name=r.get("display_name", r["action"]),
                risk_level=r.get("risk_level", "L2"),
                description=r.get("description", ""),
                payload=dict(payload),
            ))
        plan.notes.append(f"诊断驱动：level={level}")
        return plan

    # 非诊断：按 domain 检索候选，按风险升序（安全优先）
    candidates = list_actions(domain=domain, tenant_id=tenant_id)
    if not candidates and domain:
        # domain 无候选时退化为全量，避免空计划
        candidates = list_actions(tenant_id=tenant_id)
        plan.notes.append(f"domain={domain} 无候选，已退化为全量检索")

    ordered = sorted(
        candidates,
        key=lambda a: _RISK_ORDER.get(a.get("risk_level", "L2"), 2),
    )
    for a in ordered:
        plan.steps.append(PlanStep(
            action_name=a["name"],
            display_name=a.get("display_name", a["name"]),
            risk_level=a.get("risk_level", "L2"),
            description=a.get("description", ""),
            payload=dict(payload),
        ))
    plan.notes.append(f"检索候选 {len(candidates)} 个，按风险升序编排")
    return plan
