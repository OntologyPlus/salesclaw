"""内容工具 API - 静态工具目录"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.response import unified_response
from middleware.auth import get_current_user
from database import User, get_db
from services import tools_service

from .schemas import ExecuteToolRequest, AiRecommendRequest

router = APIRouter(prefix="/tools")


@router.get("/overview")
async def tools_overview(user: User = Depends(get_current_user)):
    """内容工具总览：返回静态工具目录"""
    tools = [
        {"id": "ppt_generator", "name": "学术PPT生成器", "description": "一键生成学术推广PPT", "category": "content", "icon": "presentation"},
        {"id": "visit_summary", "name": "拜访总结生成", "description": "AI自动生成拜访记录摘要", "category": "ai", "icon": "file-text"},
        {"id": "objection_handler", "name": "异议处理话术", "description": "生成针对性异议应对话术", "category": "ai", "icon": "message-square"},
        {"id": "weekly_report", "name": "周报生成器", "description": "自动汇总周报内容", "category": "report", "icon": "calendar"},
        {"id": "product_card", "name": "产品卡片制作", "description": "生成标准产品介绍卡片", "category": "content", "icon": "credit-card"},
        {"id": "clinical_search", "name": "临床文献检索", "description": "按关键词检索相关临床文献", "category": "search", "icon": "search"},
    ]
    return unified_response({"tools": tools, "total": len(tools)})


@router.post("/execute/{tool_id}")
async def execute_tool(tool_id: str, req: ExecuteToolRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """执行工具"""
    result = tools_service.execute_tool(db, user.tenant_id, user.id, tool_id, req.params)
    if result is None:
        return unified_response(None, code=40004, message="工具不存在")
    return unified_response(result)


@router.get("/recent")
async def recent_tools(user: User = Depends(get_current_user)):
    """最近使用工具"""
    return unified_response(tools_service.get_recent_tools(user.id))


@router.post("/ai-recommend")
async def ai_recommend(req: AiRecommendRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """AI 推荐工具"""
    from services.ai_insight_service import ai_insight_service
    insight = ai_insight_service.get_cached_insight(domain="tools", tenant_id=user.tenant_id, user_id=user.id, db=db)
    recommendations = tools_service.recommend_tools(req.context or {})
    return unified_response({"insight": insight, "recommendations": recommendations})
