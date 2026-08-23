"""协同办公 API - 任务管理、审批流、公告"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.response import unified_response
from middleware.auth import get_current_user
from database import User, get_db
from services import collab_service
from .schemas import (
    TaskCreateRequest,
    TaskStatusRequest,
    ApprovalCreateRequest,
    ReviewRequest,
)

router = APIRouter(prefix="/collab")


# ──────────────────────────────────────────────
# 总览
# ──────────────────────────────────────────────

@router.get("/overview")
async def overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """协同办公总览"""
    return unified_response(collab_service.get_overview(db, user.tenant_id, user.id))


# ──────────────────────────────────────────────
# 任务管理
# ──────────────────────────────────────────────

@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = Query(None),
    task_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """任务列表"""
    return unified_response(collab_service.get_tasks(db, user.tenant_id, user.id, status, task_type, page, page_size))


@router.get("/tasks/{task_id}")
async def get_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """任务详情"""
    result = collab_service.get_task(db, user.tenant_id, task_id)
    if not result:
        return unified_response(code=404, message="任务不存在")
    return unified_response(result)


@router.post("/tasks")
async def create_task(req: TaskCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建任务"""
    return unified_response(collab_service.create_task(db, user.tenant_id, user.id, req.model_dump()))


@router.patch("/tasks/{task_id}/status")
async def update_task_status(task_id: int, req: TaskStatusRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新任务状态"""
    result = collab_service.update_task_status(db, user.tenant_id, task_id, req.status)
    if not result:
        return unified_response(code=404, message="任务不存在")
    return unified_response(result)


# ──────────────────────────────────────────────
# 审批管理
# ──────────────────────────────────────────────

@router.get("/approvals")
async def list_approvals(
    status: Optional[str] = Query(None),
    approval_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """审批列表"""
    return unified_response(collab_service.get_approvals(db, user.tenant_id, user.id, status, approval_type, page, page_size))


@router.get("/approvals/{approval_id}")
async def get_approval(approval_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """审批详情"""
    result = collab_service.get_approval(db, user.tenant_id, approval_id)
    if not result:
        return unified_response(code=404, message="审批不存在")
    return unified_response(result)


@router.post("/approvals")
async def create_approval(req: ApprovalCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建审批申请"""
    return unified_response(collab_service.create_approval(db, user.tenant_id, user.id, req.model_dump()))


@router.post("/approvals/{approval_id}/review")
async def review_approval(approval_id: int, req: ReviewRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """审批：approve / reject"""
    result = collab_service.review_approval(db, user.tenant_id, user.id, approval_id, req.decision, req.comment)
    if not result:
        return unified_response(code=404, message="审批不存在")
    return unified_response(result)


# ──────────────────────────────────────────────
# F1 审批流 SLA 端点（借鉴企业级诊断体系 §7.3-7.4）
# ──────────────────────────────────────────────

@router.get("/approvals/overdue")
async def list_overdue_approvals(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取超期审批列表（escalation_level >= 1）"""
    return unified_response(collab_service.get_overdue_approvals(db, user.tenant_id, page, page_size))


@router.get("/approvals/escalated")
async def list_escalated_approvals(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取已升级审批列表（escalation_level >= 2）"""
    return unified_response(collab_service.get_escalated_approvals(db, user.tenant_id, page, page_size))


@router.post("/approvals/sla-check")
async def trigger_sla_check(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """手动触发 SLA 检查（管理员调试用）"""
    result = collab_service.check_overdue_approvals(db, user.tenant_id)
    return unified_response(result)


# ──────────────────────────────────────────────
# F3 任务阀门端点（借鉴企业级诊断体系 §9.1）
# ──────────────────────────────────────────────

@router.get("/tasks/merged")
async def get_merged_tasks(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取合并后的任务视图（按对象分组）"""
    return unified_response(collab_service.get_merged_tasks(db, user.tenant_id, user.id))


@router.post("/tasks/merge")
async def merge_tasks(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """扫描并合并同对象多项目任务"""
    return unified_response(collab_service.merge_tasks_for_user(db, user.tenant_id, user.id))


@router.get("/tasks/quota")
async def get_task_quota_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询当前用户任务配额使用情况"""
    from core.task_quota import get_user_task_quota_status
    return unified_response(get_user_task_quota_status(db, user.tenant_id, user.id))


# ──────────────────────────────────────────────
# 公告管理
# ──────────────────────────────────────────────

@router.get("/announcements")
async def list_announcements(
    ann_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """公告列表"""
    return unified_response(collab_service.get_announcements(db, user.tenant_id, ann_type, page, page_size))


@router.get("/announcements/{announcement_id}")
async def get_announcement(announcement_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """公告详情"""
    result = collab_service.get_announcement(db, user.tenant_id, announcement_id)
    if not result:
        return unified_response(code=404, message="公告不存在")
    return unified_response(result)


@router.post("/ai-insights")
async def collab_ai_insights(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """AI 协同洞察（查询预生成缓存）"""
    from services.ai_insight_service import ai_insight_service
    result = ai_insight_service.get_cached_insight(domain="collab", tenant_id=user.tenant_id, user_id=user.id, db=db)
    return unified_response(result)


# ──────────────────────────────────────────────
# F8: 闭环判定 + 月度双任务复核（借鉴企业级诊断体系 §7.5、§8.4）
# ──────────────────────────────────────────────

from pydantic import BaseModel, Field
from typing import List


class JudgeClosureRequest(BaseModel):
    achieved_metrics: Optional[List[dict]] = Field(None, description="实际达成：[{name, value, source}]")
    signal_cleared: bool = Field(True, description="触发信号是否消除（如灯色变化是否已恢复）")
    appeal_state: Optional[str] = Field(None, description="申诉状态：no_appeal/appealed/upheld/overturned")


class SetTargetMetricsRequest(BaseModel):
    target_metrics: List[dict] = Field(..., description="量化目标：[{name, value, unit, deadline}]")


class CreateCycleRequest(BaseModel):
    cycle_month: Optional[str] = Field(None, description="YYYY-MM 格式，默认上月")


@router.post("/tasks/{task_id}/judge-closure")
async def judge_task_closure(
    task_id: int,
    body: JudgeClosureRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """手动判定任务闭环状态

    决策矩阵：100%+信号消除=closed；100%但信号未消除=partial；
    60%-100%=partial；<60%且申诉中=unresolved；<60%且未申诉=unresolved+升级。
    """
    from services import closure_review_service
    return unified_response(
        closure_review_service.judge_closure(
            db, user.tenant_id, task_id,
            achieved_metrics=body.achieved_metrics,
            signal_cleared=body.signal_cleared,
            appeal_state=body.appeal_state,
            actor_id=user.id,
        )
    )


@router.get("/tasks/{task_id}/closure-detail")
async def get_task_closure_detail(
    task_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询任务闭环详情（量化目标、实际达成、达成率、闭环状态）"""
    from services import closure_review_service
    return unified_response(
        closure_review_service.get_task_closure_detail(db, user.tenant_id, task_id)
    )


@router.put("/tasks/{task_id}/target-metrics")
async def set_task_target_metrics(
    task_id: int,
    body: SetTargetMetricsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """设置任务量化目标（用于闭环判定）"""
    from services import closure_review_service
    return unified_response(
        closure_review_service.set_task_target_metrics(
            db, user.tenant_id, task_id, body.target_metrics, actor_id=user.id,
        )
    )


@router.post("/closure-cycles")
async def create_closure_cycle(
    body: CreateCycleRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """手动触发月度复核批次（默认 = 上月）

    注意：自动触发由 insight_scheduler 在每月 12 日 06:00 执行。
    """
    from services import closure_review_service
    cycle = closure_review_service.create_monthly_review_cycle(
        db, user.tenant_id, cycle_month=body.cycle_month, actor_id=user.id,
    )
    return unified_response({
        "cycle_id": cycle.id,
        "cycle_month": cycle.cycle_month,
        "status": cycle.status,
        "started_at": cycle.started_at.isoformat() if cycle.started_at else None,
    })


@router.post("/closure-cycles/{cycle_id}/run")
async def run_closure_cycle(
    cycle_id: int,
    batch_size: int = Query(50, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """执行月度复核批次（扫描未闭环任务，自动判定 + 升级 + 滚入下月）"""
    from services import closure_review_service
    return unified_response(
        closure_review_service.run_review_batch(
            db, user.tenant_id, cycle_id, batch_size=batch_size,
        )
    )


@router.get("/closure-cycles/{cycle_id}")
async def get_closure_cycle_progress(
    cycle_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询月度复核批次进度"""
    from services import closure_review_service
    return unified_response(
        closure_review_service.get_cycle_progress(db, user.tenant_id, cycle_id)
    )
