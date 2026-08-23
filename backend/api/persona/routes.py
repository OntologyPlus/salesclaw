"""角色画像库 API - 路由定义"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db, User
from core.response import unified_response
from core.pagination import PageParams
from middleware.auth import get_current_user
from services import persona_service

from .schemas import PersonaRequest, PersonaUpdateRequest, MatchRequest

router = APIRouter(prefix="/personas")


@router.get("")
async def list_personas(
    keyword: Optional[str] = None,
    persona_type: Optional[str] = None,
    is_active: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列表查询角色画像"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(persona_service.list_personas(
        db, user.tenant_id, keyword=keyword, persona_type=persona_type,
        is_active=is_active, page_params=params,
    ))


@router.post("")
async def create_persona(req: PersonaRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建角色画像"""
    return unified_response(persona_service.create_persona(db, user.tenant_id, req.dict()))


@router.get("/match")
async def match_persona(
    raw_text: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """根据文本匹配画像（供剧本解析调用）"""
    return unified_response(persona_service.match_persona(db, user.tenant_id, raw_text))


@router.get("/{persona_id}")
async def get_persona(persona_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取画像详情"""
    return unified_response(persona_service.get_persona(db, user.tenant_id, persona_id))


@router.put("/{persona_id}")
async def update_persona(persona_id: int, req: PersonaUpdateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新画像"""
    return unified_response(persona_service.update_persona(db, user.tenant_id, persona_id, req.dict(exclude_unset=True)))


@router.delete("/{persona_id}")
async def delete_persona(persona_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """删除画像（软删除）"""
    persona_service.delete_persona(db, user.tenant_id, persona_id)
    return unified_response({"deleted": True})
