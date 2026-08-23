"""数据质量门禁 API 路由（F6）

借鉴企业级诊断体系 §5.5：完整度门禁 + 三档降级。
- GET  /v1/data-quality/gates              — 列出所有域门禁
- GET  /v1/data-quality/gates/{domain}      — 查询单域门禁
- PUT  /v1/data-quality/gates/{domain}      — 更新门禁阈值
- POST /v1/data-quality/check/{domain}      — 触发即时检查
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional

from core.response import unified_response
from middleware.auth import get_current_user
from database import User, get_db

router = APIRouter(prefix="/data-quality")


class GateUpdateRequest(BaseModel):
    completeness_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    timeliness_delay_days: Optional[int] = Field(None, ge=0, le=30)
    timeliness_partial_days: Optional[int] = Field(None, ge=0, le=30)
    timeliness_cancel_days: Optional[int] = Field(None, ge=0, le=30)
    enabled: Optional[int] = Field(None, ge=0, le=1)


@router.get("/gates")
async def list_gates_endpoint(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列出所有域门禁配置（带 default fallback）"""
    from core.data_quality import list_gates
    gates = list_gates(db, user.tenant_id)
    return unified_response([{
        "id": g.id,
        "domain": g.domain,
        "completeness_threshold": g.completeness_threshold,
        "timeliness_delay_days": g.timeliness_delay_days,
        "timeliness_partial_days": g.timeliness_partial_days,
        "timeliness_cancel_days": g.timeliness_cancel_days,
        "enabled": bool(g.enabled),
        "last_check_at": g.last_check_at.isoformat() if g.last_check_at else None,
        "last_completeness": g.last_completeness,
        "last_decision": g.last_decision,
    } for g in gates])


@router.get("/gates/{domain}")
async def get_gate_endpoint(
    domain: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询单域门禁"""
    from core.data_quality import get_gate
    g = get_gate(db, user.tenant_id, domain)
    if not g:
        return unified_response(None, code=404, message=f"门禁 {domain} 不存在")
    return unified_response({
        "id": g.id,
        "domain": g.domain,
        "completeness_threshold": g.completeness_threshold,
        "timeliness_delay_days": g.timeliness_delay_days,
        "timeliness_partial_days": g.timeliness_partial_days,
        "timeliness_cancel_days": g.timeliness_cancel_days,
        "enabled": bool(g.enabled),
        "last_check_at": g.last_check_at.isoformat() if g.last_check_at else None,
        "last_completeness": g.last_completeness,
        "last_decision": g.last_decision,
    })


@router.put("/gates/{domain}")
async def update_gate_endpoint(
    domain: str,
    body: GateUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新门禁阈值（运行时调整，无需重启）"""
    from core.data_quality import update_gate
    updated = update_gate(
        db, user.tenant_id, domain,
        completeness_threshold=body.completeness_threshold,
        timeliness_delay_days=body.timeliness_delay_days,
        timeliness_partial_days=body.timeliness_partial_days,
        timeliness_cancel_days=body.timeliness_cancel_days,
        enabled=body.enabled,
        user_id=user.id,
    )
    if not updated:
        return unified_response(None, code=404, message=f"门禁 {domain} 不存在")
    return unified_response({
        "id": updated.id,
        "domain": updated.domain,
        "completeness_threshold": updated.completeness_threshold,
        "timeliness_delay_days": updated.timeliness_delay_days,
        "timeliness_partial_days": updated.timeliness_partial_days,
        "timeliness_cancel_days": updated.timeliness_cancel_days,
        "enabled": bool(updated.enabled),
    })


@router.post("/check/{domain}")
async def check_quality_endpoint(
    domain: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """触发即时质量检查

    返回决策矩阵：pass / delay / partial_cancel / cancel
    """
    from core.data_quality import check_quality_gate
    result = check_quality_gate(db, user.tenant_id, domain)
    return unified_response(result)
