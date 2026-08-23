"""学术推广活动 API（v2.2 Phase 2）

对应《医药代表管理办法》第 19-22 条学术推广活动管理。
全生命周期：立项→审批→协议→签到→费用→反馈→归档
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from core.response import unified_response
from middleware.auth import get_current_user
from database import User, get_db
from services import academic_activity_service

router = APIRouter(prefix="/academic")


# ──────────────────────────────────────────────
# 请求模型
# ──────────────────────────────────────────────

class CreateActivityRequest(BaseModel):
    title: str
    activity_type: str = Field(..., description="conference/lecture/ward_round/academic_meeting")
    organizer_id: Optional[int] = None
    co_organizers: Optional[List[Dict[str, Any]]] = None
    planned_at: Optional[str] = None
    location: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    target_audience: Optional[str] = None
    expected_attendees: int = 0
    pharma_rep_user_id: Optional[int] = None
    partner_org_id: Optional[int] = None
    agreement_id: Optional[int] = None
    authorization_letter_id: Optional[int] = None
    product_ids: Optional[List[int]] = None
    therapeutic_areas: Optional[List[str]] = None
    agenda: Optional[List[Dict[str, Any]]] = None
    materials: Optional[List[Dict[str, Any]]] = None


class ApproveActivityRequest(BaseModel):
    approval_id: Optional[int] = None
    comment: Optional[str] = None


class AttachProtocolRequest(BaseModel):
    protocol: Dict[str, Any] = Field(..., description="会议协议子表 {protocol_no, signed_by, file_url, ...}")


class CheckinRequest(BaseModel):
    checkin_evidence: Dict[str, Any] = Field(..., description="签到证据 {attendee_name, location, photo_url, ...}")


class ExpenseRequest(BaseModel):
    expense_voucher: Dict[str, Any] = Field(..., description="费用凭证 {amount, type, invoice_no, file_url, ...}")


class FeedbackRequest(BaseModel):
    feedback: str
    adverse_reactions: Optional[List[Dict[str, Any]]] = None


class CancelRequest(BaseModel):
    reason: str


# ──────────────────────────────────────────────
# CRUD + 全生命周期
# ──────────────────────────────────────────────

@router.get("/activities")
async def list_activities(
    status: Optional[str] = Query(None),
    activity_type: Optional[str] = Query(None),
    pharma_rep_user_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """学术活动列表"""
    return unified_response(
        academic_activity_service.list_activities(
            db, user.tenant_id, status, activity_type, pharma_rep_user_id, page, page_size,
        )
    )


@router.get("/activities/{activity_id}")
async def get_activity(
    activity_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """学术活动详情"""
    return unified_response(
        academic_activity_service.get_activity(db, user.tenant_id, activity_id)
    )


@router.post("/activities")
async def create_activity(
    req: CreateActivityRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """立项：创建学术活动（含上岗准入校验 + 22 项规则校验）"""
    # 解析 planned_at
    data = req.model_dump()
    if data.get("planned_at"):
        try:
            from datetime import datetime
            data["planned_at"] = datetime.fromisoformat(data["planned_at"])
        except (ValueError, TypeError):
            pass
    role = "pharma_rep"  # TODO: 从 user.role 实际获取
    return unified_response(
        academic_activity_service.create_activity(
            db, user.tenant_id, user.id, role, data,
        )
    )


@router.post("/activities/{activity_id}/approve")
async def approve_activity(
    activity_id: int,
    req: ApproveActivityRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """审批通过"""
    return unified_response(
        academic_activity_service.approve_activity(
            db, user.tenant_id, activity_id, user.id, "compliance_officer",
            req.approval_id, req.comment,
        )
    )


@router.post("/activities/{activity_id}/protocol")
async def attach_protocol(
    activity_id: int,
    req: AttachProtocolRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """附加会议协议"""
    return unified_response(
        academic_activity_service.attach_protocol(
            db, user.tenant_id, activity_id, user.id, "pharma_rep",
            req.protocol,
        )
    )


@router.post("/activities/{activity_id}/checkin")
async def checkin(
    activity_id: int,
    req: CheckinRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """签到（含 22 项规则校验）"""
    return unified_response(
        academic_activity_service.checkin(
            db, user.tenant_id, activity_id, user.id, "pharma_rep",
            req.checkin_evidence,
        )
    )


@router.post("/activities/{activity_id}/expense")
async def submit_expense(
    activity_id: int,
    req: ExpenseRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """费用核销（含 22 项规则校验）"""
    return unified_response(
        academic_activity_service.submit_expense(
            db, user.tenant_id, activity_id, user.id, "pharma_rep",
            req.expense_voucher,
        )
    )


@router.post("/activities/{activity_id}/feedback")
async def submit_feedback(
    activity_id: int,
    req: FeedbackRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """提交反馈（含不良反应收集，第 21 条第（三）项）"""
    return unified_response(
        academic_activity_service.submit_feedback(
            db, user.tenant_id, activity_id, user.id, "pharma_rep",
            req.feedback, req.adverse_reactions,
        )
    )


@router.post("/activities/{activity_id}/archive")
async def archive_activity(
    activity_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """归档"""
    return unified_response(
        academic_activity_service.archive_activity(
            db, user.tenant_id, activity_id, user.id, "pharma_rep",
        )
    )


@router.post("/activities/{activity_id}/cancel")
async def cancel_activity(
    activity_id: int,
    req: CancelRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """取消学术活动"""
    return unified_response(
        academic_activity_service.cancel_activity(
            db, user.tenant_id, activity_id, user.id, "pharma_rep",
            req.reason,
        )
    )
