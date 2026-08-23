"""F4: 绩效边界策略管理（借鉴企业级诊断体系 §10.3、附录 A.D.23-24）

原则：绩效联动只记录可控流程行为（逾期、拒不反馈等），
     不因灯色本身自动扣分/PIP/淘汰。

实现：
- enforce_performance_boundary: 行为积分计算前调用，判断是否允许联动
- check_performance_action_boundary: 工具执行前防御性校验，禁止高风险工具
- get_policy / update_policy: 策略 CRUD
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from core.exceptions import AppException
from database import PerformancePolicy

logger = logging.getLogger(__name__)


# 禁止工具黑名单（防御性校验：即使这些工具被注册也不允许调用）
FORBIDDEN_PERFORMANCE_TOOLS = {
    "compute_pip",
    "trigger_elimination",
    "adjust_bonus",
    "deduct_salary",
    "auto_pip",
    "auto_eliminate",
    "auto_deduct_bonus",
}


def enforce_performance_boundary(
    db: Session,
    tenant_id: str,
    action_type: str,
    source_signal: Optional[str] = None,
) -> bool:
    """绩效边界校验（行为积分计算前调用）

    借鉴诊断体系 §10.3："费用异常 = 经营/效率信号，不等于违规认定"
    附录 A.D.23-24："未闭环即影响绩效可能惩罚不可控结果"

    Args:
        db: 数据库 session
        tenant_id: 租户 ID
        action_type: 行为类型（如 visit_overdue / light_color_change / ai_auto_judgment）
        source_signal: 触发来源信号（可选，用于审计）

    Returns:
        True=允许联动绩效，False=禁止联动
    """
    # 优先查当前租户策略；若不存在 fallback 到 default 租户（系统级策略）
    policy = db.query(PerformancePolicy).filter(
        PerformancePolicy.tenant_id == tenant_id,
        PerformancePolicy.is_deleted == 0,
        PerformancePolicy.action_type == action_type,
    ).first()
    if policy is None:
        policy = db.query(PerformancePolicy).filter(
            PerformancePolicy.tenant_id == "default",
            PerformancePolicy.is_deleted == 0,
            PerformancePolicy.action_type == action_type,
        ).first()

    # 未配置策略时默认禁止（保守原则）
    if policy is None:
        logger.info(
            f"[performance_boundary] action_type={action_type} 未配置策略，默认禁止联动"
        )
        _publish_blocked_event(db, tenant_id, action_type, "policy_not_found", source_signal)
        return False

    if policy.allow_link_performance == 1:
        return True

    # 禁止联动：发布 performance_boundary_blocked 事件
    logger.info(
        f"[performance_boundary] action_type={action_type} 禁止联动绩效"
    )
    _publish_blocked_event(db, tenant_id, action_type, "policy_disallow", source_signal)
    return False


def _publish_blocked_event(
    db: Session,
    tenant_id: str,
    action_type: str,
    reason: str,
    source_signal: Optional[str],
) -> None:
    """发布绩效边界阻断事件"""
    try:
        from ai.event_bus import event_bus
        event_bus.publish(
            event_type="performance_boundary_blocked",
            payload={
                "action_type": action_type,
                "reason": reason,
                "source_signal": source_signal,
            },
            tenant_id=tenant_id,
            consistency="eventual",
            db=db,
        )
    except Exception as e:
        logger.warning(f"[performance_boundary] 事件发布失败: {e}")


def check_performance_action_boundary(tool_name: str, user_role: Optional[str] = None) -> None:
    """工具执行前防御性校验

    借鉴诊断体系 §10.3：禁止 AI 自动处置越界（如自动 PIP / 自动扣薪 / 自动淘汰）。
    即使这些工具被注册到 TOOL_REGISTRY，本函数仍作为防御层拦截。

    Args:
        tool_name: 工具名称
        user_role: 调用者角色

    Raises:
        AppException(425): 工具在禁止黑名单中
    """
    if tool_name in FORBIDDEN_PERFORMANCE_TOOLS:
        logger.warning(
            f"[performance_boundary] 工具 {tool_name} 被禁止调用（user_role={user_role}）"
        )
        raise AppException(
            code=425,
            message=f"绩效处置工具 {tool_name} 禁止自动调用，必须人工审批",
        )


def get_policy(db: Session, tenant_id: str, action_type: str) -> Optional[dict]:
    """查询策略详情

    优先返回当前租户策略；若不存在 fallback 到 default 租户
    """
    p = db.query(PerformancePolicy).filter(
        PerformancePolicy.tenant_id == tenant_id,
        PerformancePolicy.is_deleted == 0,
        PerformancePolicy.action_type == action_type,
    ).first()
    if p is None:
        p = db.query(PerformancePolicy).filter(
            PerformancePolicy.tenant_id == "default",
            PerformancePolicy.is_deleted == 0,
            PerformancePolicy.action_type == action_type,
        ).first()
    if not p:
        return None
    return _policy_to_dict(p)


def list_policies(db: Session, tenant_id: str) -> list:
    """列出所有策略

    优先返回当前租户策略；若当前租户无策略，fallback 到 default 租户
    """
    items = db.query(PerformancePolicy).filter(
        PerformancePolicy.tenant_id == tenant_id,
        PerformancePolicy.is_deleted == 0,
    ).order_by(PerformancePolicy.action_type).all()
    if not items:
        items = db.query(PerformancePolicy).filter(
            PerformancePolicy.tenant_id == "default",
            PerformancePolicy.is_deleted == 0,
        ).order_by(PerformancePolicy.action_type).all()
    return [_policy_to_dict(p) for p in items]


def update_policy(
    db: Session,
    tenant_id: str,
    action_type: str,
    allow: int,
    user_id: int,
    description: Optional[str] = None,
) -> Optional[dict]:
    """更新策略

    优先更新当前租户策略；若不存在 fallback 到 default 租户策略。

    Args:
        allow: 0=禁止联动绩效，1=允许
    """
    p = db.query(PerformancePolicy).filter(
        PerformancePolicy.tenant_id == tenant_id,
        PerformancePolicy.is_deleted == 0,
        PerformancePolicy.action_type == action_type,
    ).first()
    if p is None:
        p = db.query(PerformancePolicy).filter(
            PerformancePolicy.tenant_id == "default",
            PerformancePolicy.is_deleted == 0,
            PerformancePolicy.action_type == action_type,
        ).first()
    if not p:
        return None
    p.allow_link_performance = 1 if allow else 0
    p.updated_by = user_id
    if description is not None:
        p.description = description
    db.commit()
    db.refresh(p)
    return _policy_to_dict(p)


def _policy_to_dict(p: PerformancePolicy) -> dict:
    return {
        "id": p.id,
        "action_type": p.action_type,
        "allow_link_performance": p.allow_link_performance,
        "description": p.description,
        "updated_by": p.updated_by,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


__all__ = [
    "FORBIDDEN_PERFORMANCE_TOOLS",
    "enforce_performance_boundary",
    "check_performance_action_boundary",
    "get_policy",
    "list_policies",
    "update_policy",
]
