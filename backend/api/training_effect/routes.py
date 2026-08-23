"""培训效果因果归因 API - 路由定义

设计文档：SalesClaw_培训效果因果归因_B路径_规划.md §10

端点：
  GET  /v1/training/effect/overview              总览（CEO 看板）
  GET  /v1/training/effect/executions             列表查询
  GET  /v1/training/effect/executions/{id}        单条详情
  POST /v1/training/effect/evaluate              触发 AI 归因（同步 mock / 真实 LLM 异步）
  GET  /v1/training/effect/lag-curve             滞后期曲线
  POST /v1/training/effect/cohort-compare        同期类比组
"""
import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.response import unified_response
from database import User, get_db
from middleware.auth import get_current_user

from services import training_effect_service

from .schemas import EvaluationRequest


router = APIRouter(prefix="/training/effect")


# ──────────────────────────────────────────────
# 看板总览
# ──────────────────────────────────────────────

@router.get("/overview")
async def overview(
    period_days: int = Query(30, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """培训效果归因总览（CEO 看板入口）"""
    return unified_response(
        training_effect_service.overview(db, user.tenant_id, period_days=period_days)
    )


# ──────────────────────────────────────────────
# 执行记录列表 / 详情
# ──────────────────────────────────────────────

@router.get("/executions")
async def list_executions(
    user_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    period_days: int = Query(180, ge=1, le=730),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """培训效果归因执行列表"""
    return unified_response(
        training_effect_service.list_executions(
            db, user.tenant_id,
            user_id=user_id, status=status,
            period_days=period_days, limit=limit,
        )
    )


@router.get("/executions/{execution_id}")
async def get_execution(
    execution_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return unified_response(
        training_effect_service.get_execution(db, execution_id, user.tenant_id)
    )


# ──────────────────────────────────────────────
# AI 归因触发
# ──────────────────────────────────────────────

@router.post("/evaluate")
async def evaluate(
    body: EvaluationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """触发 AI 归因评估（经编排器 evaluate 意图）"""
    result = await training_effect_service.ai_attribution(
        db, body.execution_id, user.tenant_id,
    )
    return unified_response(result)


# ──────────────────────────────────────────────
# 滞后期曲线
# ──────────────────────────────────────────────

@router.get("/lag-curve")
async def lag_curve(
    execution_id: int = Query(..., description="训练效果归因执行 ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """返回 [t0, t0+30, t0+90, t0+180] 4 点的指标快照 + delta 曲线"""
    return unified_response(
        training_effect_service.lag_curve(
            db, user_id=user.id, execution_id=execution_id,
            tenant_id=user.tenant_id,
        )
    )


# ──────────────────────────────────────────────
# 同期类比组
# ──────────────────────────────────────────────

@router.post("/cohort-compare")
async def cohort_compare(
    cohort_key: str = Query(...,
        description="例如 region=East, role=MR, quarter=2026Q3"),
    period_days: int = Query(30, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """同期类比组对比"""
    return unified_response(
        training_effect_service.cohort_compare(
            db, tenant_id=user.tenant_id,
            cohort_key=cohort_key, period_days=period_days,
        )
    )
