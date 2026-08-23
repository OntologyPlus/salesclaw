"""门户 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import (
    get_db, User, VisitPlan, VisitRecord, BehaviorPointRecord,
    Course, CourseEnrollment, ExamRecord, Certificate,
)
from core.response import unified_response
from middleware.auth import get_current_user

router = APIRouter(prefix="/portal")


@router.get("/overview")
async def overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """门户概览统计（整合销售 + 培训双域）"""
    tenant_id = user.tenant_id

    # ── 销售域统计 ──
    visit_count = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id == user.id,
    ).count()
    plan_count = db.query(VisitPlan).filter(
        VisitPlan.tenant_id == tenant_id,
        VisitPlan.is_deleted == 0,
        VisitPlan.user_id == user.id,
        VisitPlan.status == "approved",
    ).count()
    total_points = db.query(func.sum(BehaviorPointRecord.points)).filter(
        BehaviorPointRecord.tenant_id == tenant_id,
        BehaviorPointRecord.is_deleted == 0,
        BehaviorPointRecord.user_id == user.id,
    ).scalar() or 0

    # ── 培训域统计 ──
    courses_count = db.query(Course).filter(
        Course.tenant_id == tenant_id,
        Course.is_deleted == 0,
        Course.is_published == 1,
    ).count()
    enrolled_count = db.query(CourseEnrollment).filter(
        CourseEnrollment.tenant_id == tenant_id,
        CourseEnrollment.is_deleted == 0,
        CourseEnrollment.user_id == user.id,
    ).count()
    certificates_count = db.query(Certificate).filter(
        Certificate.tenant_id == tenant_id,
        Certificate.is_deleted == 0,
        Certificate.user_id == user.id,
    ).count()
    # 学分
    from database import PathEnrollment
    credits = db.query(func.sum(PathEnrollment.credits_earned)).filter(
        PathEnrollment.tenant_id == tenant_id,
        PathEnrollment.is_deleted == 0,
        PathEnrollment.user_id == user.id,
    ).scalar() or 0

    return unified_response({
        # 销售域
        "visit_count": visit_count,
        "plan_count": plan_count,
        "total_points": total_points,
        "coverage_rate": 78,  # 暂保留 Mock（需计算真实覆盖率）
        # 培训域
        "training_courses": courses_count,
        "enrolled_courses": enrolled_count,
        "certificates": certificates_count,
        "credits": credits,
        # 待实现的模块
        "knowledge_docs": 156,  # Mock（知识库模块未实现）
        "pending_tasks": 8,  # Mock（协作模块未实现）
    })


@router.get("/shortcuts")
async def shortcuts(user: User = Depends(get_current_user)):
    """快捷入口"""
    return unified_response({"items": [
        {"name": "新建拜访计划", "path": "/sales/plans", "icon": "CalendarCheck"},
        {"name": "记录拜访", "path": "/sales/records", "icon": "FileText"},
        {"name": "我的画像", "path": "/profile", "icon": "Target"},
        {"name": "AI 助手", "path": "/ai", "icon": "Sparkles"},
        {"name": "知识库", "path": "/knowledge", "icon": "BookOpen"},
        {"name": "待办", "path": "/collab", "icon": "CheckSquare"},
    ]})


@router.get("/activities")
async def activities(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """最近活动（合并销售 + 培训双域活动流）"""
    tenant_id = user.tenant_id
    activities = []

    # ── 销售活动：拜访记录 ──
    visit_records = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id == user.id,
    ).order_by(VisitRecord.visit_date.desc()).limit(5).all()
    for r in visit_records:
        activities.append({
            "type": "visit",
            "title": f"拜访了 {r.summary[:30]}..." if r.summary and len(r.summary) > 30 else (r.summary or "拜访记录"),
            "date": str(r.visit_date) if r.visit_date else None,
        })

    # ── 培训活动：课程完成 ──
    course_completions = db.query(CourseEnrollment).filter(
        CourseEnrollment.tenant_id == tenant_id,
        CourseEnrollment.is_deleted == 0,
        CourseEnrollment.user_id == user.id,
        CourseEnrollment.status == "completed",
    ).order_by(CourseEnrollment.completed_at.desc()).limit(5).all()
    course_ids = {e.course_id for e in course_completions}
    courses_map = {c.id: c for c in db.query(Course).filter(
        Course.tenant_id == tenant_id,
        Course.is_deleted == 0,
        Course.id.in_(course_ids),
    ).all()} if course_ids else {}
    for e in course_completions:
        c = courses_map.get(e.course_id)
        activities.append({
            "type": "course_completed",
            "title": f"完成课程：{c.title}" if c else f"完成课程 #{e.course_id}",
            "date": e.completed_at.strftime("%Y-%m-%d %H:%M") if e.completed_at else None,
        })

    # ── 培训活动：考试提交 ──
    exam_records = db.query(ExamRecord).filter(
        ExamRecord.tenant_id == tenant_id,
        ExamRecord.is_deleted == 0,
        ExamRecord.user_id == user.id,
        ExamRecord.status == "submitted",
    ).order_by(ExamRecord.submitted_at.desc()).limit(5).all()
    for er in exam_records:
        activities.append({
            "type": "exam_submitted",
            "title": f"提交考试 #{er.exam_id}（{er.score}分）",
            "date": er.submitted_at.strftime("%Y-%m-%d %H:%M") if er.submitted_at else None,
        })

    # 合并按时间倒序
    activities.sort(key=lambda x: x.get("date") or "", reverse=True)

    return unified_response({"items": activities[:10]})
