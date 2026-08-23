"""主数据服务层

提供医院、医生、产品、区域列表查询能力。
数据来源：Hospital + Doctor + Product + Zone。
"""
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import Hospital, Doctor, Product, Zone


# ──────────────────────────────────────────────
# 医院列表
# ──────────────────────────────────────────────

def get_hospitals(db: Session, tenant_id: str, keyword: str = None,
                  page: int = 1, page_size: int = 20) -> dict:
    """医院列表：支持按名称/编码/城市搜索"""
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    q = db.query(Hospital).filter(
        Hospital.tenant_id == tenant_id,
        Hospital.is_deleted == 0,
    )
    if keyword:
        kw = f"%{keyword}%"
        q = q.filter(or_(
            Hospital.name.like(kw),
            Hospital.code.like(kw),
            Hospital.city.like(kw),
        ))

    total = q.count()
    hospitals = q.order_by(Hospital.id.asc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": [_serialize_hospital(h) for h in hospitals],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ──────────────────────────────────────────────
# 医生列表
# ──────────────────────────────────────────────

def get_doctors(db: Session, tenant_id: str, keyword: str = None,
                page: int = 1, page_size: int = 20) -> dict:
    """医生列表：支持按姓名/科室/职称搜索，含医院名"""
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    q = db.query(Doctor, Hospital).outerjoin(
        Hospital, Hospital.id == Doctor.hospital_id,
    ).filter(
        Doctor.tenant_id == tenant_id,
        Doctor.is_deleted == 0,
    )
    if keyword:
        kw = f"%{keyword}%"
        q = q.filter(or_(
            Doctor.name.like(kw),
            Doctor.department.like(kw),
            Doctor.title.like(kw),
        ))

    total = q.count()
    rows = q.order_by(Doctor.id.asc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for doctor, hospital in rows:
        items.append({
            "id": doctor.id,
            "name": doctor.name,
            "hospital_id": doctor.hospital_id,
            "hospital_name": hospital.name if hospital else None,
            "department": doctor.department,
            "title": doctor.title,
            "phone": doctor.phone,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ──────────────────────────────────────────────
# 产品列表
# ──────────────────────────────────────────────

def get_products(db: Session, tenant_id: str, keyword: str = None,
                 page: int = 1, page_size: int = 20) -> dict:
    """产品列表：支持按名称/编码/分类搜索"""
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    q = db.query(Product).filter(
        Product.tenant_id == tenant_id,
        Product.is_deleted == 0,
    )
    if keyword:
        kw = f"%{keyword}%"
        q = q.filter(or_(
            Product.name.like(kw),
            Product.code.like(kw),
            Product.category.like(kw),
        ))

    total = q.count()
    products = q.order_by(Product.id.asc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": [_serialize_product(p) for p in products],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ──────────────────────────────────────────────
# 区域列表
# ──────────────────────────────────────────────

def get_zones(db: Session, tenant_id: str, page: int = 1, page_size: int = 20) -> dict:
    """区域列表"""
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    q = db.query(Zone).filter(
        Zone.tenant_id == tenant_id,
        Zone.is_deleted == 0,
    )
    total = q.count()
    zones = q.order_by(Zone.id.asc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": [_serialize_zone(z) for z in zones],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ──────────────────────────────────────────────
# 序列化辅助
# ──────────────────────────────────────────────

def _serialize_hospital(h: Hospital) -> dict:
    return {
        "id": h.id,
        "name": h.name,
        "code": h.code,
        "level": h.level,
        "province": h.province,
        "city": h.city,
        "district": h.district,
        "address": h.address,
    }


def _serialize_product(p: Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "code": p.code,
        "category": p.category,
        "specifications": p.specifications,
        "manufacturer": p.manufacturer,
    }


def _serialize_zone(z: Zone) -> dict:
    return {
        "id": z.id,
        "name": z.name,
        "code": z.code,
        "parent_id": z.parent_id,
        "level": z.level,
    }


# ──────────────────────────────────────────────
# 数据质量规则（内存预设，无对应数据库模型）
# ──────────────────────────────────────────────

_MDM_RULES = [
    {
        "id": 1,
        "name": "医生姓名非空",
        "domain": "doctor",
        "field": "name",
        "rule_type": "not_null",
        "severity": "high",
        "is_active": 1,
    },
    {
        "id": 2,
        "name": "医院编码唯一",
        "domain": "hospital",
        "field": "code",
        "rule_type": "unique",
        "severity": "medium",
        "is_active": 1,
    },
    {
        "id": 3,
        "name": "产品分类有效",
        "domain": "product",
        "field": "category",
        "rule_type": "enum",
        "severity": "low",
        "is_active": 1,
    },
    {
        "id": 4,
        "name": "医生手机号格式校验",
        "domain": "doctor",
        "field": "phone",
        "rule_type": "format",
        "severity": "low",
        "is_active": 0,
    },
]

_next_rule_id = 5


def list_rules(db: Session, tenant_id: str) -> dict:
    """数据质量规则列表"""
    return {"items": list(_MDM_RULES), "total": len(_MDM_RULES)}


def create_rule(db: Session, tenant_id: str, data: dict) -> dict:
    """创建数据质量规则（内存存储）"""
    global _next_rule_id
    rule = {
        "id": _next_rule_id,
        "name": data.get("name"),
        "domain": data.get("domain", "general"),
        "field": data.get("field"),
        "rule_type": data.get("rule_type", "not_null"),
        "severity": data.get("severity", "medium"),
        "is_active": data.get("is_active", 1),
    }
    _MDM_RULES.append(rule)
    _next_rule_id += 1
    return rule
