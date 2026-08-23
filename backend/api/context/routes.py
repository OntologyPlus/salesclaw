"""全局上下文 API - 路由定义（N+3 ContextSwitcher 后端）"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, User
from core.response import unified_response
from middleware.auth import get_current_user
from services import context_service

router = APIRouter(prefix="/context")


class ContextUpdateRequest(BaseModel):
    scope_type: Optional[str] = None
    scope_id: Optional[int] = None
    scope_label: Optional[str] = None
    period_type: Optional[str] = None
    period_end: Optional[str] = None
    perspective: Optional[str] = None


@router.get("")
async def get_context(user: User = Depends(get_current_user)):
    """获取当前全局上下文"""
    return unified_response(context_service.get_context(user.id))


@router.put("")
async def set_context(req: ContextUpdateRequest, user: User = Depends(get_current_user)):
    """更新全局上下文（切换空间/时间/视角维度）"""
    return unified_response(context_service.set_context(user.id, req.dict(exclude_unset=True)))


@router.get("/overview")
async def context_overview(
    scope_id: Optional[int] = None,
    period_end: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """带时间游标的决策总览（period_end 设置时按历史截止点重算）"""
    return unified_response(context_service.get_period_aware_overview(
        db, user.tenant_id, user.id, scope_id=scope_id, period_end=period_end,
    ))


@router.get("/perspective")
async def perspective_data(
    perspective: str = "management",
    scope_id: Optional[int] = None,
    period_end: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """按视角返回看板数据（management/customer_development/report）"""
    return unified_response(context_service.get_perspective_data(
        db, user.tenant_id, user.id, perspective, scope_id=scope_id, period_end=period_end,
    ))


@router.get("/insight")
async def context_insight(
    domain: str = "sales",
    period_end: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询洞察缓存（按 period_end 双键）"""
    return unified_response(context_service.get_insight_with_period(
        db, user.tenant_id, user.id, domain, period_end=period_end,
    ))
