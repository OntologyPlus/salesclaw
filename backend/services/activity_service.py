"""培训活动服务层

实现培训活动编排（创建/发布/结束/下架）+ 场景关联 + 状态可编辑矩阵。    
"""
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.exceptions import NotFoundError, ValidationError, DataConflictError
from core.pagination import PageParams, paginate
from database import (
    TrainingActivity, ActivityScenarioRel, PracticeScenario, PracticeSession,
)

logger = logging.getLogger(__name__)

# 状态常量
STATUS_DRAFT = "draft"
STATUS_ONGOING = "ongoing"
STATUS_ENDED = "ended"
STATUS_OFF_SHELF = "off_shelf"

# 状态可编辑字段矩阵
_EDITABLE_FIELDS = {
    STATUS_DRAFT: None,  # None = 全部可改
    STATUS_ONGOING: {"period_end", "visible_scope", "open_practice", "open_train"},
    STATUS_ENDED: set(),
    STATUS_OFF_SHELF: set(),
}


# ──────────────────────────────────────────────
# 序列化
# ──────────────────────────────────────────────

def _fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


def _serialize_activity(a: TrainingActivity, scenario_count: int = 0) -> dict:
    return {
        "id": a.id,
        "title": a.title,
        "description": a.description,
        "status": a.status,
        "domain": a.domain,
        "product_id": a.product_id,
        "period_start": str(a.period_start) if a.period_start else None,
        "period_end": str(a.period_end) if a.period_end else None,
        "visible_scope": a.visible_scope or {},
        "open_practice": a.open_practice,
        "open_train": a.open_train,
        "pass_score": a.pass_score,
        "created_by": a.created_by,
        "published_at": _fmt(a.published_at),
        "off_shelf_at": _fmt(a.off_shelf_at),
        "scenario_count": scenario_count,
        "created_at": _fmt(a.created_at),
    }


def _serialize_scenario_rel(rel: ActivityScenarioRel, scenario: PracticeScenario = None) -> dict:
    data = {
        "id": rel.id,
        "activity_id": rel.activity_id,
        "scenario_id": rel.scenario_id,
        "sort_order": rel.sort_order,
    }
    if scenario:
        data["title"] = scenario.title
        data["scenario_type"] = scenario.scenario_type
        data["difficulty"] = scenario.difficulty
    return data


# ──────────────────────────────────────────────
# 活动 CRUD
# ──────────────────────────────────────────────

def create_activity(db: Session, tenant_id: str, data: dict) -> dict:
    if not data.get("title"):
        raise ValidationError("title 不能为空")
    activity = TrainingActivity(
        tenant_id=tenant_id,
        title=data["title"],
        description=data.get("description"),
        status=STATUS_DRAFT,
        domain=data.get("domain"),
        product_id=data.get("product_id"),
        period_start=data.get("period_start"),
        period_end=data.get("period_end"),
        visible_scope=data.get("visible_scope") or {},
        open_practice=data.get("open_practice", 1),
        open_train=data.get("open_train", 1),
        pass_score=data.get("pass_score", 60),
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return _serialize_activity(activity)


def list_activities(db: Session, tenant_id: str, status: str = None,
                    keyword: str = None, page_params: PageParams = None) -> dict:
    q = db.query(TrainingActivity).filter(
        TrainingActivity.tenant_id == tenant_id,
        TrainingActivity.is_deleted == 0,
    )
    if status:
        q = q.filter(TrainingActivity.status == status)
    if keyword:
        q = q.filter(TrainingActivity.title.like(f"%{keyword}%"))
    total = q.count()
    if page_params:
        q = q.order_by(TrainingActivity.id.desc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(TrainingActivity.id.desc())
    activities = q.all()
    items = []
    for a in activities:
        cnt = db.query(func.count(ActivityScenarioRel.id)).filter(
            ActivityScenarioRel.activity_id == a.id,
            ActivityScenarioRel.is_deleted == 0,
        ).scalar() or 0
        items.append(_serialize_activity(a, cnt))
    return paginate(items, total, page_params or PageParams())


def get_activity(db: Session, tenant_id: str, activity_id: int) -> dict:
    activity = db.query(TrainingActivity).filter(
        TrainingActivity.tenant_id == tenant_id,
        TrainingActivity.is_deleted == 0,
        TrainingActivity.id == activity_id,
    ).first()
    if not activity:
        raise NotFoundError("活动不存在")
    cnt = db.query(func.count(ActivityScenarioRel.id)).filter(
        ActivityScenarioRel.activity_id == activity_id,
        ActivityScenarioRel.is_deleted == 0,
    ).scalar() or 0
    return _serialize_activity(activity, cnt)


def update_activity(db: Session, tenant_id: str, activity_id: int, data: dict) -> dict:
    activity = db.query(TrainingActivity).filter(
        TrainingActivity.tenant_id == tenant_id,
        TrainingActivity.is_deleted == 0,
        TrainingActivity.id == activity_id,
    ).first()
    if not activity:
        raise NotFoundError("活动不存在")

    allowed = _EDITABLE_FIELDS.get(activity.status)
    if allowed is not None and len(allowed) == 0:
        raise ValidationError(f"活动状态为 {activity.status}，不可编辑")
    if allowed is not None:
        for key in data:
            if key not in allowed:
                raise ValidationError(f"活动状态为 {activity.status}，字段 {key} 不可编辑")

    for field in ["title", "description", "domain", "product_id", "period_start",
                  "period_end", "visible_scope", "open_practice", "open_train", "pass_score"]:
        if field in data and data[field] is not None:
            setattr(activity, field, data[field])
    db.commit()
    db.refresh(activity)
    return _serialize_activity(activity)


# ──────────────────────────────────────────────
# 状态流转
# ──────────────────────────────────────────────

def publish_activity(db: Session, tenant_id: str, activity_id: int) -> dict:
    activity = db.query(TrainingActivity).filter(
        TrainingActivity.tenant_id == tenant_id,
        TrainingActivity.is_deleted == 0,
        TrainingActivity.id == activity_id,
    ).first()
    if not activity:
        raise NotFoundError("活动不存在")
    if activity.status != STATUS_DRAFT:
        raise ValidationError(f"仅草稿态可发布，当前状态: {activity.status}")
    activity.status = STATUS_ONGOING
    activity.published_at = datetime.utcnow()
    db.commit()
    db.refresh(activity)
    return _serialize_activity(activity)


def end_activity(db: Session, tenant_id: str, activity_id: int) -> dict:
    activity = db.query(TrainingActivity).filter(
        TrainingActivity.tenant_id == tenant_id,
        TrainingActivity.is_deleted == 0,
        TrainingActivity.id == activity_id,
    ).first()
    if not activity:
        raise NotFoundError("活动不存在")
    if activity.status != STATUS_ONGOING:
        raise ValidationError(f"仅进行中可结束，当前状态: {activity.status}")
    activity.status = STATUS_ENDED
    db.commit()
    db.refresh(activity)
    return _serialize_activity(activity)


def off_shelf_activity(db: Session, tenant_id: str, activity_id: int) -> dict:
    activity = db.query(TrainingActivity).filter(
        TrainingActivity.tenant_id == tenant_id,
        TrainingActivity.is_deleted == 0,
        TrainingActivity.id == activity_id,
    ).first()
    if not activity:
        raise NotFoundError("活动不存在")
    if activity.status != STATUS_ENDED:
        raise ValidationError(f"仅已结束可下架，当前状态: {activity.status}")
    activity.status = STATUS_OFF_SHELF
    activity.off_shelf_at = datetime.utcnow()
    db.commit()
    db.refresh(activity)
    return _serialize_activity(activity)


# ──────────────────────────────────────────────
# 场景关联
# ──────────────────────────────────────────────

def add_scenarios(db: Session, tenant_id: str, activity_id: int, scenario_ids: list) -> int:
    activity = db.query(TrainingActivity).filter(
        TrainingActivity.tenant_id == tenant_id,
        TrainingActivity.is_deleted == 0,
        TrainingActivity.id == activity_id,
    ).first()
    if not activity:
        raise NotFoundError("活动不存在")
    added = 0
    for sid in scenario_ids:
        existing = db.query(ActivityScenarioRel).filter(
            ActivityScenarioRel.activity_id == activity_id,
            ActivityScenarioRel.scenario_id == sid,
            ActivityScenarioRel.is_deleted == 0,
        ).first()
        if existing:
            continue
        rel = ActivityScenarioRel(
            tenant_id=tenant_id,
            activity_id=activity_id,
            scenario_id=sid,
        )
        db.add(rel)
        added += 1
    db.commit()
    return added


def remove_scenarios(db: Session, tenant_id: str, activity_id: int, scenario_ids: list) -> int:
    removed = 0
    for sid in scenario_ids:
        rel = db.query(ActivityScenarioRel).filter(
            ActivityScenarioRel.tenant_id == tenant_id,
            ActivityScenarioRel.is_deleted == 0,
            ActivityScenarioRel.activity_id == activity_id,
            ActivityScenarioRel.scenario_id == sid,
        ).first()
        if rel:
            rel.is_deleted = 1
            rel.deleted_at = datetime.utcnow()
            removed += 1
    db.commit()
    return removed


def list_scenarios(db: Session, tenant_id: str, activity_id: int) -> list:
    rels = db.query(ActivityScenarioRel).filter(
        ActivityScenarioRel.tenant_id == tenant_id,
        ActivityScenarioRel.is_deleted == 0,
        ActivityScenarioRel.activity_id == activity_id,
    ).order_by(ActivityScenarioRel.sort_order.asc()).all()
    result = []
    for rel in rels:
        scenario = db.query(PracticeScenario).filter(
            PracticeScenario.id == rel.scenario_id,
            PracticeScenario.is_deleted == 0,
        ).first()
        result.append(_serialize_scenario_rel(rel, scenario))
    return result
