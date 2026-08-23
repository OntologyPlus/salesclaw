"""角色画像库服务（N+2 Step1）

管理 AI 角色画像，供 scenario-generator 剧本解析时自动匹配。
"""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import or_

from core.exceptions import NotFoundError, ValidationError
from core.pagination import PageParams, paginate
from database import PersonaLibrary

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 序列化
# ──────────────────────────────────────────────

def _serialize_persona(p: PersonaLibrary) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "priority": p.priority,
        "keywords": p.keywords or [],
        "exclusion_keywords": p.exclusion_keywords or [],
        "default_brief": p.default_brief,
        "persona_text": p.persona_text,
        "persona_type": p.persona_type,
        "is_active": p.is_active,
        "created_at": p.created_at.strftime("%Y-%m-%d %H:%M:%S") if p.created_at else None,
    }


# ──────────────────────────────────────────────
# CRUD
# ──────────────────────────────────────────────

def list_personas(db: Session, tenant_id: str, keyword: str = None,
                  persona_type: str = None, is_active: int = None,
                  page_params: PageParams = None) -> dict:
    """列表查询画像"""
    q = db.query(PersonaLibrary).filter(
        PersonaLibrary.tenant_id == tenant_id,
        PersonaLibrary.is_deleted == 0,
    )
    if keyword:
        q = q.filter(or_(
            PersonaLibrary.name.like(f"%{keyword}%"),
            PersonaLibrary.default_brief.like(f"%{keyword}%"),
        ))
    if persona_type:
        q = q.filter(PersonaLibrary.persona_type == persona_type)
    if is_active is not None:
        q = q.filter(PersonaLibrary.is_active == is_active)
    total = q.count()
    q = q.order_by(PersonaLibrary.priority.desc(), PersonaLibrary.id.desc())
    if page_params:
        q = q.offset(page_params.offset()).limit(page_params.effective_page_size())
    items = q.all()
    return paginate([_serialize_persona(p) for p in items], total, page_params or PageParams())


def get_persona(db: Session, tenant_id: str, persona_id: int) -> dict:
    p = db.query(PersonaLibrary).filter(
        PersonaLibrary.tenant_id == tenant_id,
        PersonaLibrary.is_deleted == 0,
        PersonaLibrary.id == persona_id,
    ).first()
    if not p:
        raise NotFoundError("画像不存在")
    return _serialize_persona(p)


def create_persona(db: Session, tenant_id: str, data: dict) -> dict:
    name = data.get("name")
    if not name:
        raise ValidationError("name 不能为空")
    p = PersonaLibrary(
        tenant_id=tenant_id,
        name=name,
        priority=data.get("priority", 0),
        keywords=data.get("keywords") or [],
        exclusion_keywords=data.get("exclusion_keywords") or [],
        default_brief=data.get("default_brief"),
        persona_text=data.get("persona_text"),
        persona_type=data.get("persona_type", "customer"),
        is_active=data.get("is_active", 1),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _serialize_persona(p)


def update_persona(db: Session, tenant_id: str, persona_id: int, data: dict) -> dict:
    p = db.query(PersonaLibrary).filter(
        PersonaLibrary.tenant_id == tenant_id,
        PersonaLibrary.is_deleted == 0,
        PersonaLibrary.id == persona_id,
    ).first()
    if not p:
        raise NotFoundError("画像不存在")
    for field in ("name", "priority", "keywords", "exclusion_keywords",
                  "default_brief", "persona_text", "persona_type", "is_active"):
        if field in data and data[field] is not None:
            setattr(p, field, data[field])
    db.commit()
    db.refresh(p)
    return _serialize_persona(p)


def delete_persona(db: Session, tenant_id: str, persona_id: int) -> None:
    p = db.query(PersonaLibrary).filter(
        PersonaLibrary.tenant_id == tenant_id,
        PersonaLibrary.is_deleted == 0,
        PersonaLibrary.id == persona_id,
    ).first()
    if not p:
        raise NotFoundError("画像不存在")
    p.is_deleted = 1
    db.commit()


# ──────────────────────────────────────────────
# 匹配（供 scenario_parser 调用）
# ──────────────────────────────────────────────

def match_persona(db: Session, tenant_id: str, raw_text: str) -> dict:
    """根据原始文本匹配优先级最高的画像

    规则：
    - 命中 exclusion_keywords 的画像排除
    - 按命中 keywords 数量 * (priority+1) 加权排序
    - 无命中返回 None
    """
    if not raw_text:
        return None
    personas = db.query(PersonaLibrary).filter(
        PersonaLibrary.tenant_id == tenant_id,
        PersonaLibrary.is_deleted == 0,
        PersonaLibrary.is_active == 1,
    ).all()
    best, best_score = None, 0
    for p in personas:
        # 排除词命中则跳过
        if any(kw in raw_text for kw in (p.exclusion_keywords or [])):
            continue
        # 计算命中关键词数
        hit = sum(1 for kw in (p.keywords or []) if kw in raw_text)
        if hit == 0:
            continue
        score = hit * (p.priority + 1)
        if score > best_score:
            best, best_score = p, score
    return _serialize_persona(best) if best else None
