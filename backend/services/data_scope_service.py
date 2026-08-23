"""数据范围权限服务（N+3 Step5）

基于角色 data_scope 字段过滤查询数据。
data_scope 结构：{"type": "all" | "products" | "activities", "ids": [int]}
"""
import logging
from sqlalchemy.orm import Session

from database import Role, UserRole

logger = logging.getLogger(__name__)


def get_user_data_scope(db: Session, tenant_id: str, user_id: int) -> dict:
    """获取用户的数据范围配置

    优先取用户第一个角色的 data_scope；无角色则默认 all。
    """
    user_role = db.query(UserRole).filter(
        UserRole.tenant_id == tenant_id,
        UserRole.is_deleted == 0,
        UserRole.user_id == user_id,
    ).first()
    if not user_role:
        return {"type": "all", "ids": []}
    role = db.query(Role).filter(
        Role.tenant_id == tenant_id,
        Role.is_deleted == 0,
        Role.id == user_role.role_id,
    ).first()
    if not role or not role.data_scope:
        return {"type": "all", "ids": []}
    ds = role.data_scope if isinstance(role.data_scope, dict) else {"type": "all", "ids": []}
    ds.setdefault("ids", [])
    return ds


def apply_product_scope(query, db: Session, tenant_id: str, user_id: int, product_column):
    """对带 product_id 的查询应用数据范围过滤

    Args:
        query: SQLAlchemy query
        product_column: 模型的 product_id 列对象
    Returns:
        过滤后的 query
    """
    ds = get_user_data_scope(db, tenant_id, user_id)
    if ds.get("type") == "all":
        return query
    if ds.get("type") == "products" and ds.get("ids"):
        return query.filter(product_column.in_(ds["ids"]))
    # activities 类型不适用于 product 过滤，返回原查询
    return query


def apply_activity_scope(query, db: Session, tenant_id: str, user_id: int, activity_column):
    """对带 activity_id 的查询应用数据范围过滤"""
    ds = get_user_data_scope(db, tenant_id, user_id)
    if ds.get("type") == "all":
        return query
    if ds.get("type") == "activities" and ds.get("ids"):
        return query.filter(activity_column.in_(ds["ids"]))
    return query


def can_access_product(db: Session, tenant_id: str, user_id: int, product_id: int) -> bool:
    """校验用户能否访问指定品种"""
    ds = get_user_data_scope(db, tenant_id, user_id)
    if ds.get("type") == "all":
        return True
    if ds.get("type") == "products":
        return product_id in (ds.get("ids") or [])
    return True


def can_access_activity(db: Session, tenant_id: str, user_id: int, activity_id: int) -> bool:
    """校验用户能否访问指定活动"""
    ds = get_user_data_scope(db, tenant_id, user_id)
    if ds.get("type") == "all":
        return True
    if ds.get("type") == "activities":
        return activity_id in (ds.get("ids") or [])
    return True
