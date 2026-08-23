"""PPT 演讲训战 API - 路由定义"""
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db, User
from core.response import unified_response
from core.pagination import PageParams
from middleware.auth import get_current_user
from services import ppt_speech_service

from .schemas import (
    PPTScenarioRequest, PPTScenarioUpdateRequest,
    StartSessionRequest, SubmitPageRequest, SubmitQARequest,
)

router = APIRouter(prefix="/training/ppt")


# ──────────────────────────────────────────────
# PPT 演讲场景
# ──────────────────────────────────────────────

@router.get("/scenarios")
async def list_ppt_scenarios(
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列表查询 PPT 演讲场景"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(ppt_speech_service.list_ppt_scenarios(db, user.tenant_id, keyword=keyword, page_params=params))


@router.post("/scenarios")
async def create_ppt_scenario(req: PPTScenarioRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建 PPT 演讲场景（提供 ppt_url 时自动 Mock 解析）"""
    return unified_response(ppt_speech_service.create_ppt_scenario(db, user.tenant_id, user.id, req.dict()))


@router.get("/scenarios/{scenario_id}")
async def get_ppt_scenario(scenario_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取 PPT 演讲场景详情"""
    return unified_response(ppt_speech_service.get_ppt_scenario(db, user.tenant_id, scenario_id))


@router.put("/scenarios/{scenario_id}")
async def update_ppt_scenario(scenario_id: int, req: PPTScenarioUpdateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新 PPT 演讲场景"""
    return unified_response(ppt_speech_service.update_ppt_scenario(db, user.tenant_id, scenario_id, req.dict(exclude_unset=True)))


@router.post("/scenarios/{scenario_id}/publish")
async def publish_ppt_scenario(scenario_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """发布 PPT 演讲场景"""
    return unified_response(ppt_speech_service.publish_ppt_scenario(db, user.tenant_id, scenario_id))


@router.post("/scenarios/{scenario_id}/parse")
async def parse_ppt(scenario_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """触发 Mock PPT 解析"""
    from services.ppt_speech_service import mock_parse_ppt, _serialize_scenario
    sc = ppt_speech_service.get_ppt_scenario(db, user.tenant_id, scenario_id)
    pages = mock_parse_ppt(sc.get("ppt_url") or "")
    from database import PracticeScenario
    obj = db.query(PracticeScenario).filter(
        PracticeScenario.tenant_id == user.tenant_id,
        PracticeScenario.is_deleted == 0,
        PracticeScenario.id == scenario_id,
    ).first()
    if obj:
        obj.ppt_pages = pages
        db.commit()
        db.refresh(obj)
        return unified_response(_serialize_scenario(obj))
    return unified_response(sc)


# ──────────────────────────────────────────────
# PPT 演讲会话
# ──────────────────────────────────────────────

@router.post("/sessions/start")
async def start_session(req: StartSessionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """开始 PPT 演讲会话"""
    return unified_response(ppt_speech_service.start_session(db, user.tenant_id, user.id, req.scenario_id, req.mode, req.activity_id))


@router.post("/sessions/{session_id}/page-submit")
async def submit_page(session_id: int, req: SubmitPageRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """提交单页录音"""
    return unified_response(ppt_speech_service.submit_page(db, user.tenant_id, session_id, req.page_no, req.recording))


@router.post("/sessions/{session_id}/qa")
async def submit_qa(session_id: int, req: SubmitQARequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """提交问答答案"""
    return unified_response(ppt_speech_service.submit_qa(db, user.tenant_id, session_id, req.question_id, req.answer))


@router.post("/sessions/{session_id}/complete")
async def complete_session(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """完成会话 — 生成 AI 评审"""
    return unified_response(ppt_speech_service.complete_session(db, user.tenant_id, session_id))


@router.get("/sessions/{session_id}")
async def get_session(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取会话详情"""
    return unified_response(ppt_speech_service.get_session(db, user.tenant_id, session_id))


@router.get("/sessions")
async def list_sessions(
    scenario_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列表查询演讲会话"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(ppt_speech_service.list_sessions(
        db, user.tenant_id, user_id=user.id, scenario_id=scenario_id,
        status=status, page_params=params,
    ))
