"""通知中心服务层

规则化自动催促 + 通知发送日志 + 失败导出。
"""
import logging
import csv
import io
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.exceptions import NotFoundError, ValidationError
from core.pagination import PageParams, paginate
from database import (
    NotificationRule, NotificationBatch, NotificationRecipient,
    Announcement, PracticeSession, User,
)

logger = logging.getLogger(__name__)


def _fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


def _serialize_rule(r: NotificationRule) -> dict:
    return {
        "id": r.id,
        "activity_id": r.activity_id,
        "scenario_id": r.scenario_id,
        "rule_name": r.rule_name,
        "deadline": _fmt(r.deadline),
        "windows": r.windows or [],
        "frequency": r.frequency,
        "send_times": r.send_times or [],
        "channel": r.channel,
        "target_user_type": r.target_user_type,
        "enabled": r.enabled,
        "created_at": _fmt(r.created_at),
    }


def _serialize_batch(b: NotificationBatch) -> dict:
    return {
        "id": b.id,
        "rule_id": b.rule_id,
        "trigger_at": _fmt(b.trigger_at),
        "window": b.window,
        "target_count": b.target_count,
        "success_count": b.success_count,
        "failed_count": b.failed_count,
        "message_title": b.message_title,
        "message_body": b.message_body,
    }


def _serialize_recipient(r: NotificationRecipient) -> dict:
    return {
        "id": r.id,
        "batch_id": r.batch_id,
        "learner_id": r.learner_id,
        "status": r.status,
        "reason": r.reason,
        "sent_at": _fmt(r.sent_at),
    }


# ──────────────────────────────────────────────
# 通知渠道
# ──────────────────────────────────────────────

class NotificationChannel:
    async def send(self, db: Session, tenant_id: str, user_id: int,
                   title: str, body: str) -> tuple[bool, str]:
        raise NotImplementedError


class InAppChannel(NotificationChannel):
    """站内通知 — 写入 announcements 表"""
    async def send(self, db: Session, tenant_id: str, user_id: int,
                   title: str, body: str) -> tuple[bool, str]:
        try:
            ann = Announcement(
                tenant_id=tenant_id,
                title=title,
                content=body,
                ann_type="urgent",
                publisher_id=0,
                published_at=datetime.utcnow(),
                is_pinned=0,
            )
            db.add(ann)
            db.commit()
            return True, ""
        except Exception as e:
            db.rollback()
            return False, str(e)


# ──────────────────────────────────────────────
# 规则管理
# ──────────────────────────────────────────────

def create_rule(db: Session, tenant_id: str, data: dict) -> dict:
    if not data.get("rule_name"):
        raise ValidationError("rule_name 不能为空")
    deadline = data.get("deadline")
    if isinstance(deadline, str):
        deadline = datetime.fromisoformat(deadline)
    rule = NotificationRule(
        tenant_id=tenant_id,
        activity_id=data.get("activity_id"),
        scenario_id=data.get("scenario_id"),
        rule_name=data["rule_name"],
        deadline=deadline,
        windows=data.get("windows") or ["D-3", "D-2", "D-1"],
        frequency=data.get("frequency", "daily"),
        send_times=data.get("send_times") or ["10:00", "16:00"],
        channel=data.get("channel", "in_app"),
        target_user_type=data.get("target_user_type", "all"),
        enabled=1,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _serialize_rule(rule)


def list_rules(db: Session, tenant_id: str, activity_id: int = None,
               keyword: str = None, page_params: PageParams = None) -> dict:
    q = db.query(NotificationRule).filter(
        NotificationRule.tenant_id == tenant_id,
        NotificationRule.is_deleted == 0,
    )
    if activity_id:
        q = q.filter(NotificationRule.activity_id == activity_id)
    if keyword:
        q = q.filter(NotificationRule.rule_name.like(f"%{keyword}%"))
    total = q.count()
    if page_params:
        q = q.order_by(NotificationRule.id.desc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(NotificationRule.id.desc())
    rules = q.all()
    items = [_serialize_rule(r) for r in rules]
    return paginate(items, total, page_params or PageParams())


def update_rule_status(db: Session, tenant_id: str, rule_id: int, enabled: int) -> dict:
    rule = db.query(NotificationRule).filter(
        NotificationRule.tenant_id == tenant_id,
        NotificationRule.is_deleted == 0,
        NotificationRule.id == rule_id,
    ).first()
    if not rule:
        raise NotFoundError("规则不存在")
    rule.enabled = enabled
    db.commit()
    db.refresh(rule)
    return _serialize_rule(rule)


# ──────────────────────────────────────────────
# 发送记录
# ──────────────────────────────────────────────

def list_batches(db: Session, tenant_id: str, rule_id: int = None,
                 page_params: PageParams = None) -> dict:
    q = db.query(NotificationBatch).filter(
        NotificationBatch.tenant_id == tenant_id,
        NotificationBatch.is_deleted == 0,
    )
    if rule_id:
        q = q.filter(NotificationBatch.rule_id == rule_id)
    total = q.count()
    if page_params:
        q = q.order_by(NotificationBatch.id.desc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(NotificationBatch.id.desc())
    batches = q.all()
    items = [_serialize_batch(b) for b in batches]
    return paginate(items, total, page_params or PageParams())


def get_batch(db: Session, tenant_id: str, batch_id: int) -> dict:
    batch = db.query(NotificationBatch).filter(
        NotificationBatch.tenant_id == tenant_id,
        NotificationBatch.is_deleted == 0,
        NotificationBatch.id == batch_id,
    ).first()
    if not batch:
        raise NotFoundError("批次不存在")
    recipients = db.query(NotificationRecipient).filter(
        NotificationRecipient.tenant_id == tenant_id,
        NotificationRecipient.is_deleted == 0,
        NotificationRecipient.batch_id == batch_id,
    ).all()
    return {
        **_serialize_batch(batch),
        "recipients": [_serialize_recipient(r) for r in recipients],
    }


# ──────────────────────────────────────────────
# 导出失败名单
# ──────────────────────────────────────────────

def export_failed(db: Session, tenant_id: str, batch_id: int) -> str:
    recipients = db.query(NotificationRecipient).filter(
        NotificationRecipient.tenant_id == tenant_id,
        NotificationRecipient.is_deleted == 0,
        NotificationRecipient.batch_id == batch_id,
        NotificationRecipient.status == "failed",
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["学员ID", "状态", "失败原因", "时间"])
    for r in recipients:
        writer.writerow([r.learner_id, r.status, r.reason or "", _fmt(r.sent_at)])
    return output.getvalue()
