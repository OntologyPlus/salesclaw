"""F8: 闭环判定 + 月度双任务复核（借鉴企业级诊断体系 §7.5、§8.4）

闭环判定决策矩阵：
| 量化目标达成率 | 信号消除 | 申诉 | 决策 |
|---|---|---|---|
| = 100% | 是 | 任意 | closed |
| = 100% | 否 | 任意 | partial（信号未消除，部分闭环） |
| 60% ≤ rate < 100% | 任意 | 任意 | partial（剩余滚入下月） |
| < 60% | 任意 | appealed / upheld | unresolved（保留原任务，下月复核） |
| < 60% | 否 | no_appeal | unresolved（升级 + 滚入下月） |

月度双任务机制（每月 12 日 06:00 触发）：
1. 复核任务：扫描上月及更早 status=completed 但 closure_state IS NULL 的任务，
   自动 judge_closure；未闭环任务 priority 升级 + 复制到下月。
2. 当月新诊断任务：保留原逻辑（由 insight_scheduler 调度生成）。
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import and_

from database import (
    Task,
    ClosureReviewCycle,
    BusinessSessionLocal,
)
from core.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 闭环判定
# ──────────────────────────────────────────────

def judge_closure(
    db: Session,
    tenant_id: str,
    task_id: int,
    achieved_metrics: Optional[List[dict]] = None,
    signal_cleared: bool = True,
    appeal_state: Optional[str] = None,
    actor_id: Optional[int] = None,
) -> dict:
    """手动判定任务闭环状态

    Args:
        task_id: 任务 ID
        achieved_metrics: 实际达成指标 [{name, value, source}]
        signal_cleared: 触发信号是否消除（如灯色变化是否已恢复）
        appeal_state: 申诉状态（no_appeal/appealed/upheld/overturned）
        actor_id: 操作人 user_id

    Returns:
        {task_id, closure_state, metrics_summary, message}
    """
    task = db.query(Task).filter(
        Task.tenant_id == tenant_id,
        Task.is_deleted == 0,
        Task.id == task_id,
    ).first()
    if not task:
        raise NotFoundError(f"任务 {task_id} 不存在")

    if appeal_state:
        task.appeal_state = appeal_state

    # 计算达成率
    targets = task.target_metric_json or []
    achieved = achieved_metrics or task.achieved_metric_json or []
    if achieved:
        task.achieved_metric_json = achieved

    if not targets:
        # 无量化目标 → 默认按信号消除判定
        rate = 1.0 if signal_cleared else 0.0
    else:
        target_names = {t.get("name"): t.get("value", 0) for t in targets if isinstance(t, dict)}
        achieved_map = {a.get("name"): a.get("value", 0) for a in achieved if isinstance(a, dict)}
        achieved_count = 0
        for name, target_val in target_names.items():
            actual_val = achieved_map.get(name, 0)
            try:
                if target_val and float(actual_val) >= float(target_val):
                    achieved_count += 1
            except (TypeError, ValueError):
                continue
        rate = achieved_count / len(target_names) if target_names else 1.0

    # 决策矩阵
    current_appeal = task.appeal_state or "no_appeal"
    if rate >= 1.0 and signal_cleared:
        closure_state = "closed"
        message = "全部目标达成 + 信号消除，闭环"
    elif rate >= 1.0 and not signal_cleared:
        closure_state = "partial"
        message = "目标达成但信号未消除，部分闭环"
    elif rate >= 0.6:
        closure_state = "partial"
        message = f"达成率 {rate:.0%}（60%-100%），部分闭环，剩余滚入下月"
    elif current_appeal in ("appealed", "upheld"):
        closure_state = "unresolved"
        message = f"达成率 {rate:.0%}（<60%）且申诉中（{current_appeal}），保留原任务，下月复核"
    else:
        closure_state = "unresolved"
        message = f"达成率 {rate:.0%}（<60%）且未申诉，升级 + 滚入下月"

    task.closure_state = closure_state

    # 闭环事件写入审计日志（复用 compliance_service 的链式 AuditLog）
    try:
        from services.compliance_service import append_compliance_audit_log
        append_compliance_audit_log(
            db, tenant_id,
            actor_id=actor_id or task.assignee_id,
            actor_role="system",
            action=f"task.closure_judged",
            target="task",
            target_id=task.id,
            detail={
                "closure_state": closure_state,
                "achievement_rate": round(rate, 4),
                "signal_cleared": signal_cleared,
                "appeal_state": current_appeal,
                "achieved_metrics": achieved,
            },
            is_compliance_critical=False,
        )
    except Exception as e:
        logger.debug("[closure] 写审计日志失败: %s", e)

    # 触发事件总线
    try:
        from ai.event_bus import publish
        publish("task_closure_judged", {
            "task_id": task.id,
            "closure_state": closure_state,
            "rate": round(rate, 4),
            "tenant_id": tenant_id,
        })
    except Exception as e:
        logger.debug("[closure] 事件发布失败: %s", e)

    db.commit()
    db.refresh(task)

    return {
        "task_id": task.id,
        "closure_state": closure_state,
        "metrics_summary": {
            "target_count": len(targets),
            "achieved_count": int(rate * len(targets)) if targets else (1 if signal_cleared else 0),
            "rate": round(rate, 4),
        },
        "message": message,
    }


# ──────────────────────────────────────────────
# 月度复核批次
# ──────────────────────────────────────────────

def create_monthly_review_cycle(
    db: Session,
    tenant_id: str,
    cycle_month: Optional[str] = None,
    actor_id: int = 0,
) -> "ClosureReviewCycle":
    """创建月度复核批次

    在每月 12 日 06:00 自动触发（由 insight_scheduler 调用）。
    也可由 API 手动触发。

    Args:
        cycle_month: YYYY-MM 格式，默认上月
        actor_id: 触发者 ID（自动触发时为 0）

    Returns:
        ClosureReviewCycle 实例
    """
    today = date.today()
    if cycle_month is None:
        # 默认 = 上月
        first_of_month = today.replace(day=1)
        last_month = first_of_month - timedelta(days=1)
        cycle_month = last_month.strftime("%Y-%m")

    # 幂等：同月已存在则直接返回
    existing = db.query(ClosureReviewCycle).filter(
        ClosureReviewCycle.tenant_id == tenant_id,
        ClosureReviewCycle.is_deleted == 0,
        ClosureReviewCycle.cycle_month == cycle_month,
    ).first()
    if existing:
        logger.info("[closure] 复核批次 %s 已存在，跳过创建", cycle_month)
        return existing

    cycle = ClosureReviewCycle(
        tenant_id=tenant_id,
        cycle_month=cycle_month,
        status="in_progress",
        started_at=datetime.utcnow(),
    )
    db.add(cycle)
    db.flush()

    # 触发事件
    try:
        from ai.event_bus import publish
        publish("closure_cycle_started", {
            "cycle_id": cycle.id, "cycle_month": cycle_month, "tenant_id": tenant_id,
        })
    except Exception as e:
        logger.debug("[closure] 事件发布失败: %s", e)

    db.commit()
    db.refresh(cycle)
    logger.info("[closure] 复核批次已创建 cycle_id=%s month=%s", cycle.id, cycle_month)
    return cycle


def run_review_batch(
    db: Session,
    tenant_id: str,
    cycle_id: int,
    batch_size: int = 50,
) -> dict:
    """批量处理复核子任务：自动判断闭环状态

    扫描截至上月末的所有 status=completed 但 closure_state IS NULL 的任务，
    自动 judge_closure（无实际达成数据时按信号消除 = False 判定为 partial/unresolved）。
    未闭环任务 priority 提升 + 复制到下月。

    Returns:
        {processed, closed, partial, unresolved, promoted}
    """
    cycle = db.query(ClosureReviewCycle).filter(
        ClosureReviewCycle.tenant_id == tenant_id,
        ClosureReviewCycle.is_deleted == 0,
        ClosureReviewCycle.id == cycle_id,
    ).first()
    if not cycle:
        raise NotFoundError(f"复核批次 {cycle_id} 不存在")
    if cycle.status == "completed":
        return {
            "processed": 0, "closed": 0, "partial": 0, "unresolved": 0,
            "promoted": 0, "message": "批次已完成，无需重复处理",
        }

    # 解析 cycle_month 的月末
    try:
        year, month = map(int, cycle.cycle_month.split("-"))
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)
    except (ValueError, AttributeError):
        month_end = date.today() - timedelta(days=1)

    # 查询待复核任务：status=completed 且 closure_state IS NULL 且 completed_at <= month_end
    pending_tasks = db.query(Task).filter(
        Task.tenant_id == tenant_id,
        Task.is_deleted == 0,
        Task.status == "completed",
        Task.closure_state.is_(None),
        Task.completed_at <= datetime.combine(month_end, datetime.max.time()),
    ).limit(batch_size).all()

    processed = closed = partial = unresolved = promoted = 0
    for task in pending_tasks:
        # 自动判定：无实际达成数据，按 signal_cleared=False 判定
        result = judge_closure(
            db, tenant_id, task.id,
            achieved_metrics=task.achieved_metric_json or [],
            signal_cleared=False,
            actor_id=0,
        )
        state = result["closure_state"]
        task.review_cycle_id = cycle.id
        processed += 1

        if state == "closed":
            closed += 1
        elif state == "partial":
            partial += 1
            # 复制到下月
            _promote_to_next_month(db, tenant_id, task, cycle.cycle_month)
            promoted += 1
        else:  # unresolved
            unresolved += 1
            # priority 升级 + 复制到下月
            priority_map = {"low": "medium", "medium": "high", "high": "high"}
            task.priority = priority_map.get(task.priority, "high")
            _promote_to_next_month(db, tenant_id, task, cycle.cycle_month)
            promoted += 1

    # 更新批次统计
    cycle.total_reviewed = processed
    cycle.closed_count = closed
    cycle.partial_count = partial
    cycle.unresolved_count = unresolved
    cycle.promoted_to_next_month = promoted
    cycle.status = "completed"
    cycle.completed_at = datetime.utcnow()
    db.commit()

    # 触发事件
    try:
        from ai.event_bus import publish
        publish("closure_cycle_completed", {
            "cycle_id": cycle.id, "cycle_month": cycle.cycle_month,
            "closed": closed, "partial": partial, "unresolved": unresolved,
            "promoted": promoted, "tenant_id": tenant_id,
        })
    except Exception as e:
        logger.debug("[closure] 事件发布失败: %s", e)

    return {
        "processed": processed,
        "closed": closed,
        "partial": partial,
        "unresolved": unresolved,
        "promoted": promoted,
        "cycle_id": cycle.id,
        "cycle_month": cycle.cycle_month,
    }


def _promote_to_next_month(
    db: Session, tenant_id: str, task: Task, current_cycle_month: str,
) -> "Optional[Task]":
    """将未闭环任务复制到下月（保留原任务，新建复核子任务）"""
    try:
        # 计算下月 due_date
        try:
            year, month = map(int, current_cycle_month.split("-"))
            if month == 12:
                next_month_start = date(year + 1, 1, 1)
            else:
                next_month_start = date(year, month + 1, 1)
            next_due = next_month_start + timedelta(days=14)  # 下月 15 日
        except (ValueError, AttributeError):
            next_due = date.today() + timedelta(days=30)

        new_task = Task(
            tenant_id=tenant_id,
            title=f"[复核] {task.title}",
            description=f"原任务 #{task.id} 闭环未通过，自动滚入下月复核。\n原描述：{task.description or ''}",
            task_type="closure_review",
            status="pending",
            priority=task.priority,
            assignee_id=task.assignee_id,
            creator_id=task.creator_id,
            due_date=next_due,
            related_type=task.related_type,
            related_id=task.related_id,
            source_project=task.source_project or "closure_review",
            target_metric_json=task.target_metric_json,
        )
        db.add(new_task)
        db.flush()

        # 触发事件
        try:
            from ai.event_bus import publish
            publish("task_promoted_to_next_month", {
                "original_task_id": task.id,
                "new_task_id": new_task.id,
                "due_date": next_due.isoformat(),
                "tenant_id": tenant_id,
            })
        except Exception:
            pass

        return new_task
    except Exception as e:
        logger.warning("[closure] 滚入下月失败 task_id=%s: %s", task.id, e)
        return None


def get_cycle_progress(db: Session, tenant_id: str, cycle_id: int) -> dict:
    """查询月度复核批次进度"""
    cycle = db.query(ClosureReviewCycle).filter(
        ClosureReviewCycle.tenant_id == tenant_id,
        ClosureReviewCycle.is_deleted == 0,
        ClosureReviewCycle.id == cycle_id,
    ).first()
    if not cycle:
        raise NotFoundError(f"复核批次 {cycle_id} 不存在")
    total = cycle.total_reviewed or 0
    closed = cycle.closed_count or 0
    return {
        "cycle_id": cycle.id,
        "cycle_month": cycle.cycle_month,
        "status": cycle.status,
        "total_reviewed": total,
        "closed_count": closed,
        "partial_count": cycle.partial_count or 0,
        "unresolved_count": cycle.unresolved_count or 0,
        "promoted_to_next_month": cycle.promoted_to_next_month or 0,
        "completion_rate": round(closed / total, 4) if total > 0 else 0.0,
        "started_at": cycle.started_at.isoformat() if cycle.started_at else None,
        "completed_at": cycle.completed_at.isoformat() if cycle.completed_at else None,
    }


def get_task_closure_detail(db: Session, tenant_id: str, task_id: int) -> dict:
    """查询任务闭环详情"""
    task = db.query(Task).filter(
        Task.tenant_id == tenant_id,
        Task.is_deleted == 0,
        Task.id == task_id,
    ).first()
    if not task:
        raise NotFoundError(f"任务 {task_id} 不存在")

    targets = task.target_metric_json or []
    achieved = task.achieved_metric_json or []

    # 计算达成率
    target_names = {t.get("name"): t.get("value", 0) for t in targets if isinstance(t, dict)}
    achieved_map = {a.get("name"): a.get("value", 0) for a in achieved if isinstance(a, dict)}
    achieved_count = 0
    for name, target_val in target_names.items():
        actual_val = achieved_map.get(name, 0)
        try:
            if target_val and float(actual_val) >= float(target_val):
                achieved_count += 1
        except (TypeError, ValueError):
            continue
    rate = achieved_count / len(target_names) if target_names else None

    return {
        "task_id": task.id,
        "title": task.title,
        "status": task.status,
        "closure_state": task.closure_state,
        "appeal_state": task.appeal_state,
        "review_cycle_id": task.review_cycle_id,
        "target_metrics": targets,
        "achieved_metrics": achieved,
        "achievement_rate": round(rate, 4) if rate is not None else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


def set_task_target_metrics(
    db: Session, tenant_id: str, task_id: int,
    target_metrics: List[dict], actor_id: Optional[int] = None,
) -> dict:
    """设置任务量化目标（用于闭环判定）"""
    task = db.query(Task).filter(
        Task.tenant_id == tenant_id,
        Task.is_deleted == 0,
        Task.id == task_id,
    ).first()
    if not task:
        raise NotFoundError(f"任务 {task_id} 不存在")
    if not isinstance(target_metrics, list):
        raise ValidationError("target_metrics 必须是数组")
    for m in target_metrics:
        if not isinstance(m, dict) or "name" not in m or "value" not in m:
            raise ValidationError("每个 target_metric 必须包含 name 和 value 字段")
    task.target_metric_json = target_metrics
    db.commit()
    db.refresh(task)
    return {
        "task_id": task.id,
        "target_metrics": task.target_metric_json,
    }


__all__ = [
    "judge_closure",
    "create_monthly_review_cycle",
    "run_review_batch",
    "get_cycle_progress",
    "get_task_closure_detail",
    "set_task_target_metrics",
]
