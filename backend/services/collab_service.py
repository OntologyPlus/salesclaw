"""协同办公服务层

提供任务管理、审批流、公告能力。
支持与销售执行、培训域联动（如拜访计划审批、培训任务关联）。
"""
import json
import logging
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

logger = logging.getLogger(__name__)

from database import (
    Task, Approval, Announcement,
    User, VisitPlan, Course,
)


# ──────────────────────────────────────────────
# 协同办公总览
# ──────────────────────────────────────────────

def get_overview(db: Session, tenant_id: str, user_id: int) -> dict:
    """协同办公总览：任务/审批/公告汇总"""
    now = datetime.utcnow()
    today = now.date()

    # 任务统计
    total_tasks = db.query(Task).filter(
        Task.tenant_id == tenant_id, Task.is_deleted == 0, Task.assignee_id == user_id,
    ).count()
    pending_tasks = db.query(Task).filter(
        Task.tenant_id == tenant_id, Task.is_deleted == 0, Task.assignee_id == user_id,
        Task.status.in_(["pending", "in_progress"]),
    ).count()
    overdue_tasks = db.query(Task).filter(
        Task.tenant_id == tenant_id, Task.is_deleted == 0, Task.assignee_id == user_id,
        Task.status.in_(["pending", "in_progress"]),
        Task.due_date < today,
    ).count()
    completed_tasks = db.query(Task).filter(
        Task.tenant_id == tenant_id, Task.is_deleted == 0, Task.assignee_id == user_id,
        Task.status == "completed",
    ).count()

    # 审批统计
    pending_approvals = db.query(Approval).filter(
        Approval.tenant_id == tenant_id, Approval.is_deleted == 0,
        Approval.applicant_id == user_id, Approval.status == "pending",
    ).count()

    # 公告统计
    announcements = db.query(Announcement).filter(
        Announcement.tenant_id == tenant_id, Announcement.is_deleted == 0,
    ).order_by(Announcement.is_pinned.desc(), Announcement.published_at.desc()).limit(5).all()

    # 学术推广活动统计（三流看板入口）
    academic_activity_count = 0
    academic_pending_approval = 0
    academic_ongoing = 0
    academic_archived = 0
    try:
        from database import AcademicActivity
        aq = db.query(AcademicActivity).filter(
            AcademicActivity.tenant_id == tenant_id,
            AcademicActivity.is_deleted == 0,
        )
        academic_activity_count = aq.count()
        academic_pending_approval = aq.filter(
            AcademicActivity.status.in_(["draft", "pending_approval"]),
        ).count()
        academic_ongoing = aq.filter(
            AcademicActivity.status.in_(["approved", "ongoing"]),
        ).count()
        academic_archived = aq.filter(
            AcademicActivity.status.in_(["completed", "archived"]),
        ).count()
    except Exception:
        pass

    return {
        "total_tasks": total_tasks,
        "pending_tasks": pending_tasks,
        "overdue_tasks": overdue_tasks,
        "completed_tasks": completed_tasks,
        "pending_approvals": pending_approvals,
        "announcements_count": db.query(Announcement).filter(
            Announcement.tenant_id == tenant_id, Announcement.is_deleted == 0,
        ).count(),
        "recent_announcements": [_announcement_to_dict(a) for a in announcements],
        "academic_activity_count": academic_activity_count,
        "academic_pending_approval": academic_pending_approval,
        "academic_ongoing": academic_ongoing,
        "academic_archived": academic_archived,
    }


# ──────────────────────────────────────────────
# 任务管理
# ──────────────────────────────────────────────

def get_tasks(db: Session, tenant_id: str, user_id: int, status: str = None,
              task_type: str = None, page: int = 1, page_size: int = 20) -> dict:
    """获取任务列表"""
    q = db.query(Task).filter(
        Task.tenant_id == tenant_id, Task.is_deleted == 0, Task.assignee_id == user_id,
    )
    if status and status != "all":
        q = q.filter(Task.status == status)
    if task_type and task_type != "all":
        q = q.filter(Task.task_type == task_type)
    total = q.count()
    tasks = q.order_by(Task.due_date.asc().nullslast(), Task.priority.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_task_to_dict(t) for t in tasks],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_task(db: Session, tenant_id: str, task_id: int) -> dict:
    """获取任务详情"""
    t = db.query(Task).filter(
        Task.tenant_id == tenant_id, Task.is_deleted == 0, Task.id == task_id,
    ).first()
    if not t:
        return None
    return _task_to_dict(t)


def create_task(db: Session, tenant_id: str, creator_id: int, data: dict) -> dict:
    """创建任务

    F3 增强（借鉴企业级诊断体系 §9.1）：
    - 创建前调用 enforce_task_quota 校验配额
    - 计算 dedup_key 并查重：若已存在同 dedup_key 的未完成任务，
      将新任务合并到主任务的 merged_from（追加 id）并返回主任务
    - 超配额时写入 TaskQuotaDrop 并返回 drop 信息
    """
    from core.task_quota import enforce_task_quota, compute_dedup_key

    assignee_id = data.get("assignee_id", creator_id)
    priority = data.get("priority", "medium")
    related_type = data.get("related_type")
    related_id = data.get("related_id")
    task_type = data.get("task_type", "general")
    source_project = data.get("source_project")

    # 1. 配额校验
    quota_ok = enforce_task_quota(db, tenant_id, assignee_id, priority)
    if not quota_ok:
        # 写入 TaskQuotaDrop 记录
        from database import TaskQuotaDrop
        try:
            drop = TaskQuotaDrop(
                tenant_id=tenant_id,
                user_id=assignee_id,
                title=data.get("title", ""),
                task_type=task_type,
                priority=priority,
                related_type=related_type,
                related_id=related_id,
                drop_reason="daily_quota_exceeded",
                drop_strategy="priority_then_due",
                source_project=source_project,
                payload_json=json.dumps(data, ensure_ascii=False, default=str),
            )
            db.add(drop)
            db.commit()
        except Exception:
            db.rollback()
        return {"dropped": True, "reason": "daily_quota_exceeded", "message": "今日任务配额已用尽，已写入丢弃记录"}

    # 2. 计算 dedup_key 并查重
    dedup_key = compute_dedup_key(related_type, related_id, task_type, date.today().isoformat())
    if dedup_key:
        existing = db.query(Task).filter(
            Task.tenant_id == tenant_id,
            Task.is_deleted == 0,
            Task.status.in_(["pending", "in_progress"]),
            Task.dedup_key == dedup_key,
        ).first()
        if existing:
            # 合并：将新任务信息追加到主任务的 merged_from
            merged_from = json.loads(existing.merged_from) if existing.merged_from else []
            merged_from.append({
                "title": data.get("title", ""),
                "priority": priority,
                "due_date": data.get("due_date"),
                "task_type": task_type,
                "source_project": source_project,
                "submitted_at": datetime.utcnow().isoformat(),
            })
            existing.merged_from = json.dumps(merged_from, ensure_ascii=False, default=str)
            # 主任务取最高 priority
            priority_rank = {"high": 3, "medium": 2, "low": 1}
            if priority_rank.get(priority, 2) > priority_rank.get(existing.priority, 2):
                existing.priority = priority
            db.commit()
            db.refresh(existing)
            return _task_to_dict(existing)

    # 3. 正常创建任务
    task = Task(
        tenant_id=tenant_id,
        title=data.get("title", ""),
        description=data.get("description"),
        task_type=task_type,
        status="pending",
        priority=priority,
        assignee_id=assignee_id,
        creator_id=creator_id,
        due_date=_parse_date(data.get("due_date")),
        related_type=related_type,
        related_id=related_id,
        dedup_key=dedup_key,
        source_project=source_project,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return _task_to_dict(task)


def merge_tasks_for_user(db: Session, tenant_id: str, user_id: int) -> dict:
    """F3: 扫描同对象多项目任务并合并（借鉴诊断体系 §9.1）

    遍历用户在途任务，对同一 related_type + related_id 的多条任务合并为一条主任务 + 子任务列表。
    主任务取最高 priority 与最早 due_date。
    """
    tasks = db.query(Task).filter(
        Task.tenant_id == tenant_id,
        Task.is_deleted == 0,
        Task.assignee_id == user_id,
        Task.status.in_(["pending", "in_progress"]),
        Task.related_type.isnot(None),
        Task.related_id.isnot(None),
    ).all()

    # 按 (related_type, related_id) 分组
    groups: dict[tuple, list[Task]] = {}
    for t in tasks:
        key = (t.related_type, t.related_id)
        groups.setdefault(key, []).append(t)

    merged_count = 0
    priority_rank = {"high": 3, "medium": 2, "low": 1}
    for key, group_tasks in groups.items():
        if len(group_tasks) <= 1:
            continue
        # 选主任务：priority 最高 + due_date 最早
        main_task = max(group_tasks, key=lambda t: (
            priority_rank.get(t.priority, 2),
            -((t.due_date - date.today()).days if t.due_date else 9999),
        ))
        sub_tasks = [t for t in group_tasks if t.id != main_task.id]

        # 合并子任务信息到主任务 merged_from
        merged_from = json.loads(main_task.merged_from) if main_task.merged_from else []
        for st in sub_tasks:
            merged_from.append({
                "id": st.id,
                "title": st.title,
                "priority": st.priority,
                "due_date": st.due_date.isoformat() if st.due_date else None,
                "task_type": st.task_type,
                "source_project": st.source_project,
            })
            # 标记子任务为已合并（不删除，便于回溯）
            st.status = "cancelled"
            st.description = (st.description or "") + f"\n[已合并到主任务 #{main_task.id}]"
        main_task.merged_from = json.dumps(merged_from, ensure_ascii=False, default=str)
        merged_count += 1

    if merged_count > 0:
        db.commit()
    return {"tenant_id": tenant_id, "user_id": user_id, "merged_groups": merged_count}


def get_merged_tasks(db: Session, tenant_id: str, user_id: int) -> dict:
    """F3: 返回合并后的任务视图（按对象分组）

    每组含主任务 + 子任务列表。
    """
    tasks = db.query(Task).filter(
        Task.tenant_id == tenant_id,
        Task.is_deleted == 0,
        Task.assignee_id == user_id,
        Task.status.in_(["pending", "in_progress"]),
    ).all()

    # 按对象分组（related_type+related_id 为 None 的归到 misc 组）
    groups: dict[str, list[Task]] = {}
    for t in tasks:
        if t.related_type and t.related_id:
            key = f"{t.related_type}#{t.related_id}"
        else:
            key = f"misc#{t.id}"
        groups.setdefault(key, []).append(t)

    result = []
    for key, group_tasks in groups.items():
        # 主任务取 priority 最高 + merged_from 非空 的（若有），否则取第一个
        main_task = next((t for t in group_tasks if t.merged_from), group_tasks[0])
        sub_tasks = [t for t in group_tasks if t.id != main_task.id]
        result.append({
            "object_key": key,
            "main_task": _task_to_dict(main_task),
            "sub_tasks": [_task_to_dict(t) for t in sub_tasks],
            "total_count": len(group_tasks),
        })

    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "groups": result,
        "total_groups": len(result),
    }


def update_task_status(db: Session, tenant_id: str, task_id: int, status: str) -> dict:
    """更新任务状态"""
    t = db.query(Task).filter(
        Task.tenant_id == tenant_id, Task.is_deleted == 0, Task.id == task_id,
    ).first()
    if not t:
        return None
    t.status = status
    if status == "completed":
        t.completed_at = datetime.utcnow()
    elif status == "in_progress" and not t.completed_at:
        pass
    db.commit()
    db.refresh(t)
    return _task_to_dict(t)


# ──────────────────────────────────────────────
# 审批管理
# ──────────────────────────────────────────────

def get_approvals(db: Session, tenant_id: str, user_id: int, status: str = None,
                  approval_type: str = None, page: int = 1, page_size: int = 20) -> dict:
    """获取审批列表"""
    q = db.query(Approval).filter(
        Approval.tenant_id == tenant_id, Approval.is_deleted == 0,
        Approval.applicant_id == user_id,
    )
    if status and status != "all":
        q = q.filter(Approval.status == status)
    if approval_type and approval_type != "all":
        q = q.filter(Approval.approval_type == approval_type)
    total = q.count()
    approvals = q.order_by(Approval.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_approval_to_dict(a) for a in approvals],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_approval(db: Session, tenant_id: str, approval_id: int) -> dict:
    """获取审批详情"""
    a = db.query(Approval).filter(
        Approval.tenant_id == tenant_id, Approval.is_deleted == 0, Approval.id == approval_id,
    ).first()
    if not a:
        return None
    return _approval_to_dict(a)


def create_approval(db: Session, tenant_id: str, applicant_id: int, data: dict) -> dict:
    """创建审批申请

    F1 增强（借鉴企业级诊断体系 §7.4）：
    - 根据 priority / approval_type 计算 sla_hours
    - 设置 submitted_at = now()（SLA 起算）
    - 发布 approval_submitted 事件
    """
    from config import settings
    priority = data.get("priority", "normal")
    approval_type = data.get("approval_type", "general")
    sla_hours = _compute_sla_hours(priority, approval_type, settings)

    appr = Approval(
        tenant_id=tenant_id,
        title=data.get("title", ""),
        approval_type=approval_type,
        status="pending",
        applicant_id=applicant_id,
        content=data.get("description"),
        related_type=data.get("related_type"),
        related_id=data.get("related_id"),
        submitted_at=datetime.utcnow(),
        sla_hours=sla_hours,
        reminder_count=0,
        escalation_level=0,
        auto_approved=0,
        reject_count=0,
    )
    db.add(appr)
    db.commit()
    db.refresh(appr)

    # 发布 approval_submitted 事件（eventual 一致性）
    try:
        from ai.event_bus import event_bus
        event_bus.publish(
            event_type="approval_submitted",
            payload={
                "approval_id": appr.id,
                "applicant_id": applicant_id,
                "approval_type": approval_type,
                "priority": priority,
                "sla_hours": sla_hours,
                "title": appr.title,
            },
            tenant_id=tenant_id,
            consistency="eventual",
            db=db,
        )
    except Exception as e:
        logger.debug("协同事件发布失败（不影响主流程）: %s", e)

    return _approval_to_dict(appr)


# 别名：submit_approval 等价于 create_approval（保留以匹配计划文档命名）
submit_approval = create_approval


def _compute_sla_hours(priority: str, approval_type: str, settings) -> int:
    """根据优先级与审批类型计算 SLA 时长（小时）

    借鉴诊断体系 §7.4：黑灯 48h / 红灯 7 自然日 / 普通 2 工作日
    """
    if priority == "black" or approval_type == "black_alert":
        return settings.APPROVAL_SLA_BLACK
    if priority == "red" or approval_type in ("red_alert", "compliance_violation"):
        return settings.APPROVAL_SLA_RED
    return settings.APPROVAL_SLA_NORMAL


def review_approval(db: Session, tenant_id: str, approver_id: int, approval_id: int,
                    decision: str, comment: str = None) -> dict:
    """审批：approve / reject

    F1 增强（借鉴企业级诊断体系 §7.4 + §13）：
    - reject 时：reject_count++，submitted_at 重置（打回重计时），status 保持 pending
    - 打回 2 次后：escalation_level++，触发升级
    - approve 时：保持原联动逻辑（拜访计划状态推进等）
    """
    a = db.query(Approval).filter(
        Approval.tenant_id == tenant_id, Approval.is_deleted == 0, Approval.id == approval_id,
    ).first()
    if not a:
        return None

    if decision == "approve":
        a.status = "approved"
        a.approver_id = approver_id
        a.reviewed_at = datetime.utcnow()
        a.review_comment = comment
        a.auto_approved = 0  # 显式审批，标记非默认同意

        # 联动：拜访计划审批通过时更新计划状态
        if a.related_type == "visit_plan" and a.related_id:
            plan = db.query(VisitPlan).filter(
                VisitPlan.id == a.related_id, VisitPlan.tenant_id == tenant_id,
            ).first()
            if plan and plan.status == "pending":
                plan.status = "approved"
                plan.approved_by = approver_id
                plan.approved_at = datetime.utcnow()

    elif decision == "reject":
        # 打回重计时：status 保持 pending，submitted_at 重置，reject_count++
        a.status = "pending"
        a.approver_id = approver_id
        a.reviewed_at = datetime.utcnow()
        a.review_comment = comment
        a.reject_count = (a.reject_count or 0) + 1
        a.submitted_at = datetime.utcnow()  # 重新起算 SLA
        a.reminder_count = 0  # 重置提醒计数

        # 打回 2 次后自动升级
        if a.reject_count >= 2:
            a.escalation_level = (a.escalation_level or 0) + 1
            a.escalated_to = approver_id  # 占位：实际应查上级经理
            try:
                from ai.event_bus import event_bus
                event_bus.publish(
                    event_type="approval_escalated",
                    payload={
                        "approval_id": a.id,
                        "applicant_id": a.applicant_id,
                        "reject_count": a.reject_count,
                        "escalation_level": a.escalation_level,
                        "reason": "rejected_twice",
                    },
                    tenant_id=tenant_id,
                    consistency="eventual",
                    db=db,
                )
            except Exception as e:
                logger.debug("协同事件发布失败（不影响主流程）: %s", e)

    db.commit()
    db.refresh(a)
    return _approval_to_dict(a)


def auto_default_approve(db: Session, tenant_id: str = "default") -> dict:
    """F1: 默认同意机制（每小时调度）

    借鉴诊断体系 §13：仅适用一般改进计划；黑灯/合规/申诉裁决/规则变更必须显式审批。

    流程：
    1. 查询所有 pending 且 (now - submitted_at) > sla_hours 的审批
    2. 排除 DEFAULT_APPROVE_EXCLUDED_TYPES（黑灯/合规/申诉/规则变更）
    3. 标记 status = "approved"，auto_approved = 1
    4. 发布 approval_default_approved 事件
    """
    from config import settings
    now = datetime.utcnow()
    excluded_types = settings.default_approve_excluded_list

    # 查询超期且未排除的审批
    overdue_approvals = db.query(Approval).filter(
        Approval.tenant_id == tenant_id,
        Approval.is_deleted == 0,
        Approval.status == "pending",
        Approval.submitted_at.isnot(None),
        ~Approval.approval_type.in_(excluded_types) if excluded_types else True,
    ).all()

    approved_count = 0
    for a in overdue_approvals:
        sla_seconds = (a.sla_hours or 48) * 3600
        elapsed = (now - (a.submitted_at or a.created_at)).total_seconds()
        if elapsed > sla_seconds:
            a.status = "approved"
            a.auto_approved = 1
            a.reviewed_at = now
            a.review_comment = "默认同意（SLA 超期，非高风险类型）"
            approved_count += 1
            try:
                from ai.event_bus import event_bus
                event_bus.publish(
                    event_type="approval_default_approved",
                    payload={
                        "approval_id": a.id,
                        "applicant_id": a.applicant_id,
                        "approval_type": a.approval_type,
                        "sla_hours": a.sla_hours,
                        "elapsed_hours": int(elapsed // 3600),
                    },
                    tenant_id=tenant_id,
                    consistency="eventual",
                    db=db,
                )
            except Exception as e:
                logger.debug("协同事件发布失败（不影响主流程）: %s", e)

    if approved_count > 0:
        db.commit()
    return {"tenant_id": tenant_id, "auto_approved_count": approved_count}


def check_overdue_approvals(db: Session, tenant_id: str = "default") -> dict:
    """F1: 超期检查与升级（每小时调度）

    借鉴诊断体系 §7.4 + §13：
    - 剩余时间 < 20% → 发送提醒（reminder_count++）
    - 已超期但不在排除列表 → 调用 auto_default_approve
    - 已超期且在排除列表 → escalation_level++，发布 approval_overdue 事件
    - escalation_level 达到 2 → 发布 approval_escalated 事件
    """
    from config import settings
    now = datetime.utcnow()
    threshold = settings.APPROVAL_REMINDER_THRESHOLD
    excluded_types = settings.default_approve_excluded_list

    pending_approvals = db.query(Approval).filter(
        Approval.tenant_id == tenant_id,
        Approval.is_deleted == 0,
        Approval.status == "pending",
        Approval.submitted_at.isnot(None),
    ).all()

    reminded = 0
    overdue_escalated = 0
    fully_escalated = 0

    for a in pending_approvals:
        sla_seconds = (a.sla_hours or 48) * 3600
        elapsed = (now - (a.submitted_at or a.created_at)).total_seconds()
        progress = elapsed / sla_seconds if sla_seconds > 0 else 1.0

        # 1. 剩余 20% 提醒
        if threshold <= progress < 1.0:
            a.reminder_count = (a.reminder_count or 0) + 1
            reminded += 1
            # TODO: 通过 notification_service 推送提醒

        # 2. 已超期
        elif progress >= 1.0:
            is_excluded = a.approval_type in excluded_types if excluded_types else False

            if not is_excluded:
                # 非高风险类型：留给 auto_default_approve 处理
                continue

            # 高风险类型：升级
            a.escalation_level = (a.escalation_level or 0) + 1
            overdue_escalated += 1
            try:
                from ai.event_bus import event_bus
                event_bus.publish(
                    event_type="approval_overdue",
                    payload={
                        "approval_id": a.id,
                        "applicant_id": a.applicant_id,
                        "approval_type": a.approval_type,
                        "sla_hours": a.sla_hours,
                        "elapsed_hours": int(elapsed // 3600),
                        "escalation_level": a.escalation_level,
                    },
                    tenant_id=tenant_id,
                    consistency="eventual",
                    db=db,
                )

                # 升级到 Level 2：发布 escalated 事件
                if a.escalation_level >= 2:
                    fully_escalated += 1
                    event_bus.publish(
                        event_type="approval_escalated",
                        payload={
                            "approval_id": a.id,
                            "applicant_id": a.applicant_id,
                            "approval_type": a.approval_type,
                            "escalation_level": a.escalation_level,
                            "reason": "overdue_high_risk",
                        },
                        tenant_id=tenant_id,
                        consistency="eventual",
                        db=db,
                    )
            except Exception as e:
                logger.debug("协同事件发布失败（不影响主流程）: %s", e)

    if reminded + overdue_escalated > 0:
        db.commit()

    # 处理非高风险类型的默认同意
    auto_result = auto_default_approve(db, tenant_id)

    return {
        "tenant_id": tenant_id,
        "reminded": reminded,
        "overdue_escalated": overdue_escalated,
        "fully_escalated": fully_escalated,
        "auto_approved": auto_result.get("auto_approved_count", 0),
    }


def get_overdue_approvals(db: Session, tenant_id: str, page: int = 1, page_size: int = 20) -> dict:
    """F1: 获取超期审批列表（escalation_level >= 1）"""
    now = datetime.utcnow()
    q = db.query(Approval).filter(
        Approval.tenant_id == tenant_id,
        Approval.is_deleted == 0,
        Approval.status == "pending",
        Approval.submitted_at.isnot(None),
        Approval.escalation_level >= 1,
    )
    total = q.count()
    items = q.order_by(Approval.escalation_level.desc(), Approval.submitted_at.asc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {
        "items": [_approval_to_dict(a) for a in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_escalated_approvals(db: Session, tenant_id: str, page: int = 1, page_size: int = 20) -> dict:
    """F1: 获取已升级审批列表（escalation_level >= 2）"""
    q = db.query(Approval).filter(
        Approval.tenant_id == tenant_id,
        Approval.is_deleted == 0,
        Approval.escalation_level >= 2,
    )
    total = q.count()
    items = q.order_by(Approval.escalation_level.desc(), Approval.submitted_at.asc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {
        "items": [_approval_to_dict(a) for a in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ──────────────────────────────────────────────
# 公告管理
# ──────────────────────────────────────────────

def get_announcements(db: Session, tenant_id: str, ann_type: str = None,
                      page: int = 1, page_size: int = 20) -> dict:
    """获取公告列表"""
    q = db.query(Announcement).filter(
        Announcement.tenant_id == tenant_id, Announcement.is_deleted == 0,
    )
    if ann_type and ann_type != "all":
        q = q.filter(Announcement.ann_type == ann_type)
    total = q.count()
    announcements = q.order_by(
        Announcement.is_pinned.desc(), Announcement.published_at.desc(),
    ).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_announcement_to_dict(a) for a in announcements],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_announcement(db: Session, tenant_id: str, announcement_id: int) -> dict:
    """获取公告详情（增加浏览数）"""
    a = db.query(Announcement).filter(
        Announcement.tenant_id == tenant_id, Announcement.is_deleted == 0, Announcement.id == announcement_id,
    ).first()
    if not a:
        return None
    a.view_count = (a.view_count or 0) + 1
    db.commit()
    db.refresh(a)
    return _announcement_to_dict(a)


# ──────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────

def _parse_date(s):
    if not s:
        return None
    try:
        return date.fromisoformat(s) if isinstance(s, str) else s
    except (ValueError, TypeError):
        return None


def _task_to_dict(t: Task) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "task_type": t.task_type,
        "status": t.status,
        "priority": t.priority,
        "assignee_id": t.assignee_id,
        "creator_id": t.creator_id,
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "related_type": t.related_type,
        "related_id": t.related_id,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        # F3 阀门字段
        "dedup_key": t.dedup_key,
        "merged_from": json.loads(t.merged_from) if t.merged_from else None,
        "source_project": t.source_project,
    }


def _approval_to_dict(a: Approval) -> dict:
    return {
        "id": a.id,
        "title": a.title,
        "approval_type": a.approval_type,
        "status": a.status,
        "applicant_id": a.applicant_id,
        "approver_id": a.approver_id,
        "content": a.content,
        "related_type": a.related_type,
        "related_id": a.related_id,
        "reviewed_at": a.reviewed_at.isoformat() if a.reviewed_at else None,
        "review_comment": a.review_comment,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        # F1 SLA 字段
        "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
        "sla_hours": a.sla_hours,
        "reminder_count": a.reminder_count,
        "escalation_level": a.escalation_level,
        "escalated_to": a.escalated_to,
        "auto_approved": a.auto_approved,
        "reject_count": a.reject_count,
    }


def _announcement_to_dict(a: Announcement) -> dict:
    return {
        "id": a.id,
        "title": a.title,
        "content": a.content,
        "ann_type": a.ann_type,
        "publisher_id": a.publisher_id,
        "published_at": a.published_at.isoformat() if a.published_at else None,
        "is_pinned": a.is_pinned,
        "view_count": a.view_count,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
