"""ActionExecutor — Logic 平面的执行层（风险门禁 + 权限校验 + 溯源）。

职责：
    - 解析 LogicPlan 为可执行步骤
    - 风险门禁：L4 动作需 dry_run=True 或 explicit_confirm=True，否则拦截
    - 权限校验：占位（读 action.permission_required），真实校验可在 main 注入
    - 逐步执行：复用 logic.registry.dispatch 派发 handler，全程 provenance.track 包裹
    - 失败非阻断：单步失败记录 error 并继续，整体返回汇总

"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    action: str
    risk_level: str
    ok: bool
    skipped: bool = False
    reason: str = ""
    output: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "risk_level": self.risk_level,
            "ok": self.ok,
            "skipped": self.skipped,
            "reason": self.reason,
            "output": self.output,
        }


@dataclass
class ExecutionResult:
    goal: str
    total: int
    executed: int
    skipped: int
    failed: int
    steps: list[StepResult] = field(default_factory=list)
    activity_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "total": self.total,
            "executed": self.executed,
            "skipped": self.skipped,
            "failed": self.failed,
            "activity_id": self.activity_id,
            "steps": [s.to_dict() for s in self.steps],
        }


class ActionExecutor:
    """动作执行器（无状态，可复用）。"""

    def __init__(self, *, agent_id: Optional[str] = None,
                 mgr=None, permission_checker=None, gate=None):
        """
        Args:
            agent_id: 溯源 agent（谁发起的执行）
            mgr: ProvenanceManager；默认 None 时内部自建
            permission_checker: 可选 (user, permission_required) -> bool
                                不传则占位放行（架构验证）。若同时传 gate 则优先用 gate。
            gate: 可选 governance.ActionGate；传入后由治理门禁统一裁决
                  （权限 + L4 审批单），覆盖内置的简化 _gate。
        """
        from provenance.manager import ProvenanceManager, track
        self._ProvenanceManager = ProvenanceManager
        self._track = track
        self._mgr = mgr or ProvenanceManager()
        self._agent_id = agent_id
        self._permission_checker = permission_checker
        self._gate_obj = gate

    # ── 风险门禁 ───────────────────────────────
    def _gate(self, action: dict, *, dry_run: bool,
              explicit_confirm: bool, user=None,
              approval_ticket: Optional[str] = None) -> tuple[bool, str]:
        """返回 (放行?, 原因)。

        优先级：
            1. 若注入 governance.ActionGate → 统一裁决（权限 + L4 审批单）
            2. 否则内置简化门禁（L4 需 dry_run/explicit_confirm，占位权限）
        """
        if self._gate_obj is not None:
            decision = self._gate_obj.policy_for(
                action, user=user, approval_ticket=approval_ticket)
            return decision.allowed, decision.reason

        risk = action.get("risk_level", "L2")
        if risk == "L4" and not dry_run and not explicit_confirm:
            return False, "L4 高风险动作需 dry_run=True 或 explicit_confirm=True"
        perm = action.get("permission_required")
        if perm and self._permission_checker is not None and user is not None:
            if not self._permission_checker(user, perm):
                return False, f"缺少权限: {perm}"
        return True, ""

    # ── 主入口 ─────────────────────────────────
    def run(self, plan, *, user=None, dry_run: bool = False,
            explicit_confirm: bool = False,
            approval_ticket: Optional[str] = None) -> ExecutionResult:
        from logic.registry import dispatch

        result = ExecutionResult(goal=plan.goal, total=len(plan.steps),
                                 executed=0, skipped=0, failed=0)

        with self._track("logic.execute", name=plan.goal,
                         agent_id=self._agent_id, mgr=self._mgr) as act:
            result.activity_id = act.activity_id
            for step in plan.steps:
                action = {
                    "name": step.action_name,
                    "risk_level": step.risk_level,
                    "description": step.description,
                    "permission_required": None,
                }
                # 补全来自 registry 的权限字段
                from ontology.actions import get_action
                meta = get_action(step.action_name)
                if meta:
                    action["permission_required"] = meta.get("permission_required")

                ok, reason = self._gate(action, dry_run=dry_run,
                                        explicit_confirm=explicit_confirm,
                                        user=user, approval_ticket=approval_ticket)
                if not ok:
                    result.skipped += 1
                    result.steps.append(StepResult(
                        action=step.action_name, risk_level=step.risk_level,
                        ok=False, skipped=True, reason=reason,
                    ))
                    continue

                if dry_run:
                    result.skipped += 1
                    result.steps.append(StepResult(
                        action=step.action_name, risk_level=step.risk_level,
                        ok=True, skipped=True, reason="dry_run 预览，未执行",
                    ))
                    continue

                try:
                    out = dispatch(action, step.payload, {"user": user})
                    result.executed += 1
                    result.steps.append(StepResult(
                        action=step.action_name, risk_level=step.risk_level,
                        ok=True, output=out or {},
                    ))
                except Exception as e:  # 单步失败非阻断
                    logger.error("动作执行失败 %s: %s", step.action_name, e, exc_info=True)
                    result.failed += 1
                    result.steps.append(StepResult(
                        action=step.action_name, risk_level=step.risk_level,
                        ok=False, reason=str(e),
                    ))
        return result
