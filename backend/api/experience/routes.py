"""经验值 API - 路由定义"""
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db, User
from core.response import unified_response
from core.pagination import PageParams
from middleware.auth import get_current_user
from services import experience_service

router = APIRouter(prefix="/experience")


@router.get("/me")
async def my_points(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取我的经验值汇总"""
    return unified_response(experience_service.get_user_points(db, user.tenant_id, user.id))


@router.get("/me/history")
async def my_history(
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询我的经验值记录"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(experience_service.list_user_experience(db, user.tenant_id, user.id, params))


@router.get("/leaderboard")
async def leaderboard(
    year_month: Optional[str] = None,
    product_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """月度 Top20 排行榜"""
    return unified_response(experience_service.get_monthly_top20(db, user.tenant_id, year_month, product_id))
