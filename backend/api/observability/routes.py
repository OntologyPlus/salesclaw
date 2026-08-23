"""可观测 API - 系统运行指标 + AI 事件总线"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.response import unified_response
from middleware.auth import get_current_user
from database import User, get_db, AIEvent, DeadLetter
from services import observability_service
from ai.event_bus import event_bus, AIEventBus

from .schemas import AlertConfigRequest

router = APIRouter(prefix="/observability")


@router.get("/metrics")
async def metrics(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """系统运行指标：用户、拜访、课程、LLM、表数、域分布"""
    return unified_response(observability_service.get_metrics(db, user.tenant_id))


@router.get("/events")
async def events(event_type: str = None, status: str = None, limit: int = 20,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """AI 事件列表（支持 event_type/status 过滤）"""
    items = event_bus.get_events(
        user.tenant_id, db,
        event_type=event_type, status=status, limit=limit,
    )
    return unified_response({"items": items, "total": len(items)})


@router.get("/dead-letters")
async def dead_letters(limit: int = 20,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """死信队列"""
    items = event_bus.get_dead_letters(user.tenant_id, db, limit=limit)
    return unified_response(items)


@router.get("/event-stats")
async def event_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """12 种 AI 事件类型统计"""
    stats = []
    for event_type, desc in AIEventBus.EVENT_TYPES.items():
        # 总数
        total = db.query(AIEvent).filter(
            AIEvent.tenant_id == user.tenant_id,
            AIEvent.is_deleted == 0,
            AIEvent.event_type == event_type,
        ).count()
        # 各状态计数
        completed = db.query(AIEvent).filter(
            AIEvent.tenant_id == user.tenant_id,
            AIEvent.is_deleted == 0,
            AIEvent.event_type == event_type,
            AIEvent.status == "completed",
        ).count()
        failed = db.query(AIEvent).filter(
            AIEvent.tenant_id == user.tenant_id,
            AIEvent.is_deleted == 0,
            AIEvent.event_type == event_type,
            AIEvent.status == "failed",
        ).count()
        pending = db.query(AIEvent).filter(
            AIEvent.tenant_id == user.tenant_id,
            AIEvent.is_deleted == 0,
            AIEvent.event_type == event_type,
            AIEvent.status == "pending",
        ).count()
        # 死信数
        dead_letter_count = db.query(DeadLetter).filter(
            DeadLetter.tenant_id == user.tenant_id,
            DeadLetter.is_deleted == 0,
            DeadLetter.event_type == event_type,
        ).count()
        stats.append({
            "type": event_type,
            "desc": desc,
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "dead_letter_count": dead_letter_count,
        })
    return unified_response({"items": stats})


@router.get("/alerts")
async def list_alerts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """告警列表"""
    return unified_response(observability_service.list_alerts(db, user.tenant_id))


@router.post("/alerts/config")
async def config_alerts(req: AlertConfigRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """告警配置"""
    return unified_response(observability_service.config_alerts(db, user.tenant_id, req.dict(exclude_unset=True)))


@router.post("/ai-insights")
async def observability_ai_insights(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """AI 健康洞察"""
    from services.ai_insight_service import ai_insight_service
    result = ai_insight_service.get_cached_insight(domain="observability", tenant_id=user.tenant_id, user_id=user.id, db=db)
    return unified_response(result)
