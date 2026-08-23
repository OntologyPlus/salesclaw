"""智能培训域服务层"""
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.exceptions import NotFoundError, ValidationError, DataConflictError
from core.pagination import PageParams, paginate
from database import (
    Course, CourseEnrollment, Question, Exam, ExamRecord,
    LearningPath, PathEnrollment, Certificate,
    PracticeScenario, PracticeSession, Product,
)
from services import profile_service

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 序列化辅助
# ──────────────────────────────────────────────

def _serialize_course(c: Course, enrollment=None) -> dict:
    data = {
        "id": c.id,
        "title": c.title,
        "description": c.description,
        "course_type": c.course_type,
        "category": c.category,
        "difficulty": c.difficulty,
        "duration_minutes": c.duration_minutes,
        "cover_image": c.cover_image,
        "content_url": c.content_url,
        "tags": c.tags or [],
        "is_published": c.is_published,
        "enroll_count": c.enroll_count,
        "avg_rating": c.avg_rating,
        "created_at": c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else None,
    }
    if enrollment is not None:
        data["enrollment_status"] = enrollment.status if enrollment else None
        data["progress"] = enrollment.progress if enrollment else 0
    return data


def _serialize_question(q: Question) -> dict:
    return {
        "id": q.id,
        "question_type": q.question_type,
        "content": q.content,
        "options": q.options or [],
        "answer": q.answer or [],
        "explanation": q.explanation,
        "difficulty": q.difficulty,
        "category": q.category,
        "points": q.points,
    }


def _serialize_exam(e: Exam, questions=None) -> dict:
    data = {
        "id": e.id,
        "title": e.title,
        "description": e.description,
        "duration_minutes": e.duration_minutes,
        "pass_score": e.pass_score,
        "question_ids": e.question_ids or [],
        "status": e.status,
        "start_at": e.start_at.strftime("%Y-%m-%d %H:%M:%S") if e.start_at else None,
        "end_at": e.end_at.strftime("%Y-%m-%d %H:%M:%S") if e.end_at else None,
        "max_attempts": e.max_attempts,
        "attempt_count": e.attempt_count,
    }
    if questions is not None:
        data["questions"] = [_serialize_question(q) for q in questions]
    return data


def _serialize_exam_record(r: ExamRecord) -> dict:
    return {
        "id": r.id,
        "exam_id": r.exam_id,
        "user_id": r.user_id,
        "status": r.status,
        "answers": r.answers or [],
        "score": r.score,
        "passed": r.passed,
        "started_at": r.started_at.strftime("%Y-%m-%d %H:%M:%S") if r.started_at else None,
        "submitted_at": r.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if r.submitted_at else None,
        "ai_comment": r.ai_comment,
    }


def _serialize_path(p: LearningPath) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "description": p.description,
        "target_role": p.target_role,
        "stages": p.stages or [],
        "total_credits": p.total_credits,
        "enroll_count": p.enroll_count,
        "is_published": p.is_published,
    }


def _serialize_certificate(c: Certificate) -> dict:
    return {
        "id": c.id,
        "user_id": c.user_id,
        "title": c.title,
        "cert_type": c.cert_type,
        "source_id": c.source_id,
        "score": c.score,
        "issued_at": c.issued_at.strftime("%Y-%m-%d %H:%M:%S") if c.issued_at else None,
        "expire_at": c.expire_at.strftime("%Y-%m-%d %H:%M:%S") if c.expire_at else None,
        "cert_no": c.cert_no,
    }


def _serialize_scenario(s: PracticeScenario, product=None) -> dict:
    data = {
        "id": s.id,
        "title": s.title,
        "description": s.description,
        "scenario_type": s.scenario_type,
        "customer_profile": s.customer_profile,
        "product_id": s.product_id,
        "product_name": product.name if product else None,
        "difficulty": s.difficulty,
        "target_skills": s.target_skills or [],
        "is_published": s.is_published,
        "doctor_id": getattr(s, "doctor_id", None),
        "hospital_id": getattr(s, "hospital_id", None),
    }
    return data


def _serialize_session(s: PracticeSession) -> dict:
    return {
        "id": s.id,
        "scenario_id": s.scenario_id,
        "user_id": s.user_id,
        "status": s.status,
        "messages": s.messages or [],
        "score": s.score,
        "feedback": s.feedback,
        "started_at": s.started_at.strftime("%Y-%m-%d %H:%M:%S") if s.started_at else None,
        "ended_at": s.ended_at.strftime("%Y-%m-%d %H:%M:%S") if s.ended_at else None,
    }


def _issue_certificate(db: Session, tenant_id: str, user_id: int, title: str,
                       cert_type: str, source_id: int, score: int = None) -> Certificate:
    """颁发证书（内部使用）"""
    cert = Certificate(
        tenant_id=tenant_id,
        user_id=user_id,
        title=title,
        cert_type=cert_type,
        source_id=source_id,
        score=score,
        issued_at=datetime.utcnow(),
        cert_no=f"CERT-{cert_type.upper()}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{user_id}",
    )
    db.add(cert)
    return cert


# ──────────────────────────────────────────────
# 概览统计
# ──────────────────────────────────────────────

def get_overview(db: Session, tenant_id: str, user_id: int) -> dict:
    """培训概览统计"""
    courses_count = db.query(Course).filter(
        Course.tenant_id == tenant_id,
        Course.is_deleted == 0,
        Course.is_published == 1,
    ).count()

    enrolled_count = db.query(CourseEnrollment).filter(
        CourseEnrollment.tenant_id == tenant_id,
        CourseEnrollment.is_deleted == 0,
        CourseEnrollment.user_id == user_id,
    ).count()

    completed_count = db.query(CourseEnrollment).filter(
        CourseEnrollment.tenant_id == tenant_id,
        CourseEnrollment.is_deleted == 0,
        CourseEnrollment.user_id == user_id,
        CourseEnrollment.status == "completed",
    ).count()

    # 平均进度
    avg_progress = db.query(func.avg(CourseEnrollment.progress)).filter(
        CourseEnrollment.tenant_id == tenant_id,
        CourseEnrollment.is_deleted == 0,
        CourseEnrollment.user_id == user_id,
    ).scalar()
    avg_progress = round(float(avg_progress), 1) if avg_progress else 0

    # 考试通过率
    total_exam_records = db.query(ExamRecord).filter(
        ExamRecord.tenant_id == tenant_id,
        ExamRecord.is_deleted == 0,
        ExamRecord.user_id == user_id,
        ExamRecord.status == "submitted",
    ).count()
    passed_exam_records = db.query(ExamRecord).filter(
        ExamRecord.tenant_id == tenant_id,
        ExamRecord.is_deleted == 0,
        ExamRecord.user_id == user_id,
        ExamRecord.status == "submitted",
        ExamRecord.passed == 1,
    ).count()
    exam_pass_rate = round(passed_exam_records / total_exam_records * 100, 1) if total_exam_records > 0 else 0

    # 学分（来自路径）
    credits = db.query(func.sum(PathEnrollment.credits_earned)).filter(
        PathEnrollment.tenant_id == tenant_id,
        PathEnrollment.is_deleted == 0,
        PathEnrollment.user_id == user_id,
    ).scalar() or 0

    certificates_count = db.query(Certificate).filter(
        Certificate.tenant_id == tenant_id,
        Certificate.is_deleted == 0,
        Certificate.user_id == user_id,
    ).count()

    paths_count = db.query(LearningPath).filter(
        LearningPath.tenant_id == tenant_id,
        LearningPath.is_deleted == 0,
        LearningPath.is_published == 1,
    ).count()

    return {
        "courses_count": courses_count,
        "enrolled_count": enrolled_count,
        "completed_count": completed_count,
        "avg_progress": avg_progress,
        "exam_pass_rate": exam_pass_rate,
        "credits": credits,
        "certificates_count": certificates_count,
        "paths_count": paths_count,
    }


# ──────────────────────────────────────────────
# 课程
# ──────────────────────────────────────────────

def list_courses(db: Session, tenant_id: str, category: str = None, difficulty: str = None,
                 keyword: str = None, page_params: PageParams = None) -> dict:
    """列表查询课程"""
    q = db.query(Course).filter(
        Course.tenant_id == tenant_id,
        Course.is_deleted == 0,
    )
    if category:
        q = q.filter(Course.category == category)
    if difficulty:
        q = q.filter(Course.difficulty == difficulty)
    if keyword:
        q = q.filter(Course.title.like(f"%{keyword}%"))
    total = q.count()
    if page_params:
        q = q.order_by(Course.id.desc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(Course.id.desc())
    courses = q.all()
    items = [{
        "id": c.id,
        "title": c.title,
        "course_type": c.course_type,
        "category": c.category,
        "difficulty": c.difficulty,
        "duration_minutes": c.duration_minutes,
        "enroll_count": c.enroll_count,
        "avg_rating": c.avg_rating,
        "is_published": c.is_published,
    } for c in courses]
    return paginate(items, total, page_params or PageParams())


def get_course(db: Session, tenant_id: str, course_id: int) -> dict:
    """获取课程详情"""
    course = db.query(Course).filter(
        Course.tenant_id == tenant_id,
        Course.is_deleted == 0,
        Course.id == course_id,
    ).first()
    if not course:
        raise NotFoundError("课程不存在")
    return _serialize_course(course)


def create_course(db: Session, tenant_id: str, data: dict) -> dict:
    """创建课程"""
    if not data.get("title"):
        raise ValidationError("title 不能为空")
    course = Course(
        tenant_id=tenant_id,
        title=data["title"],
        description=data.get("description"),
        course_type=data.get("course_type", "video"),
        category=data.get("category"),
        difficulty=data.get("difficulty", "beginner"),
        duration_minutes=data.get("duration_minutes", 0),
        cover_image=data.get("cover_image"),
        content_url=data.get("content_url"),
        tags=data.get("tags") or [],
        is_published=data.get("is_published", 0),
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return _serialize_course(course)


def update_course(db: Session, tenant_id: str, course_id: int, data: dict) -> dict:
    """更新课程"""
    course = db.query(Course).filter(
        Course.tenant_id == tenant_id,
        Course.is_deleted == 0,
        Course.id == course_id,
    ).first()
    if not course:
        raise NotFoundError("课程不存在")
    for field in ["title", "description", "course_type", "category", "difficulty",
                  "duration_minutes", "cover_image", "content_url", "tags", "is_published"]:
        if field in data and data[field] is not None:
            setattr(course, field, data[field])
    db.commit()
    db.refresh(course)
    return _serialize_course(course)


def delete_course(db: Session, tenant_id: str, course_id: int) -> None:
    """软删除课程"""
    course = db.query(Course).filter(
        Course.tenant_id == tenant_id,
        Course.is_deleted == 0,
        Course.id == course_id,
    ).first()
    if not course:
        raise NotFoundError("课程不存在")
    course.is_deleted = 1
    course.deleted_at = datetime.utcnow()
    db.commit()


def enroll_course(db: Session, tenant_id: str, user_id: int, course_id: int) -> dict:
    """选课"""
    course = db.query(Course).filter(
        Course.tenant_id == tenant_id,
        Course.is_deleted == 0,
        Course.id == course_id,
    ).first()
    if not course:
        raise NotFoundError("课程不存在")
    existing = db.query(CourseEnrollment).filter(
        CourseEnrollment.tenant_id == tenant_id,
        CourseEnrollment.is_deleted == 0,
        CourseEnrollment.course_id == course_id,
        CourseEnrollment.user_id == user_id,
    ).first()
    if existing:
        return {
            "id": existing.id,
            "course_id": course_id,
            "status": existing.status,
            "already_enrolled": True,
        }
    enroll = CourseEnrollment(
        tenant_id=tenant_id,
        course_id=course_id,
        user_id=user_id,
        status="enrolled",
        progress=0,
        enrolled_at=datetime.utcnow(),
    )
    db.add(enroll)
    course.enroll_count = (course.enroll_count or 0) + 1
    db.commit()
    db.refresh(enroll)
    return {
        "id": enroll.id,
        "course_id": course_id,
        "status": enroll.status,
        "already_enrolled": False,
    }


def get_course_progress(db: Session, tenant_id: str, user_id: int, course_id: int) -> dict:
    """获取课程进度"""
    enroll = db.query(CourseEnrollment).filter(
        CourseEnrollment.tenant_id == tenant_id,
        CourseEnrollment.is_deleted == 0,
        CourseEnrollment.course_id == course_id,
        CourseEnrollment.user_id == user_id,
    ).first()
    if not enroll:
        raise NotFoundError("尚未选课")
    return {
        "course_id": course_id,
        "status": enroll.status,
        "progress": enroll.progress,
        "last_position": enroll.last_position,
        "enrolled_at": enroll.enrolled_at.strftime("%Y-%m-%d %H:%M:%S") if enroll.enrolled_at else None,
        "completed_at": enroll.completed_at.strftime("%Y-%m-%d %H:%M:%S") if enroll.completed_at else None,
    }


def update_course_progress(db: Session, tenant_id: str, user_id: int, course_id: int,
                           progress: int, last_position: int = 0) -> dict:
    """更新课程进度，100% 时设为 completed 并自动颁发证书，触发能力分重算"""
    enroll = db.query(CourseEnrollment).filter(
        CourseEnrollment.tenant_id == tenant_id,
        CourseEnrollment.is_deleted == 0,
        CourseEnrollment.course_id == course_id,
        CourseEnrollment.user_id == user_id,
    ).first()
    if not enroll:
        raise NotFoundError("尚未选课")
    new_ability_score = None
    if progress is not None:
        enroll.progress = max(0, min(100, int(progress)))
        if enroll.progress >= 100 and enroll.status != "completed":
            enroll.status = "completed"
            enroll.completed_at = datetime.utcnow()
            # 颁发证书
            course = db.query(Course).filter(Course.id == course_id).first()
            cert_title = f"{course.title}结业证书" if course else "课程结业证书"
            _issue_certificate(db, tenant_id, user_id, cert_title, "course", course_id)
            # 行为→能力飞轮：课程完成触发能力分重算
            new_ability_score = profile_service.recalculate_ability_score(db, tenant_id, user_id)
            # 发布课程完成事件（触发能力分重算 + 拜访建议推送）
            try:
                from ai.event_bus import event_bus
                event_bus.publish(
                    "course_completed",
                    {
                        "user_id": user_id,
                        "course_id": course_id,
                        "tenant_id": tenant_id,
                    },
                    tenant_id=tenant_id,
                    consistency="eventual",
                    db=db,
                )
            except Exception as e:
                logger.warning("课程完成事件发布失败: %s", e, exc_info=True)
        elif enroll.status == "enrolled":
            enroll.status = "in_progress"
    if last_position is not None:
        enroll.last_position = last_position
    db.commit()
    db.refresh(enroll)
    return {
        "course_id": course_id,
        "status": enroll.status,
        "progress": enroll.progress,
        "last_position": enroll.last_position,
        "completed_at": enroll.completed_at.strftime("%Y-%m-%d %H:%M:%S") if enroll.completed_at else None,
        "ability_score": new_ability_score,
    }


# ──────────────────────────────────────────────
# 题库
# ──────────────────────────────────────────────

def list_questions(db: Session, tenant_id: str, category: str = None, question_type: str = None,
                   difficulty: str = None, page_params: PageParams = None) -> dict:
    """列表查询题目"""
    q = db.query(Question).filter(
        Question.tenant_id == tenant_id,
        Question.is_deleted == 0,
    )
    if category:
        q = q.filter(Question.category == category)
    if question_type:
        q = q.filter(Question.question_type == question_type)
    if difficulty:
        q = q.filter(Question.difficulty == difficulty)
    total = q.count()
    if page_params:
        q = q.order_by(Question.id.desc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(Question.id.desc())
    questions = q.all()
    items = [{
        "id": qs.id,
        "question_type": qs.question_type,
        "content": qs.content,
        "options": qs.options or [],
        "difficulty": qs.difficulty,
        "category": qs.category,
        "points": qs.points,
    } for qs in questions]
    return paginate(items, total, page_params or PageParams())


def create_question(db: Session, tenant_id: str, data: dict) -> dict:
    """创建题目"""
    if not data.get("content"):
        raise ValidationError("content 不能为空")
    if not data.get("question_type"):
        raise ValidationError("question_type 不能为空")
    question = Question(
        tenant_id=tenant_id,
        question_type=data["question_type"],
        content=data["content"],
        options=data.get("options") or [],
        answer=data.get("answer") or [],
        explanation=data.get("explanation"),
        difficulty=data.get("difficulty", "medium"),
        category=data.get("category"),
        points=data.get("points", 5),
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return _serialize_question(question)


# ──────────────────────────────────────────────
# 考试
# ──────────────────────────────────────────────

def list_exams(db: Session, tenant_id: str, status: str = None,
               page_params: PageParams = None) -> dict:
    """列表查询考试"""
    q = db.query(Exam).filter(
        Exam.tenant_id == tenant_id,
        Exam.is_deleted == 0,
    )
    if status:
        q = q.filter(Exam.status == status)
    total = q.count()
    if page_params:
        q = q.order_by(Exam.id.desc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(Exam.id.desc())
    exams = q.all()
    items = [{
        "id": e.id,
        "title": e.title,
        "description": e.description,
        "duration_minutes": e.duration_minutes,
        "pass_score": e.pass_score,
        "status": e.status,
        "start_at": e.start_at.strftime("%Y-%m-%d %H:%M:%S") if e.start_at else None,
        "end_at": e.end_at.strftime("%Y-%m-%d %H:%M:%S") if e.end_at else None,
        "question_count": len(e.question_ids or []),
        "attempt_count": e.attempt_count,
    } for e in exams]
    return paginate(items, total, page_params or PageParams())


def get_exam(db: Session, tenant_id: str, exam_id: int) -> dict:
    """获取考试详情（含题目）"""
    exam = db.query(Exam).filter(
        Exam.tenant_id == tenant_id,
        Exam.is_deleted == 0,
        Exam.id == exam_id,
    ).first()
    if not exam:
        raise NotFoundError("考试不存在")
    question_ids = exam.question_ids or []
    questions = []
    if question_ids:
        questions = db.query(Question).filter(
            Question.id.in_(question_ids),
            Question.is_deleted == 0,
        ).all()
        # 保持 question_ids 顺序
        qmap = {q.id: q for q in questions}
        questions = [qmap[qid] for qid in question_ids if qid in qmap]
    return _serialize_exam(exam, questions)


def create_exam(db: Session, tenant_id: str, data: dict) -> dict:
    """创建考试"""
    if not data.get("title"):
        raise ValidationError("title 不能为空")
    exam = Exam(
        tenant_id=tenant_id,
        title=data["title"],
        description=data.get("description"),
        duration_minutes=data.get("duration_minutes", 60),
        pass_score=data.get("pass_score", 60),
        question_ids=data.get("question_ids") or [],
        status=data.get("status", "draft"),
        start_at=data.get("start_at"),
        end_at=data.get("end_at"),
        max_attempts=data.get("max_attempts", 1),
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return _serialize_exam(exam)


def submit_exam(db: Session, tenant_id: str, user_id: int, exam_id: int, answers: list) -> dict:
    """提交考试，自动阅卷"""
    exam = db.query(Exam).filter(
        Exam.tenant_id == tenant_id,
        Exam.is_deleted == 0,
        Exam.id == exam_id,
    ).first()
    if not exam:
        raise NotFoundError("考试不存在")
    question_ids = exam.question_ids or []
    questions = db.query(Question).filter(
        Question.id.in_(question_ids),
        Question.is_deleted == 0,
    ).all() if question_ids else []
    qmap = {q.id: q for q in questions}
    # 阅卷
    total_points = 0
    earned_points = 0
    answer_map = {a.get("question_id"): (a.get("answer") or []) for a in answers}
    for qid in question_ids:
        q = qmap.get(qid)
        if not q:
            continue
        total_points += q.points or 0
        user_ans = answer_map.get(qid, [])
        correct_ans = q.answer or []
        # 统一为字符串集合比较
        if set(str(x) for x in user_ans) == set(str(x) for x in correct_ans) and correct_ans:
            earned_points += q.points or 0
    score = round(earned_points / total_points * 100) if total_points > 0 else 0
    passed = 1 if score >= (exam.pass_score or 60) else 0
    now = datetime.utcnow()
    record = ExamRecord(
        tenant_id=tenant_id,
        exam_id=exam_id,
        user_id=user_id,
        status="submitted",
        answers=answers,
        score=score,
        passed=passed,
        submitted_at=now,
        ai_comment="自动阅卷完成。" + ("通过考试，建议继续巩固。" if passed else "未通过，建议复习相关课程后重试。"),
    )
    db.add(record)
    exam.attempt_count = (exam.attempt_count or 0) + 1
    # 通过则颁发证书
    if passed:
        _issue_certificate(db, tenant_id, user_id, f"{exam.title}通过证书", "exam", exam_id, score)
    db.commit()
    # 考试通过 → 发 exam_passed 事件（B 路径：触发培训效果归因建 DecisionExecution）
    if passed:
        try:
            from ai.event_bus import event_bus
            event_bus.publish(
                "exam_passed",
                {
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "exam_id": exam_id,
                    "exam_title": exam.title,
                    "score": score,
                    "__event_type__": "exam_passed",
                },
                tenant_id=tenant_id,
                consistency="eventual",
                affected_domains=["training", "profile", "decision"],
            )
        except Exception as e:
            logger.warning("考试通过事件发布失败: %s", e, exc_info=True)
    db.refresh(record)
    # 考试未通过 → 发布课程推荐事件（触发学习需求重算）
    if not passed:
        try:
            from ai.event_bus import event_bus
            event_bus.publish(
                "course_recommended",
                {
                    "user_id": user_id,
                    "exam_id": exam_id,
                    "score": score,
                    "reason": "exam_failed",
                },
                tenant_id=tenant_id,
                consistency="eventual",
                db=db,
            )
        except Exception as e:
            logger.warning("考试低分课程推荐事件发布失败: %s", e, exc_info=True)
    return _serialize_exam_record(record)


def get_exam_result(db: Session, tenant_id: str, user_id: int, exam_id: int) -> dict:
    """获取考试结果（取最近一次）"""
    record = db.query(ExamRecord).filter(
        ExamRecord.tenant_id == tenant_id,
        ExamRecord.is_deleted == 0,
        ExamRecord.exam_id == exam_id,
        ExamRecord.user_id == user_id,
    ).order_by(ExamRecord.id.desc()).first()
    if not record:
        raise NotFoundError("暂无考试记录")
    return _serialize_exam_record(record)


# ──────────────────────────────────────────────
# 学习路径
# ──────────────────────────────────────────────

def list_paths(db: Session, tenant_id: str, page_params: PageParams = None) -> dict:
    """列表查询学习路径"""
    q = db.query(LearningPath).filter(
        LearningPath.tenant_id == tenant_id,
        LearningPath.is_deleted == 0,
    )
    total = q.count()
    if page_params:
        q = q.order_by(LearningPath.id.desc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(LearningPath.id.desc())
    paths = q.all()
    items = [{
        "id": p.id,
        "title": p.title,
        "description": p.description,
        "target_role": p.target_role,
        "total_credits": p.total_credits,
        "enroll_count": p.enroll_count,
        "is_published": p.is_published,
        "stages_count": len(p.stages or []),
    } for p in paths]
    return paginate(items, total, page_params or PageParams())


def get_path(db: Session, tenant_id: str, path_id: int) -> dict:
    """获取学习路径详情"""
    path = db.query(LearningPath).filter(
        LearningPath.tenant_id == tenant_id,
        LearningPath.is_deleted == 0,
        LearningPath.id == path_id,
    ).first()
    if not path:
        raise NotFoundError("学习路径不存在")
    return _serialize_path(path)


def create_path(db: Session, tenant_id: str, data: dict) -> dict:
    """创建学习路径"""
    if not data.get("title"):
        raise ValidationError("title 不能为空")
    path = LearningPath(
        tenant_id=tenant_id,
        title=data["title"],
        description=data.get("description"),
        target_role=data.get("target_role"),
        stages=data.get("stages") or [],
        total_credits=data.get("total_credits", 0),
        is_published=data.get("is_published", 0),
    )
    db.add(path)
    db.commit()
    db.refresh(path)
    return _serialize_path(path)


def enroll_path(db: Session, tenant_id: str, user_id: int, path_id: int) -> dict:
    """学习路径选课"""
    path = db.query(LearningPath).filter(
        LearningPath.tenant_id == tenant_id,
        LearningPath.is_deleted == 0,
        LearningPath.id == path_id,
    ).first()
    if not path:
        raise NotFoundError("学习路径不存在")
    existing = db.query(PathEnrollment).filter(
        PathEnrollment.tenant_id == tenant_id,
        PathEnrollment.is_deleted == 0,
        PathEnrollment.path_id == path_id,
        PathEnrollment.user_id == user_id,
    ).first()
    if existing:
        return {
            "id": existing.id,
            "path_id": path_id,
            "status": existing.status,
            "already_enrolled": True,
        }
    enroll = PathEnrollment(
        tenant_id=tenant_id,
        path_id=path_id,
        user_id=user_id,
        current_stage=1,
        credits_earned=0,
        status="enrolled",
        enrolled_at=datetime.utcnow(),
    )
    db.add(enroll)
    path.enroll_count = (path.enroll_count or 0) + 1
    db.commit()
    db.refresh(enroll)
    return {
        "id": enroll.id,
        "path_id": path_id,
        "status": enroll.status,
        "current_stage": enroll.current_stage,
        "already_enrolled": False,
    }


# ──────────────────────────────────────────────
# 我的学习
# ──────────────────────────────────────────────

def get_my_learning(db: Session, tenant_id: str, user_id: int) -> dict:
    """我的学习概览"""
    # 进行中课程
    in_progress_enrolls = db.query(CourseEnrollment).filter(
        CourseEnrollment.tenant_id == tenant_id,
        CourseEnrollment.is_deleted == 0,
        CourseEnrollment.user_id == user_id,
        CourseEnrollment.status.in_(["enrolled", "in_progress"]),
    ).all()
    course_ids = {e.course_id for e in in_progress_enrolls}
    courses_map = {c.id: c for c in db.query(Course).filter(Course.id.in_(course_ids)).all()} if course_ids else {}
    in_progress_courses = [{
        "course_id": e.course_id,
        "title": courses_map.get(e.course_id).title if courses_map.get(e.course_id) else None,
        "progress": e.progress,
        "status": e.status,
    } for e in in_progress_enrolls]

    # 已完成课程
    completed_enrolls = db.query(CourseEnrollment).filter(
        CourseEnrollment.tenant_id == tenant_id,
        CourseEnrollment.is_deleted == 0,
        CourseEnrollment.user_id == user_id,
        CourseEnrollment.status == "completed",
    ).all()
    completed_course_ids = {e.course_id for e in completed_enrolls}
    completed_courses_map = {c.id: c for c in db.query(Course).filter(Course.id.in_(completed_course_ids)).all()} if completed_course_ids else {}
    completed_courses = [{
        "course_id": e.course_id,
        "title": completed_courses_map.get(e.course_id).title if completed_courses_map.get(e.course_id) else None,
        "completed_at": e.completed_at.strftime("%Y-%m-%d %H:%M:%S") if e.completed_at else None,
    } for e in completed_enrolls]

    # 进行中路径
    in_progress_paths = db.query(PathEnrollment).filter(
        PathEnrollment.tenant_id == tenant_id,
        PathEnrollment.is_deleted == 0,
        PathEnrollment.user_id == user_id,
        PathEnrollment.status == "enrolled",
    ).all()
    path_ids = {e.path_id for e in in_progress_paths}
    paths_map = {p.id: p for p in db.query(LearningPath).filter(LearningPath.id.in_(path_ids)).all()} if path_ids else {}
    in_progress_path_list = [{
        "path_id": e.path_id,
        "title": paths_map.get(e.path_id).title if paths_map.get(e.path_id) else None,
        "current_stage": e.current_stage,
        "credits_earned": e.credits_earned,
    } for e in in_progress_paths]

    # 学分
    credits = db.query(func.sum(PathEnrollment.credits_earned)).filter(
        PathEnrollment.tenant_id == tenant_id,
        PathEnrollment.is_deleted == 0,
        PathEnrollment.user_id == user_id,
    ).scalar() or 0

    # 证书数
    certificates_count = db.query(Certificate).filter(
        Certificate.tenant_id == tenant_id,
        Certificate.is_deleted == 0,
        Certificate.user_id == user_id,
    ).count()

    return {
        "in_progress_courses": in_progress_courses,
        "completed_courses": completed_courses,
        "in_progress_paths": in_progress_path_list,
        "credits": credits,
        "certificates_count": certificates_count,
    }


# ──────────────────────────────────────────────
# 证书
# ──────────────────────────────────────────────

def list_certificates(db: Session, tenant_id: str, user_id: int,
                      page_params: PageParams = None) -> dict:
    """列表查询证书"""
    q = db.query(Certificate).filter(
        Certificate.tenant_id == tenant_id,
        Certificate.is_deleted == 0,
        Certificate.user_id == user_id,
    )
    total = q.count()
    if page_params:
        q = q.order_by(Certificate.issued_at.desc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(Certificate.issued_at.desc())
    certs = q.all()
    items = [_serialize_certificate(c) for c in certs]
    return paginate(items, total, page_params or PageParams())


# ──────────────────────────────────────────────
# 演练
# ──────────────────────────────────────────────

def list_scenarios(db: Session, tenant_id: str, page_params: PageParams = None) -> dict:
    """列表查询演练场景"""
    q = db.query(PracticeScenario).filter(
        PracticeScenario.tenant_id == tenant_id,
        PracticeScenario.is_deleted == 0,
        PracticeScenario.is_published == 1,
    )
    total = q.count()
    if page_params:
        q = q.order_by(PracticeScenario.id.desc()).offset(page_params.offset()).limit(page_params.effective_page_size())
    else:
        q = q.order_by(PracticeScenario.id.desc())
    scenarios = q.all()
    product_ids = {s.product_id for s in scenarios if s.product_id}
    products = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()} if product_ids else {}
    items = [_serialize_scenario(s, products.get(s.product_id)) for s in scenarios]
    return paginate(items, total, page_params or PageParams())


def start_practice(db: Session, tenant_id: str, user_id: int, scenario_id: int) -> dict:
    """开始演练，创建会话，返回 session_id 和 AI 开场白"""
    scenario = db.query(PracticeScenario).filter(
        PracticeScenario.tenant_id == tenant_id,
        PracticeScenario.is_deleted == 0,
        PracticeScenario.id == scenario_id,
    ).first()
    if not scenario:
        raise NotFoundError("演练场景不存在")
    opening = (
        f"您好，我是 {scenario.title} 场景中的客户。\n"
        f"{scenario.customer_profile or ''}\n"
        "请开始您的拜访吧。"
    )
    session = PracticeSession(
        tenant_id=tenant_id,
        scenario_id=scenario_id,
        user_id=user_id,
        status="in_progress",
        messages=[{"role": "ai", "content": opening}],
        started_at=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {
        "session_id": session.id,
        "scenario_id": scenario_id,
        "opening": opening,
        "status": session.status,
    }


async def practice_message(db: Session, tenant_id: str, user_id: int, session_id: int,
                           message: str) -> dict:
    """演练对话，返回 AI 回复"""
    session = db.query(PracticeSession).filter(
        PracticeSession.tenant_id == tenant_id,
        PracticeSession.is_deleted == 0,
        PracticeSession.id == session_id,
        PracticeSession.user_id == user_id,
    ).first()
    if not session:
        raise NotFoundError("演练会话不存在")
    if session.status != "in_progress":
        raise ValidationError("会话已结束")
    from ai.orchestrator import Orchestrator
    orch = Orchestrator()
    scenario = db.query(PracticeScenario).filter(PracticeScenario.id == session.scenario_id).first()
    messages = (session.messages or []) + [{"role": "user", "content": message}]
    reply = await orch.practice_reply(scenario, messages)
    session.messages = messages + [{"role": "ai", "content": reply}]
    db.commit()
    return {
        "session_id": session_id,
        "reply": reply,
    }


def end_practice(db: Session, tenant_id: str, user_id: int, session_id: int) -> dict:
    """结束演练，AI 评分和反馈"""
    session = db.query(PracticeSession).filter(
        PracticeSession.tenant_id == tenant_id,
        PracticeSession.is_deleted == 0,
        PracticeSession.id == session_id,
        PracticeSession.user_id == user_id,
    ).first()
    if not session:
        raise NotFoundError("演练会话不存在")
    if session.status != "in_progress":
        return {
            "session_id": session_id,
            "score": session.score,
            "feedback": session.feedback,
            "already_ended": True,
        }
    # Mock 评分
    msg_count = len([m for m in (session.messages or []) if m.get("role") == "user"])
    score = min(95, 60 + msg_count * 5)
    feedback = (
        f"演练结束。共交流 {msg_count} 轮。\n"
        f"得分：{score} 分。\n"
        "亮点：能围绕客户需求展开对话。\n"
        "改进建议：可补充更多临床数据支撑，强化价值塑造。"
    )
    session.status = "completed"
    session.score = score
    session.feedback = feedback
    session.ended_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return {
        "session_id": session_id,
        "score": session.score,
        "feedback": session.feedback,
        "status": session.status,
    }


def generate_scenario_from_doctor(
    db: Session, tenant_id: str, doctor_id: int, user_id: int = None
) -> dict:
    """基于真实医生画像生成演练场景

    查询医生信息（姓名、科室、职称、所属医院）+ 近期拜访反馈，
    调用 LLM 生成个性化演练场景。LLM 不可用时降级为规则生成。

    Returns:
        生成的 PracticeScenario 字典
    """
    from database import Doctor, Hospital, VisitRecord, VisitFeedback
    from ai.llm_client import llm_client

    doctor = db.query(Doctor).filter(
        Doctor.id == doctor_id,
        Doctor.tenant_id == tenant_id,
        Doctor.is_deleted == 0,
    ).first()
    if not doctor:
        return {"error": "doctor_not_found", "doctor_id": doctor_id}

    hospital = db.query(Hospital).filter(Hospital.id == doctor.hospital_id).first() if doctor.hospital_id else None

    # 查询近 30 天拜访反馈
    recent_feedbacks = db.query(VisitFeedback).join(
        VisitRecord, VisitRecord.id == VisitFeedback.record_id
    ).filter(
        VisitRecord.doctor_id == doctor_id,
        VisitRecord.tenant_id == tenant_id,
        VisitFeedback.is_deleted == 0,
    ).order_by(VisitFeedback.created_at.desc()).limit(5).all()

    # 构建医生画像
    profile_parts = [
        f"姓名：{doctor.name}",
        f"科室：{doctor.department or '未知'}",
        f"职称：{doctor.title or '未知'}",
        f"医院：{hospital.name if hospital else '未知'}",
    ]
    if recent_feedbacks:
        objections = []
        for fb in recent_feedbacks:
            objections.extend(fb.objections or [])
        if objections:
            profile_parts.append(f"近期异议：{', '.join(set(objections[:5]))}")

    customer_profile = "\n".join(profile_parts)

    # 调用 LLM 生成场景
    system_prompt = f"""你是医药销售培训专家。基于以下客户画像，生成一个个性化的演练场景。

客户画像：
{customer_profile}

请输出 JSON 格式：
{{
    "title": "场景标题（简短）",
    "description": "场景描述（1-2 句话）",
    "scenario_type": "visit | negotiation | objection",
    "difficulty": "easy | medium | hard",
    "target_skills": ["技能1", "技能2", "技能3"]
}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"请为医生 {doctor.name} 生成演练场景"},
    ]

    scenario_data = None
    provider = "mock_fallback"
    try:
        result = llm_client.chat(messages=messages, intent="scene", tenant_id=tenant_id)
        if result.get("provider") != "mock" and result.get("content"):
            import json
            import re
            content = result["content"]
            # 尝试提取 JSON
            json_match = re.search(r'\{[^{}]*"title"[^{}]*\}', content, re.DOTALL)
            if json_match:
                try:
                    scenario_data = json.loads(json_match.group(0))
                    provider = result.get("provider")
                except Exception as e:
                    logger.debug("LLM 演练场景 JSON 解析失败: %s", e, exc_info=True)
    except Exception as e:
        logger.debug("LLM 演练场景生成失败: %s", e, exc_info=True)

    # 持久化
    if scenario_data:
        scenario = PracticeScenario(
            tenant_id=tenant_id,
            title=scenario_data.get("title", f"{doctor.name} 演练场景"),
            description=scenario_data.get("description", ""),
            scenario_type=scenario_data.get("scenario_type", "visit"),
            customer_profile=customer_profile,
            difficulty=scenario_data.get("difficulty", "medium"),
            target_skills=scenario_data.get("target_skills", []),
            is_published=0,
            doctor_id=doctor_id,
            hospital_id=doctor.hospital_id,
        )
    else:
        # 降级：生成基于画像的简单场景
        scenario = PracticeScenario(
            tenant_id=tenant_id,
            title=f"拜访 {doctor.name}（{doctor.department or ''}）",
            description="基于真实医生画像生成的演练场景",
            scenario_type="visit",
            customer_profile=customer_profile,
            difficulty="medium",
            target_skills=["开场", "需求探寻", "缔结"],
            is_published=0,
            doctor_id=doctor_id,
            hospital_id=doctor.hospital_id,
        )

    db.add(scenario)
    db.commit()
    db.refresh(scenario)

    return {
        "scenario_id": scenario.id,
        "doctor_id": doctor_id,
        "doctor_name": doctor.name,
        "title": scenario.title,
        "description": scenario.description,
        "scenario_type": scenario.scenario_type,
        "difficulty": scenario.difficulty,
        "target_skills": scenario.target_skills,
        "customer_profile": customer_profile,
        "provider": provider,
    }


# ──────────────────────────────────────────────
# N+4 Batch 2.3: 培训域自适应
# 实现 TrainingServicePort：recommend_scenarios / apply_session_to_ability
# 跨域调用通过 registry.get(ProfileServicePort)，不直接 import 跨域 service。
# ──────────────────────────────────────────────

def recommend_scenarios(db: Session, user_id: int, context: dict = None) -> list:
    """基于画像弱项 + 近期训练 + RAG 知识推荐 Top5

    通过 registry.get(ProfileServicePort).get_weakest_dimensions() 获取弱项，
    匹配 PracticeScenario.target_skills / scoring_dimensions。

    Args:
        user_id: 用户 ID
        context: 可选上下文 {dimension, scenario_type, ...}

    Returns:
        推荐场景列表 [{id, title, scenario_type, difficulty, target_skills, reason}]
    """
    from core.service_registry import registry
    from core.service_ports import ProfileServicePort

    ctx = context or {}
    target_dimension = ctx.get("dimension")
    scenario_type = ctx.get("scenario_type")

    # 1. 获取画像弱项
    weak_dims = []
    profile_svc = registry.get(ProfileServicePort)
    if profile_svc is not None:
        weak_dims = profile_svc.get_weakest_dimensions(db, user_id, n=2)
    weak_dim_keys = [d["dimension"] for d in weak_dims]

    # 如果指定了 dimension，优先匹配
    if target_dimension and target_dimension not in weak_dim_keys:
        weak_dim_keys.insert(0, target_dimension)

    # 2. 查询已发布的场景
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(days=30)
    query = db.query(PracticeScenario).filter(
        PracticeScenario.is_deleted == 0,
        PracticeScenario.is_published == 1,
    )
    if scenario_type:
        query = query.filter(PracticeScenario.scenario_type == scenario_type)

    scenarios = query.order_by(PracticeScenario.id.desc()).limit(20).all()
    if not scenarios:
        return []

    # 3. 排除近 30 天已完成的场景
    completed_scenario_ids = db.query(PracticeSession.scenario_id).filter(
        PracticeSession.user_id == user_id,
        PracticeSession.status == "completed",
        PracticeSession.is_deleted == 0,
        PracticeSession.started_at >= since,
    ).distinct().all()
    completed_ids = {sid[0] for sid in completed_scenario_ids}

    candidates = [s for s in scenarios if s.id not in completed_ids]
    if not candidates:
        candidates = scenarios  # 若全已完成，返回全部

    # 4. 按弱项匹配度排序
    def match_score(s):
        skills = list(s.target_skills or [])
        dims = list(s.scoring_dimensions or [])
        # 提取 scoring_dimensions 中的 key
        dim_keys = [d.get("key") if isinstance(d, dict) else d for d in dims]
        all_keys = set(skills + dim_keys)
        hits = len([k for k in weak_dim_keys if k in all_keys])
        return hits

    candidates.sort(key=match_score, reverse=True)
    top5 = candidates[:5]

    return [{
        "id": s.id,
        "title": s.title,
        "scenario_type": s.scenario_type,
        "difficulty": s.difficulty,
        "target_skills": s.target_skills or [],
        "reason": f"命中弱项 {weak_dim_keys}" if weak_dim_keys else "推荐学习",
    } for s in top5]


def apply_session_to_ability(db: Session, session_id: int) -> dict:
    """训练完成 → 画像更新

    根据 session_type 决定 delta 映射：
    - PPT 训战通过 → visit_skill +2, product_knowledge +1
    - 考试 90+ → product_knowledge +3
    - 场景练习通过 → visit_skill +1, customer_relation +1

    Args:
        session_id: 演练会话 ID

    Returns:
        {ok, applied: [{dimension, delta, source}]}
    """
    from core.service_registry import registry
    from core.service_ports import ProfileServicePort

    profile_svc = registry.get(ProfileServicePort)
    if profile_svc is None:
        return {"ok": False, "error": "ProfileService 未注册"}

    session = db.query(PracticeSession).filter(
        PracticeSession.is_deleted == 0,
        PracticeSession.id == session_id,
    ).first()
    if not session:
        return {"ok": False, "error": "演练会话不存在"}
    if session.status != "completed":
        return {"ok": False, "error": f"会话状态 {session.status} 不可传导"}

    scenario = db.query(PracticeScenario).filter(
        PracticeScenario.id == session.scenario_id,
        PracticeScenario.is_deleted == 0,
    ).first()

    # 根据 scenario_type 和 score 决定 delta 映射
    score = session.score or 0
    scenario_type = scenario.scenario_type if scenario else "visit"
    tenant_id = session.tenant_id or "default"
    user_id = session.user_id

    delta_map = []  # [(dimension, delta)]
    if scenario_type == "ppt_speech":
        if score >= 60:  # 通过
            delta_map.append(("visit_skill", 2.0))
            delta_map.append(("product_knowledge", 1.0))
    elif scenario_type == "visit":
        if score >= 60:
            delta_map.append(("visit_skill", 1.0))
            delta_map.append(("customer_relation", 1.0))
    elif scenario_type == "negotiation":
        if score >= 60:
            delta_map.append(("customer_relation", 2.0))
            delta_map.append(("visit_skill", 1.0))
    else:
        # 默认：通过即 +1 visit_skill
        if score >= 60:
            delta_map.append(("visit_skill", 1.0))

    # 高分加成
    if score >= 90:
        delta_map.append(("product_knowledge", 3.0))

    applied = []
    for dimension, delta in delta_map:
        result = profile_svc.update_ability_score(
            db, user_id, dimension, delta,
            source="training", source_id=session_id,
            evidence={"session_id": session_id, "score": score,
                      "scenario_type": scenario_type},
            tenant_id=tenant_id,
        )
        if result.get("ok"):
            applied.append({
                "dimension": dimension,
                "delta": delta,
                "new_score": result.get("new_score"),
            })

    # 记录 lineage
    try:
        from core.service_registry import registry as _reg
        from core.service_ports import DataLineageServicePort
        lineage_svc = _reg.get(DataLineageServicePort)
        if lineage_svc is not None:
            lineage_svc.record_lineage(
                db,
                source={"type": "training", "id": session_id},
                target={"type": "ability_profile", "id": user_id,
                        "field": "training_session", "value": score},
                transformation="training_session_to_ability",
                user_id=user_id,
                tenant_id=tenant_id,
            )
    except Exception:
        pass

    # 发布事件
    try:
        from ai.event_bus import event_bus
        event_bus.publish(
            "practice_session_completed",
            {"session_id": session_id, "user_id": user_id,
             "scenario_type": scenario_type, "score": score},
            tenant_id=tenant_id,
            consistency="eventual",
            affected_domains=["profile", "sales"],
        )
    except Exception:
        pass

    return {"ok": True, "applied": applied}


def create_scene_from_draft(db: Session, tenant_id: str, user_id: int, draft_dict: dict) -> dict:
    """N+5：基于工作流草稿创建培训场景

    字段映射（同源性原则）：
    - title ← draft.title_bg.title
    - description ← draft.title_bg.scene_background（repBriefing）
    - scenario_type ← draft.config.scenario_types[0] 或 collection.scenario_type
    - customer_profile ← draft.collection.doctor_persona
    - target_skills ← draft.collection.best_practice_points
    - knowledge_needs ← draft.knowledge.ids
    - context_payload ← draft.context_payload（doctor + coach，对用户不可见）
    - difficulty ← 默认 medium
    - is_published ← 0（草稿态，需用户后续发布）

    Args:
        db: 数据库会话
        tenant_id: 租户 ID
        user_id: 创建者 ID
        draft_dict: SceneDraft.to_dict() 的完整字典

    Returns:
        {"scenario_id": int} 或 {"error": str}
    """
    from database import PracticeScenario

    title_bg = draft_dict.get("title_bg", {}) or {}
    collection = draft_dict.get("collection", {}) or {}
    config = draft_dict.get("config", {}) or {}
    knowledge = draft_dict.get("knowledge", {}) or {}
    context_payload = draft_dict.get("context_payload", {}) or {}

    title = (title_bg.get("title") or "").strip()
    scene_background = (title_bg.get("scene_background") or "").strip()

    if not title:
        return {"error": "title 不能为空"}
    if not scene_background:
        return {"error": "scene_background 不能为空（同源性要求）"}

    # scenario_type 优先取 collection 中显式指定的，否则取 config 列表第一个
    scenario_type = collection.get("scenario_type") or (
        (config.get("scenario_types") or ["visit"])[0]
    )

    scenario = PracticeScenario(
        tenant_id=tenant_id,
        title=title,
        description=scene_background,  # repBriefing（同源）
        scenario_type=scenario_type,
        customer_profile=collection.get("doctor_persona", ""),
        target_skills=collection.get("best_practice_points", []) or [],
        knowledge_needs=knowledge.get("ids", []) or [],
        context_payload={
            "doctor": context_payload.get("doctor", {}) or {},
            "coach": context_payload.get("coach", {}) or {},
            "ready": True,
        },
        difficulty="medium",
        is_published=0,
        created_by=user_id,
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)

    # 发布场景创建事件（可选，失败不影响主流程）
    try:
        from ai.event_bus import event_bus
        event_bus.publish(
            "scene_created_from_workflow",
            {
                "scenario_id": scenario.id,
                "title": scenario.title,
                "user_id": user_id,
            },
            tenant_id=tenant_id,
            consistency="eventual",
            affected_domains=["training"],
        )
    except Exception:
        pass  # 事件发布失败不影响主流程

    return {"scenario_id": scenario.id}
