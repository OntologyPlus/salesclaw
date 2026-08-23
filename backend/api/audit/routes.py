"""审计 API - 审计日志/总览"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.response import unified_response
from middleware.auth import get_current_user, require_permission
from database import User, get_db
from services import audit_service

router = APIRouter(prefix="/audit")


@router.get("/overview")
async def audit_overview(user: User = Depends(require_permission("audit.read")), db: Session = Depends(get_db)):
    """审计总览：总日志数、今日日志数、Top Actions"""
    return unified_response(audit_service.get_overview(db, user.tenant_id))


@router.get("/logs")
async def list_logs(
    action: str = Query(None),
    actor_id: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("audit.read")),
    db: Session = Depends(get_db),
):
    """审计日志列表：支持按 action、actor_id 过滤"""
    actor_id_int = None
    if actor_id:
        try:
            actor_id_int = int(actor_id)
        except (ValueError, TypeError):
            actor_id_int = None
    return unified_response(audit_service.get_logs(db, user.tenant_id, action, actor_id_int, page, page_size))


@router.get("/export")
async def export_logs(
    format: str = Query("json"),
    action: str = Query(None),
    actor_id: str = Query(None),
    user: User = Depends(require_permission("audit.read")),
    db: Session = Depends(get_db),
):
    """导出审计日志（支持 format=csv/json）"""
    actor_id_int = None
    if actor_id:
        try:
            actor_id_int = int(actor_id)
        except (ValueError, TypeError):
            actor_id_int = None
    return unified_response(audit_service.export_logs(db, user.tenant_id, format, action, actor_id_int))


@router.get("/stats")
async def audit_stats(
    dimension: str = Query("action"),
    user: User = Depends(require_permission("audit.read")),
    db: Session = Depends(get_db),
):
    """审计统计（按 action/actor 聚合）"""
    return unified_response(audit_service.get_stats(db, user.tenant_id, dimension))


@router.post("/ai-insights")
async def audit_ai_insights(
    user: User = Depends(require_permission("audit.read")),
    db: Session = Depends(get_db),
):
    """AI 审计洞察"""
    from services.ai_insight_service import ai_insight_service
    result = ai_insight_service.get_cached_insight(domain="audit", tenant_id=user.tenant_id, user_id=user.id, db=db)
    return unified_response(result)
