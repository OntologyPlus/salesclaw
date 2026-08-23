"""培训活动 API - 活动编排 + 数据看板"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from core.response import unified_response
from core.pagination import PageParams
from middleware.auth import get_current_user
from database import get_db, User
from services import activity_service, activity_analytics_service
from .schemas import ActivityCreateRequest, ActivityUpdateRequest, AddScenariosRequest

router = APIRouter(prefix="/training/activities")


# ──────────────────────────────────────────────
# 活动 CRUD
# ──────────────────────────────────────────────

@router.post("")
async def create_activity(req: ActivityCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建培训活动"""
    return unified_response(activity_service.create_activity(db, user.tenant_id, req.model_dump()))


@router.get("")
async def list_activities(
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """活动列表"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(activity_service.list_activities(db, user.tenant_id, status, keyword, params))


@router.get("/{activity_id}")
async def get_activity(activity_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """活动详情"""
    return unified_response(activity_service.get_activity(db, user.tenant_id, activity_id))


@router.put("/{activity_id}")
async def update_activity(activity_id: int, req: ActivityUpdateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新活动（按状态矩阵校验可编辑字段）"""
    return unified_response(activity_service.update_activity(db, user.tenant_id, activity_id, req.model_dump(exclude_unset=True)))


# ──────────────────────────────────────────────
# 状态流转
# ──────────────────────────────────────────────

@router.post("/{activity_id}/publish")
async def publish_activity(activity_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """发布活动（draft → ongoing）"""
    return unified_response(activity_service.publish_activity(db, user.tenant_id, activity_id))


@router.post("/{activity_id}/end")
async def end_activity(activity_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """结束活动（ongoing → ended）"""
    return unified_response(activity_service.end_activity(db, user.tenant_id, activity_id))


@router.post("/{activity_id}/off-shelf")
async def off_shelf_activity(activity_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """下架活动（ended → off_shelf）"""
    return unified_response(activity_service.off_shelf_activity(db, user.tenant_id, activity_id))


# ──────────────────────────────────────────────
# 场景关联
# ──────────────────────────────────────────────

@router.get("/{activity_id}/scenarios")
async def list_scenarios(activity_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """活动关联场景列表"""
    return unified_response(activity_service.list_scenarios(db, user.tenant_id, activity_id))


@router.post("/{activity_id}/scenarios")
async def add_scenarios(activity_id: int, req: AddScenariosRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """添加场景到活动"""
    count = activity_service.add_scenarios(db, user.tenant_id, activity_id, req.scenario_ids)
    return unified_response({"added": count})


@router.delete("/{activity_id}/scenarios/{scenario_id}")
async def remove_scenario(activity_id: int, scenario_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """从活动移除场景"""
    count = activity_service.remove_scenarios(db, user.tenant_id, activity_id, [scenario_id])
    return unified_response({"removed": count})


# ──────────────────────────────────────────────
# 数据看板
# ──────────────────────────────────────────────

@router.get("/{activity_id}/analytics/summary")
async def analytics_summary(activity_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """KPI 概览"""
    return unified_response(activity_analytics_service.get_kpi_summary(db, user.tenant_id, activity_id))


@router.get("/{activity_id}/analytics/trend")
async def analytics_trend(
    activity_id: int,
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """每日训练趋势"""
    return unified_response(activity_analytics_service.get_trend(db, user.tenant_id, activity_id, days))


@router.get("/{activity_id}/analytics/department")
async def analytics_department(
    activity_id: int,
    keyword: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """按部门聚合"""
    return unified_response(activity_analytics_service.aggregate_by_department(db, user.tenant_id, activity_id, keyword))


@router.get("/{activity_id}/analytics/scenario")
async def analytics_scenario(
    activity_id: int,
    keyword: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """按场景聚合"""
    return unified_response(activity_analytics_service.aggregate_by_scenario(db, user.tenant_id, activity_id, keyword))


@router.get("/{activity_id}/analytics/learner")
async def analytics_learner(
    activity_id: int,
    keyword: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """按学员聚合"""
    return unified_response(activity_analytics_service.aggregate_by_learner(db, user.tenant_id, activity_id, keyword))


@router.get("/{activity_id}/analytics/export")
async def analytics_export(
    activity_id: int,
    dimension: str = Query("department"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """CSV 导出"""
    csv_str = activity_analytics_service.export_csv(db, user.tenant_id, activity_id, dimension)
    return Response(content=csv_str, media_type="text/csv", headers={
        "Content-Disposition": f"attachment; filename=activity_{activity_id}_{dimension}.csv"
    })
