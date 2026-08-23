"""主数据 API - 医院/医生/产品/区域管理"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.response import unified_response
from middleware.auth import get_current_user
from database import User, get_db
from services import mdm_service

from .schemas import CreateRuleRequest

router = APIRouter(prefix="/mdm")


@router.get("/hospitals")
async def list_hospitals(
    keyword: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """医院列表：支持按名称/编码/城市搜索"""
    return unified_response(mdm_service.get_hospitals(db, user.tenant_id, keyword, page, page_size))


@router.get("/doctors")
async def list_doctors(
    keyword: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """医生列表：支持按姓名/科室/职称搜索，含医院名"""
    return unified_response(mdm_service.get_doctors(db, user.tenant_id, keyword, page, page_size))


@router.get("/products")
async def list_products(
    keyword: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """产品列表：支持按名称/编码/分类搜索"""
    return unified_response(mdm_service.get_products(db, user.tenant_id, keyword, page, page_size))


@router.get("/zones")
async def list_zones(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """区域列表"""
    return unified_response(mdm_service.get_zones(db, user.tenant_id, page, page_size))


@router.get("/rules")
async def list_rules(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """数据质量规则列表"""
    return unified_response(mdm_service.list_rules(db, user.tenant_id))


@router.post("/rules")
async def create_rule(req: CreateRuleRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建数据质量规则"""
    return unified_response(mdm_service.create_rule(db, user.tenant_id, req.dict(exclude_unset=True)))


@router.post("/ai-insights")
async def mdm_ai_insights(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """AI 数据治理洞察"""
    from services.ai_insight_service import ai_insight_service
    result = ai_insight_service.get_cached_insight(domain="mdm", tenant_id=user.tenant_id, user_id=user.id, db=db)
    return unified_response(result)
