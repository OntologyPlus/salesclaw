"""数据流追踪服务 — 记录并查询数据从哪来、到哪去、影响了谁

N+4 高内聚低耦合：作为独立服务实现 DataLineageServicePort，
其他域通过 registry.get(DataLineageServicePort) 调用，不直接 import。
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from database import DataLineage


def record_lineage(db: Session, source: dict, target: dict,
                  transformation: str, user_id: int = None,
                  tenant_id: str = None) -> int:
    """记录一次数据流动

    Args:
        source: {type, id, value?}
        target: {type, id, field?, value?}
        transformation: 如 'ability_score_updated' / 'insight_generated_from'
        user_id: 关联用户 ID（可选）
        tenant_id: 租户 ID

    Returns:
        新建的 DataLineage 记录 ID
    """
    record = DataLineage(
        tenant_id=str(tenant_id) if tenant_id else "default",
        source_type=source.get("type"),
        source_id=source.get("id"),
        target_type=target.get("type"),
        target_id=target.get("id"),
        transformation=transformation,
        payload={"source": source, "target": target},
        user_id=user_id,
        occurred_at=datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record.id


def trace_upstream(db: Session, target_type: str, target_id: int) -> list[dict]:
    """追溯数据来源（向上）

    Args:
        target_type: 目标类型（如 'insight' / 'ability_profile'）
        target_id: 目标 ID

    Returns:
        上游 lineage 记录列表（按时间倒序）
    """
    rows = db.query(DataLineage).filter(
        DataLineage.target_type == target_type,
        DataLineage.target_id == target_id,
        DataLineage.is_deleted == 0,
    ).order_by(DataLineage.occurred_at.desc()).all()
    return [_to_dict(r) for r in rows]


def trace_downstream(db: Session, source_type: str, source_id: int) -> list[dict]:
    """追溯数据下游（向下）

    Args:
        source_type: 源类型（如 'collection' / 'training'）
        source_id: 源 ID

    Returns:
        下游 lineage 记录列表（按时间倒序）
    """
    rows = db.query(DataLineage).filter(
        DataLineage.source_type == source_type,
        DataLineage.source_id == source_id,
        DataLineage.is_deleted == 0,
    ).order_by(DataLineage.occurred_at.desc()).all()
    return [_to_dict(r) for r in rows]


def get_impact_chain(db: Session, user_id: int, days: int = 7) -> list[dict]:
    """获取用户的影响链时间线

    Args:
        user_id: 用户 ID
        days: 时间窗口（天）

    Returns:
        影响链时间线列表（按时间倒序，最多 200 条）
    """
    since = datetime.utcnow() - timedelta(days=days)
    rows = db.query(DataLineage).filter(
        DataLineage.user_id == user_id,
        DataLineage.occurred_at >= since,
        DataLineage.is_deleted == 0,
    ).order_by(DataLineage.occurred_at.desc()).limit(200).all()
    return [_to_dict(r) for r in rows]


def _to_dict(r: DataLineage) -> dict:
    """将 DataLineage ORM 实例转为 dict"""
    return {
        "id": r.id,
        "source_type": r.source_type,
        "source_id": r.source_id,
        "target_type": r.target_type,
        "target_id": r.target_id,
        "transformation": r.transformation,
        "payload": r.payload or {},
        "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
    }


__all__ = [
    "record_lineage",
    "trace_upstream",
    "trace_downstream",
    "get_impact_chain",
]
