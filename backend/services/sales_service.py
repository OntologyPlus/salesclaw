"""销售执行域服务层"""
import logging
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_

from core.exceptions import NotFoundError, ValidationError, DataConflictError
from core.pagination import PageParams, paginate
from database import (
    Hospital, Doctor, Product,
    CoverageAssignment, VisitPlan, VisitPlanItem, VisitRecord, VisitFeedback,
    CoverageMatrix, BehaviorPointRule, BehaviorPointRecord,
    InstructionPointRule, InstructionPointRecord, WeeklyReport,
    CourseEnrollment, ExamRecord, PathEnrollment,
)
from services import profile_service

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 辖区多源分管
# ──────────────────────────────────────────────

def get_effective_coverage(db: Session, tenant_id: str, user_id: int,
                           product_id: int = None, doctor_id: int = None,
                           effective_date: date = None) -> list:
    """获取用户在指定日期有效的覆盖分管记录

    规则：
    - source_type=agent 的记录为只读代理
    - is_temp=1 且 temp_expires_at < effective_date 的记录已过期
    - start_date <= effective_date <= end_date（或 end_date 为空）
    """
    if effective_date is None:
        effective_date = date.today()

    q = db.query(CoverageAssignment).filter(
        CoverageAssignment.tenant_id == tenant_id,
        CoverageAssignment.is_deleted == 0,
        CoverageAssignment.user_id == user_id,
        or_(
            CoverageAssignment.start_date.is_(None),
            CoverageAssignment.start_date <= effective_date,
        ),
        or_(
            CoverageAssignment.end_date.is_(None),
            CoverageAssignment.end_date >= effective_date,
        ),
    )
    # 排除已过期的临时特批
    q = q.filter(or_(
        CoverageAssignment.is_temp == 0,
        and_(
            CoverageAssignment.is_temp == 1,
            or_(
                CoverageAssignment.temp_expires_at.is_(None),
                CoverageAssignment.temp_expires_at >= effective_date,
            ),
        ),
    ))
    if product_id:
        q = q.filter(or_(
            CoverageAssignment.product_id == product_id,
            CoverageAssignment.product_id.is_(None),
        ))
    if doctor_id:
        q = q.filter(or_(
            CoverageAssignment.doctor_id == doctor_id,
            CoverageAssignment.doctor_id.is_(None),
        ))
    assignments = q.all()
    return [{
        "id": a.id,
        "user_id": a.user_id,
        "hospital_id": a.hospital_id,
        "doctor_id": a.doctor_id,
        "product_id": a.product_id,
        "role": a.role,
        "source_type": a.source_type,
        "is_temp": a.is_temp,
        "temp_expires_at": a.temp_expires_at.strftime("%Y-%m-%d %H:%M:%S") if a.temp_expires_at else None,
        "agent_user_id": a.agent_user_id,
        "start_date": str(a.start_date) if a.start_date else None,
        "end_date": str(a.end_date) if a.end_date else None,
    } for a in assignments]


# ──────────────────────────────────────────────
# 序列化辅助
# ──────────────────────────────────────────────

def _serialize_plan(plan: VisitPlan, items: list = None) -> dict:
    """序列化拜访计划"""
    data = {
        "id": plan.id,
        "user_id": plan.user_id,
        "period": plan.period,
        "target_count": plan.target_count,
        "status": plan.status,
        "submitted_at": plan.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if plan.submitted_at else None,
        "approved_by": plan.approved_by,
        "approved_at": plan.approved_at.strftime("%Y-%m-%d %H:%M:%S") if plan.approved_at else None,
        "reject_reason": plan.reject_reason,
        "ai_score": plan.ai_score,
        "ai_suggestion": plan.ai_suggestion,
        "created_at": plan.created_at.strftime("%Y-%m-%d %H:%M:%S") if plan.created_at else None,
    }
    if items is not None:
        data["items"] = [_serialize_plan_item(i) for i in items]
    return data


def _serialize_plan_item(item: VisitPlanItem) -> dict:
    """序列化拜访计划明细"""
    return {
        "id": item.id,
        "plan_id": item.plan_id,
        "hospital_id": item.hospital_id,
        "doctor_id": item.doctor_id,
        "product_id": item.product_id,
        "planned_date": str(item.planned_date) if item.planned_date else None,
        "priority": item.priority,
        "visit_type": item.visit_type,
        "remark": item.remark,
    }


def _serialize_record(record: VisitRecord, hospital=None, doctor=None, product=None) -> dict:
    """序列化拜访记录"""
    data = {
        "id": record.id,
        "user_id": record.user_id,
        "plan_id": record.plan_id,
        "plan_item_id": record.plan_item_id,
        "hospital_id": record.hospital_id,
        "doctor_id": record.doctor_id,
        "product_id": record.product_id,
        "visit_date": str(record.visit_date) if record.visit_date else None,
        "visit_type": record.visit_type,
        "duration_minutes": record.duration_minutes,
        "location": record.location,
        "summary": record.summary,
        "status": record.status,
        "ai_extracted": record.ai_extracted,
        "created_at": record.created_at.strftime("%Y-%m-%d %H:%M:%S") if record.created_at else None,
    }
    if hospital is not None:
        data["hospital_name"] = hospital.name
    if doctor is not None:
        data["doctor_name"] = doctor.name
    if product is not None:
        data["product_name"] = product.name
    return data


def _serialize_feedback(feedback: VisitFeedback, record=None) -> dict:
    """序列化拜访反馈"""
    data = {
        "id": feedback.id,
        "record_id": feedback.record_id,
        "sentiment": feedback.sentiment,
        "interest_points": feedback.interest_points or [],
        "objections": feedback.objections or [],
        "action_items": feedback.action_items or [],
        "ai_raw_response": feedback.ai_raw_response,
        "created_at": feedback.created_at.strftime("%Y-%m-%d %H:%M:%S") if feedback.created_at else None,
    }
    if record is not None:
        data["visit_date"] = str(record.visit_date) if record.visit_date else None
        data["summary"] = record.summary
    return data


def _parse_date(s: str):
    """解析日期字符串，支持 YYYY-MM-DD"""
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise ValidationError(f"日期格式错误：{s}，应为 YYYY-MM-DD")


# ──────────────────────────────────────────────
# 概览统计
# ──────────────────────────────────────────────

def get_overview(db: Session, tenant_id: str, user_id: int) -> dict:
    """销售概览统计"""
    visit_plans_count = db.query(VisitPlan).filter(
        VisitPlan.tenant_id == tenant_id,
        VisitPlan.is_deleted == 0,
        VisitPlan.user_id == user_id,
    ).count()

    visit_records_count = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id == user_id,
    ).count()

    pending_plans = db.query(VisitPlan).filter(
        VisitPlan.tenant_id == tenant_id,
        VisitPlan.is_deleted == 0,
        VisitPlan.status == "pending",
    ).count()

    # 覆盖率：已覆盖医院数 / 总医院数
    total_hospitals = db.query(Hospital).filter(
        Hospital.tenant_id == tenant_id,
        Hospital.is_deleted == 0,
    ).count()
    covered_hospitals = db.query(VisitRecord.hospital_id).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
    ).distinct().count()
    coverage_rate = round(covered_hospitals / total_hospitals * 100, 1) if total_hospitals > 0 else 0

    # 行为积分
    total_points = db.query(func.sum(BehaviorPointRecord.points)).filter(
        BehaviorPointRecord.tenant_id == tenant_id,
        BehaviorPointRecord.is_deleted == 0,
        BehaviorPointRecord.user_id == user_id,
    ).scalar() or 0

    # 平均 AI 评分
    avg_score = db.query(func.avg(VisitPlan.ai_score)).filter(
        VisitPlan.tenant_id == tenant_id,
        VisitPlan.is_deleted == 0,
        VisitPlan.ai_score.isnot(None),
    ).scalar()
    avg_score = round(float(avg_score), 1) if avg_score else 0

    return {
        "visit_plans_count": visit_plans_count,
        "visit_records_count": visit_records_count,
        "pending_plans": pending_plans,
        "coverage_rate": coverage_rate,
        "avg_score": avg_score,
        "total_points": total_points,
    }


# ──────────────────────────────────────────────
# 拜访计划 CRUD + 状态机
# ──────────────────────────────────────────────

def list_plans(db: Session, tenant_id: str, status: str = None, user_id: int = None,
               page_params: PageParams = None) -> dict:
    """列表查询拜访计划"""
    q = db.query(VisitPlan).filter(
        VisitPlan.tenant_id == tenant_id,
        VisitPlan.is_deleted == 0,
    )
    if status:
        q = q.filter(VisitPlan.status == status)
    if user_id:
        q = q.filter(VisitPlan.user_id == user_id)
    total = q.count()
    if page_params:
        q = q.order_by(VisitPlan.id.desc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(VisitPlan.id.desc())
    plans = q.all()
    return paginate([_serialize_plan(p) for p in plans], total, page_params or PageParams())


def get_plan(db: Session, tenant_id: str, plan_id: int) -> dict:
    """获取拜访计划详情（含明细）"""
    plan = db.query(VisitPlan).filter(
        VisitPlan.tenant_id == tenant_id,
        VisitPlan.is_deleted == 0,
        VisitPlan.id == plan_id,
    ).first()
    if not plan:
        raise NotFoundError("拜访计划不存在")
    items = db.query(VisitPlanItem).filter(
        VisitPlanItem.tenant_id == tenant_id,
        VisitPlanItem.is_deleted == 0,
        VisitPlanItem.plan_id == plan_id,
    ).all()
    return _serialize_plan(plan, items)


def create_plan(db: Session, tenant_id: str, user_id: int, data: dict) -> dict:
    """创建拜访计划"""
    period = data.get("period")
    if not period:
        raise ValidationError("period 不能为空")
    plan = VisitPlan(
        tenant_id=tenant_id,
        user_id=user_id,
        period=period,
        target_count=data.get("target_count", 0),
        status="draft",
    )
    db.add(plan)
    db.flush()
    # 处理明细
    items = data.get("items") or []
    for it in items:
        item = VisitPlanItem(
            tenant_id=tenant_id,
            plan_id=plan.id,
            hospital_id=it.get("hospital_id"),
            doctor_id=it.get("doctor_id"),
            product_id=it.get("product_id"),
            planned_date=_parse_date(it.get("planned_date")) if it.get("planned_date") else None,
            priority=it.get("priority", "medium"),
            visit_type=it.get("visit_type", "academic"),
            remark=it.get("remark"),
        )
        db.add(item)
    db.commit()
    db.refresh(plan)
    return _serialize_plan(plan)


def update_plan(db: Session, tenant_id: str, plan_id: int, data: dict) -> dict:
    """更新拜访计划"""
    plan = db.query(VisitPlan).filter(
        VisitPlan.tenant_id == tenant_id,
        VisitPlan.is_deleted == 0,
        VisitPlan.id == plan_id,
    ).first()
    if not plan:
        raise NotFoundError("拜访计划不存在")
    if plan.status not in ("draft", "rejected"):
        raise ValidationError("仅 draft 或 rejected 状态的计划可修改")
    if "period" in data and data["period"] is not None:
        plan.period = data["period"]
    if "target_count" in data and data["target_count"] is not None:
        plan.target_count = data["target_count"]
    db.commit()
    db.refresh(plan)
    return _serialize_plan(plan)


def delete_plan(db: Session, tenant_id: str, plan_id: int) -> None:
    """软删除拜访计划"""
    plan = db.query(VisitPlan).filter(
        VisitPlan.tenant_id == tenant_id,
        VisitPlan.is_deleted == 0,
        VisitPlan.id == plan_id,
    ).first()
    if not plan:
        raise NotFoundError("拜访计划不存在")
    now = datetime.utcnow()
    plan.is_deleted = 1
    plan.deleted_at = now
    # 软删明细
    items = db.query(VisitPlanItem).filter(
        VisitPlanItem.tenant_id == tenant_id,
        VisitPlanItem.is_deleted == 0,
        VisitPlanItem.plan_id == plan_id,
    ).all()
    for it in items:
        it.is_deleted = 1
        it.deleted_at = now
    db.commit()


def submit_plan(db: Session, tenant_id: str, plan_id: int, user_id: int) -> dict:
    """提交拜访计划（draft/rejected → pending）"""
    plan = db.query(VisitPlan).filter(
        VisitPlan.tenant_id == tenant_id,
        VisitPlan.is_deleted == 0,
        VisitPlan.id == plan_id,
    ).first()
    if not plan:
        raise NotFoundError("拜访计划不存在")
    if plan.status not in ("draft", "rejected"):
        raise ValidationError(f"当前状态 {plan.status} 不允许提交")
    plan.status = "pending"
    plan.submitted_at = datetime.utcnow()
    plan.reject_reason = None
    db.commit()
    db.refresh(plan)
    return _serialize_plan(plan)


def approve_plan(db: Session, tenant_id: str, plan_id: int, approver_id: int) -> dict:
    """审批通过（pending → approved）"""
    plan = db.query(VisitPlan).filter(
        VisitPlan.tenant_id == tenant_id,
        VisitPlan.is_deleted == 0,
        VisitPlan.id == plan_id,
    ).first()
    if not plan:
        raise NotFoundError("拜访计划不存在")
    if plan.status != "pending":
        raise ValidationError(f"当前状态 {plan.status} 不允许审批")
    plan.status = "approved"
    plan.approved_by = approver_id
    plan.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(plan)
    return _serialize_plan(plan)


def reject_plan(db: Session, tenant_id: str, plan_id: int, approver_id: int, reason: str) -> dict:
    """驳回（pending → rejected）"""
    plan = db.query(VisitPlan).filter(
        VisitPlan.tenant_id == tenant_id,
        VisitPlan.is_deleted == 0,
        VisitPlan.id == plan_id,
    ).first()
    if not plan:
        raise NotFoundError("拜访计划不存在")
    if plan.status != "pending":
        raise ValidationError(f"当前状态 {plan.status} 不允许驳回")
    if not reason:
        raise ValidationError("驳回原因不能为空")
    plan.status = "rejected"
    plan.approved_by = approver_id
    plan.approved_at = datetime.utcnow()
    plan.reject_reason = reason
    db.commit()
    db.refresh(plan)
    return _serialize_plan(plan)


# ──────────────────────────────────────────────
# 拜访计划明细
# ──────────────────────────────────────────────

def add_plan_item(db: Session, tenant_id: str, plan_id: int, data: dict) -> dict:
    """新增拜访计划明细"""
    plan = db.query(VisitPlan).filter(
        VisitPlan.tenant_id == tenant_id,
        VisitPlan.is_deleted == 0,
        VisitPlan.id == plan_id,
    ).first()
    if not plan:
        raise NotFoundError("拜访计划不存在")
    if plan.status not in ("draft", "rejected"):
        raise ValidationError("仅 draft 或 rejected 状态的计划可新增明细")
    item = VisitPlanItem(
        tenant_id=tenant_id,
        plan_id=plan_id,
        hospital_id=data.get("hospital_id"),
        doctor_id=data.get("doctor_id"),
        product_id=data.get("product_id"),
        planned_date=_parse_date(data["planned_date"]) if data.get("planned_date") else None,
        priority=data.get("priority", "medium"),
        visit_type=data.get("visit_type", "academic"),
        remark=data.get("remark"),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_plan_item(item)


def list_plan_items(db: Session, tenant_id: str, plan_id: int) -> list:
    """查询拜访计划明细"""
    items = db.query(VisitPlanItem).filter(
        VisitPlanItem.tenant_id == tenant_id,
        VisitPlanItem.is_deleted == 0,
        VisitPlanItem.plan_id == plan_id,
    ).order_by(VisitPlanItem.id.asc()).all()
    return [_serialize_plan_item(i) for i in items]


def delete_plan_item(db: Session, tenant_id: str, plan_id: int, item_id: int) -> None:
    """软删除拜访计划明细"""
    item = db.query(VisitPlanItem).filter(
        VisitPlanItem.tenant_id == tenant_id,
        VisitPlanItem.is_deleted == 0,
        VisitPlanItem.id == item_id,
        VisitPlanItem.plan_id == plan_id,
    ).first()
    if not item:
        raise NotFoundError("拜访计划明细不存在")
    item.is_deleted = 1
    item.deleted_at = datetime.utcnow()
    db.commit()


# ──────────────────────────────────────────────
# 拜访记录 CRUD
# ──────────────────────────────────────────────

def list_records(db: Session, tenant_id: str, hospital_id: int = None, doctor_id: int = None,
                 user_id: int = None, page_params: PageParams = None) -> dict:
    """列表查询拜访记录"""
    q = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
    )
    if hospital_id:
        q = q.filter(VisitRecord.hospital_id == hospital_id)
    if doctor_id:
        q = q.filter(VisitRecord.doctor_id == doctor_id)
    if user_id:
        q = q.filter(VisitRecord.user_id == user_id)
    total = q.count()
    if page_params:
        q = q.order_by(VisitRecord.visit_date.desc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(VisitRecord.visit_date.desc())
    records = q.all()
    # 批量取关联主数据
    hospital_ids = {r.hospital_id for r in records if r.hospital_id}
    doctor_ids = {r.doctor_id for r in records if r.doctor_id}
    product_ids = {r.product_id for r in records if r.product_id}
    hospitals = {h.id: h for h in db.query(Hospital).filter(Hospital.id.in_(hospital_ids)).all()} if hospital_ids else {}
    doctors = {d.id: d for d in db.query(Doctor).filter(Doctor.id.in_(doctor_ids)).all()} if doctor_ids else {}
    products = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()} if product_ids else {}
    items = [_serialize_record(
        r,
        hospitals.get(r.hospital_id),
        doctors.get(r.doctor_id),
        products.get(r.product_id),
    ) for r in records]
    return paginate(items, total, page_params or PageParams())


def get_record(db: Session, tenant_id: str, record_id: int) -> dict:
    """获取拜访记录详情"""
    record = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.id == record_id,
    ).first()
    if not record:
        raise NotFoundError("拜访记录不存在")
    hospital = db.query(Hospital).filter(Hospital.id == record.hospital_id).first() if record.hospital_id else None
    doctor = db.query(Doctor).filter(Doctor.id == record.doctor_id).first() if record.doctor_id else None
    product = db.query(Product).filter(Product.id == record.product_id).first() if record.product_id else None
    return _serialize_record(record, hospital, doctor, product)


def create_record(db: Session, tenant_id: str, user_id: int, data: dict) -> dict:
    """创建拜访记录"""
    if not data.get("visit_date"):
        raise ValidationError("visit_date 不能为空")
    record = VisitRecord(
        tenant_id=tenant_id,
        user_id=user_id,
        plan_id=data.get("plan_id"),
        plan_item_id=data.get("plan_item_id"),
        hospital_id=data.get("hospital_id"),
        doctor_id=data.get("doctor_id"),
        product_id=data.get("product_id"),
        visit_date=_parse_date(data["visit_date"]),
        visit_type=data.get("visit_type", "academic"),
        duration_minutes=data.get("duration_minutes", 30),
        location=data.get("location"),
        summary=data.get("summary"),
        status="completed",
    )
    db.add(record)
    db.flush()
    # F4.4: 绩效边界校验（借鉴诊断体系 §10.3）
    # 只允许联动"可控行为"，禁止联动"业务结果"或"AI 自动判定"
    from core.performance_policy import enforce_performance_boundary
    _boundary_ok = enforce_performance_boundary(
        db, tenant_id, "complete_visit",
        source_signal=f"visit_record:{record.id}",
    )
    if not _boundary_ok:
        logger.info(
            "[sales] 拜访积分写入被绩效边界策略阻断（record_id=%s）",
            record.id,
        )
    # 自动加积分：完成拜访 +5
    rule = db.query(BehaviorPointRule).filter(
        BehaviorPointRule.tenant_id == tenant_id,
        BehaviorPointRule.is_deleted == 0,
        BehaviorPointRule.action_code == "complete_visit",
        BehaviorPointRule.is_active == 1,
    ).first()
    if rule and _boundary_ok:
        bpr = BehaviorPointRecord(
            tenant_id=tenant_id,
            user_id=user_id,
            rule_id=rule.id,
            record_id=record.id,
            points=rule.points,
            occurred_at=datetime.utcnow(),
        )
        db.add(bpr)
    # 学术拜访额外加分
    if data.get("visit_type") == "academic" and _boundary_ok:
        a_rule = db.query(BehaviorPointRule).filter(
            BehaviorPointRule.tenant_id == tenant_id,
            BehaviorPointRule.is_deleted == 0,
            BehaviorPointRule.action_code == "academic_visit",
            BehaviorPointRule.is_active == 1,
        ).first()
        if a_rule:
            db.add(BehaviorPointRecord(
                tenant_id=tenant_id,
                user_id=user_id,
                rule_id=a_rule.id,
                record_id=record.id,
                points=a_rule.points,
                occurred_at=datetime.utcnow(),
            ))
    # 更新覆盖矩阵
    _update_coverage_matrix(db, tenant_id, record.hospital_id, record.product_id, record.visit_date)
    db.commit()
    db.refresh(record)
    hospital = db.query(Hospital).filter(Hospital.id == record.hospital_id).first() if record.hospital_id else None
    doctor = db.query(Doctor).filter(Doctor.id == record.doctor_id).first() if record.doctor_id else None
    product = db.query(Product).filter(Product.id == record.product_id).first() if record.product_id else None
    # 行为→能力飞轮：基于拜访数据推荐培训
    learning_needs = profile_service.get_learning_needs(db, tenant_id, user_id)
    suggested_training = learning_needs.get("recommendations", [])[:3]
    result = _serialize_record(record, hospital, doctor, product)
    result["suggested_training"] = suggested_training

    # 发布拜访反馈事件（触发学习需求重算 + 高频异议检测）
    try:
        from ai.event_bus import event_bus
        event_bus.publish(
            "visit_record_feedback",
            {
                "user_id": user_id,
                "record_id": record.id,
                "doctor_id": record.doctor_id,
                "hospital_id": record.hospital_id,
            },
            tenant_id=tenant_id,
            consistency="eventual",
            db=db,
        )
    except Exception as e:
        logger.warning("拜访反馈事件发布失败: %s", e, exc_info=True)

    return result


def update_record(db: Session, tenant_id: str, record_id: int, data: dict) -> dict:
    """更新拜访记录"""
    record = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.id == record_id,
    ).first()
    if not record:
        raise NotFoundError("拜访记录不存在")
    if "plan_id" in data:
        record.plan_id = data["plan_id"]
    if "hospital_id" in data:
        record.hospital_id = data["hospital_id"]
    if "doctor_id" in data:
        record.doctor_id = data["doctor_id"]
    if "product_id" in data:
        record.product_id = data["product_id"]
    if "visit_date" in data and data["visit_date"]:
        record.visit_date = _parse_date(data["visit_date"])
    if "visit_type" in data:
        record.visit_type = data["visit_type"]
    if "duration_minutes" in data:
        record.duration_minutes = data["duration_minutes"]
    if "location" in data:
        record.location = data["location"]
    if "summary" in data:
        record.summary = data["summary"]
    db.commit()
    db.refresh(record)
    hospital = db.query(Hospital).filter(Hospital.id == record.hospital_id).first() if record.hospital_id else None
    doctor = db.query(Doctor).filter(Doctor.id == record.doctor_id).first() if record.doctor_id else None
    product = db.query(Product).filter(Product.id == record.product_id).first() if record.product_id else None
    return _serialize_record(record, hospital, doctor, product)


def delete_record(db: Session, tenant_id: str, record_id: int) -> None:
    """软删除拜访记录"""
    record = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.id == record_id,
    ).first()
    if not record:
        raise NotFoundError("拜访记录不存在")
    record.is_deleted = 1
    record.deleted_at = datetime.utcnow()
    db.commit()


# ──────────────────────────────────────────────
# 拜访反馈
# ──────────────────────────────────────────────

def list_feedbacks(db: Session, tenant_id: str, record_id: int = None,
                   page_params: PageParams = None) -> dict:
    """列表查询拜访反馈"""
    q = db.query(VisitFeedback).filter(
        VisitFeedback.tenant_id == tenant_id,
        VisitFeedback.is_deleted == 0,
    )
    if record_id:
        q = q.filter(VisitFeedback.record_id == record_id)
    total = q.count()
    if page_params:
        q = q.order_by(VisitFeedback.id.desc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(VisitFeedback.id.desc())
    feedbacks = q.all()
    record_ids = {f.record_id for f in feedbacks}
    records = {r.id: r for r in db.query(VisitRecord).filter(VisitRecord.id.in_(record_ids)).all()} if record_ids else {}
    items = [_serialize_feedback(f, records.get(f.record_id)) for f in feedbacks]
    return paginate(items, total, page_params or PageParams())


def get_feedback(db: Session, tenant_id: str, feedback_id: int) -> dict:
    """获取拜访反馈详情"""
    feedback = db.query(VisitFeedback).filter(
        VisitFeedback.tenant_id == tenant_id,
        VisitFeedback.is_deleted == 0,
        VisitFeedback.id == feedback_id,
    ).first()
    if not feedback:
        raise NotFoundError("拜访反馈不存在")
    record = db.query(VisitRecord).filter(VisitRecord.id == feedback.record_id).first()
    return _serialize_feedback(feedback, record)


def create_feedback(db: Session, tenant_id: str, user_id: int, data: dict) -> dict:
    """创建拜访反馈"""
    record_id = data.get("record_id")
    if not record_id:
        raise ValidationError("record_id 不能为空")
    record = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.id == record_id,
    ).first()
    if not record:
        raise NotFoundError("拜访记录不存在")
    feedback = VisitFeedback(
        tenant_id=tenant_id,
        record_id=record_id,
        sentiment=data.get("sentiment", "neutral"),
        interest_points=data.get("interest_points") or [],
        objections=data.get("objections") or [],
        action_items=data.get("action_items") or [],
    )
    db.add(feedback)
    db.flush()
    # 正面反馈加积分
    if data.get("sentiment") == "positive":
        rule = db.query(BehaviorPointRule).filter(
            BehaviorPointRule.tenant_id == tenant_id,
            BehaviorPointRule.is_deleted == 0,
            BehaviorPointRule.action_code == "positive_feedback",
            BehaviorPointRule.is_active == 1,
        ).first()
        if rule:
            # F4.4: 绩效边界校验（借鉴诊断体系 §10.3）
            from core.performance_policy import enforce_performance_boundary
            _boundary_ok = enforce_performance_boundary(
                db, tenant_id, "positive_feedback",
                source_signal=f"visit_feedback:{feedback.id}",
            )
            if not _boundary_ok:
                logger.info(
                    "[sales] 正面反馈积分写入被绩效边界策略阻断（feedback_id=%s）",
                    feedback.id,
                )
            else:
                db.add(BehaviorPointRecord(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    rule_id=rule.id,
                    record_id=record_id,
                    points=rule.points,
                    occurred_at=datetime.utcnow(),
                ))
    db.commit()
    db.refresh(feedback)
    return _serialize_feedback(feedback, record)


def update_feedback(db: Session, tenant_id: str, feedback_id: int, data: dict) -> dict:
    """更新拜访反馈"""
    feedback = db.query(VisitFeedback).filter(
        VisitFeedback.tenant_id == tenant_id,
        VisitFeedback.is_deleted == 0,
        VisitFeedback.id == feedback_id,
    ).first()
    if not feedback:
        raise NotFoundError("拜访反馈不存在")
    if "sentiment" in data:
        feedback.sentiment = data["sentiment"]
    if "interest_points" in data:
        feedback.interest_points = data["interest_points"]
    if "objections" in data:
        feedback.objections = data["objections"]
    if "action_items" in data:
        feedback.action_items = data["action_items"]
    db.commit()
    db.refresh(feedback)
    record = db.query(VisitRecord).filter(VisitRecord.id == feedback.record_id).first()
    return _serialize_feedback(feedback, record)


def delete_feedback(db: Session, tenant_id: str, feedback_id: int) -> None:
    """软删除拜访反馈"""
    feedback = db.query(VisitFeedback).filter(
        VisitFeedback.tenant_id == tenant_id,
        VisitFeedback.is_deleted == 0,
        VisitFeedback.id == feedback_id,
    ).first()
    if not feedback:
        raise NotFoundError("拜访反馈不存在")
    feedback.is_deleted = 1
    feedback.deleted_at = datetime.utcnow()
    db.commit()


# ──────────────────────────────────────────────
# 覆盖分管
# ──────────────────────────────────────────────

def list_coverage(db: Session, tenant_id: str, user_id: int = None,
                  page_params: PageParams = None) -> dict:
    """列表查询覆盖分管"""
    q = db.query(CoverageAssignment).filter(
        CoverageAssignment.tenant_id == tenant_id,
        CoverageAssignment.is_deleted == 0,
    )
    if user_id:
        q = q.filter(CoverageAssignment.user_id == user_id)
    total = q.count()
    if page_params:
        q = q.order_by(CoverageAssignment.id.desc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(CoverageAssignment.id.desc())
    items = q.all()
    # 关联主数据
    hospital_ids = {c.hospital_id for c in items if c.hospital_id}
    doctor_ids = {c.doctor_id for c in items if c.doctor_id}
    product_ids = {c.product_id for c in items if c.product_id}
    hospitals = {h.id: h for h in db.query(Hospital).filter(Hospital.id.in_(hospital_ids)).all()} if hospital_ids else {}
    doctors = {d.id: d for d in db.query(Doctor).filter(Doctor.id.in_(doctor_ids)).all()} if doctor_ids else {}
    products = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()} if product_ids else {}
    result = [{
        "id": c.id,
        "user_id": c.user_id,
        "hospital_id": c.hospital_id,
        "hospital_name": hospitals.get(c.hospital_id).name if c.hospital_id and hospitals.get(c.hospital_id) else None,
        "doctor_id": c.doctor_id,
        "doctor_name": doctors.get(c.doctor_id).name if c.doctor_id and doctors.get(c.doctor_id) else None,
        "product_id": c.product_id,
        "product_name": products.get(c.product_id).name if c.product_id and products.get(c.product_id) else None,
        "role": c.role,
        "start_date": str(c.start_date) if c.start_date else None,
        "end_date": str(c.end_date) if c.end_date else None,
    } for c in items]
    return paginate(result, total, page_params or PageParams())


def assign_coverage(db: Session, tenant_id: str, data: dict) -> dict:
    """分配覆盖"""
    cov = CoverageAssignment(
        tenant_id=tenant_id,
        user_id=data["user_id"],
        hospital_id=data.get("hospital_id"),
        doctor_id=data.get("doctor_id"),
        product_id=data.get("product_id"),
        role=data.get("role", "primary"),
        start_date=_parse_date(data["start_date"]) if data.get("start_date") else None,
    )
    db.add(cov)
    db.commit()
    db.refresh(cov)
    return {
        "id": cov.id,
        "user_id": cov.user_id,
        "hospital_id": cov.hospital_id,
        "doctor_id": cov.doctor_id,
        "product_id": cov.product_id,
        "role": cov.role,
        "start_date": str(cov.start_date) if cov.start_date else None,
    }


def delete_coverage(db: Session, tenant_id: str, coverage_id: int) -> None:
    """软删除覆盖分配"""
    cov = db.query(CoverageAssignment).filter(
        CoverageAssignment.tenant_id == tenant_id,
        CoverageAssignment.is_deleted == 0,
        CoverageAssignment.id == coverage_id,
    ).first()
    if not cov:
        raise NotFoundError("覆盖分配不存在")
    cov.is_deleted = 1
    cov.deleted_at = datetime.utcnow()
    db.commit()


# ──────────────────────────────────────────────
# 覆盖矩阵
# ──────────────────────────────────────────────

def list_matrix(db: Session, tenant_id: str, hospital_id: int = None,
                product_id: int = None, page_params: PageParams = None) -> dict:
    """列表查询覆盖矩阵"""
    q = db.query(CoverageMatrix).filter(
        CoverageMatrix.tenant_id == tenant_id,
        CoverageMatrix.is_deleted == 0,
    )
    if hospital_id:
        q = q.filter(CoverageMatrix.hospital_id == hospital_id)
    if product_id:
        q = q.filter(CoverageMatrix.product_id == product_id)
    total = q.count()
    if page_params:
        q = q.order_by(CoverageMatrix.id.asc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(CoverageMatrix.id.asc())
    items = q.all()
    # 关联主数据
    hospital_ids = {m.hospital_id for m in items}
    product_ids = {m.product_id for m in items}
    hospitals = {h.id: h for h in db.query(Hospital).filter(Hospital.id.in_(hospital_ids)).all()} if hospital_ids else {}
    products = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()} if product_ids else {}
    result = [{
        "id": m.id,
        "hospital_id": m.hospital_id,
        "hospital_name": hospitals.get(m.hospital_id).name if hospitals.get(m.hospital_id) else None,
        "product_id": m.product_id,
        "product_name": products.get(m.product_id).name if products.get(m.product_id) else None,
        "visit_count": m.visit_count,
        "last_visit_date": str(m.last_visit_date) if m.last_visit_date else None,
        "coverage_level": m.coverage_level,
        "trend": m.trend,
    } for m in items]
    return paginate(result, total, page_params or PageParams())


def _update_coverage_matrix(db: Session, tenant_id: str, hospital_id: int, product_id: int, visit_date) -> None:
    """更新覆盖矩阵（内部使用）"""
    if not hospital_id or not product_id:
        return
    matrix = db.query(CoverageMatrix).filter(
        CoverageMatrix.tenant_id == tenant_id,
        CoverageMatrix.is_deleted == 0,
        CoverageMatrix.hospital_id == hospital_id,
        CoverageMatrix.product_id == product_id,
    ).first()
    if not matrix:
        matrix = CoverageMatrix(
            tenant_id=tenant_id,
            hospital_id=hospital_id,
            product_id=product_id,
            visit_count=0,
            coverage_level="none",
            trend="stable",
        )
        db.add(matrix)
        db.flush()
    matrix.visit_count = (matrix.visit_count or 0) + 1
    if matrix.last_visit_date is None or visit_date > matrix.last_visit_date:
        matrix.last_visit_date = visit_date
    # 重新计算覆盖等级
    cnt = matrix.visit_count
    if cnt >= 3:
        matrix.coverage_level = "high"
    elif cnt >= 2:
        matrix.coverage_level = "medium"
    elif cnt >= 1:
        matrix.coverage_level = "low"
    else:
        matrix.coverage_level = "none"
    matrix.trend = "up"


def refresh_matrix(db: Session, tenant_id: str) -> dict:
    """根据拜访记录刷新覆盖矩阵统计"""
    # 查所有矩阵行
    matrices = db.query(CoverageMatrix).filter(
        CoverageMatrix.tenant_id == tenant_id,
        CoverageMatrix.is_deleted == 0,
    ).all()
    # 按 hospital_id × product_id 汇总拜访记录
    rows = db.query(
        VisitRecord.hospital_id,
        VisitRecord.product_id,
        func.count(VisitRecord.id),
        func.max(VisitRecord.visit_date),
    ).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.hospital_id.isnot(None),
        VisitRecord.product_id.isnot(None),
    ).group_by(VisitRecord.hospital_id, VisitRecord.product_id).all()
    stats = {(r[0], r[1]): (r[2], r[3]) for r in rows}
    updated = 0
    existing_keys = set()
    for m in matrices:
        key = (m.hospital_id, m.product_id)
        existing_keys.add(key)
        if key in stats:
            cnt, last_date = stats[key]
            m.visit_count = cnt
            m.last_visit_date = last_date
            if cnt >= 3:
                m.coverage_level = "high"
            elif cnt >= 2:
                m.coverage_level = "medium"
            elif cnt >= 1:
                m.coverage_level = "low"
            else:
                m.coverage_level = "none"
            updated += 1
    # 为新的 hospital × product 组合创建矩阵行
    for (h_id, p_id), (cnt, last_date) in stats.items():
        if (h_id, p_id) not in existing_keys:
            level = "high" if cnt >= 3 else ("medium" if cnt >= 2 else ("low" if cnt >= 1 else "none"))
            db.add(CoverageMatrix(
                tenant_id=tenant_id,
                hospital_id=h_id,
                product_id=p_id,
                visit_count=cnt,
                last_visit_date=last_date,
                coverage_level=level,
                trend="up",
            ))
            updated += 1
    db.commit()
    return {"refreshed": updated}


# ──────────────────────────────────────────────
# 积分管理
# ──────────────────────────────────────────────

def list_behavior_rules(db: Session, tenant_id: str) -> list:
    """查询行为积分规则"""
    rules = db.query(BehaviorPointRule).filter(
        BehaviorPointRule.tenant_id == tenant_id,
        BehaviorPointRule.is_deleted == 0,
    ).order_by(BehaviorPointRule.id.asc()).all()
    return [{
        "id": r.id,
        "name": r.name,
        "action_code": r.action_code,
        "points": r.points,
        "description": r.description,
        "is_active": r.is_active,
    } for r in rules]


def list_behavior_records(db: Session, tenant_id: str, user_id: int = None,
                          page_params: PageParams = None) -> dict:
    """查询行为积分记录"""
    q = db.query(BehaviorPointRecord).filter(
        BehaviorPointRecord.tenant_id == tenant_id,
        BehaviorPointRecord.is_deleted == 0,
    )
    if user_id:
        q = q.filter(BehaviorPointRecord.user_id == user_id)
    total = q.count()
    if page_params:
        q = q.order_by(BehaviorPointRecord.occurred_at.desc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(BehaviorPointRecord.occurred_at.desc())
    records = q.all()
    rule_ids = {r.rule_id for r in records}
    rules = {rl.id: rl for rl in db.query(BehaviorPointRule).filter(BehaviorPointRule.id.in_(rule_ids)).all()} if rule_ids else {}
    items = [{
        "id": r.id,
        "user_id": r.user_id,
        "rule_id": r.rule_id,
        "rule_name": rules.get(r.rule_id).name if rules.get(r.rule_id) else None,
        "record_id": r.record_id,
        "points": r.points,
        "occurred_at": r.occurred_at.strftime("%Y-%m-%d %H:%M:%S") if r.occurred_at else None,
    } for r in records]
    return paginate(items, total, page_params or PageParams())


def get_points_summary(db: Session, tenant_id: str, user_id: int) -> dict:
    """积分汇总"""
    behavior_total = db.query(func.sum(BehaviorPointRecord.points)).filter(
        BehaviorPointRecord.tenant_id == tenant_id,
        BehaviorPointRecord.is_deleted == 0,
        BehaviorPointRecord.user_id == user_id,
    ).scalar() or 0
    instruction_total = db.query(func.sum(InstructionPointRecord.points)).filter(
        InstructionPointRecord.tenant_id == tenant_id,
        InstructionPointRecord.is_deleted == 0,
        InstructionPointRecord.user_id == user_id,
    ).scalar() or 0
    behavior_count = db.query(BehaviorPointRecord).filter(
        BehaviorPointRecord.tenant_id == tenant_id,
        BehaviorPointRecord.is_deleted == 0,
        BehaviorPointRecord.user_id == user_id,
    ).count()
    instruction_count = db.query(InstructionPointRecord).filter(
        InstructionPointRecord.tenant_id == tenant_id,
        InstructionPointRecord.is_deleted == 0,
        InstructionPointRecord.user_id == user_id,
    ).count()
    return {
        "behavior_points": behavior_total,
        "instruction_points": instruction_total,
        "total_points": behavior_total + instruction_total,
        "behavior_record_count": behavior_count,
        "instruction_record_count": instruction_count,
    }


# ──────────────────────────────────────────────
# 周报
# ──────────────────────────────────────────────

def list_weekly_reports(db: Session, tenant_id: str, user_id: int = None,
                        page_params: PageParams = None) -> dict:
    """列表查询周报"""
    q = db.query(WeeklyReport).filter(
        WeeklyReport.tenant_id == tenant_id,
        WeeklyReport.is_deleted == 0,
    )
    if user_id:
        q = q.filter(WeeklyReport.user_id == user_id)
    total = q.count()
    if page_params:
        q = q.order_by(WeeklyReport.week_start.desc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(WeeklyReport.week_start.desc())
    reports = q.all()
    items = [{
        "id": r.id,
        "user_id": r.user_id,
        "week_start": str(r.week_start) if r.week_start else None,
        "week_end": str(r.week_end) if r.week_end else None,
        "visit_count": r.visit_count,
        "feedback_count": r.feedback_count,
        "total_points": r.total_points,
        "summary": r.summary,
        "ai_summary": r.ai_summary,
    } for r in reports]
    return paginate(items, total, page_params or PageParams())


def generate_weekly_report(db: Session, tenant_id: str, user_id: int, week_start: str = None) -> dict:
    """生成周报（默认本周，整合销售+培训双域数据）"""
    today = date.today()
    if week_start:
        start = _parse_date(week_start)
    else:
        # 本周一
        start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    # 检查是否已存在
    existing = db.query(WeeklyReport).filter(
        WeeklyReport.tenant_id == tenant_id,
        WeeklyReport.is_deleted == 0,
        WeeklyReport.user_id == user_id,
        WeeklyReport.week_start == start,
    ).first()
    if existing:
        return {
            "id": existing.id,
            "week_start": str(existing.week_start),
            "week_end": str(existing.week_end),
            "visit_count": existing.visit_count,
            "feedback_count": existing.feedback_count,
            "total_points": existing.total_points,
            "courses_completed": existing.courses_completed,
            "exams_taken": existing.exams_taken,
            "credits_earned": existing.credits_earned,
            "avg_exam_score": existing.avg_exam_score,
            "summary": existing.summary,
            "ai_summary": existing.ai_summary,
            "already_exists": True,
        }
    # 统计本周拜访
    visit_count = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id == user_id,
        VisitRecord.visit_date >= start,
        VisitRecord.visit_date <= end,
    ).count()
    # 统计本周反馈
    feedback_count = db.query(VisitFeedback).join(
        VisitRecord, VisitRecord.id == VisitFeedback.record_id
    ).filter(
        VisitFeedback.tenant_id == tenant_id,
        VisitFeedback.is_deleted == 0,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id == user_id,
        VisitRecord.visit_date >= start,
        VisitRecord.visit_date <= end,
    ).count()
    # 统计本周积分
    total_points = db.query(func.sum(BehaviorPointRecord.points)).filter(
        BehaviorPointRecord.tenant_id == tenant_id,
        BehaviorPointRecord.is_deleted == 0,
        BehaviorPointRecord.user_id == user_id,
        BehaviorPointRecord.occurred_at >= datetime.combine(start, datetime.min.time()),
        BehaviorPointRecord.occurred_at <= datetime.combine(end, datetime.max.time()),
    ).scalar() or 0
    # 统计本周培训数据
    week_start_dt = datetime.combine(start, datetime.min.time())
    week_end_dt = datetime.combine(end, datetime.max.time())
    courses_completed = db.query(CourseEnrollment).filter(
        CourseEnrollment.tenant_id == tenant_id,
        CourseEnrollment.is_deleted == 0,
        CourseEnrollment.user_id == user_id,
        CourseEnrollment.status == "completed",
        CourseEnrollment.completed_at >= week_start_dt,
        CourseEnrollment.completed_at <= week_end_dt,
    ).count()
    exam_records = db.query(ExamRecord).filter(
        ExamRecord.tenant_id == tenant_id,
        ExamRecord.is_deleted == 0,
        ExamRecord.user_id == user_id,
        ExamRecord.status == "submitted",
        ExamRecord.submitted_at >= week_start_dt,
        ExamRecord.submitted_at <= week_end_dt,
    ).all()
    exams_taken = len(exam_records)
    avg_exam_score = round(sum(r.score or 0 for r in exam_records) / exams_taken) if exams_taken > 0 else 0
    credits_earned = db.query(func.sum(PathEnrollment.credits_earned)).filter(
        PathEnrollment.tenant_id == tenant_id,
        PathEnrollment.is_deleted == 0,
        PathEnrollment.user_id == user_id,
    ).scalar() or 0
    summary = (
        f"本周（{start} 至 {end}）共完成拜访 {visit_count} 次，"
        f"收到反馈 {feedback_count} 条，获得积分 {total_points} 分；"
        f"完成课程 {courses_completed} 门，参加考试 {exams_taken} 次"
        f"（平均 {avg_exam_score} 分），累计学分 {credits_earned}。"
    )
    ai_summary = (
        f"本周拜访活跃度{'良好' if visit_count >= 5 else '需提升'}，"
        f"培训完成{'达标' if courses_completed >= 1 else '不足'}。"
        f"{'建议下周加强课程学习' if courses_completed == 0 else '保持学习节奏'}。"
    )
    report = WeeklyReport(
        tenant_id=tenant_id,
        user_id=user_id,
        week_start=start,
        week_end=end,
        visit_count=visit_count,
        feedback_count=feedback_count,
        total_points=total_points,
        courses_completed=courses_completed,
        exams_taken=exams_taken,
        credits_earned=credits_earned,
        avg_exam_score=avg_exam_score,
        summary=summary,
        ai_summary=ai_summary,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {
        "id": report.id,
        "week_start": str(report.week_start),
        "week_end": str(report.week_end),
        "visit_count": report.visit_count,
        "feedback_count": report.feedback_count,
        "total_points": report.total_points,
        "courses_completed": report.courses_completed,
        "exams_taken": report.exams_taken,
        "credits_earned": report.credits_earned,
        "avg_exam_score": report.avg_exam_score,
        "summary": report.summary,
        "ai_summary": report.ai_summary,
        "already_exists": False,
    }


# ──────────────────────────────────────────────
# 主数据查询
# ──────────────────────────────────────────────

def list_hospitals(db: Session, tenant_id: str, keyword: str = None,
                   page_params: PageParams = None) -> dict:
    """查询医院列表"""
    q = db.query(Hospital).filter(
        Hospital.tenant_id == tenant_id,
        Hospital.is_deleted == 0,
    )
    if keyword:
        q = q.filter(Hospital.name.like(f"%{keyword}%"))
    total = q.count()
    if page_params:
        q = q.order_by(Hospital.id.asc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(Hospital.id.asc())
    items = q.all()
    result = [{
        "id": h.id,
        "name": h.name,
        "code": h.code,
        "level": h.level,
        "province": h.province,
        "city": h.city,
        "district": h.district,
        "address": h.address,
    } for h in items]
    return paginate(result, total, page_params or PageParams())


def list_doctors(db: Session, tenant_id: str, hospital_id: int = None,
                 keyword: str = None, page_params: PageParams = None) -> dict:
    """查询医生列表"""
    q = db.query(Doctor).filter(
        Doctor.tenant_id == tenant_id,
        Doctor.is_deleted == 0,
    )
    if hospital_id:
        q = q.filter(Doctor.hospital_id == hospital_id)
    if keyword:
        q = q.filter(Doctor.name.like(f"%{keyword}%"))
    total = q.count()
    if page_params:
        q = q.order_by(Doctor.id.asc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(Doctor.id.asc())
    items = q.all()
    result = [{
        "id": d.id,
        "name": d.name,
        "hospital_id": d.hospital_id,
        "department": d.department,
        "title": d.title,
        "phone": d.phone,
    } for d in items]
    return paginate(result, total, page_params or PageParams())


def list_products(db: Session, tenant_id: str, keyword: str = None,
                  page_params: PageParams = None) -> dict:
    """查询产品列表"""
    q = db.query(Product).filter(
        Product.tenant_id == tenant_id,
        Product.is_deleted == 0,
    )
    if keyword:
        q = q.filter(Product.name.like(f"%{keyword}%"))
    total = q.count()
    if page_params:
        q = q.order_by(Product.id.asc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(Product.id.asc())
    items = q.all()
    result = [{
        "id": p.id,
        "name": p.name,
        "code": p.code,
        "category": p.category,
        "specifications": p.specifications,
        "manufacturer": p.manufacturer,
    } for p in items]
    return paginate(result, total, page_params or PageParams())
