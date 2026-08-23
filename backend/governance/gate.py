"""Action 治理门禁 — 把 logic 执行平面的占位权限升级为可配置策略（治理平面）。

职责：
    - 权限校验：可注入 permission_checker(user, perm) -> bool
    - 审批流：L4 高风险动作需审批单（approval_ticket），否则拒绝
    - 策略可解释：policy_for 返回结构化判定，供 api 透出拒绝原因

与 logic.executor 解耦：executor 在 _gate 中调用 ActionGate.policy_for，
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)

PermissionChecker = Callable[[object, Optional[str]], bool]


@dataclass
class GateDecision:
    allowed: bool
    reason: str = ""
    requires_approval: bool = False

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "requires_approval": self.requires_approval,
        }


class ActionGate:
    """动作治理门禁（无状态，可复用）。"""

    # 需要审批单的风险等级
    _APPROVAL_RISK = {"L4"}

    def __init__(self, permission_checker: Optional[PermissionChecker] = None):
        # 默认权限放行（架构验证）；生产注入真实 checker
        self._permission_checker = permission_checker

    def policy_for(self, action: dict, *, user=None,
                   approval_ticket: Optional[str] = None) -> GateDecision:
        risk = action.get("risk_level", "L2")
        perm = action.get("permission_required")

        # 1) 权限校验
        if perm and self._permission_checker is not None and user is not None:
            if not self._permission_checker(user, perm):
                return GateDecision(False, f"缺少权限: {perm}")

        # 2) 高风险审批门禁
        if risk in self._APPROVAL_RISK:
            if not approval_ticket:
                return GateDecision(
                    False, "L4 高风险动作需审批单 (approval_ticket)", requires_approval=True)
            # ticket 校验（此处仅校验非空；真实实现查审批系统）
            if not self._ticket_valid(approval_ticket):
                return GateDecision(False, "审批单无效或已过期", requires_approval=True)

        return GateDecision(True, "通过门禁")

    def _ticket_valid(self, ticket: str) -> bool:
        # 占位：真实实现应查审批系统/签名。当前接受非空 + 以 "TICKET-" 前缀演示。
        return isinstance(ticket, str) and ticket.startswith("TICKET-")
