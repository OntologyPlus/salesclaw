"""综合能力画像 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db, User
from core.response import unified_response
from middleware.auth import get_current_user
from services import profile_service

router = APIRouter(prefix="/profile")


@router.get("/score")
async def comprehensive_score(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """综合能力评分（行为分×0.4 + 能力分×0.4 + 业绩分×0.2）"""
    return unified_response(
        profile_service.get_comprehensive_score(db, user.tenant_id, user.id)
    )


@router.get("/learning-needs")
async def learning_needs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """学习需求分析（推荐课程 + 异议关键词 + 薄弱点）"""
    return unified_response(
        profile_service.get_learning_needs(db, user.tenant_id, user.id)
    )


@router.get("/radar")
async def radar(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """雷达图数据（6 维度）"""
    return unified_response(
        profile_service.get_radar(db, user.tenant_id, user.id)
    )


@router.get("/full")
async def full_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """全息画像（基本信息 + 综合分 + 雷达图 + 学习需求 + 近期活动）"""
    return unified_response(
        profile_service.get_full_profile(db, user.tenant_id, user.id)
    )
