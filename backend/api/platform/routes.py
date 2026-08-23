"""平台管理 API - 租户/用户/角色管理"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.response import unified_response
from middleware.auth import get_current_user, require_permission
from database import User, get_db
from services import platform_service

from .schemas import UpdateConfigRequest

router = APIRouter(prefix="/platform")


@router.get("/overview")
async def platform_overview(user: User = Depends(require_permission("platform.read")), db: Session = Depends(get_db)):
    """平台总览：租户信息 + 用户数 + 角色数 + 活跃会话数"""
    return unified_response(platform_service.get_overview(db, user.tenant_id))


@router.get("/users")
async def platform_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("platform.read")),
    db: Session = Depends(get_db),
):
    """用户列表"""
    return unified_response(platform_service.get_users(db, user.tenant_id, page, page_size))


@router.get("/roles")
async def platform_roles(user: User = Depends(require_permission("platform.read")), db: Session = Depends(get_db)):
    """角色列表"""
    return unified_response(platform_service.get_roles(db, user.tenant_id))


@router.get("/configs")
async def list_configs(user: User = Depends(require_permission("platform.read")), db: Session = Depends(get_db)):
    """配置列表"""
    return unified_response(platform_service.list_configs(db, user.tenant_id))


@router.put("/configs/{key}")
async def update_config(key: str, req: UpdateConfigRequest, user: User = Depends(require_permission("platform.write")), db: Session = Depends(get_db)):
    """更新配置"""
    result = platform_service.update_config(db, user.tenant_id, key, req.value)
    if result is None:
        return unified_response(None, code=40004, message="租户不存在")
    return unified_response(result)


@router.post("/ai-insights")
async def platform_ai_insights(
    user: User = Depends(require_permission("platform.read")),
    db: Session = Depends(get_db),
):
    """AI 平台优化"""
    from services.ai_insight_service import ai_insight_service
    result = ai_insight_service.get_cached_insight(domain="platform", tenant_id=user.tenant_id, user_id=user.id, db=db)
    return unified_response(result)
