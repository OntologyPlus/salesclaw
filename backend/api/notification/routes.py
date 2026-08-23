"""通知中心 API - 规则管理 + 发送记录 + 失败导出"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from core.response import unified_response
from core.pagination import PageParams
from middleware.auth import get_current_user
from database import get_db, User
from services import notification_service
from .schemas import RuleCreateRequest, RuleStatusRequest

router = APIRouter(prefix="/notifications")


# ──────────────────────────────────────────────
# 规则管理
# ──────────────────────────────────────────────

@router.post("/rules")
async def create_rule(req: RuleCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建通知催促规则"""
    return unified_response(notification_service.create_rule(db, user.tenant_id, req.model_dump()))


@router.get("/rules")
async def list_rules(
    activity_id: Optional[int] = None,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """规则列表"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(notification_service.list_rules(db, user.tenant_id, activity_id, keyword, params))


@router.patch("/rules/{rule_id}/status")
async def update_rule_status(rule_id: int, req: RuleStatusRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """启停规则"""
    return unified_response(notification_service.update_rule_status(db, user.tenant_id, rule_id, req.enabled))


# ──────────────────────────────────────────────
# 发送记录
# ──────────────────────────────────────────────

@router.get("/batches")
async def list_batches(
    rule_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """发送记录列表"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(notification_service.list_batches(db, user.tenant_id, rule_id, params))


@router.get("/batches/{batch_id}")
async def get_batch(batch_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """批次详情（含 recipients 明细）"""
    return unified_response(notification_service.get_batch(db, user.tenant_id, batch_id))


@router.get("/batches/{batch_id}/export-failed")
async def export_failed(batch_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """导出失败名单 CSV"""
    csv_str = notification_service.export_failed(db, user.tenant_id, batch_id)
    return Response(content=csv_str, media_type="text/csv", headers={
        "Content-Disposition": f"attachment; filename=failed_batch_{batch_id}.csv"
    })
