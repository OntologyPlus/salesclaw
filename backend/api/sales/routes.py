"""销售执行 API - 路由定义"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db, User
from core.response import unified_response
from core.pagination import PageParams
from middleware.auth import get_current_user
from services import sales_service

from .schemas import (
    CreatePlanRequest,
    UpdatePlanRequest,
    RejectRequest,
    PlanItemRequest,
    CreateRecordRequest,
    UpdateRecordRequest,
    CreateFeedbackRequest,
    UpdateFeedbackRequest,
    AssignCoverageRequest,
)

router = APIRouter(prefix="/sales")


# ──────────────────────────────────────────────
# 概览
# ──────────────────────────────────────────────

@router.get("/overview")
async def overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """销售概览统计"""
    return unified_response(sales_service.get_overview(db, user.tenant_id, user.id))


# ──────────────────────────────────────────────
# 拜访计划 CRUD + 状态机
# ──────────────────────────────────────────────

@router.get("/visit-plans")
async def list_plans(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列表查询拜访计划"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(sales_service.list_plans(db, user.tenant_id, status=status, user_id=user.id, page_params=params))


@router.post("/visit-plans")
async def create_plan(req: CreatePlanRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建拜访计划"""
    plan = sales_service.create_plan(db, user.tenant_id, user.id, req.dict())
    return unified_response(plan)


@router.get("/visit-plans/{plan_id}")
async def get_plan(plan_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取拜访计划详情"""
    return unified_response(sales_service.get_plan(db, user.tenant_id, plan_id))


@router.put("/visit-plans/{plan_id}")
async def update_plan(plan_id: int, req: UpdatePlanRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新拜访计划"""
    return unified_response(sales_service.update_plan(db, user.tenant_id, plan_id, req.dict(exclude_unset=True)))


@router.delete("/visit-plans/{plan_id}")
async def delete_plan(plan_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """删除拜访计划（软删除）"""
    sales_service.delete_plan(db, user.tenant_id, plan_id)
    return unified_response({"deleted": True})


@router.post("/visit-plans/{plan_id}/submit")
async def submit_plan(plan_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """提交拜访计划（draft/rejected → pending）"""
    return unified_response(sales_service.submit_plan(db, user.tenant_id, plan_id, user.id))


@router.post("/visit-plans/{plan_id}/approve")
async def approve_plan(plan_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """审批通过（pending → approved）"""
    return unified_response(sales_service.approve_plan(db, user.tenant_id, plan_id, user.id))


@router.post("/visit-plans/{plan_id}/reject")
async def reject_plan(plan_id: int, req: RejectRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """驳回（pending → rejected）"""
    return unified_response(sales_service.reject_plan(db, user.tenant_id, plan_id, user.id, req.reason))


@router.post("/visit-plans/ai-recommend")
async def ai_recommend(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """AI 推荐拜访计划（基于真实覆盖分配 + 反馈数据）"""
    from ai.orchestrator import Orchestrator
    orch = Orchestrator()
    result = await orch.recommend_visit_plan(db, user)
    return unified_response(result)


# ──────────────────────────────────────────────
# 拜访计划明细
# ──────────────────────────────────────────────

@router.get("/visit-plans/{plan_id}/items")
async def list_plan_items(plan_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """查询拜访计划明细"""
    return unified_response({"items": sales_service.list_plan_items(db, user.tenant_id, plan_id)})


@router.post("/visit-plans/{plan_id}/items")
async def add_plan_item(plan_id: int, req: PlanItemRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """新增拜访计划明细"""
    return unified_response(sales_service.add_plan_item(db, user.tenant_id, plan_id, req.dict(exclude_unset=True)))


@router.delete("/visit-plans/{plan_id}/items/{item_id}")
async def delete_plan_item(plan_id: int, item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """删除拜访计划明细（软删除）"""
    sales_service.delete_plan_item(db, user.tenant_id, plan_id, item_id)
    return unified_response({"deleted": True})


# ──────────────────────────────────────────────
# 拜访记录 CRUD
# ──────────────────────────────────────────────

@router.get("/visit-records")
async def list_records(
    hospital_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列表查询拜访记录"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(sales_service.list_records(db, user.tenant_id, hospital_id=hospital_id, doctor_id=doctor_id, user_id=user.id, page_params=params))


@router.post("/visit-records")
async def create_record(req: CreateRecordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建拜访记录"""
    return unified_response(sales_service.create_record(db, user.tenant_id, user.id, req.dict(exclude_unset=True)))


@router.get("/visit-records/{record_id}")
async def get_record(record_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取拜访记录详情"""
    return unified_response(sales_service.get_record(db, user.tenant_id, record_id))


@router.put("/visit-records/{record_id}")
async def update_record(record_id: int, req: UpdateRecordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新拜访记录"""
    return unified_response(sales_service.update_record(db, user.tenant_id, record_id, req.dict(exclude_unset=True)))


@router.delete("/visit-records/{record_id}")
async def delete_record(record_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """删除拜访记录（软删除）"""
    sales_service.delete_record(db, user.tenant_id, record_id)
    return unified_response({"deleted": True})


# ──────────────────────────────────────────────
# 拜访反馈
# ──────────────────────────────────────────────

@router.get("/visit-feedbacks")
async def list_feedbacks(
    record_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列表查询拜访反馈"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(sales_service.list_feedbacks(db, user.tenant_id, record_id=record_id, page_params=params))


@router.post("/visit-feedbacks")
async def create_feedback(req: CreateFeedbackRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建拜访反馈"""
    return unified_response(sales_service.create_feedback(db, user.tenant_id, user.id, req.dict(exclude_unset=True)))


@router.get("/visit-feedbacks/{feedback_id}")
async def get_feedback(feedback_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取拜访反馈详情"""
    return unified_response(sales_service.get_feedback(db, user.tenant_id, feedback_id))


@router.put("/visit-feedbacks/{feedback_id}")
async def update_feedback(feedback_id: int, req: UpdateFeedbackRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新拜访反馈"""
    return unified_response(sales_service.update_feedback(db, user.tenant_id, feedback_id, req.dict(exclude_unset=True)))


@router.delete("/visit-feedbacks/{feedback_id}")
async def delete_feedback(feedback_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """删除拜访反馈（软删除）"""
    sales_service.delete_feedback(db, user.tenant_id, feedback_id)
    return unified_response({"deleted": True})


# ──────────────────────────────────────────────
# 覆盖分管
# ──────────────────────────────────────────────

@router.get("/coverage")
async def list_coverage(
    user_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列表查询覆盖分管"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(sales_service.list_coverage(db, user.tenant_id, user_id=user_id or user.id, page_params=params))


@router.get("/coverage/effective")
async def get_effective_coverage(
    product_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
    effective_date: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前用户有效覆盖分管（多源分管 + 临时特批过滤）"""
    from datetime import date as date_type
    d = date_type.fromisoformat(effective_date) if effective_date else None
    result = sales_service.get_effective_coverage(
        db, user.tenant_id, user.id, product_id, doctor_id, d
    )
    return unified_response(result)


@router.post("/coverage")
async def assign_coverage(req: AssignCoverageRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """分配覆盖"""
    return unified_response(sales_service.assign_coverage(db, user.tenant_id, req.dict(exclude_unset=True)))


@router.delete("/coverage/{coverage_id}")
async def delete_coverage(coverage_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """删除覆盖分配（软删除）"""
    sales_service.delete_coverage(db, user.tenant_id, coverage_id)
    return unified_response({"deleted": True})


# ──────────────────────────────────────────────
# 覆盖矩阵
# ──────────────────────────────────────────────

@router.get("/matrix")
async def list_matrix(
    hospital_id: Optional[int] = None,
    product_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列表查询覆盖矩阵"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(sales_service.list_matrix(db, user.tenant_id, hospital_id=hospital_id, product_id=product_id, page_params=params))


@router.post("/matrix/refresh")
async def refresh_matrix(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """根据拜访记录刷新覆盖矩阵统计"""
    return unified_response(sales_service.refresh_matrix(db, user.tenant_id))


# ──────────────────────────────────────────────
# 积分
# ──────────────────────────────────────────────

@router.get("/points/rules")
async def list_behavior_rules(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """查询行为积分规则"""
    return unified_response({"items": sales_service.list_behavior_rules(db, user.tenant_id)})


@router.get("/points/records")
async def list_behavior_records(
    user_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询行为积分记录"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(sales_service.list_behavior_records(db, user.tenant_id, user_id=user_id or user.id, page_params=params))


@router.get("/points/summary")
async def points_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """积分汇总"""
    return unified_response(sales_service.get_points_summary(db, user.tenant_id, user.id))


# ──────────────────────────────────────────────
# 周报
# ──────────────────────────────────────────────

@router.get("/weekly-reports")
async def list_weekly_reports(
    user_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列表查询周报"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(sales_service.list_weekly_reports(db, user.tenant_id, user_id=user_id or user.id, page_params=params))


@router.post("/weekly-reports/generate")
async def generate_weekly_report(
    week_start: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """生成周报（默认本周）"""
    return unified_response(sales_service.generate_weekly_report(db, user.tenant_id, user.id, week_start))


# ──────────────────────────────────────────────
# 主数据查询
# ──────────────────────────────────────────────

@router.get("/hospitals")
async def list_hospitals(
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询医院列表"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(sales_service.list_hospitals(db, user.tenant_id, keyword=keyword, page_params=params))


@router.get("/doctors")
async def list_doctors(
    hospital_id: Optional[int] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询医生列表"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(sales_service.list_doctors(db, user.tenant_id, hospital_id=hospital_id, keyword=keyword, page_params=params))


@router.get("/products")
async def list_products(
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询产品列表"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(sales_service.list_products(db, user.tenant_id, keyword=keyword, page_params=params))


@router.post("/ai-insights")
async def sales_ai_insights(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """AI 销售洞察（查询预生成缓存）"""
    from services.ai_insight_service import ai_insight_service
    result = ai_insight_service.get_cached_insight(domain="sales", tenant_id=user.tenant_id, user_id=user.id, db=db)
    return unified_response(result)


@router.post("/territory-query")
async def territory_query(
    question: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """AI 辖区数据查询（自然语言：如"朝阳01辖区本周达成率？"）"""
    from services import territory_service
    result = await territory_service.query_territory(db, user.tenant_id, user.id, question)
    return unified_response(result)
