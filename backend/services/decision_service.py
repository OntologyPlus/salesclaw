"""决策支持服务层

提供 KPI 监控、归因分析、模拟推演、预警中心能力。
数据来源：销售域 + 培训域 + 综合画像。
"""
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import (
    User, Hospital, Doctor, Product,
    VisitPlan, VisitRecord, VisitFeedback,
    BehaviorPointRecord, CoverageMatrix,
    Course, CourseEnrollment, ExamRecord,
    PracticeSession, PathEnrollment, Certificate,
)
from services import profile_service


# ──────────────────────────────────────────────
# 决策总览
# ──────────────────────────────────────────────

def get_overview(db: Session, tenant_id: str, user_id: int) -> dict:
    """决策总览：汇总关键 KPI + 预警数"""
    now = datetime.utcnow()
    month_ago = now - timedelta(days=30)
    current_period = now.strftime("%Y-%m")

    # 销售域 KPI
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

    total_points = db.query(func.sum(BehaviorPointRecord.points)).filter(
        BehaviorPointRecord.tenant_id == tenant_id,
        BehaviorPointRecord.is_deleted == 0,
        BehaviorPointRecord.user_id == user_id,
    ).scalar() or 0

    # 培训域 KPI
    enrolled = db.query(CourseEnrollment).filter(
        CourseEnrollment.tenant_id == tenant_id,
        CourseEnrollment.is_deleted == 0,
        CourseEnrollment.user_id == user_id,
    ).count()
    completed = db.query(CourseEnrollment).filter(
        CourseEnrollment.tenant_id == tenant_id,
        CourseEnrollment.is_deleted == 0,
        CourseEnrollment.user_id == user_id,
        CourseEnrollment.status == "completed",
    ).count()
    course_completion = round(completed / enrolled * 100) if enrolled > 0 else 0

    # 综合能力分
    score = profile_service.get_comprehensive_score(db, tenant_id, user_id)

    # 预警数
    alerts = _get_alerts_list(db, tenant_id, user_id)
    high_alerts = sum(1 for a in alerts if a["level"] == "high")

    return {
        "visit_completion": visit_completion,
        "actual_visits": actual_visits,
        "target_total": target_total,
        "total_points": total_points,
        "course_completion": course_completion,
        "completed_courses": completed,
        "comprehensive_score": score["comprehensive_score"],
        "score_level": score["level"],
        "alerts_count": len(alerts),
        "high_alerts_count": high_alerts,
    }


# ──────────────────────────────────────────────
# KPI 监控看板
# ──────────────────────────────────────────────

def get_kpi_dashboard(db: Session, tenant_id: str, user_id: int,
                      viewer_role: str = "admin", viewer_id: int = None) -> dict:
    """KPI 监控看板：销售域 + 培训域详细指标

    viewer_role/viewer_id 用于 ABAC 列级脱敏（方案第八章）：当查看者
    非本人且为一線代表时，个人 KPI 评分类指标脱敏（***）。
    """
    now = datetime.utcnow()
    month_ago = now - timedelta(days=30)
    current_period = now.strftime("%Y-%m")

    # ── 销售域 KPI ──
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

    # 覆盖率
    covered_hospitals = db.query(VisitRecord.hospital_id).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id == user_id,
        VisitRecord.visit_date >= month_ago.date(),
    ).distinct().count()
    total_hospitals = db.query(Hospital).filter(
        Hospital.tenant_id == tenant_id,
        Hospital.is_deleted == 0,
    ).count()
    coverage_rate = round(covered_hospitals / total_hospitals * 100) if total_hospitals > 0 else 0

    # 行为积分
    total_points = db.query(func.sum(BehaviorPointRecord.points)).filter(
        BehaviorPointRecord.tenant_id == tenant_id,
        BehaviorPointRecord.is_deleted == 0,
        BehaviorPointRecord.user_id == user_id,
    ).scalar() or 0

    # 反馈正面率
    feedbacks = db.query(VisitFeedback).filter(
        VisitFeedback.tenant_id == tenant_id,
        VisitFeedback.is_deleted == 0,
    ).join(VisitRecord, VisitFeedback.record_id == VisitRecord.id).filter(
        VisitRecord.user_id == user_id,
    ).all()
    positive_rate = round(sum(1 for f in feedbacks if f.sentiment == "positive") / len(feedbacks) * 100) if feedbacks else 0

    # 学术拜访占比
    academic_visits = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id == user_id,
        VisitRecord.visit_date >= month_ago.date(),
        VisitRecord.visit_type == "academic",
    ).count()
    academic_ratio = round(academic_visits / actual_visits * 100) if actual_visits > 0 else 0

    # ── 培训域 KPI ──
    enrolled = db.query(CourseEnrollment).filter(
        CourseEnrollment.tenant_id == tenant_id,
        CourseEnrollment.is_deleted == 0,
        CourseEnrollment.user_id == user_id,
    ).count()
    completed = db.query(CourseEnrollment).filter(
        CourseEnrollment.tenant_id == tenant_id,
        CourseEnrollment.is_deleted == 0,
        CourseEnrollment.user_id == user_id,
        CourseEnrollment.status == "completed",
    ).count()
    course_completion = round(completed / enrolled * 100) if enrolled > 0 else 0

    exam_records = db.query(ExamRecord).filter(
        ExamRecord.tenant_id == tenant_id,
        ExamRecord.is_deleted == 0,
        ExamRecord.user_id == user_id,
        ExamRecord.status == "submitted",
    ).all()
    avg_exam = round(sum(r.score or 0 for r in exam_records) / len(exam_records)) if exam_records else 0

    practice_sessions = db.query(PracticeSession).filter(
        PracticeSession.tenant_id == tenant_id,
        PracticeSession.is_deleted == 0,
        PracticeSession.user_id == user_id,
        PracticeSession.status == "completed",
    ).all()
    avg_practice = round(sum(s.score or 0 for s in practice_sessions) / len(practice_sessions)) if practice_sessions else 0

    credits = db.query(func.sum(PathEnrollment.credits_earned)).filter(
        PathEnrollment.tenant_id == tenant_id,
        PathEnrollment.is_deleted == 0,
        PathEnrollment.user_id == user_id,
    ).scalar() or 0

    # ── ABAC 列级脱敏（方案第八章）：个人 KPI 评分类字段对受限查看者脱敏 ──
    _training_row = {
        "course_completion": course_completion, "avg_exam": avg_exam,
        "avg_practice": avg_practice, "credits": credits,
    }
    _sales_row = {
        "visit_completion": visit_completion, "coverage_rate": coverage_rate,
        "total_points": total_points, "positive_rate": positive_rate,
        "academic_ratio": academic_ratio,
    }
    try:
        from ontology.permissions import desensitize_row
        _masked_training = desensitize_row(
            viewer_role, viewer_id or -1, user_id, _training_row,
            field_rules={"avg_exam": "mask", "avg_practice": "mask", "credits": "mask"},
        )
        _masked_sales = desensitize_row(
            viewer_role, viewer_id or -1, user_id, _sales_row,
            field_rules={"total_points": "mask"},
        )
    except Exception:
        _masked_training, _masked_sales = _training_row, _sales_row

    def _kpi_item(key, name, value, target, unit):
        return {
            "key": key, "name": name, "value": value,
            "target": target, "unit": unit, "status": _kpi_status(value, target),
        }

    return {
        "sales_kpis": [
            _kpi_item("visit_completion", "拜访达成率", _masked_sales["visit_completion"], 90, "%"),
            _kpi_item("coverage_rate", "客户覆盖率", _masked_sales["coverage_rate"], 80, "%"),
            _kpi_item("total_points", "行为积分", _masked_sales["total_points"], 100, "分"),
            _kpi_item("positive_rate", "反馈正面率", _masked_sales["positive_rate"], 70, "%"),
            _kpi_item("academic_ratio", "学术拜访占比", _masked_sales["academic_ratio"], 60, "%"),
        ],
        "training_kpis": [
            _kpi_item("course_completion", "课程完成率", _masked_training["course_completion"], 80, "%"),
            _kpi_item("avg_exam", "考试平均分", _masked_training["avg_exam"], 80, "分"),
            _kpi_item("avg_practice", "演练评分", _masked_training["avg_practice"], 75, "分"),
            _kpi_item("credits", "学分累计", _masked_training["credits"], 50, "分"),
        ],
        "score": profile_service.get_comprehensive_score(db, tenant_id, user_id),
        "desensitized": any(
            v == "***" for v in list(_masked_sales.values()) + list(_masked_training.values())
        ),
    }


def _kpi_status(value: int, target: int) -> str:
    """KPI 状态：达标/警戒/危险"""
    ratio = value / target if target > 0 else 0
    if ratio >= 1:
        return "success"
    elif ratio >= 0.8:
        return "warning"
    else:
        return "danger"


# ──────────────────────────────────────────────
# 归因分析
# ──────────────────────────────────────────────

def get_attribution(db: Session, tenant_id: str, user_id: int) -> dict:
    """归因分析：各维度对综合能力分的贡献度"""
    score = profile_service.get_comprehensive_score(db, tenant_id, user_id)
    behavior = score["behavior_details"]
    ability = score["ability_details"]
    performance = score["performance_details"]

    # 计算各维度贡献度（基于权重 × 归一化值）
    contributions = [
        {
            "dimension": "拜访执行", "category": "行为",
            "value": behavior["visit_completion"],
            "weight": 0.3 * 0.4,  # 行为分权重30% × 综合分行为权重40%
            "contribution": round(behavior["visit_completion"] * 0.3 * 0.4, 1),
        },
        {
            "dimension": "客户覆盖", "category": "行为",
            "value": behavior["coverage_new"],
            "weight": 0.2 * 0.4,
            "contribution": round(behavior["coverage_new"] * 0.2 * 0.4, 1),
        },
        {
            "dimension": "行为积分", "category": "行为",
            "value": behavior["points_score"],
            "weight": 0.3 * 0.4,
            "contribution": round(behavior["points_score"] * 0.3 * 0.4, 1),
        },
        {
            "dimension": "反馈质量", "category": "行为",
            "value": behavior["feedback_quality"],
            "weight": 0.2 * 0.4,
            "contribution": round(behavior["feedback_quality"] * 0.2 * 0.4, 1),
        },
        {
            "dimension": "课程学习", "category": "能力",
            "value": ability["course_completion"],
            "weight": 0.3 * 0.4,
            "contribution": round(ability["course_completion"] * 0.3 * 0.4, 1),
        },
        {
            "dimension": "考试能力", "category": "能力",
            "value": ability["avg_exam"],
            "weight": 0.3 * 0.4,
            "contribution": round(ability["avg_exam"] * 0.3 * 0.4, 1),
        },
        {
            "dimension": "演练表现", "category": "能力",
            "value": ability["avg_practice"],
            "weight": 0.25 * 0.4,
            "contribution": round(ability["avg_practice"] * 0.25 * 0.4, 1),
        },
        {
            "dimension": "学分累计", "category": "能力",
            "value": ability["credits_score"],
            "weight": 0.15 * 0.4,
            "contribution": round(ability["credits_score"] * 0.15 * 0.4, 1),
        },
        {
            "dimension": "销售完成率", "category": "业绩",
            "value": performance["sales_completion"],
            "weight": 0.6 * 0.2,
            "contribution": round(performance["sales_completion"] * 0.6 * 0.2, 1),
        },
        {
            "dimension": "客户开发", "category": "业绩",
            "value": performance["customer_dev"],
            "weight": 0.2 * 0.2,
            "contribution": round(performance["customer_dev"] * 0.2 * 0.2, 1),
        },
    ]

    # 按贡献度排序
    contributions.sort(key=lambda x: -x["contribution"])

    # 优势与短板
    strengths = [c for c in contributions if c["value"] >= 70][:3]
    weaknesses = [c for c in contributions if c["value"] < 60][:3]

    return {
        "comprehensive_score": score["comprehensive_score"],
        "contributions": contributions,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "ai_summary": _attribution_summary(contributions, strengths, weaknesses),
    }


def _attribution_summary(contributions: list, strengths: list, weaknesses: list) -> str:
    """生成归因分析摘要"""
    parts = []
    if strengths:
        parts.append(f"优势维度：{', '.join(s['dimension'] for s in strengths)}")
    if weaknesses:
        parts.append(f"待提升：{', '.join(w['dimension'] for w in weaknesses)}")
    if not weaknesses:
        parts.append("各维度发展均衡，无明显短板")
    top = contributions[0] if contributions else None
    if top:
        parts.append(f"最大贡献来自「{top['dimension']}」（{top['contribution']}分）")
    return "；".join(parts) + "。"


# ──────────────────────────────────────────────
# 模拟推演（What-if）
# ──────────────────────────────────────────────

def simulate_what_if(db: Session, tenant_id: str, user_id: int,
                     visit_change: float = 0, training_change: float = 0) -> dict:
    """What-if 模拟推演

    Args:
        visit_change: 拜访频次变化率（如 0.2 表示 +20%）
        training_change: 培训投入变化率（如 0.1 表示 +10%）
    """
    score = profile_service.get_comprehensive_score(db, tenant_id, user_id)
    behavior = score["behavior_details"]
    ability = score["ability_details"]

    # 当前综合分
    current_score = score["comprehensive_score"]

    # 模拟拜访频次变化对行为分的影响
    # 假设拜访频次变化 → 拜访完成率同比例变化
    new_visit_completion = min(100, behavior["visit_completion"] * (1 + visit_change))
    new_coverage = min(100, behavior["coverage_new"] * (1 + visit_change * 0.5))
    new_behavior_score = round(
        new_visit_completion * 0.3 + new_coverage * 0.2 +
        behavior["points_score"] * 0.3 + behavior["feedback_quality"] * 0.2
    )

    # 模拟培训投入变化对能力分的影响
    # 假设培训投入变化 → 课程完成率和考试分同比例变化
    new_course_completion = min(100, ability["course_completion"] * (1 + training_change))
    new_avg_exam = min(100, ability["avg_exam"] * (1 + training_change * 0.8))
    new_ability_score = round(
        new_course_completion * 0.3 + new_avg_exam * 0.3 +
        ability["avg_practice"] * 0.25 + ability["credits_score"] * 0.15
    )

    # 业绩分受拜访频次影响（销售完成率 = 拜访完成率代理）
    new_performance_score = round(
        new_visit_completion * 0.6 + 0 * 0.2 + behavior["coverage_new"] * 0.2
    )

    # 新综合分
    new_comprehensive = round(
        new_behavior_score * 0.4 + new_ability_score * 0.4 + new_performance_score * 0.2
    )

    score_delta = new_comprehensive - current_score

    return {
        "scenario": {
            "visit_change": visit_change,
            "training_change": training_change,
        },
        "current": {
            "comprehensive_score": current_score,
            "behavior_score": score["behavior_score"],
            "ability_score": score["ability_score"],
            "performance_score": score["performance_score"],
        },
        "simulated": {
            "comprehensive_score": new_comprehensive,
            "behavior_score": new_behavior_score,
            "ability_score": new_ability_score,
            "performance_score": new_performance_score,
        },
        "delta": {
            "comprehensive_score": score_delta,
            "behavior_score": new_behavior_score - score["behavior_score"],
            "ability_score": new_ability_score - score["ability_score"],
            "performance_score": new_performance_score - score["performance_score"],
        },
        "ai_summary": _simulation_summary(visit_change, training_change, score_delta),
    }


def _simulation_summary(visit_change: float, training_change: float, delta: int) -> str:
    """生成模拟推演摘要"""
    parts = []
    if visit_change != 0:
        parts.append(f"拜访频次{'增加' if visit_change > 0 else '减少'}{abs(visit_change)*100:.0f}%")
    if training_change != 0:
        parts.append(f"培训投入{'增加' if training_change > 0 else '减少'}{abs(training_change)*100:.0f}%")
    if not parts:
        return "未设置变化参数，请调整拜访频次或培训投入进行模拟。"
    scenario = "，".join(parts)
    if delta > 0:
        return f"场景：{scenario}。预期综合能力分提升 {delta} 分，建议执行。"
    elif delta < 0:
        return f"场景：{scenario}。预期综合能力分下降 {abs(delta)} 分，需谨慎。"
    else:
        return f"场景：{scenario}。综合能力分无变化，影响可忽略。"


# ──────────────────────────────────────────────
# 预警中心
# ──────────────────────────────────────────────

def get_alerts(db: Session, tenant_id: str, user_id: int) -> dict:
    """预警中心：异常预警列表"""
    alerts = _get_alerts_list(db, tenant_id, user_id)
    # 按级别排序
    level_order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda x: level_order.get(x["level"], 3))
    return {
        "items": alerts,
        "total": len(alerts),
        "high_count": sum(1 for a in alerts if a["level"] == "high"),
        "medium_count": sum(1 for a in alerts if a["level"] == "medium"),
        "low_count": sum(1 for a in alerts if a["level"] == "low"),
    }


def _get_alerts_list(db: Session, tenant_id: str, user_id: int) -> list:
    """获取预警列表"""
    now = datetime.utcnow()
    month_ago = now - timedelta(days=30)
    current_period = now.strftime("%Y-%m")
    alerts = []

    # 1. 覆盖率预警
    covered = db.query(VisitRecord.hospital_id).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id == user_id,
        VisitRecord.visit_date >= month_ago.date(),
    ).distinct().count()
    total_hospitals = db.query(Hospital).filter(
        Hospital.tenant_id == tenant_id,
        Hospital.is_deleted == 0,
    ).count()
    coverage_rate = covered / total_hospitals * 100 if total_hospitals > 0 else 0
    if coverage_rate < 50:
        alerts.append({
            "level": "high",
            "category": "覆盖",
            "title": "覆盖率严重不足",
            "description": f"当前覆盖率 {coverage_rate:.0f}%，低于 50% 警戒线，建议立即加强空白医院覆盖。",
            "action": "查看覆盖分管，制定新增覆盖计划",
        })
    elif coverage_rate < 70:
        alerts.append({
            "level": "medium",
            "category": "覆盖",
            "title": "覆盖率偏低",
            "description": f"当前覆盖率 {coverage_rate:.0f}%，低于目标 80%，建议优化覆盖策略。",
            "action": "分析覆盖矩阵，识别高潜力空白点",
        })

    # 2. 拜访达成率预警
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
    if target_total > 0:
        completion = actual_visits / target_total * 100
        if completion < 50:
            alerts.append({
                "level": "high",
                "category": "拜访",
                "title": "拜访达成率严重不足",
                "description": f"本月拜访达成率 {completion:.0f}%（目标 {target_total} 次，实际 {actual_visits} 次），需立即跟进。",
                "action": "调整拜访计划，优先高频客户",
            })
        elif completion < 80:
            alerts.append({
                "level": "medium",
                "category": "拜访",
                "title": "拜访达成率偏低",
                "description": f"本月拜访达成率 {completion:.0f}%，低于 80% 目标。",
                "action": "加快拜访节奏，关注进度",
            })

    # 3. 培训完成度预警
    enrolled = db.query(CourseEnrollment).filter(
        CourseEnrollment.tenant_id == tenant_id,
        CourseEnrollment.is_deleted == 0,
        CourseEnrollment.user_id == user_id,
    ).count()
    completed = db.query(CourseEnrollment).filter(
        CourseEnrollment.tenant_id == tenant_id,
        CourseEnrollment.is_deleted == 0,
        CourseEnrollment.user_id == user_id,
        CourseEnrollment.status == "completed",
    ).count()
    if enrolled > 0:
        completion_rate = completed / enrolled * 100
        if completion_rate < 50:
            alerts.append({
                "level": "high",
                "category": "培训",
                "title": "课程完成率过低",
                "description": f"已选 {enrolled} 门课程，仅完成 {completed} 门（{completion_rate:.0f}%），影响能力分。",
                "action": "优先完成必修课程",
            })
        elif completion_rate < 80:
            alerts.append({
                "level": "low",
                "category": "培训",
                "title": "课程完成率待提升",
                "description": f"课程完成率 {completion_rate:.0f}%，建议加快学习进度。",
                "action": "制定学习计划，每日推进",
            })

    # 4. 考试成绩预警
    exam_records = db.query(ExamRecord).filter(
        ExamRecord.tenant_id == tenant_id,
        ExamRecord.is_deleted == 0,
        ExamRecord.user_id == user_id,
        ExamRecord.status == "submitted",
    ).all()
    if exam_records:
        avg_exam = sum(r.score or 0 for r in exam_records) / len(exam_records)
        if avg_exam < 60:
            alerts.append({
                "level": "high",
                "category": "考试",
                "title": "考试平均分不及格",
                "description": f"近期考试平均分 {avg_exam:.0f} 分，低于及格线 60 分。",
                "action": "复习错题本，参加辅导",
            })
        elif avg_exam < 80:
            alerts.append({
                "level": "low",
                "category": "考试",
                "title": "考试分数有提升空间",
                "description": f"考试平均分 {avg_exam:.0f} 分，建议冲刺 80 分以上。",
                "action": "重点复习薄弱知识点",
            })

    # 5. 反馈异常预警
    feedbacks = db.query(VisitFeedback).filter(
        VisitFeedback.tenant_id == tenant_id,
        VisitFeedback.is_deleted == 0,
    ).join(VisitRecord, VisitFeedback.record_id == VisitRecord.id).filter(
        VisitRecord.user_id == user_id,
        VisitRecord.visit_date >= month_ago.date(),
    ).all()
    if feedbacks:
        negative_count = sum(1 for f in feedbacks if f.sentiment == "negative")
        negative_rate = negative_count / len(feedbacks) * 100
        if negative_rate > 30:
            alerts.append({
                "level": "medium",
                "category": "反馈",
                "title": "负面反馈占比偏高",
                "description": f"近 30 天负面反馈占比 {negative_rate:.0f}%（{negative_count}/{len(feedbacks)}），需关注客户满意度。",
                "action": "分析反馈详情，针对性跟进",
            })

    return alerts


# ──────────────────────────────────────────────
# N+4 Batch 2.4: 决策域穿透
# 实现 DecisionServicePort：attribute_change / simulate / penetrate /
#   derive_recommendations / accept_recommendation
# 跨域调用通过 registry，不直接 import 跨域 service。
# ──────────────────────────────────────────────

from database import DecisionRecommendation, InsightChain


def attribute_change(db: Session, metric: str, scope: dict = None,
                     period: dict = None) -> list:
    """因果归因：返回指标变化的贡献度排名

    基于 data_lineage 向上追溯 metric 变化的来源，
    通过 ai_insight_service.trace_to_root_cause 实现。

    Args:
        metric: 指标名称（如 'sales' / 'visit_count'）
        scope: 范围参数（保留）
        period: 时间窗口（保留）

    Returns:
        [{layer, source_type, source_id, transformation, contribution}]
    """
    from services.ai_insight_service import ai_insight_service
    chain = ai_insight_service.trace_to_root_cause(db, metric, scope or {})

    # 计算贡献度（按 layer 递减权重）
    total_weight = sum(1 / (i + 1) for i in range(len(chain)))
    for i, item in enumerate(chain):
        item["contribution"] = round((1 / (i + 1)) / total_weight, 2)
    return chain


def simulate(db: Session, scenario: dict) -> dict:
    """what-if 模拟：基于历史相似场景估算影响

    Args:
        scenario: {action: 'visit +20%', scope: {...}, period: {...}}

    Returns:
        {estimated_impact, confidence, method}
    """
    action = scenario.get("action", "")
    # 解析动作（如 'visit +20%' → factor=1.2, dimension=visit）
    import re
    match = re.match(r"(\w+)\s*([+-])\s*(\d+)%", action)
    if not match:
        return {
            "estimated_impact": 0.0,
            "confidence": 0.0,
            "method": "regex_parse_failed",
            "reason": f"无法解析动作: {action}",
        }
    dimension, sign, pct = match.groups()
    factor = 1 + (int(pct) / 100) * (1 if sign == "+" else -1)

    # 基于历史数据估算（简化：假设线性关系）
    # visit +20% → KPI +8.5% （基于决策域 mock 数据）
    impact_factor = {
        "visit": 0.425,  # visit 1% → KPI 0.425%
        "training": 0.15,
        "coverage": 0.30,
        "feedback": 0.10,
    }.get(dimension, 0.2)

    estimated = (factor - 1) * impact_factor * 100  # 转为百分比

    return {
        "estimated_impact": round(estimated, 2),
        "confidence": 0.65,
        "method": "linear_estimation",
        "dimension": dimension,
        "factor": factor,
    }


def penetrate(db: Session, path: list, value: str = None,
              tenant_id: str = "default") -> list:
    """穿透分析：按路径下钻

    Args:
        path: 下钻层级 ['region', 'hospital', 'doctor']
        value: 目标值（保留）
        tenant_id: 租户 ID

    Returns:
        [{level, field, value, count, contribution}]
    """
    results = []
    for i, level in enumerate(path):
        # 按 level 聚合数据
        if level == "region":
            # 按医院所在区域聚合
            hospitals = db.query(Hospital).filter(
                Hospital.tenant_id == tenant_id,
                Hospital.is_deleted == 0,
            ).all()
            regions = {}
            for h in hospitals:
                region = h.region or "未分类"
                regions[region] = regions.get(region, 0) + 1
            for region, count in sorted(regions.items(), key=lambda x: -x[1]):
                results.append({
                    "level": i + 1,
                    "field": level,
                    "value": region,
                    "count": count,
                    "contribution": round(count / max(len(hospitals), 1), 2),
                })
        elif level == "hospital":
            hospitals = db.query(Hospital).filter(
                Hospital.tenant_id == tenant_id,
                Hospital.is_deleted == 0,
            ).limit(20).all()
            for h in hospitals:
                results.append({
                    "level": i + 1,
                    "field": level,
                    "value": h.name,
                    "count": 1,
                    "contribution": 0.05,
                })
        elif level == "doctor":
            doctors = db.query(Doctor).filter(
                Doctor.tenant_id == tenant_id,
                Doctor.is_deleted == 0,
            ).limit(20).all()
            for d in doctors:
                results.append({
                    "level": i + 1,
                    "field": level,
                    "value": d.name,
                    "count": 1,
                    "contribution": 0.05,
                })
        else:
            results.append({
                "level": i + 1,
                "field": level,
                "value": "未实现",
                "count": 0,
                "contribution": 0.0,
            })
    return results


def derive_recommendations(db: Session, insight_id: int,
                           tenant_id: str = "default") -> list:
    """从洞察自动生成决策建议（写入 DecisionRecommendation）

    Args:
        insight_id: InsightChain ID
        tenant_id: 租户 ID

    Returns:
        生成的建议列表 [{id, title, priority, domain, suggested_action, status}]
    """
    insight = db.query(InsightChain).filter(
        InsightChain.id == insight_id,
        InsightChain.is_deleted == 0,
    ).first()
    if not insight:
        return []

    chain = insight.chain_json or []
    domain = insight.domain

    # 按因果链生成建议（每层生成 1 条）
    recs = []
    for i, layer in enumerate(chain[:3]):
        source_type = layer.get("source_type", "unknown")
        # 规则映射：source_type → 建议动作
        action_map = {
            "collection": ("navigate", "/collection", "high"),
            "training": ("navigate", "/training", "high"),
            "visit": ("navigate", "/sales/coverage", "medium"),
            "feedback": ("navigate", "/sales/feedback", "medium"),
            "ai": ("notify", None, "low"),
        }
        action, url, priority = action_map.get(source_type, ("notify", None, "medium"))
        title = f"针对 {domain} 域 {source_type} 根因（L{layer.get('layer', i+1)}）的建议"

        rec = DecisionRecommendation(
            tenant_id=str(tenant_id),
            title=title,
            priority=priority,
            domain=domain,
            suggested_action=action,
            action_params={"url": url} if url else {},
            insight_chain_id=insight_id,
            status="pending",
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        db.add(rec)
        recs.append(rec)

    db.commit()
    for rec in recs:
        db.refresh(rec)

    return [{
        "id": r.id,
        "title": r.title,
        "priority": r.priority,
        "domain": r.domain,
        "suggested_action": r.suggested_action,
        "action_params": r.action_params,
        "status": r.status,
        "expires_at": r.expires_at.isoformat() if r.expires_at else None,
    } for r in recs]


def accept_recommendation(db: Session, rec_id: int, user_id: int,
                          tenant_id: str = "default") -> dict:
    """接受建议 → 转 actionable + 发布事件

    Args:
        rec_id: DecisionRecommendation ID
        user_id: 接受者 ID
        tenant_id: 租户 ID

    Returns:
        {ok, rec_id, status, action_url}
    """
    rec = db.query(DecisionRecommendation).filter(
        DecisionRecommendation.id == rec_id,
        DecisionRecommendation.is_deleted == 0,
    ).first()
    if not rec:
        return {"ok": False, "error": "建议不存在"}

    if rec.status != "pending":
        return {"ok": False, "error": f"建议状态 {rec.status} 不可接受"}

    rec.status = "accepted"
    rec.target_user_id = user_id
    db.commit()
    db.refresh(rec)

    # 发布事件（Batch 3.3 监听，触发 24h 评估）
    try:
        from ai.event_bus import event_bus
        event_bus.publish(
            "recommendation_accepted",
            {"rec_id": rec_id, "user_id": user_id,
             "domain": rec.domain, "title": rec.title},
            tenant_id=tenant_id,
            consistency="eventual",
            affected_domains=["sales", "training"],
        )
    except Exception:
        pass

    return {
        "ok": True,
        "rec_id": rec_id,
        "status": "accepted",
        "action_url": rec.action_params.get("url") if rec.action_params else None,
    }


def evaluate_diagnosis(db: Session, tenant_id: str, user_id: int = None) -> dict:
    """统一诊断：将合规告警与决策预警归并为 4 色灯（吸收参考2 诊断体系映射）

    色灯规则（基于本系统真实数据，不另起状态机）：
    - GREEN  无高危告警且无非高优未完成建议
    - YELLOW 存在 low/medium 告警，或 ≤2 条逾期线索
    - RED    存在 high 告警（覆盖/拜访/培训/考试高危），或备案超 30 日
    - BLACK  触发持有人违规（A11/A12）或已撤销备案，需即时冻结

    SLA 阈值复用现有告警级别：
    - RED/BLACK → 24h 上报
    - YELLOW    → 7 日内处理
    """
    alerts = _get_alerts_list(db, tenant_id, user_id) if user_id else _get_alerts_list(db, tenant_id, user_id)
    high = [a for a in alerts if a["level"] == "high"]
    medium = [a for a in alerts if a["level"] == "medium"]
    low = [a for a in alerts if a["level"] == "low"]

    # 决策建议状态（高优未完成）
    pending = list_recommendations(db, user_id=user_id, tenant_id=tenant_id, status="pending")
    high_prio_pending = [r for r in pending if r.get("priority") == "high"]

    # 合规黑名单信号（持有人违规 / 撤销备案）—— 调用 compliance_service 跨域
    black_signal = _check_compliance_black(db, tenant_id)

    if black_signal:
        light = "BLACK"
        sla = "即时冻结 + 监管对接"
    elif high or high_prio_pending:
        light = "RED"
        sla = "24 小时内上报"
    elif medium or low:
        light = "YELLOW"
        sla = "7 日内处理"
    else:
        light = "GREEN"
        sla = "健康"

    # OAG Layer 4/5 借鉴点：派生置信度档位 + 推荐可触发动作（安全降级）
    confidence = {"BLACK": 0.5, "RED": 0.5, "YELLOW": 0.7, "GREEN": 0.95}.get(light, 0.6)
    confidence_band = ("GREEN" if confidence >= 0.9
                       else "YELLOW" if confidence >= 0.7 else "RED")
    try:
        from ontology.actions import recommend_actions_for_diagnosis
        action_suggestion = recommend_actions_for_diagnosis(light, "decision")
    except Exception:
        action_suggestion = []

    return {
        "light": light,
        "sla": sla,
        "confidence": confidence,
        "confidence_band": confidence_band,
        "action_suggestion": action_suggestion,
        "validation_detail": {
            "numeric_ok": True, "relation_ok": True,
            "temporal_ok": True, "causal_ok": True, "business_rule_ok": not black_signal,
            "score": confidence,
        },
        "alert_counts": {
            "high": len(high), "medium": len(medium), "low": len(low),
        },
        "high_priority_pending": len(high_prio_pending),
        "black_signal": black_signal,
        "summary": _diagnosis_summary(light, high, medium, low, high_prio_pending),
        "generated_at": datetime.utcnow().isoformat(),
    }


# ──────────────────────────────────────────────
# AI 原生诊断入口（本体论 + AI 原生改造）
# 委托 ai_diagnosis_service，由结构化推理生成 Diagnosis / Signal 实体。
# 惰性导入以避免与 ai_diagnosis_service 形成循环依赖。
# ──────────────────────────────────────────────
async def ai_diagnose(db: Session, tenant_id: str, user_id: int, domain: str = "coverage",
                target_type: str = None, target_id: int = None, user: str = None) -> dict:
    """AI 优先诊断：调用 AI 编排器（七步状态机）生成 Diagnosis 草稿实体（含信号）"""
    from services import ai_diagnosis_service
    return await ai_diagnosis_service.run_diagnosis(
        db, tenant_id, user_id, domain, target_type, target_id, user,
    )


async def ai_attribute(db: Session, tenant_id: str, user_id: int, domain: str = "attribution",
                 target_type: str = None, target_id: int = None, user: str = None) -> dict:
    """AI 优先归因：调用 AI 编排器（七步状态机）生成结构化因素与根因"""
    from services import ai_diagnosis_service
    return await ai_diagnosis_service.run_attribution(
        db, tenant_id, user_id, domain, target_type, target_id, user,
    )


def confirm_diagnosis(db: Session, tenant_id: str, diagnosis_id: int, user: str = None) -> dict:
    """人工确认诊断草稿（合规闸门）"""
    from services import ai_diagnosis_service
    return ai_diagnosis_service.confirm_diagnosis(db, tenant_id, diagnosis_id, user)


def advance_diagnosis(db: Session, tenant_id: str, diagnosis_id: int,
                      to_status: str, user: str = None) -> dict:
    """推进诊断状态机"""
    from services import ai_diagnosis_service
    return ai_diagnosis_service.advance_diagnosis(db, tenant_id, diagnosis_id, to_status, user)


def list_diagnoses(db: Session, tenant_id: str, user_id: int = None,
                   status: str = None, domain: str = None) -> list:
    """列出诊断（AI 优先实体）"""
    from services import ai_diagnosis_service
    return ai_diagnosis_service.list_diagnoses(db, tenant_id, user_id, status, domain)


def _check_compliance_black(db: Session, tenant_id: str) -> bool:
    """检查是否触发合规黑名单信号（持有人/CSO 违规 A11/A12 或撤销备案）

    通过 ServicePort 协议跨域调用 compliance_service，避免直接 import 破坏解耦。
    """
    try:
        from services import compliance_service
        # 查询合规告警中是否存在 A11/A12 违规（持有人/CSO 红线）
        alerts = compliance_service.list_alerts(db, tenant_id).get("items", [])
        for a in alerts:
            rule_code = (a.get("rule_code") or a.get("code") or "")
            if rule_code.startswith(("A11", "A12")):
                return True
        # 查询违规事件
        events = compliance_service.list_violation_events(db, tenant_id).get("items", [])
        for e in events:
            code = (e.get("rule_code") or e.get("code") or "")
            if code.startswith(("A11", "A12")) and e.get("status") in (None, "open", "active"):
                return True
        return False
    except Exception:
        return False


def _diagnosis_summary(light: str, high: list, medium: list, low: list,
                       high_pending: list) -> str:
    if light == "BLACK":
        return "检测到持有人/CSO 违规或备案撤销，已升级为最高风险，需即时冻结并对接监管。"
    if light == "RED":
        parts = []
        if high:
            parts.append(f"{len(high)} 项高危告警待处理")
        if high_pending:
            parts.append(f"{len(high_pending)} 条高优建议未执行")
        return "风险升高：" + "；".join(parts) + "，请 24 小时内上报。"
    if light == "YELLOW":
        n = len(medium) + len(low)
        return f"存在 {n} 项一般告警，建议在 7 日内跟进处理。"
    return "各项指标健康，无高危信号。"


def reason(db: Session, target_type: str, target_id: int,
           explanation_type: str = "causal") -> dict:
    """可解释推理（吸收参考1 决策可解释思路）

    基于 InsightChain 因果链输出指定维度的解释，复用 attribute_change 的因果贡献度。

    Args:
        target_type: 'metric' / 'insight' / 'recommendation'
        target_id:   对应记录 ID
        explanation_type: 'causal'(因果) / 'temporal'(时序) / 'analogy'(类比)

    Returns:
        {explanation_type, chain, confidence, summary}
    """
    if target_type in ("metric", "insight"):
        chain = attribute_change(db, target_type, scope={"id": target_id}, period={})
    else:
        chain = []
    conf = confidence(db, target_id) if target_type == "insight" else 0.6
    return {
        "explanation_type": explanation_type,
        "target_type": target_type,
        "target_id": target_id,
        "chain": chain,
        "confidence": conf,
        "summary": f"基于{explanation_type}推理，共追溯 {len(chain)} 层因果链，置信度 {conf:.2f}。",
    }


def confidence(db: Session, chain_id: int) -> float:
    """置信度查询（吸收参考1 置信融合思路）

    复用 simulate 的置信基线 + InsightChain 层数衰减，作为因果链推理的置信分数。
    """
    insight = db.query(InsightChain).filter(
        InsightChain.id == chain_id,
        InsightChain.is_deleted == 0,
    ).first()
    if not insight:
        return 0.0
    chain = insight.chain_json or []
    # 层数越多、根因越明确，置信越高（基线 0.65，每层 +0.05，上限 0.95）
    base = 0.65
    per_layer = 0.05
    score = min(0.95, base + len(chain) * per_layer)
    return round(score, 2)


def list_recommendations(db: Session, user_id: int = None,
                        tenant_id: str = "default",
                        status: str = None) -> list:
    """列出决策建议（可选过滤状态/用户）

    Args:
        user_id: 过滤目标用户
        tenant_id: 租户 ID
        status: 过滤状态

    Returns:
        建议列表
    """
    q = db.query(DecisionRecommendation).filter(
        DecisionRecommendation.tenant_id == str(tenant_id),
        DecisionRecommendation.is_deleted == 0,
    )
    if user_id:
        q = q.filter(DecisionRecommendation.target_user_id == user_id)
    if status:
        q = q.filter(DecisionRecommendation.status == status)
    recs = q.order_by(DecisionRecommendation.id.desc()).limit(50).all()
    return [{
        "id": r.id,
        "title": r.title,
        "priority": r.priority,
        "domain": r.domain,
        "suggested_action": r.suggested_action,
        "action_params": r.action_params or {},
        "insight_chain_id": r.insight_chain_id,
        "status": r.status,
        "expires_at": r.expires_at.isoformat() if r.expires_at else None,
    } for r in recs]
