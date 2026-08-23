"""会议论坛 API - 会议/话题管理"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.response import unified_response
from middleware.auth import get_current_user
from database import User, get_db
from services import cfm_service
from .schemas import CreateMeetingRequest, UpdateMeetingRequest, CreateTopicRequest

router = APIRouter(prefix="/cfm")


@router.get("/overview")
async def cfm_overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """CFM 总览：会议数、话题数、即将开始的会议、热门话题"""
    return unified_response(cfm_service.get_overview(db, user.tenant_id))


@router.get("/meetings")
async def cfm_meetings(
    status: str = Query(None),
    meeting_type: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """会议列表：支持按状态、类型过滤"""
    return unified_response(cfm_service.get_meetings(db, user.tenant_id, status, meeting_type, page, page_size))


@router.get("/topics")
async def cfm_topics(
    category: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """论坛话题列表：支持按分类过滤"""
    return unified_response(cfm_service.get_topics(db, user.tenant_id, category, page, page_size))


@router.post("/meetings")
async def create_meeting(req: CreateMeetingRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建会议"""
    return unified_response(cfm_service.create_meeting(db, user.tenant_id, user.id, req.dict(exclude_unset=True)))


@router.put("/meetings/{meeting_id}")
async def update_meeting(meeting_id: int, req: UpdateMeetingRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新会议"""
    result = cfm_service.update_meeting(db, user.tenant_id, meeting_id, req.dict(exclude_unset=True))
    if result is None:
        return unified_response(None, code=40004, message="会议不存在")
    return unified_response(result)


@router.post("/topics")
async def create_topic(req: CreateTopicRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """发起论坛话题"""
    return unified_response(cfm_service.create_topic(db, user.tenant_id, user.id, req.dict(exclude_unset=True)))


@router.post("/ai-insights")
async def cfm_ai_insights(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """AI 会议论坛洞察"""
    from services.ai_insight_service import ai_insight_service
    result = ai_insight_service.get_cached_insight(domain="cfm", tenant_id=user.tenant_id, user_id=user.id, db=db)
    return unified_response(result)
