"""客户关系管理服务层

提供 KOL/客户/互动总览、客户列表、互动列表能力。
数据来源：Doctor + VisitRecord + VisitFeedback + Hospital + Product。
"""
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import (
    Doctor, Hospital, Product,
    VisitRecord, VisitFeedback,
)


# ──────────────────────────────────────────────
# CRM 总览
# ──────────────────────────────────────────────

def get_overview(db: Session, tenant_id: str, user_id: int) -> dict:
    """CRM 总览：KOL 数、客户数、互动数、最近互动"""
    # 互动总数（拜访记录数）
    interactions_count = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id == user_id,
    ).count()

    # 客户数：被该用户拜访过的不同医生数
    customer_count = db.query(VisitRecord.doctor_id).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id == user_id,
        VisitRecord.doctor_id.isnot(None),
    ).distinct().count()

    # KOL 数：被拜访 >=2 次的医生
    visit_counts = db.query(
        VisitRecord.doctor_id,
        func.count(VisitRecord.id).label("cnt"),
    ).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id == user_id,
        VisitRecord.doctor_id.isnot(None),
    ).group_by(VisitRecord.doctor_id).all()
    kols_count = sum(1 for row in visit_counts if row.cnt >= 2)

    # 最近 5 条互动
    recent_records = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id == user_id,
    ).order_by(VisitRecord.visit_date.desc()).limit(5).all()

    doctor_ids = [r.doctor_id for r in recent_records if r.doctor_id]
    hospital_ids = [r.hospital_id for r in recent_records if r.hospital_id]
    doctors_map = {d.id: d.name for d in db.query(Doctor).filter(Doctor.id.in_(doctor_ids)).all()} if doctor_ids else {}
    hospitals_map = {h.id: h.name for h in db.query(Hospital).filter(Hospital.id.in_(hospital_ids)).all()} if hospital_ids else {}

    recent_interactions = []
    for r in recent_records:
        recent_interactions.append({
            "id": r.id,
            "doctor_name": doctors_map.get(r.doctor_id),
            "hospital_name": hospitals_map.get(r.hospital_id),
            "visit_date": str(r.visit_date) if r.visit_date else None,
            "summary": r.summary,
        })

    return {
        "kols_count": kols_count,
        "customer_count": customer_count,
        "interactions_count": interactions_count,
        "recent_interactions": recent_interactions,
    }


# ──────────────────────────────────────────────
# 客户列表
# ──────────────────────────────────────────────

def get_customers(db: Session, tenant_id: str, user_id: int, page: int = 1, page_size: int = 20) -> dict:
    """客户列表：医生 + 拜访次数 + 最近拜访 + 医院名 + 反馈情感"""
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    # 子查询：每个医生的拜访次数与最近拜访日期
    visit_stats = db.query(
        VisitRecord.doctor_id.label("did"),
        func.count(VisitRecord.id).label("visit_count"),
        func.max(VisitRecord.visit_date).label("last_visit_date"),
    ).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id == user_id,
        VisitRecord.doctor_id.isnot(None),
    ).group_by(VisitRecord.doctor_id).subquery()

    # 基础查询：Doctor + 医院 + 拜访统计
    base_q = db.query(
        Doctor, Hospital, visit_stats.c.visit_count, visit_stats.c.last_visit_date,
    ).join(visit_stats, visit_stats.c.did == Doctor.id
    ).outerjoin(Hospital, Hospital.id == Doctor.hospital_id
    ).filter(
        Doctor.tenant_id == tenant_id,
        Doctor.is_deleted == 0,
    )

    total = base_q.count()
    rows = base_q.order_by(visit_stats.c.last_visit_date.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # 拉取这些医生的最新反馈情感
    doctor_ids = [row[0].id for row in rows]
    feedbacks_map = {}
    if doctor_ids:
        # 通过 record_id join VisitRecord 找到 doctor_id
        fb_rows = db.query(
            VisitRecord.doctor_id, VisitFeedback.sentiment,
        ).join(VisitFeedback, VisitFeedback.record_id == VisitRecord.id
        ).filter(
            VisitRecord.tenant_id == tenant_id,
            VisitRecord.is_deleted == 0,
            VisitRecord.user_id == user_id,
            VisitRecord.doctor_id.in_(doctor_ids),
            VisitFeedback.is_deleted == 0,
        ).order_by(VisitFeedback.id.desc()).all()
        # 取每个医生最新一条反馈情感
        for did, sentiment in fb_rows:
            if did not in feedbacks_map:
                feedbacks_map[did] = sentiment

    items = []
    for doctor, hospital, visit_count, last_visit_date in rows:
        items.append({
            "id": doctor.id,
            "name": doctor.name,
            "department": doctor.department,
            "title": doctor.title,
            "phone": doctor.phone,
            "hospital_id": doctor.hospital_id,
            "hospital_name": hospital.name if hospital else None,
            "visit_count": visit_count or 0,
            "last_visit_date": str(last_visit_date) if last_visit_date else None,
            "sentiment": feedbacks_map.get(doctor.id),
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ──────────────────────────────────────────────
# 互动列表
# ──────────────────────────────────────────────

def get_interactions(db: Session, tenant_id: str, user_id: int, page: int = 1, page_size: int = 20) -> dict:
    """互动列表：拜访记录 + 医生名 + 医院名 + 产品名 + 情感"""
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    base_q = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id == user_id,
    )
    total = base_q.count()
    records = base_q.order_by(VisitRecord.visit_date.desc()).offset((page - 1) * page_size).limit(page_size).all()

    doctor_ids = [r.doctor_id for r in records if r.doctor_id]
    hospital_ids = [r.hospital_id for r in records if r.hospital_id]
    product_ids = [r.product_id for r in records if r.product_id]
    record_ids = [r.id for r in records]

    doctors_map = {d.id: d.name for d in db.query(Doctor).filter(Doctor.id.in_(doctor_ids)).all()} if doctor_ids else {}
    hospitals_map = {h.id: h.name for h in db.query(Hospital).filter(Hospital.id.in_(hospital_ids)).all()} if hospital_ids else {}
    products_map = {p.id: p.name for p in db.query(Product).filter(Product.id.in_(product_ids)).all()} if product_ids else {}

    feedbacks_map = {}
    if record_ids:
        fb_rows = db.query(VisitFeedback).filter(
            VisitFeedback.record_id.in_(record_ids),
            VisitFeedback.is_deleted == 0,
        ).order_by(VisitFeedback.id.desc()).all()
        for fb in fb_rows:
            if fb.record_id not in feedbacks_map:
                feedbacks_map[fb.record_id] = fb.sentiment

    items = []
    for r in records:
        items.append({
            "id": r.id,
            "doctor_id": r.doctor_id,
            "doctor_name": doctors_map.get(r.doctor_id),
            "hospital_id": r.hospital_id,
            "hospital_name": hospitals_map.get(r.hospital_id),
            "product_id": r.product_id,
            "product_name": products_map.get(r.product_id),
            "visit_date": str(r.visit_date) if r.visit_date else None,
            "visit_type": r.visit_type,
            "duration_minutes": r.duration_minutes,
            "summary": r.summary,
            "status": r.status,
            "sentiment": feedbacks_map.get(r.id),
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ──────────────────────────────────────────────
# 客户详情
# ──────────────────────────────────────────────

def _parse_date(s):
    """解析 YYYY-MM-DD 日期字符串"""
    if not s:
        return None
    try:
        return datetime.strptime(str(s), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def get_customer_detail(db: Session, tenant_id: str, customer_id: int) -> dict:
    """客户详情：医生信息 + 医院名 + 拜访次数 + 最近拜访 + 最新反馈情感"""
    doctor = db.query(Doctor).filter(
        Doctor.id == customer_id,
        Doctor.tenant_id == tenant_id,
        Doctor.is_deleted == 0,
    ).first()
    if not doctor:
        return None

    hospital = db.query(Hospital).filter(
        Hospital.id == doctor.hospital_id,
        Hospital.is_deleted == 0,
    ).first()

    visit_count = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.doctor_id == customer_id,
    ).count()

    last_visit = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.doctor_id == customer_id,
    ).order_by(VisitRecord.visit_date.desc()).first()

    # 最新反馈情感
    latest_feedback = db.query(VisitFeedback).join(
        VisitRecord, VisitRecord.id == VisitFeedback.record_id,
    ).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.doctor_id == customer_id,
        VisitFeedback.is_deleted == 0,
    ).order_by(VisitFeedback.id.desc()).first()

    return {
        "id": doctor.id,
        "name": doctor.name,
        "department": doctor.department,
        "title": doctor.title,
        "phone": doctor.phone,
        "hospital_id": doctor.hospital_id,
        "hospital_name": hospital.name if hospital else None,
        "visit_count": visit_count,
        "last_visit_date": str(last_visit.visit_date) if last_visit and last_visit.visit_date else None,
        "sentiment": latest_feedback.sentiment if latest_feedback else None,
    }


# ──────────────────────────────────────────────
# 记录互动
# ──────────────────────────────────────────────

def create_interaction(db: Session, tenant_id: str, user_id: int, data: dict) -> dict:
    """记录互动：创建一条拜访记录"""
    record = VisitRecord(
        tenant_id=tenant_id,
        user_id=user_id,
        hospital_id=data.get("hospital_id"),
        doctor_id=data.get("doctor_id"),
        product_id=data.get("product_id"),
        visit_date=_parse_date(data.get("visit_date")),
        visit_type=data.get("visit_type", "academic"),
        duration_minutes=data.get("duration_minutes", 30),
        location=data.get("location"),
        summary=data.get("summary"),
        status=data.get("status", "completed"),
        created_by=user_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "id": record.id,
        "doctor_id": record.doctor_id,
        "hospital_id": record.hospital_id,
        "product_id": record.product_id,
        "visit_date": str(record.visit_date) if record.visit_date else None,
        "visit_type": record.visit_type,
        "duration_minutes": record.duration_minutes,
        "summary": record.summary,
        "status": record.status,
    }


# ──────────────────────────────────────────────
# KOL 列表
# ──────────────────────────────────────────────

def list_kols(db: Session, tenant_id: str) -> dict:
    """KOL 列表：被拜访 >= 2 次的医生"""
    visit_counts = db.query(
        VisitRecord.doctor_id,
        func.count(VisitRecord.id).label("cnt"),
    ).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.doctor_id.isnot(None),
    ).group_by(VisitRecord.doctor_id).having(func.count(VisitRecord.id) >= 2).all()

    doctor_ids = [row.doctor_id for row in visit_counts]
    visit_map = {row.doctor_id: row.cnt for row in visit_counts}

    if not doctor_ids:
        return {"items": [], "total": 0}

    rows = db.query(Doctor, Hospital).outerjoin(
        Hospital, Hospital.id == Doctor.hospital_id,
    ).filter(
        Doctor.id.in_(doctor_ids),
        Doctor.tenant_id == tenant_id,
        Doctor.is_deleted == 0,
    ).all()

    items = []
    for doctor, hospital in rows:
        items.append({
            "id": doctor.id,
            "name": doctor.name,
            "department": doctor.department,
            "title": doctor.title,
            "hospital_name": hospital.name if hospital else None,
            "visit_count": visit_map.get(doctor.id, 0),
        })

    return {"items": items, "total": len(items)}
