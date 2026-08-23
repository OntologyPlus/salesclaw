"""智能培训 API - 路由定义"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db, User
from core.response import unified_response
from core.pagination import PageParams
from middleware.auth import get_current_user
from services import training_service

from .schemas import (
    CreateCourseRequest,
    UpdateCourseRequest,
    UpdateProgressRequest,
    CreateQuestionRequest,
    CreateExamRequest,
    SubmitExamRequest,
    CreatePathRequest,
    StartPracticeRequest,
    PracticeMessageRequest,
    EndPracticeRequest,
)

router = APIRouter(prefix="/training")


# ──────────────────────────────────────────────
# 概览
# ──────────────────────────────────────────────

@router.get("/overview")
async def overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """培训概览统计"""
    return unified_response(training_service.get_overview(db, user.tenant_id, user.id))


# ──────────────────────────────────────────────
# 课程
# ──────────────────────────────────────────────

@router.get("/courses")
async def list_courses(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列表查询课程"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(training_service.list_courses(
        db, user.tenant_id, category=category, difficulty=difficulty,
        keyword=keyword, page_params=params,
    ))


@router.post("/courses")
async def create_course(req: CreateCourseRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建课程"""
    return unified_response(training_service.create_course(db, user.tenant_id, req.dict(exclude_unset=True)))


@router.get("/courses/{course_id}")
async def get_course(course_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取课程详情"""
    return unified_response(training_service.get_course(db, user.tenant_id, course_id))


@router.put("/courses/{course_id}")
async def update_course(course_id: int, req: UpdateCourseRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新课程"""
    return unified_response(training_service.update_course(db, user.tenant_id, course_id, req.dict(exclude_unset=True)))


@router.delete("/courses/{course_id}")
async def delete_course(course_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """删除课程（软删除）"""
    training_service.delete_course(db, user.tenant_id, course_id)
    return unified_response({"deleted": True})


@router.post("/courses/{course_id}/enroll")
async def enroll_course(course_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """选课"""
    return unified_response(training_service.enroll_course(db, user.tenant_id, user.id, course_id))


@router.get("/courses/{course_id}/progress")
async def get_course_progress(course_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取课程进度"""
    return unified_response(training_service.get_course_progress(db, user.tenant_id, user.id, course_id))


@router.post("/courses/{course_id}/progress")
async def update_course_progress(course_id: int, req: UpdateProgressRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """更新课程进度"""
    return unified_response(training_service.update_course_progress(
        db, user.tenant_id, user.id, course_id, req.progress, req.last_position,
    ))


@router.post("/ai-recommend-learning")
async def ai_recommend_learning(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """AI 推荐学习路径（基于真实拜访数据）"""
    from ai.orchestrator import Orchestrator
    orch = Orchestrator()
    result = await orch.recommend_learning_path(db, user)
    return unified_response(result)


# ──────────────────────────────────────────────
# 题库
# ──────────────────────────────────────────────

@router.get("/questions")
async def list_questions(
    category: Optional[str] = None,
    question_type: Optional[str] = None,
    difficulty: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列表查询题目"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(training_service.list_questions(
        db, user.tenant_id, category=category, question_type=question_type,
        difficulty=difficulty, page_params=params,
    ))


@router.post("/questions")
async def create_question(req: CreateQuestionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建题目"""
    return unified_response(training_service.create_question(db, user.tenant_id, req.dict(exclude_unset=True)))


# ──────────────────────────────────────────────
# 考试
# ──────────────────────────────────────────────

@router.get("/exams")
async def list_exams(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列表查询考试"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(training_service.list_exams(db, user.tenant_id, status=status, page_params=params))


@router.post("/exams")
async def create_exam(req: CreateExamRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建考试"""
    return unified_response(training_service.create_exam(db, user.tenant_id, req.dict(exclude_unset=True)))


@router.get("/exams/{exam_id}")
async def get_exam(exam_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取考试详情（含题目）"""
    return unified_response(training_service.get_exam(db, user.tenant_id, exam_id))


@router.post("/exams/{exam_id}/submit")
async def submit_exam(exam_id: int, req: SubmitExamRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """提交考试，自动阅卷"""
    return unified_response(training_service.submit_exam(db, user.tenant_id, user.id, exam_id, req.answers))


@router.get("/exams/{exam_id}/result")
async def get_exam_result(exam_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取考试结果"""
    return unified_response(training_service.get_exam_result(db, user.tenant_id, user.id, exam_id))


# ──────────────────────────────────────────────
# 学习路径
# ──────────────────────────────────────────────

@router.get("/paths")
async def list_paths(
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列表查询学习路径"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(training_service.list_paths(db, user.tenant_id, page_params=params))


@router.post("/paths")
async def create_path(req: CreatePathRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """创建学习路径"""
    return unified_response(training_service.create_path(db, user.tenant_id, req.dict(exclude_unset=True)))


@router.get("/paths/{path_id}")
async def get_path(path_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取学习路径详情"""
    return unified_response(training_service.get_path(db, user.tenant_id, path_id))


@router.post("/paths/{path_id}/enroll")
async def enroll_path(path_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """学习路径选课"""
    return unified_response(training_service.enroll_path(db, user.tenant_id, user.id, path_id))


# ──────────────────────────────────────────────
# 我的学习
# ──────────────────────────────────────────────

@router.get("/my-learning")
async def my_learning(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """我的学习概览"""
    return unified_response(training_service.get_my_learning(db, user.tenant_id, user.id))


# ──────────────────────────────────────────────
# 证书
# ──────────────────────────────────────────────

@router.get("/certificates")
async def list_certificates(
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列表查询证书"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(training_service.list_certificates(db, user.tenant_id, user.id, page_params=params))


# ──────────────────────────────────────────────
# 演练
# ──────────────────────────────────────────────

@router.get("/scenarios")
async def list_scenarios(
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列表查询演练场景"""
    params = PageParams(page=page, page_size=page_size)
    return unified_response(training_service.list_scenarios(db, user.tenant_id, page_params=params))


@router.post("/practice/start")
async def start_practice(req: StartPracticeRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """开始演练"""
    return unified_response(training_service.start_practice(db, user.tenant_id, user.id, req.scenario_id))


@router.post("/practice/message")
async def practice_message(req: PracticeMessageRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """演练对话"""
    return unified_response(await training_service.practice_message(
        db, user.tenant_id, user.id, req.session_id, req.message,
    ))


@router.post("/practice/end")
async def end_practice(req: EndPracticeRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """结束演练"""
    return unified_response(training_service.end_practice(db, user.tenant_id, user.id, req.session_id))


@router.post("/scenarios/from-doctor/{doctor_id}")
async def generate_scenario_from_doctor(
    doctor_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """基于真实医生画像生成演练场景"""
    result = training_service.generate_scenario_from_doctor(
        db=db,
        tenant_id=str(user.tenant_id),
        doctor_id=doctor_id,
        user_id=user.id,
    )
    if result.get("error"):
        return unified_response(None, code=40004, message=result["error"])
    return unified_response(result)


@router.post("/ai-insights")
async def training_ai_insights(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """AI 培训洞察（查询预生成缓存）"""
    from services.ai_insight_service import ai_insight_service
    result = ai_insight_service.get_cached_insight(domain="training", tenant_id=user.tenant_id, user_id=user.id, db=db)
    return unified_response(result)
