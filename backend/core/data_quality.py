"""F6: 数据质量门禁 + 三档降级（借鉴企业级诊断体系 §5.5）

决策矩阵：
| 完整度 | 数据延迟 | 决策           | 动作                                 |
|--------|----------|----------------|--------------------------------------|
| ≥ 阈值 | ≤ 3 天   | pass           | 正常生成洞察                         |
| ≥ 阈值 | 3-7 天   | delay          | 生成洞察但标记 source="delayed"      |
| ≥ 阈值 | > 7 天   | partial_cancel | 仅生成低优先级洞察，confidence=0.3   |
| < 阈值 | 任意     | cancel         | 停止生成 + 派发补数工单 + 返回低置信 |

域完整度计算：
- sales:     visit_records + visit_plans + behavior_point_records 三表当月记录数 / 历史平均
- training:  practice_sessions + exam_records + courses 三表当月记录数
- decision:  decision_recommendations + ability_profiles 当月更新数
- compliance: compliance_commitments + audit_logs + pharma_rep_profiles 当月数
"""
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 域完整度计算
# ──────────────────────────────────────────────

def _count_monthly(db: Session, model, tenant_id: str, target_month: date) -> int:
    """统计某模型在某租户当月的记录数"""
    try:
        month_start = target_month.replace(day=1)
        if target_month.month == 12:
            month_end = date(target_month.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(target_month.year, target_month.month + 1, 1) - timedelta(days=1)
        return db.query(func.count(model.id)).filter(
            model.tenant_id == tenant_id,
            model.is_deleted == 0,
            model.created_at >= datetime.combine(month_start, datetime.min.time()),
            model.created_at <= datetime.combine(month_end, datetime.max.time()),
        ).scalar() or 0
    except Exception as e:
        logger.debug("[data_quality] 统计 %s 失败: %s", model.__name__, e)
        return 0


def _avg_history_3months(db: Session, model, tenant_id: str, target_month: date) -> float:
    """计算过去 3 个月平均记录数（基准）"""
    try:
        total = 0
        for i in range(1, 4):
            ref_month = (target_month.replace(day=1) - timedelta(days=30 * i))
            total += _count_monthly(db, model, tenant_id, ref_month)
        return max(total / 3.0, 1.0)  # 至少 1，避免除零
    except Exception as e:
        logger.debug("[data_quality] 基准计算失败: %s", e)
        return 1.0


def compute_completeness(db: Session, tenant_id: str, domain: str,
                          snapshot_date: Optional[date] = None) -> float:
    """计算指定域的完整度（0.0-1.0）

    Args:
        db: 数据库会话
        tenant_id: 租户 ID
        domain: 域名（sales/training/decision/compliance）
        snapshot_date: 快照日期（默认今天）

    Returns:
        完整度 0.0-1.0（1.0 = 数据充分）
    """
    snapshot_date = snapshot_date or date.today()
    try:
        if domain == "sales":
            from database import VisitRecord, VisitPlan, BehaviorPointRecord
            cur = _count_monthly(db, VisitRecord, tenant_id, snapshot_date)
            base = _avg_history_3months(db, VisitRecord, tenant_id, snapshot_date)
            # 多表加权：拜访记录 0.5 + 拜访计划 0.3 + 行为积分 0.2
            ratio_vr = min(cur / base, 1.0) if base > 0 else 0.0
            cur_vp = _count_monthly(db, VisitPlan, tenant_id, snapshot_date)
            base_vp = _avg_history_3months(db, VisitPlan, tenant_id, snapshot_date)
            ratio_vp = min(cur_vp / base_vp, 1.0) if base_vp > 0 else 0.0
            cur_bp = _count_monthly(db, BehaviorPointRecord, tenant_id, snapshot_date)
            base_bp = _avg_history_3months(db, BehaviorPointRecord, tenant_id, snapshot_date)
            ratio_bp = min(cur_bp / base_bp, 1.0) if base_bp > 0 else 0.0
            return ratio_vr * 0.5 + ratio_vp * 0.3 + ratio_bp * 0.2

        if domain == "training":
            from database import PracticeSession, ExamRecord, Course
            cur_ps = _count_monthly(db, PracticeSession, tenant_id, snapshot_date)
            base_ps = _avg_history_3months(db, PracticeSession, tenant_id, snapshot_date)
            ratio_ps = min(cur_ps / base_ps, 1.0) if base_ps > 0 else 0.0
            cur_er = _count_monthly(db, ExamRecord, tenant_id, snapshot_date)
            base_er = _avg_history_3months(db, ExamRecord, tenant_id, snapshot_date)
            ratio_er = min(cur_er / base_er, 1.0) if base_er > 0 else 0.0
            return ratio_ps * 0.6 + ratio_er * 0.4

        if domain == "decision":
            from database import DecisionRecommendation, AbilityProfile
            cur_dr = _count_monthly(db, DecisionRecommendation, tenant_id, snapshot_date)
            base_dr = _avg_history_3months(db, DecisionRecommendation, tenant_id, snapshot_date)
            ratio_dr = min(cur_dr / base_dr, 1.0) if base_dr > 0 else 0.0
            cur_ap = _count_monthly(db, AbilityProfile, tenant_id, snapshot_date)
            base_ap = _avg_history_3months(db, AbilityProfile, tenant_id, snapshot_date)
            ratio_ap = min(cur_ap / base_ap, 1.0) if base_ap > 0 else 0.0
            return ratio_dr * 0.5 + ratio_ap * 0.5

        if domain == "compliance":
            from database import AuditLog, PharmaRepProfile
            cur_al = _count_monthly(db, AuditLog, tenant_id, snapshot_date)
            base_al = _avg_history_3months(db, AuditLog, tenant_id, snapshot_date)
            ratio_al = min(cur_al / base_al, 1.0) if base_al > 0 else 0.0
            cur_pr = _count_monthly(db, PharmaRepProfile, tenant_id, snapshot_date)
            base_pr = _avg_history_3months(db, PharmaRepProfile, tenant_id, snapshot_date)
            ratio_pr = min(cur_pr / base_pr, 1.0) if base_pr > 0 else 0.0
            return ratio_al * 0.6 + ratio_pr * 0.4

        # 未识别的域：默认完整度 1.0（不阻断）
        logger.debug("[data_quality] 未识别的域 %s，默认完整度 1.0", domain)
        return 1.0
    except Exception as e:
        logger.warning("[data_quality] 完整度计算异常 domain=%s: %s", domain, e)
        return 1.0  # 异常时降级为允许（避免阻断业务）


# ──────────────────────────────────────────────
# 三档降级决策
# ──────────────────────────────────────────────

def _calculate_data_delay_days(db: Session, tenant_id: str, domain: str,
                                snapshot_date: date) -> int:
    """计算数据延迟天数（最近一条记录距今天数）"""
    try:
        if domain == "sales":
            from database import VisitRecord
            latest = db.query(VisitRecord.created_at).filter(
                VisitRecord.tenant_id == tenant_id,
                VisitRecord.is_deleted == 0,
            ).order_by(VisitRecord.created_at.desc()).first()
        elif domain == "training":
            from database import PracticeSession
            latest = db.query(PracticeSession.created_at).filter(
                PracticeSession.tenant_id == tenant_id,
                PracticeSession.is_deleted == 0,
            ).order_by(PracticeSession.created_at.desc()).first()
        elif domain == "decision":
            from database import DecisionRecommendation
            latest = db.query(DecisionRecommendation.created_at).filter(
                DecisionRecommendation.tenant_id == tenant_id,
                DecisionRecommendation.is_deleted == 0,
            ).order_by(DecisionRecommendation.created_at.desc()).first()
        elif domain == "compliance":
            from database import AuditLog
            latest = db.query(AuditLog.ts).filter(
                AuditLog.tenant_id == tenant_id,
                AuditLog.is_deleted == 0,
            ).order_by(AuditLog.ts.desc()).first()
            if latest and latest[0]:
                return max((snapshot_date - latest[0].date()).days, 0)
            return 0
        else:
            return 0

        if latest and latest[0]:
            return max((snapshot_date - latest[0].date()).days, 0)
        return 0
    except Exception as e:
        logger.debug("[data_quality] 延迟计算失败: %s", e)
        return 0


def _dispatch_repair_task(db: Session, tenant_id: str, domain: str,
                          completeness: float, snapshot_date: date) -> Optional[int]:
    """派发补数工单（复用 Task 表，task_type="data_repair"）"""
    try:
        from database import Task
        title = f"[数据断点] {domain} 域完整度 {completeness:.2%} 低于阈值"
        # 去重：避免同月重复派发
        existing = db.query(Task).filter(
            Task.tenant_id == tenant_id,
            Task.is_deleted == 0,
            Task.task_type == "data_repair",
            Task.related_type == "data_quality",
            Task.related_id.is_(None),
            Task.title == title,
        ).first()
        if existing:
            return existing.id

        task = Task(
            tenant_id=tenant_id,
            title=title,
            description=f"快照日期 {snapshot_date.isoformat()}：{domain} 域数据完整度 {completeness:.2%}，"
                        f"低于阈值，需补数后才能生成正式 AI 洞察。",
            task_type="data_repair",
            status="pending",
            priority="high",
            assignee_id=1,  # 默认分配给 admin
            creator_id=1,
            due_date=snapshot_date + timedelta(days=3),
            related_type="data_quality",
            source_project=domain,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        logger.info("[data_quality] 已派发补数工单 task_id=%s (domain=%s)",
                    task.id, domain)
        return task.id
    except Exception as e:
        logger.warning("[data_quality] 派发补数工单失败: %s", e)
        db.rollback()
        return None


def check_quality_gate(db: Session, tenant_id: str, domain: str,
                        snapshot_date: Optional[date] = None) -> Dict[str, Any]:
    """执行数据质量门禁检查

    Returns:
        {
            "domain": str,
            "completeness": float,
            "threshold": float,
            "delay_days": int,
            "decision": "pass" | "delay" | "partial_cancel" | "cancel",
            "gate_id": int | None,
            "repair_task_id": int | None,
            "message": str,
        }
    """
    from database import DataQualityGate
    snapshot_date = snapshot_date or date.today()

    # 查询门禁配置（优先当前租户，fallback 到 default）
    gate = db.query(DataQualityGate).filter(
        DataQualityGate.tenant_id == tenant_id,
        DataQualityGate.is_deleted == 0,
        DataQualityGate.domain == domain,
    ).first()
    if gate is None:
        gate = db.query(DataQualityGate).filter(
            DataQualityGate.tenant_id == "default",
            DataQualityGate.is_deleted == 0,
            DataQualityGate.domain == domain,
        ).first()

    if gate is None or gate.enabled == 0:
        # 无配置或禁用 → 默认放行
        return {
            "domain": domain,
            "completeness": 1.0,
            "threshold": 0.60,
            "delay_days": 0,
            "decision": "pass",
            "gate_id": None,
            "repair_task_id": None,
            "message": "门禁未配置或已禁用，默认放行",
        }

    # 计算完整度
    completeness = compute_completeness(db, tenant_id, domain, snapshot_date)
    delay_days = _calculate_data_delay_days(db, tenant_id, domain, snapshot_date)

    # 三档降级决策
    threshold = gate.completeness_threshold
    if completeness < threshold:
        decision = "cancel"
        message = f"完整度 {completeness:.2%} < 阈值 {threshold:.2%}，判定数据断点"
        repair_task_id = _dispatch_repair_task(db, tenant_id, domain, completeness, snapshot_date)
    elif delay_days > gate.timeliness_cancel_days:
        decision = "partial_cancel"
        message = f"数据延迟 {delay_days} 天 > {gate.timeliness_cancel_days} 天，部分取消"
        repair_task_id = None
    elif delay_days > gate.timeliness_delay_days:
        decision = "delay"
        message = f"数据延迟 {delay_days} 天 > {gate.timeliness_delay_days} 天，延期发布"
        repair_task_id = None
    else:
        decision = "pass"
        message = f"完整度 {completeness:.2%} ≥ 阈值 {threshold:.2%}，延迟 {delay_days} 天 ≤ {gate.timeliness_delay_days} 天"
        repair_task_id = None

    # 更新门禁状态
    try:
        gate.last_check_at = datetime.utcnow()
        gate.last_completeness = completeness
        gate.last_decision = decision
        db.commit()
    except Exception as e:
        logger.warning("[data_quality] 更新门禁状态失败: %s", e)
        db.rollback()

    return {
        "domain": domain,
        "completeness": round(completeness, 4),
        "threshold": threshold,
        "delay_days": delay_days,
        "decision": decision,
        "gate_id": gate.id,
        "repair_task_id": repair_task_id,
        "message": message,
    }


# ──────────────────────────────────────────────
# CRUD
# ──────────────────────────────────────────────

def get_gate(db: Session, tenant_id: str, domain: str) -> "Optional[DataQualityGate]":
    """查询单域门禁（带 default fallback）"""
    from database import DataQualityGate
    gate = db.query(DataQualityGate).filter(
        DataQualityGate.tenant_id == tenant_id,
        DataQualityGate.is_deleted == 0,
        DataQualityGate.domain == domain,
    ).first()
    if gate is None:
        gate = db.query(DataQualityGate).filter(
            DataQualityGate.tenant_id == "default",
            DataQualityGate.is_deleted == 0,
            DataQualityGate.domain == domain,
        ).first()
    return gate


def list_gates(db: Session, tenant_id: str) -> list:
    """列出所有域门禁（带 default fallback）"""
    from database import DataQualityGate
    # 先查当前租户，再补 default 中未覆盖的域
    gates = db.query(DataQualityGate).filter(
        DataQualityGate.tenant_id == tenant_id,
        DataQualityGate.is_deleted == 0,
    ).all()
    covered = {g.domain for g in gates}
    defaults = db.query(DataQualityGate).filter(
        DataQualityGate.tenant_id == "default",
        DataQualityGate.is_deleted == 0,
    ).all()
    for g in defaults:
        if g.domain not in covered:
            gates.append(g)
    return gates


def update_gate(db: Session, tenant_id: str, domain: str,
                 completeness_threshold: Optional[float] = None,
                 timeliness_delay_days: Optional[int] = None,
                 timeliness_partial_days: Optional[int] = None,
                 timeliness_cancel_days: Optional[int] = None,
                 enabled: Optional[int] = None,
                 user_id: Optional[int] = None) -> "Optional[DataQualityGate]":
    """更新门禁阈值（若当前租户无独立门禁则复制 default 一份再更新）"""
    from database import DataQualityGate
    gate = db.query(DataQualityGate).filter(
        DataQualityGate.tenant_id == tenant_id,
        DataQualityGate.is_deleted == 0,
        DataQualityGate.domain == domain,
    ).first()
    if gate is None:
        # 从 default 复制一份
        default_gate = db.query(DataQualityGate).filter(
            DataQualityGate.tenant_id == "default",
            DataQualityGate.is_deleted == 0,
            DataQualityGate.domain == domain,
        ).first()
        if default_gate is None:
            return None
        gate = DataQualityGate(
            tenant_id=tenant_id,
            domain=domain,
            completeness_threshold=default_gate.completeness_threshold,
            timeliness_delay_days=default_gate.timeliness_delay_days,
            timeliness_partial_days=default_gate.timeliness_partial_days,
            timeliness_cancel_days=default_gate.timeliness_cancel_days,
            enabled=default_gate.enabled,
            updated_by=user_id,
        )
        db.add(gate)
        db.flush()

    if completeness_threshold is not None:
        gate.completeness_threshold = completeness_threshold
    if timeliness_delay_days is not None:
        gate.timeliness_delay_days = timeliness_delay_days
    if timeliness_partial_days is not None:
        gate.timeliness_partial_days = timeliness_partial_days
    if timeliness_cancel_days is not None:
        gate.timeliness_cancel_days = timeliness_cancel_days
    if enabled is not None:
        gate.enabled = enabled
    gate.updated_by = user_id
    db.commit()
    db.refresh(gate)
    return gate


__all__ = [
    "compute_completeness",
    "check_quality_gate",
    "get_gate",
    "list_gates",
    "update_gate",
]
