"""客户关系 API - KOL/客户/互动管理"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.response import unified_response
from middleware.auth import get_current_user
from database import User, get_db
from services import crm_service

from .schemas import CreateInteractionRequest

router = APIRouter(prefix="/crm")


@router.get("/overview")
async def crm_overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """CRM 总览：KOL 数、客户数、互动数、最近互动"""
    return unified_response(crm_service.get_overview(db, user.tenant_id, user.id))


@router.get("/customers")
async def crm_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """客户列表：医生 + 拜访次数 + 最近拜访 + 医院 + 情感"""
    return unified_response(crm_service.get_customers(db, user.tenant_id, user.id, page, page_size))


@router.get("/interactions")
async def crm_interactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """互动列表：拜访记录 + 医生 + 医院 + 产品 + 情感"""
    return unified_response(crm_service.get_interactions(db, user.tenant_id, user.id, page, page_size))


@router.get("/customers/{customer_id}")
async def customer_detail(customer_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """客户详情"""
    result = crm_service.get_customer_detail(db, user.tenant_id, customer_id)
    if result is None:
        return unified_response(None, code=40004, message="客户不存在")
    return unified_response(result)


@router.post("/interactions")
async def create_interaction(req: CreateInteractionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """记录互动"""
    return unified_response(crm_service.create_interaction(db, user.tenant_id, user.id, req.dict(exclude_unset=True)))


@router.get("/kols")
async def list_kols(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """KOL 列表"""
    return unified_response(crm_service.list_kols(db, user.tenant_id))


@router.post("/ai-insights")
async def crm_ai_insights(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """AI 客户洞察"""
    from services.ai_insight_service import ai_insight_service
    result = ai_insight_service.get_cached_insight(domain="crm", tenant_id=user.tenant_id, user_id=user.id, db=db)
    return unified_response(result)
