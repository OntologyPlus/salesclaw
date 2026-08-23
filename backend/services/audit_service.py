"""审计服务层

提供审计日志列表、审计总览能力。
数据来源：AuditLog。
"""
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import AuditLog


# ──────────────────────────────────────────────
# 审计总览
# ──────────────────────────────────────────────

def get_overview(db: Session, tenant_id: str) -> dict:
    """审计总览：总日志数、今日日志数、Top Actions"""
    total_logs = db.query(AuditLog).filter(
        AuditLog.tenant_id == tenant_id,
        AuditLog.is_deleted == 0,
    ).count()

    today = datetime.utcnow().date()
    today_start = datetime(today.year, today.month, today.day)
    today_logs = db.query(AuditLog).filter(
        AuditLog.tenant_id == tenant_id,
        AuditLog.is_deleted == 0,
        AuditLog.ts >= today_start,
    ).count()

    # Top actions
    action_rows = db.query(
        AuditLog.action,
        func.count(AuditLog.id).label("cnt"),
    ).filter(
        AuditLog.tenant_id == tenant_id,
        AuditLog.is_deleted == 0,
    ).group_by(AuditLog.action).order_by(func.count(AuditLog.id).desc()).limit(10).all()

    top_actions = [{"action": row.action, "count": row.cnt} for row in action_rows]

    return {
        "total_logs": total_logs,
        "today_logs": today_logs,
        "top_actions": top_actions,
    }


# ──────────────────────────────────────────────
# 审计日志列表
# ──────────────────────────────────────────────

def get_logs(db: Session, tenant_id: str, action: str = None, actor_id: int = None,
             page: int = 1, page_size: int = 20) -> dict:
    """审计日志列表：支持按 action、actor_id 过滤，按时间倒序"""
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    q = db.query(AuditLog).filter(
        AuditLog.tenant_id == tenant_id,
        AuditLog.is_deleted == 0,
    )
    if action:
        q = q.filter(AuditLog.action == action)
    if actor_id is not None:
        q = q.filter(AuditLog.actor_id == actor_id)

    total = q.count()
    logs = q.order_by(AuditLog.ts.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for log in logs:
        items.append({
            "id": log.id,
            "actor_id": log.actor_id,
            "action": log.action,
            "target": log.target,
            "target_id": log.target_id,
            "detail": log.detail,
            "ts": log.ts.strftime("%Y-%m-%d %H:%M:%S") if log.ts else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ──────────────────────────────────────────────
# 导出审计日志
# ──────────────────────────────────────────────

def export_logs(db: Session, tenant_id: str, format: str = "json",
                action: str = None, actor_id: int = None) -> dict:
    """导出审计日志：支持 csv/json 格式，最多导出 10000 条"""
    q = db.query(AuditLog).filter(
        AuditLog.tenant_id == tenant_id,
        AuditLog.is_deleted == 0,
    )
    if action:
        q = q.filter(AuditLog.action == action)
    if actor_id is not None:
        q = q.filter(AuditLog.actor_id == actor_id)

    logs = q.order_by(AuditLog.ts.desc()).limit(10000).all()

    items = [{
        "id": log.id,
        "actor_id": log.actor_id,
        "action": log.action,
        "target": log.target,
        "target_id": log.target_id,
        "detail": log.detail,
        "ts": log.ts.strftime("%Y-%m-%d %H:%M:%S") if log.ts else None,
    } for log in logs]

    if format == "csv":
        import csv
        import io
        output = io.StringIO()
        if items:
            writer = csv.DictWriter(output, fieldnames=list(items[0].keys()))
            writer.writeheader()
            writer.writerows(items)
        return {"format": "csv", "content": output.getvalue(), "total": len(items)}

    return {"format": "json", "items": items, "total": len(items)}


# ──────────────────────────────────────────────
# 审计统计
# ──────────────────────────────────────────────

def get_stats(db: Session, tenant_id: str, dimension: str = "action") -> dict:
    """审计统计：按 action/actor 聚合，返回 Top 20"""
    if dimension == "actor":
        rows = db.query(
            AuditLog.actor_id,
            func.count(AuditLog.id).label("cnt"),
        ).filter(
            AuditLog.tenant_id == tenant_id,
            AuditLog.is_deleted == 0,
        ).group_by(AuditLog.actor_id).order_by(func.count(AuditLog.id).desc()).limit(20).all()
        items = [{"actor_id": row.actor_id, "count": row.cnt} for row in rows]
    else:
        rows = db.query(
            AuditLog.action,
            func.count(AuditLog.id).label("cnt"),
        ).filter(
            AuditLog.tenant_id == tenant_id,
            AuditLog.is_deleted == 0,
        ).group_by(AuditLog.action).order_by(func.count(AuditLog.id).desc()).limit(20).all()
        items = [{"action": row.action, "count": row.cnt} for row in rows]

    return {"dimension": dimension, "items": items}
