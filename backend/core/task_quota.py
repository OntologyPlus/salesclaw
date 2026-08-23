"""F3: 任务配额管理（借鉴企业级诊断体系 §9.1）

治理机制任务负载阀门：
- 只推送需行动对象
- 同对象多项目异常合并展示
- 设个人每月待办上限和优先级

实现：
- enforce_task_quota: 创建任务前校验配额
- compute_dedup_key: 计算去重键
"""
import hashlib
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from config import settings

logger = logging.getLogger(__name__)


def compute_dedup_key(
    related_type: Optional[str],
    related_id: Optional[int],
    task_type: str,
    date_str: str,
) -> Optional[str]:
    """计算任务去重键

    去重键 = SHA-256(related_type + related_id + task_type + date)
    若 related_type 或 related_id 为 None，返回 None（不参与去重）。
    """
    if not related_type or not related_id:
        return None
    raw = f"{related_type}|{related_id}|{task_type}|{date_str}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def enforce_task_quota(
    db: Session,
    tenant_id: str,
    user_id: int,
    new_task_priority: str = "medium",
) -> bool:
    """创建任务前校验配额

    借鉴诊断体系 §9.1：单用户单日新任务上限 + 单用户在途任务上限。

    规则：
    - 今日已创建任务数 >= MAX_DAILY_TASKS_PER_USER 且新任务 priority != "high"
      → 返回 False（写丢弃记录由调用方负责）
    - 在途任务数 >= MAX_ACTIVE_TASKS_PER_USER 且新任务 priority != "high"
      → 返回 False

    Args:
        db: 数据库 session
        tenant_id: 租户 ID
        user_id: 被分配人 user_id
        new_task_priority: 新任务优先级 high/medium/low

    Returns:
        True=允许创建，False=应丢弃
    """
    from database import Task

    # high 优先级任务不受配额限制
    if new_task_priority == "high":
        return True

    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    # 1. 单日新任务上限
    daily_count = db.query(Task).filter(
        Task.tenant_id == tenant_id,
        Task.is_deleted == 0,
        Task.assignee_id == user_id,
        Task.created_at >= today_start,
        Task.created_at <= today_end,
    ).count()

    if daily_count >= settings.MAX_DAILY_TASKS_PER_USER:
        logger.info(
            f"[task_quota] 用户 {user_id} 今日已创建 {daily_count} 任务，超过上限 {settings.MAX_DAILY_TASKS_PER_USER}"
        )
        return False

    # 2. 在途任务上限
    active_count = db.query(Task).filter(
        Task.tenant_id == tenant_id,
        Task.is_deleted == 0,
        Task.assignee_id == user_id,
        Task.status.in_(["pending", "in_progress"]),
    ).count()

    if active_count >= settings.MAX_ACTIVE_TASKS_PER_USER:
        logger.info(
            f"[task_quota] 用户 {user_id} 在途任务 {active_count}，超过上限 {settings.MAX_ACTIVE_TASKS_PER_USER}"
        )
        return False

    return True


def get_user_task_quota_status(db: Session, tenant_id: str, user_id: int) -> dict:
    """查询用户任务配额使用情况"""
    from database import Task

    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    daily_count = db.query(Task).filter(
        Task.tenant_id == tenant_id,
        Task.is_deleted == 0,
        Task.assignee_id == user_id,
        Task.created_at >= today_start,
        Task.created_at <= today_end,
    ).count()

    active_count = db.query(Task).filter(
        Task.tenant_id == tenant_id,
        Task.is_deleted == 0,
        Task.assignee_id == user_id,
        Task.status.in_(["pending", "in_progress"]),
    ).count()

    return {
        "user_id": user_id,
        "daily_created": daily_count,
        "daily_limit": settings.MAX_DAILY_TASKS_PER_USER,
        "daily_remaining": max(0, settings.MAX_DAILY_TASKS_PER_USER - daily_count),
        "active_tasks": active_count,
        "active_limit": settings.MAX_ACTIVE_TASKS_PER_USER,
        "active_remaining": max(0, settings.MAX_ACTIVE_TASKS_PER_USER - active_count),
        "drop_strategy": settings.TASK_QUOTA_DROP_STRATEGY,
    }


__all__ = [
    "compute_dedup_key",
    "enforce_task_quota",
    "get_user_task_quota_status",
]
