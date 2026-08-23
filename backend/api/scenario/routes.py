"""场景剧本解析 API - 路由定义"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db, User
from core.response import unified_response
from middleware.auth import get_current_user
from services import scenario_parser

from .schemas import ParseRequest, SaveScenarioRequest

router = APIRouter(prefix="/scenarios")


@router.post("/parse")
async def parse_scenario(req: ParseRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """AI 解析剧本文本为结构化场景"""
    return unified_response(await scenario_parser.parse_scenario(db, user.tenant_id, req.raw_text))


@router.post("/save")
async def save_scenario(req: SaveScenarioRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """保存解析结果为场景草稿（三步创建的最后一步）"""
    return unified_response(scenario_parser.save_parsed_scenario(db, user.tenant_id, user.id, req.dict(exclude_unset=True)))


@router.get("/default-scoring-rules")
async def default_scoring_rules(user: User = Depends(get_current_user)):
    """获取默认五维评分模板"""
    return unified_response({"items": scenario_parser.DEFAULT_SCORING_RULES})
