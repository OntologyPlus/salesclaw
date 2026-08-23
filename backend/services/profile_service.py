"""综合能力画像服务层

实现"行为-能力飞轮"的数据基础：
综合分 = 行为分×0.4 + 能力分×0.4 + 业绩分×0.2
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import (
    User, Hospital,
    VisitPlan, VisitRecord, VisitFeedback,
    BehaviorPointRecord,
    Course, CourseEnrollment, ExamRecord,
    LearningPath, PathEnrollment, Certificate,
    PracticeSession,
)


# ──────────────────────────────────────────────
# 行为分（0-100）
# ──────────────────────────────────────────────

def _calc_behavior_score(db: Session, tenant_id: str, user_id: int) -> dict:
    """行为分 = 拜访完成率 30% + 覆盖新增 20% + 行为积分 30% + 反馈质量 20%"""
    now = datetime.utcnow()
    month_ago = now - timedelta(days=30)

    # 1. 拜访完成率（30%）：本期 VisitPlan.target_count vs 实际 VisitRecord 数
    current_period = now.strftime("%Y-%m")
    plans = db.query(VisitPlan).filter(
        VisitPlan.tenant_id == tenant_id,
        VisitPlan.is_deleted == 0,
        VisitPlan.user_id == user_id,
        VisitPlan.period == current_period,
    ).all()
    target_total = sum(p.target_count or 0 for p in plans)
    actual_visits = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id == user_id,
        VisitRecord.visit_date >= month_ago.date(),
    ).count()
    visit_completion = min(100, round(actual_visits / target_total * 100)) if target_total > 0 else (50 if actual_visits > 0 else 0)

    # 2. 覆盖新增（20%）：近 30 天新覆盖医院数（归一化，最多 5 家=100）
    new_hospitals = db.query(VisitRecord.hospital_id).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id == user_id,
        VisitRecord.visit_date >= month_ago.date(),
    ).distinct().count()
    coverage_new = min(100, new_hospitals * 20)

    # 3. 行为积分（30%）：BehaviorPointRecord 总分（归一化，100 分=100）
    total_points = db.query(func.sum(BehaviorPointRecord.points)).filter(
        BehaviorPointRecord.tenant_id == tenant_id,
        BehaviorPointRecord.is_deleted == 0,
        BehaviorPointRecord.user_id == user_id,
    ).scalar() or 0
    points_score = min(100, int(total_points))

    # 4. 反馈质量（20%）：VisitFeedback.sentiment 正面占比
    feedbacks = db.query(VisitFeedback).filter(
        VisitFeedback.tenant_id == tenant_id,
        VisitFeedback.is_deleted == 0,
    ).join(VisitRecord, VisitFeedback.record_id == VisitRecord.id).filter(
        VisitRecord.user_id == user_id,
    ).all()
    if feedbacks:
        positive = sum(1 for f in feedbacks if f.sentiment == "positive")
        feedback_quality = round(positive / len(feedbacks) * 100)
    else:
        feedback_quality = 0

    behavior_score = round(
        visit_completion * 0.3 + coverage_new * 0.2 + points_score * 0.3 + feedback_quality * 0.2
    )
    return {
        "score": behavior_score,
        "details": {
            "visit_completion": visit_completion,
            "coverage_new": coverage_new,
            "points_score": points_score,
            "feedback_quality": feedback_quality,
            "actual_visits": actual_visits,
            "target_total": target_total,
            "total_points": total_points,
            "feedbacks_count": len(feedbacks),
        },
    }


# ──────────────────────────────────────────────
# 能力分（0-100）
# ──────────────────────────────────────────────

def _calc_ability_score(db: Session, tenant_id: str, user_id: int) -> dict:
    """能力分 = 课程完成率 30% + 考试平均分 30% + 演练评分 25% + 学分累计 15%"""
    # 1. 课程完成率（30%）
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
    course_completion = round(completed_count / enrolled_count * 100) if enrolled_count > 0 else 0

    # 2. 考试平均分（30%）
    exam_records = db.query(ExamRecord).filter(
        ExamRecord.tenant_id == tenant_id,
        ExamRecord.is_deleted == 0,
        ExamRecord.user_id == user_id,
        ExamRecord.status == "submitted",
    ).all()
    avg_exam = round(sum(r.score or 0 for r in exam_records) / len(exam_records)) if exam_records else 0

    # 3. 演练评分（25%）
    practice_sessions = db.query(PracticeSession).filter(
        PracticeSession.tenant_id == tenant_id,
        PracticeSession.is_deleted == 0,
        PracticeSession.user_id == user_id,
        PracticeSession.status == "completed",
    ).all()
    avg_practice = round(sum(s.score or 0 for s in practice_sessions) / len(practice_sessions)) if practice_sessions else 0

    # 4. 学分累计（15%）：归一化（50 学分=100）
    credits = db.query(func.sum(PathEnrollment.credits_earned)).filter(
        PathEnrollment.tenant_id == tenant_id,
        PathEnrollment.is_deleted == 0,
        PathEnrollment.user_id == user_id,
    ).scalar() or 0
    credits_score = min(100, int(credits * 2))

    ability_score = round(
        course_completion * 0.3 + avg_exam * 0.3 + avg_practice * 0.25 + credits_score * 0.15
    )
    return {
        "score": ability_score,
        "details": {
            "course_completion": course_completion,
            "avg_exam": avg_exam,
            "avg_practice": avg_practice,
            "credits_score": credits_score,
            "enrolled_count": enrolled_count,
            "completed_count": completed_count,
            "exam_count": len(exam_records),
            "practice_count": len(practice_sessions),
            "credits": credits,
        },
    }


# ──────────────────────────────────────────────
# 业绩分（0-100）
# ──────────────────────────────────────────────

def _calc_performance_score(db: Session, tenant_id: str, user_id: int) -> dict:
    """业绩分 = 销售完成率 60% + 增长率 20% + 客户开发 20%
    当前无销售业绩表，用拜访完成率代理销售完成率。
    """
    # 1. 销售完成率（60%）：用拜访完成率代理
    now = datetime.utcnow()
    month_ago = now - timedelta(days=30)
    current_period = now.strftime("%Y-%m")
    plans = db.query(VisitPlan).filter(
        VisitPlan.tenant_id == tenant_id,
        VisitPlan.is_deleted == 0,
        VisitPlan.user_id == user_id,
        VisitPlan.period == current_period,
    ).all()
    target_total = sum(p.target_count or 0 for p in plans)
    actual_visits = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id == user_id,
        VisitRecord.visit_date >= month_ago.date(),
    ).count()
    sales_completion = min(100, round(actual_visits / target_total * 100)) if target_total > 0 else (50 if actual_visits > 0 else 0)

    # 2. 增长率（20%）：暂 Mock 0（无历史对比数据）
    growth_rate = 0

    # 3. 客户开发（20%）：近 30 天新增 Doctor 数（归一化，5 个=100）
    # 注意：Doctor 表无 created_by，用 VisitRecord 中近 30 天新出现的 doctor_id 数代理
    new_doctors = db.query(VisitRecord.doctor_id).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id == user_id,
        VisitRecord.visit_date >= month_ago.date(),
        VisitRecord.doctor_id.isnot(None),
    ).distinct().count()
    customer_dev = min(100, new_doctors * 20)

    performance_score = round(
        sales_completion * 0.6 + growth_rate * 0.2 + customer_dev * 0.2
    )
    return {
        "score": performance_score,
        "details": {
            "sales_completion": sales_completion,
            "growth_rate": growth_rate,
            "customer_dev": customer_dev,
            "new_doctors": new_doctors,
        },
    }


# ──────────────────────────────────────────────
# 综合能力评分
# ──────────────────────────────────────────────

def get_comprehensive_score(db: Session, tenant_id: str, user_id: int) -> dict:
    """综合能力评分 = 行为分×0.4 + 能力分×0.4 + 业绩分×0.2"""
    behavior = _calc_behavior_score(db, tenant_id, user_id)
    ability = _calc_ability_score(db, tenant_id, user_id)
    performance = _calc_performance_score(db, tenant_id, user_id)

    comprehensive = round(
        behavior["score"] * 0.4 + ability["score"] * 0.4 + performance["score"] * 0.2
    )

    # 等级标签
    if comprehensive >= 90:
        level = "卓越"
    elif comprehensive >= 80:
        level = "优秀"
    elif comprehensive >= 70:
        level = "良好"
    elif comprehensive >= 60:
        level = "合格"
    else:
        level = "待提升"

    return {
        "comprehensive_score": comprehensive,
        "level": level,
        "behavior_score": behavior["score"],
        "ability_score": ability["score"],
        "performance_score": performance["score"],
        "behavior_details": behavior["details"],
        "ability_details": ability["details"],
        "performance_details": performance["details"],
    }


def recalculate_ability_score(db: Session, tenant_id: str, user_id: int) -> int:
    """重算能力分（课程完成时触发，返回新分数）"""
    ability = _calc_ability_score(db, tenant_id, user_id)
    return ability["score"]


# ──────────────────────────────────────────────
# 雷达图数据（6 维度）
# ──────────────────────────────────────────────

def get_radar(db: Session, tenant_id: str, user_id: int) -> dict:
    """雷达图 6 维度数据"""
    behavior = _calc_behavior_score(db, tenant_id, user_id)
    ability = _calc_ability_score(db, tenant_id, user_id)
    performance = _calc_performance_score(db, tenant_id, user_id)

    dimensions = [
        {"name": "拜访执行", "value": behavior["details"]["visit_completion"], "full_mark": 100},
        {"name": "客户覆盖", "value": behavior["details"]["coverage_new"], "full_mark": 100},
        {"name": "行为积分", "value": behavior["details"]["points_score"], "full_mark": 100},
        {"name": "课程学习", "value": ability["details"]["course_completion"], "full_mark": 100},
        {"name": "考试能力", "value": ability["details"]["avg_exam"], "full_mark": 100},
        {"name": "演练表现", "value": ability["details"]["avg_practice"], "full_mark": 100},
    ]
    return {"dimensions": dimensions}


# ──────────────────────────────────────────────
# 学习需求分析
# ──────────────────────────────────────────────

def get_learning_needs(db: Session, tenant_id: str, user_id: int) -> dict:
    """学习需求分析：基于拜访反馈异议 + 涉及产品，推荐匹配课程"""
    now = datetime.utcnow()
    month_ago = now - timedelta(days=30)

    # 1. 近 30 天拜访反馈中的异议关键词
    feedbacks = db.query(VisitFeedback).filter(
        VisitFeedback.tenant_id == tenant_id,
        VisitFeedback.is_deleted == 0,
    ).join(VisitRecord, VisitFeedback.record_id == VisitRecord.id).filter(
        VisitRecord.user_id == user_id,
        VisitRecord.visit_date >= month_ago.date(),
    ).all()

    objections = {}
    for fb in feedbacks:
        for obj in (fb.objections or []):
            objections[obj] = objections.get(obj, 0) + 1

    # 2. 近 30 天涉及的产品分类
    visit_product_ids = db.query(VisitRecord.product_id).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id == user_id,
        VisitRecord.visit_date >= month_ago.date(),
        VisitRecord.product_id.isnot(None),
    ).distinct().all()
    product_ids = [pid[0] for pid in visit_product_ids if pid[0]]

    # 3. 已完成课程 ID（排除）
    completed_course_ids = set(
        ce.course_id for ce in db.query(CourseEnrollment).filter(
            CourseEnrollment.tenant_id == tenant_id,
            CourseEnrollment.is_deleted == 0,
            CourseEnrollment.user_id == user_id,
            CourseEnrollment.status == "completed",
        ).all()
    )

    # 4. 查询推荐课程（匹配 category 或 tags，排除已完成）
    recommendations = []
    if product_ids:
        from database import Product
        products = db.query(Product).filter(Product.id.in_(product_ids)).all()
        categories = set(p.category for p in products if p.category)
        if categories:
            courses = db.query(Course).filter(
                Course.tenant_id == tenant_id,
                Course.is_deleted == 0,
                Course.is_published == 1,
                Course.category.in_(categories),
            ).limit(10).all()
            for c in courses:
                if c.id in completed_course_ids:
                    continue
                recommendations.append({
                    "type": "course",
                    "id": c.id,
                    "title": c.title,
                    "category": c.category,
                    "difficulty": c.difficulty,
                    "duration_minutes": c.duration_minutes,
                    "reason": f"您近 30 天拜访涉及 {c.category or '相关'} 类产品，建议学习此课程加强产品知识。",
                    "priority": "high" if c.difficulty == "intermediate" else "medium",
                })

    # 5. 若无匹配，推荐通用课程
    if not recommendations:
        courses = db.query(Course).filter(
            Course.tenant_id == tenant_id,
            Course.is_deleted == 0,
            Course.is_published == 1,
        ).limit(3).all()
        for c in courses:
            if c.id in completed_course_ids:
                continue
            recommendations.append({
                "type": "course",
                "id": c.id,
                "title": c.title,
                "category": c.category,
                "difficulty": c.difficulty,
                "duration_minutes": c.duration_minutes,
                "reason": "推荐学习此课程提升综合能力。",
                "priority": "medium",
            })

    # 6. 薄弱点分析
    ability = _calc_ability_score(db, tenant_id, user_id)
    weaknesses = []
    details = ability["details"]
    if details["course_completion"] < 60:
        weaknesses.append({"dimension": "课程完成率", "value": details["course_completion"], "suggestion": "加快课程学习进度"})
    if details["avg_exam"] < 60:
        weaknesses.append({"dimension": "考试平均分", "value": details["avg_exam"], "suggestion": "复习薄弱知识点后重考"})
    if details["avg_practice"] < 60 and details["practice_count"] > 0:
        weaknesses.append({"dimension": "演练评分", "value": details["avg_practice"], "suggestion": "增加场景演练频次"})

    return {
        "recommendations": recommendations[:5],
        "objections": [{"keyword": k, "count": v} for k, v in sorted(objections.items(), key=lambda x: -x[1])[:5]],
        "weaknesses": weaknesses,
    }


# ──────────────────────────────────────────────
# 全息画像
# ──────────────────────────────────────────────

def get_full_profile(db: Session, tenant_id: str, user_id: int) -> dict:
    """全息画像：基本信息 + 综合分 + 雷达图 + 学习需求 + 近期活动"""
    user = db.query(User).filter(
        User.tenant_id == tenant_id,
        User.is_deleted == 0,
        User.id == user_id,
    ).first()

    score = get_comprehensive_score(db, tenant_id, user_id)
    radar = get_radar(db, tenant_id, user_id)
    learning_needs = get_learning_needs(db, tenant_id, user_id)

    # 近期活动（合并拜访 + 培训）
    now = datetime.utcnow()
    month_ago = now - timedelta(days=30)
    activities = []

    visit_records = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id == user_id,
    ).order_by(VisitRecord.visit_date.desc()).limit(5).all()
    for r in visit_records:
        activities.append({
            "type": "visit",
            "title": r.summary[:40] + "..." if r.summary and len(r.summary) > 40 else (r.summary or "拜访记录"),
            "date": str(r.visit_date) if r.visit_date else None,
        })

    course_completions = db.query(CourseEnrollment).filter(
        CourseEnrollment.tenant_id == tenant_id,
        CourseEnrollment.is_deleted == 0,
        CourseEnrollment.user_id == user_id,
        CourseEnrollment.status == "completed",
    ).order_by(CourseEnrollment.completed_at.desc()).limit(5).all()
    course_ids = {e.course_id for e in course_completions}
    courses_map = {c.id: c for c in db.query(Course).filter(Course.id.in_(course_ids)).all()} if course_ids else {}
    for e in course_completions:
        c = courses_map.get(e.course_id)
        activities.append({
            "type": "course_completed",
            "title": f"完成课程：{c.title}" if c else f"完成课程 #{e.course_id}",
            "date": e.completed_at.strftime("%Y-%m-%d %H:%M") if e.completed_at else None,
        })

    exam_records = db.query(ExamRecord).filter(
        ExamRecord.tenant_id == tenant_id,
        ExamRecord.is_deleted == 0,
        ExamRecord.user_id == user_id,
        ExamRecord.status == "submitted",
    ).order_by(ExamRecord.submitted_at.desc()).limit(5).all()
    for er in exam_records:
        activities.append({
            "type": "exam_submitted",
            "title": f"提交考试 #{er.exam_id}（{er.score}分）",
            "date": er.submitted_at.strftime("%Y-%m-%d %H:%M") if er.submitted_at else None,
        })

    activities.sort(key=lambda x: x.get("date") or "", reverse=True)

    return {
        "user": {
            "id": user.id if user else user_id,
            "username": user.username if user else None,
            "display_name": user.display_name if user else None,
            "email": user.email if user else None,
        },
        "score": score,
        "radar": radar,
        "learning_needs": learning_needs,
        "activities": activities[:10],
    }


# ──────────────────────────────────────────────
# N+4 Batch 2.1: 5 维动态画像主线
# 实现 ProfileServicePort：update_ability_score / apply_decay /
#   get_ability_summary / get_weakest_dimensions / detect_weakness
# 跨域调用通过 registry.get(ProfileServicePort) 调用本组函数。
# ──────────────────────────────────────────────

from core.constants import (
    ABILITY_DIMENSIONS, DECAY_THRESHOLD_DAYS, DECAY_RATE,
    ABILITY_SOURCE_TYPES,
)
from database import AbilityProfile, ProfileHistory


def update_ability_score(db: Session, user_id: int, dimension: str,
                        delta: float, source: str, source_id: int = None,
                        evidence: dict = None, tenant_id: str = "default") -> dict:
    """更新能力分（增量 + 历史记录 + 证据 + lineage）

    Args:
        user_id: 用户 ID
        dimension: 维度（product_knowledge/visit_skill/customer_relation/compliance/ai_application）
        delta: 增量（正数加分，负数减分）
        source: 来源（training/visit/collection/feedback/ai）
        source_id: 来源记录 ID
        evidence: 证据详情
        tenant_id: 租户 ID

    Returns:
        {ok, dimension, new_score, delta} 或 {ok=False, error}
    """
    valid_dims = [k for k, _ in ABILITY_DIMENSIONS]
    if dimension not in valid_dims:
        return {"ok": False, "error": f"未知维度 {dimension}"}
    if source not in ABILITY_SOURCE_TYPES:
        return {"ok": False, "error": f"未知来源 {source}"}

    # 1. get_or_create AbilityProfile
    profile = db.query(AbilityProfile).filter(
        AbilityProfile.user_id == user_id,
        AbilityProfile.dimension == dimension,
        AbilityProfile.is_deleted == 0,
    ).first()
    old_score = profile.score if profile else 0.0
    new_score = max(0.0, min(100.0, old_score + delta))

    if profile is None:
        profile = AbilityProfile(
            tenant_id=str(tenant_id),
            user_id=user_id,
            dimension=dimension,
            score=new_score,
            sample_size=1,
        )
        db.add(profile)
    else:
        profile.score = new_score
        profile.sample_size = (profile.sample_size or 0) + 1
        profile.last_updated_at = datetime.utcnow()

    # 2. 更新证据（保留最近 5 条）
    ev_list = list(profile.evidence_json or [])
    ev_list.insert(0, {
        "source": source,
        "source_id": source_id,
        "delta": delta,
        "evidence": evidence or {},
        "at": datetime.utcnow().isoformat(),
    })
    profile.evidence_json = ev_list[:5]

    # 3. 写历史
    history = ProfileHistory(
        tenant_id=str(tenant_id),
        user_id=user_id,
        dimension=dimension,
        delta=delta,
        source=source,
        source_id=source_id,
        new_score=new_score,
        occurred_at=datetime.utcnow(),
    )
    db.add(history)
    db.commit()
    db.refresh(profile)

    # 4. 记录 lineage（高内聚低耦合 — 通过 DataLineageServicePort）
    try:
        from core.service_registry import registry
        from core.service_ports import DataLineageServicePort
        lineage_svc = registry.get(DataLineageServicePort)
        if lineage_svc is not None:
            lineage_svc.record_lineage(
                db,
                source={"type": source, "id": source_id},
                target={"type": "ability_profile", "id": profile.id,
                        "field": dimension, "value": new_score},
                transformation="ability_score_updated",
                user_id=user_id,
                tenant_id=tenant_id,
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"记录 ability lineage 失败: {e}")

    # 5. 发布事件
    try:
        from ai.event_bus import event_bus
        event_bus.publish(
            "ability_score_updated",
            {"user_id": user_id, "dimension": dimension,
             "delta": delta, "new_score": new_score},
            tenant_id=tenant_id,
            consistency="eventual",
            affected_domains=["training", "decision"],
        )
    except Exception:
        pass

    return {
        "ok": True,
        "dimension": dimension,
        "new_score": new_score,
        "delta": delta,
    }


def apply_decay(db: Session, tenant_id: str, days: int = DECAY_THRESHOLD_DAYS) -> int:
    """衰减任务：30 天无训练 → 维度分数 -5%

    Args:
        tenant_id: 租户 ID
        days: 无更新阈值天数

    Returns:
        衰减的画像数
    """
    threshold = datetime.utcnow() - timedelta(days=days)
    profiles = db.query(AbilityProfile).filter(
        AbilityProfile.tenant_id == str(tenant_id),
        AbilityProfile.is_deleted == 0,
        AbilityProfile.last_updated_at < threshold,
    ).all()
    count = 0
    for p in profiles:
        decay_delta = -p.score * DECAY_RATE
        p.score = max(0.0, p.score + decay_delta)
        p.decay_factor = (p.decay_factor or 1.0) * (1 - DECAY_RATE)
        count += 1
    if count > 0:
        db.commit()
        try:
            from ai.event_bus import event_bus
            event_bus.publish(
                "ability_decay_applied",
                {"count": count, "tenant_id": tenant_id},
                tenant_id=tenant_id,
                consistency="eventual",
                affected_domains=["training"],
            )
        except Exception:
            pass
    return count


def get_ability_summary(db: Session, user_id: int) -> dict:
    """返回 5 维 + 总分 + 趋势

    Returns:
        {dimensions: {dim: {score, samples, trend_30d, evidence}}, total_score}
    """
    profiles = db.query(AbilityProfile).filter(
        AbilityProfile.user_id == user_id,
        AbilityProfile.is_deleted == 0,
    ).all()
    dims = {
        p.dimension: {
            "score": p.score,
            "samples": p.sample_size,
            "trend_30d": p.trend_30d,
            "evidence": p.evidence_json or [],
        }
        for p in profiles
    }
    # 填充未记录的维度
    for key, _ in ABILITY_DIMENSIONS:
        if key not in dims:
            dims[key] = {"score": 0.0, "samples": 0, "trend_30d": 0.0, "evidence": []}
    total = sum(d["score"] for d in dims.values()) / len(ABILITY_DIMENSIONS)
    return {"dimensions": dims, "total_score": round(total, 1)}


def get_weakest_dimensions(db: Session, user_id: int, n: int = 2) -> list:
    """找出最弱的 N 个维度"""
    summary = get_ability_summary(db, user_id)
    dims = summary["dimensions"]
    sorted_dims = sorted(dims.items(), key=lambda x: x[1]["score"])
    return [{"dimension": k, "score": v["score"]} for k, v in sorted_dims[:n]]


def detect_weakness(db: Session, user_id: int, threshold: float = 70.0) -> list:
    """检测低于阈值的维度"""
    summary = get_ability_summary(db, user_id)
    return [
        {"dimension": k, "score": v["score"]}
        for k, v in summary["dimensions"].items()
        if v["score"] < threshold
    ]
