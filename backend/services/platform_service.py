"""平台管理服务层

提供租户总览、用户列表、角色列表能力。
数据来源：Tenant + User + Role + SessionRecord。
"""
from datetime import datetime
from sqlalchemy.orm import Session

from database import Tenant, User, Role, SessionRecord


# ──────────────────────────────────────────────
# 平台总览
# ──────────────────────────────────────────────

def get_overview(db: Session, tenant_id: str) -> dict:
    """平台总览：租户信息 + 用户数 + 角色数 + 活跃会话数"""
    tenant = db.query(Tenant).filter(Tenant.id == int(tenant_id)).first()

    users_count = db.query(User).filter(
        User.tenant_id == tenant_id,
        User.is_deleted == 0,
    ).count()

    roles_count = db.query(Role).filter(
        Role.tenant_id == tenant_id,
        Role.is_deleted == 0,
    ).count()

    now = datetime.utcnow()
    active_sessions = db.query(SessionRecord).filter(
        SessionRecord.tenant_id == tenant_id,
        SessionRecord.is_deleted == 0,
        SessionRecord.expires_at > now,
    ).count()

    return {
        "tenant": {
            "id": tenant.id if tenant else None,
            "name": tenant.name if tenant else None,
            "code": tenant.code if tenant else None,
            "created_at": tenant.created_at.strftime("%Y-%m-%d %H:%M:%S") if tenant and tenant.created_at else None,
        },
        "users_count": users_count,
        "roles_count": roles_count,
        "active_sessions": active_sessions,
    }


# ──────────────────────────────────────────────
# 用户列表
# ──────────────────────────────────────────────

def get_users(db: Session, tenant_id: str, page: int = 1, page_size: int = 20) -> dict:
    """用户列表"""
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    q = db.query(User).filter(
        User.tenant_id == tenant_id,
        User.is_deleted == 0,
    )
    total = q.count()
    users = q.order_by(User.id.asc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for u in users:
        items.append({
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "email": u.email,
            "role_id": u.role_id,
            "is_active": u.is_active,
            "last_login_at": u.last_login_at.strftime("%Y-%m-%d %H:%M:%S") if u.last_login_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ──────────────────────────────────────────────
# 角色列表
# ──────────────────────────────────────────────

def get_roles(db: Session, tenant_id: str) -> dict:
    """角色列表"""
    roles = db.query(Role).filter(
        Role.tenant_id == tenant_id,
        Role.is_deleted == 0,
    ).order_by(Role.id.asc()).all()

    items = []
    for r in roles:
        items.append({
            "id": r.id,
            "name": r.name,
            "code": r.code,
            "permissions": r.permissions or [],
        })

    return {"items": items, "total": len(items)}


# ──────────────────────────────────────────────
# 平台配置（基于 Tenant.settings JSON 字段）
# ──────────────────────────────────────────────

_DEFAULT_CONFIGS = {
    "ai_proactive_mode": "balanced",
    "max_concurrent_sessions": 10,
    "data_retention_days": 90,
    "enable_audit_log": True,
}


def list_configs(db: Session, tenant_id: str) -> dict:
    """配置列表：读取租户配置，合并默认值"""
    tenant = db.query(Tenant).filter(Tenant.id == int(tenant_id)).first()
    configs = dict(_DEFAULT_CONFIGS)
    if tenant and tenant.settings:
        configs.update(tenant.settings)
    items = [{"key": k, "value": v} for k, v in configs.items()]
    return {"items": items, "total": len(items)}


def update_config(db: Session, tenant_id: str, key: str, value) -> dict:
    """更新配置：写入租户 settings JSON 字段"""
    tenant = db.query(Tenant).filter(Tenant.id == int(tenant_id)).first()
    if not tenant:
        return None
    configs = dict(tenant.settings) if tenant.settings else {}
    configs[key] = value
    tenant.settings = configs
    db.commit()
    return {"key": key, "value": value}
