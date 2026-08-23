"""安全护栏引擎 + AI 权限 L1-L4 分级

包含两部分：
1. AIPermissionMatrix：场景-角色-权限矩阵（医药销售适配），L1-L4 分级
2. SafetyValvesEngine：合规检测 + 权限分级检查，输出拦截/放行/审批决策

权限分级：
- L1_observe：只读查询
- L2_suggest：查询+建议
- L3_assist：查询+建议+辅助执行（需人工确认）
- L4_automate：自动执行
"""
from typing import Any, Optional


class AIPermissionMatrix:
    """AI 权限分级矩阵 - 场景 × 角色 -> 权限级别"""

    # 权限级别定义
    LEVELS = {
        "L1_observe": "只读查询",
        "L2_suggest": "查询+建议",
        "L3_assist": "查询+建议+辅助执行（需人工确认）",
        "L4_automate": "自动执行",
    }

    # 级别排序（用于比较）
    _LEVEL_RANK = {"L1_observe": 1, "L2_suggest": 2, "L3_assist": 3, "L4_automate": 4}

    # 角色别名归一化（中文 -> 英文 key，与现有 RBAC 体系对齐）
    ROLE_ALIASES = {
        "销售代表": "sales_rep",
        "sales_rep": "sales_rep",
        "区域经理": "regional_manager",
        "regional_manager": "regional_manager",
        "总监": "sales_director",
        "sales_director": "sales_director",
        "合规官": "compliance_officer",
        "compliance_officer": "compliance_officer",
        "培训经理": "training_manager",
        "training_manager": "training_manager",
    }

    # 场景-角色-权限矩阵（医药销售适配）
    # 结构：{scenario: {role_key: level}}
    PERMISSION_MATRIX = {
        "visit_plan": {
            "sales_rep": "L2_suggest",
            "regional_manager": "L3_assist",
            "sales_director": "L4_automate",
        },
        "training_enrollment": {
            "sales_rep": "L4_automate",
            "regional_manager": "L4_automate",
            "training_manager": "L4_automate",
        },
        "data_export": {
            "sales_rep": "L1_observe",
            "regional_manager": "L2_suggest",
            "sales_director": "L3_assist",
        },
        "compliance_check": {
            "sales_rep": "L1_observe",
            "regional_manager": "L1_observe",
            "compliance_officer": "L4_automate",
        },
    }

    # 高风险操作自动插入审批（无论权限级别，命中即触发审批流）
    AUTO_APPROVAL_TRIGGERS = {
        "data_export",
        "bulk_delete",
        "promise_sales_target",
        "auto_dispatch_alert",
        "kpi_compute",
        "compliance_violation_report",
    }

    # 操作类型 -> 所需最低权限级别
    _ACTION_LEVEL = {
        "read": "L1_observe",
        "query": "L1_observe",
        "observe": "L1_observe",
        "suggest": "L2_suggest",
        "recommend": "L2_suggest",
        "assist": "L3_assist",
        "execute": "L3_assist",
        "automate": "L4_automate",
        "auto_execute": "L4_automate",
    }

    def _normalize_role(self, role: str) -> str:
        """归一化角色名（中文别名 -> 英文 key）"""
        if not role:
            return ""
        return self.ROLE_ALIASES.get(role, role)

    def get_permission(self, scenario: str, role: str) -> str:
        """获取指定场景+角色的权限级别

        未配置的场景/角色默认返回最低权限 L1_observe（最小权限原则）
        """
        scenario = scenario or ""
        role_key = self._normalize_role(role)
        scenario_matrix = self.PERMISSION_MATRIX.get(scenario, {})
        return scenario_matrix.get(role_key, "L1_observe")

    def check_action(self, scenario: str, role: str, action_type: str) -> dict:
        """检查某个操作是否被允许

        Args:
            scenario: 业务场景（如 visit_plan）
            role: 用户角色（中文或英文 key 均可）
            action_type: 操作类型（read/suggest/assist/automate 等）

        Returns:
            {allowed, level, needs_approval}
        """
        level = self.get_permission(scenario, role)
        # 未知操作类型默认按 L2 建议（AI 典型行为）要求
        required = self._ACTION_LEVEL.get(action_type, "L2_suggest")
        allowed = self._LEVEL_RANK.get(level, 1) >= self._LEVEL_RANK.get(required, 2)

        # 需要审批的条件：
        # 1. 操作命中自动审批触发器
        # 2. 或操作所需级别 >= L3（辅助执行需人工确认）
        needs_approval = (
            action_type in self.AUTO_APPROVAL_TRIGGERS
            or self._LEVEL_RANK.get(required, 2) >= 3
        )

        return {
            "allowed": allowed,
            "level": level,
            "needs_approval": needs_approval,
        }


class SafetyValvesEngine:
    """安全阀引擎 - 合规检测 + 权限分级检查"""

    # 医药合规规则
    COMPLIANCE_RULES = {
        "forbidden_words": [
            "统方",
            "回扣",
            "礼品礼金",
            "处方统计",
            "商业贿赂",
        ],
        "forbidden_actions": [
            "promise_sales_target",
            "count_prescriptions",
            "offer_kickback",
        ],
    }

    def __init__(self, permission_matrix: Optional[AIPermissionMatrix] = None):
        self.permissions = permission_matrix or AIPermissionMatrix()

    # ──────────────────────────────────────────────
    # 合规检测
    # ──────────────────────────────────────────────

    def _check_compliance(self, action: Any, context: Any) -> list[str]:
        """执行合规检测，返回违规描述列表"""
        violations: list[str] = []

        # 汇总待检测文本
        text_parts: list[str] = []
        if isinstance(action, str):
            text_parts.append(action)
        elif isinstance(action, dict):
            for k in ("name", "type", "text", "content", "description"):
                v = action.get(k)
                if isinstance(v, str):
                    text_parts.append(v)
        if isinstance(context, dict):
            for k in ("text", "content", "query", "message", "prompt"):
                v = context.get(k)
                if isinstance(v, str):
                    text_parts.append(v)
        elif isinstance(context, str):
            text_parts.append(context)

        combined_text = " ".join(text_parts)

        # 禁止词检测
        for word in self.COMPLIANCE_RULES["forbidden_words"]:
            if word in combined_text:
                violations.append(f"命中禁止词：{word}")

        # 禁止行为检测
        action_name = ""
        if isinstance(action, str):
            action_name = action
        elif isinstance(action, dict):
            action_name = action.get("name") or action.get("type") or ""

        for forbidden in self.COMPLIANCE_RULES["forbidden_actions"]:
            if forbidden == action_name:
                violations.append(f"命中禁止行为：{forbidden}")

        return violations

    # ──────────────────────────────────────────────
    # 主入口
    # ──────────────────────────────────────────────

    def check(self, action: Any, context: Any = None,
              user_role: Optional[str] = None,
              scenario: Optional[str] = None) -> dict:
        """安全阀检查 - 合规 + 权限

        Args:
            action: 操作（字符串操作名 或 dict 含 name/type/text）
            context: 上下文（dict，可能含待检测文本）
            user_role: 用户角色
            scenario: 业务场景

        Returns:
            {
                passed: bool,
                violations: [str, ...],
                risk_level: "low" | "medium" | "high",
                permission_level: str,
                needs_approval: bool,
            }
        """
        context = context or {}
        violations: list[str] = []

        # 1. 合规检测（禁止词/禁止行为）
        violations.extend(self._check_compliance(action, context))

        # 2. 权限分级检查
        action_type = ""
        if isinstance(action, str):
            action_type = action
        elif isinstance(action, dict):
            action_type = action.get("type") or action.get("name") or ""

        permission_level = "L1_observe"
        needs_approval = False
        permission_blocked = False

        if scenario and user_role:
            perm_result = self.permissions.check_action(scenario, user_role, action_type)
            permission_level = perm_result["level"]
            needs_approval = perm_result["needs_approval"]
            if not perm_result["allowed"]:
                permission_blocked = True
                violations.append(
                    f"权限不足：角色 {user_role} 在场景 {scenario} 下权限为 "
                    f"{perm_result['level']}，不满足该操作要求"
                )

        # 3. 风险分级
        has_compliance_violation = any(
            "禁止词" in v or "禁止行为" in v for v in violations
        )
        if has_compliance_violation:
            risk_level = "high"
        elif permission_blocked:
            risk_level = "high"
        elif needs_approval:
            risk_level = "medium"
        else:
            risk_level = "low"

        # passed：无任何违规且权限未被阻断
        passed = len(violations) == 0

        return {
            "passed": passed,
            "violations": violations,
            "risk_level": risk_level,
            "permission_level": permission_level,
            "needs_approval": needs_approval,
        }


# 全局单例
safety_valves_engine = SafetyValvesEngine()


__all__ = [
    "AIPermissionMatrix",
    "SafetyValvesEngine",
    "safety_valves_engine",
]
