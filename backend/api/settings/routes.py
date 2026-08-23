"""设置 API - 用户个人资料 + 通知订阅 + AI 模型配置"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config import settings as app_settings
from core.response import unified_response
from middleware.auth import get_current_user
from database import User, NotificationSubscription, Role, LlmCallLog, get_db
from services import settings_service

from .schemas import UpdatePreferencesRequest

router = APIRouter(prefix="/settings")


@router.get("/overview")
async def settings_overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """设置总览：用户资料 + 通知订阅列表"""
    # 角色信息
    role_name = None
    if user.role_id:
        role = db.query(Role).filter(
            Role.id == user.role_id,
            Role.is_deleted == 0,
        ).first()
        if role:
            role_name = role.name

    profile = {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "role_id": user.role_id,
        "role_name": role_name,
    }

    # 通知订阅列表
    subscriptions = db.query(NotificationSubscription).filter(
        NotificationSubscription.tenant_id == user.tenant_id,
        NotificationSubscription.user_id == user.id,
        NotificationSubscription.is_deleted == 0,
    ).order_by(NotificationSubscription.id.asc()).all()

    subscription_items = []
    for sub in subscriptions:
        subscription_items.append({
            "id": sub.id,
            "channel": sub.channel,
            "target": sub.target,
            "config": sub.config or {},
        })

    return unified_response({
        "profile": profile,
        "notification_subscriptions": subscription_items,
    })


@router.get("/ai-config")
async def ai_config(user: User = Depends(get_current_user)):
    """AI 模型配置（只读展示）"""
    return unified_response({
        "provider": app_settings.LLM_PROVIDER,
        "model": app_settings.LLM_MODEL,
        "base_url": app_settings.LLM_BASE_URL,
        "enable_thinking": app_settings.LLM_ENABLE_THINKING,
        "reasoning_budget": app_settings.LLM_REASONING_BUDGET,
        "temperature": app_settings.LLM_TEMPERATURE,
        "top_p": app_settings.LLM_TOP_P,
        "max_tokens": app_settings.LLM_MAX_TOKENS,
    })


@router.get("/llm-logs")
async def llm_logs(limit: int = 10, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """最近 LLM 调用日志"""
    logs = db.query(LlmCallLog).filter(
        LlmCallLog.tenant_id == user.tenant_id,
        LlmCallLog.is_deleted == 0,
    ).order_by(LlmCallLog.ts.desc()).limit(max(1, min(limit, 100))).all()

    items = [{
        "id": log.id,
        "provider": log.provider,
        "model": log.model,
        "prompt_tokens": log.prompt_tokens,
        "completion_tokens": log.completion_tokens,
        "duration_ms": log.duration_ms,
        "status": log.status,
        "ts": log.ts.strftime("%Y-%m-%d %H:%M:%S") if log.ts else None,
    } for log in logs]

    return unified_response({"items": items, "total": len(items)})


@router.get("/preferences")
async def get_preferences(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """用户偏好"""
    return unified_response(settings_service.get_preferences(db, user.tenant_id, user.id))


@router.put("/preferences")
async def update_preferences(req: UpdatePreferencesRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新偏好"""
    return unified_response(settings_service.update_preferences(db, user.tenant_id, user.id, req.preferences))


@router.post("/ai-insights")
async def settings_ai_insights(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """AI 个性化建议"""
    from services.ai_insight_service import ai_insight_service
    result = ai_insight_service.get_cached_insight(domain="settings", tenant_id=user.tenant_id, user_id=user.id, db=db)
    return unified_response(result)
