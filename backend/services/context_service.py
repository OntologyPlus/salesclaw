"""全局上下文服务（N+3 Step1-3）

管理"当前选中实体"全局上下文（空间维度 / 时间维度 / 视角），
并提供 period_end（历史周期时间游标）感知的指标聚合。

三维：
- 空间维度：post(岗位) / zone(辖区) / region(地区) / area(大区)
- 时间维度：day / week / month / quarter / year（支持历史周期 period_end）
- 视角：management(管理周期) / customer_development(客户发展) / report(报告与指令)
"""
import logging
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from database import (
    VisitRecord, VisitPlan, VisitFeedback, BehaviorPointRecord,
    PracticeSession, CourseEnrollment, AIInsightCache, User, Zone,
    CoverageAssignment,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 上下文状态（内存态，按 user_id 隔离）
# ──────────────────────────────────────────────

_context_store: dict[int, dict] = {}

DEFAULT_CONTEXT = {
    "scope_type": "post",  # post/zone/region/area
    "scope_id": None,  # 当 scope_type != post 时的实体 ID
    "scope_label": "我的岗位",
    "period_type": "month",  # day/week/month/quarter/year
    "period_end": None,  # ISO date string 或 None（当期）
    "perspective": "management",  # management/customer_development/report
}


def get_context(user_id: int) -> dict:
    return dict(_context_store.get(user_id, DEFAULT_CONTEXT))


def set_context(user_id: int, context: dict) -> dict:
    current = get_context(user_id)
    current.update({k: v for k, v in context.items() if k in DEFAULT_CONTEXT})
    _context_store[user_id] = current
    return current


# ──────────────────────────────────────────────
# 时间游标辅助
# ──────────────────────────────────────────────

def _parse_period_end(period_end: str) -> date:
    """解析 ISO 日期字符串为 date"""
    if not period_end:
        return None
    try:
        return datetime.strptime(period_end, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _period_end_filter(column, period_end: date):
    """生成 <= period_end 的过滤条件"""
    if period_end is None:
        return None
    return column <= period_end


# ──────────────────────────────────────────────
# period_end 感知的指标聚合
# ──────────────────────────────────────────────

def get_period_aware_overview(db: Session, tenant_id: str, user_id: int,
                              scope_id: int = None, period_end: str = None) -> dict:
    """带时间游标的决策总览

    当 period_end 设置时，所有日期指标仅统计 <= period_end 的记录，
    实现"历史周期重算"。
    """
    pe = _parse_period_end(period_end)
    base_q = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
    )
    if scope_id:
        # 按辖区过滤（通过 user_id 间接关联 zone）
        users_in_zone = _users_in_scope(db, tenant_id, scope_id)
        if users_in_zone:
            base_q = base_q.filter(VisitRecord.user_id.in_(users_in_zone))
    else:
        base_q = base_q.filter(VisitRecord.user_id == user_id)
    if pe is not None:
        base_q = base_q.filter(VisitRecord.visit_date <= pe)

    visit_count = base_q.count()
    # 计划数
    plan_q = db.query(VisitPlan).filter(
        VisitPlan.tenant_id == tenant_id,
        VisitPlan.is_deleted == 0,
    )
    if scope_id:
        if users_in_zone:
            plan_q = plan_q.filter(VisitPlan.user_id.in_(users_in_zone))
    else:
        plan_q = plan_q.filter(VisitPlan.user_id == user_id)
    plan_count = plan_q.count()

    # 培训训战次数
    ps_q = db.query(PracticeSession).filter(
        PracticeSession.tenant_id == tenant_id,
        PracticeSession.is_deleted == 0,
    )
    if scope_id:
        if users_in_zone:
            ps_q = ps_q.filter(PracticeSession.user_id.in_(users_in_zone))
    else:
        ps_q = ps_q.filter(PracticeSession.user_id == user_id)
    if pe is not None:
        ps_q = ps_q.filter(PracticeSession.started_at <= pe)
    practice_count = ps_q.count()

    # 行为积分
    points_q = db.query(func.sum(BehaviorPointRecord.points)).filter(
        BehaviorPointRecord.tenant_id == tenant_id,
        BehaviorPointRecord.is_deleted == 0,
    )
    if scope_id:
        if users_in_zone:
            points_q = points_q.filter(BehaviorPointRecord.user_id.in_(users_in_zone))
    else:
        points_q = points_q.filter(BehaviorPointRecord.user_id == user_id)
    total_points = points_q.scalar() or 0

    return {
        "scope_id": scope_id,
        "period_end": period_end,
        "visit_count": visit_count,
        "plan_count": plan_count,
        "practice_count": practice_count,
        "total_points": int(total_points),
        "is_historical": pe is not None,
    }


def _users_in_scope(db: Session, tenant_id: str, scope_id: int) -> list:
    """查询辖区下的用户 ID 列表"""
    assignments = db.query(CoverageAssignment.user_id).filter(
        CoverageAssignment.tenant_id == tenant_id,
        CoverageAssignment.is_deleted == 0,
        CoverageAssignment.hospital_id == scope_id,  # scope_id 视为医院/辖区标识
    ).distinct().all()
    return [a[0] for a in assignments] if assignments else []


# ──────────────────────────────────────────────
# period_end 感知的洞察缓存查询
# ──────────────────────────────────────────────

def get_insight_with_period(db: Session, tenant_id: str, user_id: int,
                            domain: str, period_end: str = None) -> dict:
    """查询洞察缓存（按 period_end 双键）

    - period_end=None：查当期缓存（period_end IS NULL）
    - period_end 设置：查历史周期缓存
    """
    from datetime import date as date_cls
    pe = _parse_period_end(period_end)
    today = date.today()
    q = db.query(AIInsightCache).filter(
        AIInsightCache.tenant_id == tenant_id,
        AIInsightCache.domain == domain,
        AIInsightCache.is_deleted == 0,
        AIInsightCache.insight_date == today,
    )
    if user_id:
        q = q.filter(AIInsightCache.user_id == user_id)
    if pe is None:
        q = q.filter(AIInsightCache.period_end.is_(None))
    else:
        q = q.filter(AIInsightCache.period_end == pe)
    cache = q.first()
    if not cache:
        return {"found": False, "domain": domain, "period_end": period_end}
    import json
    return {
        "found": True,
        "domain": cache.domain,
        "period_end": str(cache.period_end) if cache.period_end else None,
        "summary": cache.summary,
        "insights": json.loads(cache.insights_json) if cache.insights_json else [],
        "recommendations": json.loads(cache.recommendations_json) if cache.recommendations_json else [],
        "risk_alerts": json.loads(cache.risk_alerts_json) if cache.risk_alerts_json else [],
    }


# ──────────────────────────────────────────────
# 三视角看板数据
# ──────────────────────────────────────────────

def get_perspective_data(db: Session, tenant_id: str, user_id: int,
                         perspective: str, scope_id: int = None,
                         period_end: str = None) -> dict:
    """根据视角返回对应看板数据"""
    if perspective == "management":
        # 管理周期：决策总览 + KPI
        return get_period_aware_overview(db, tenant_id, user_id, scope_id, period_end)
    elif perspective == "customer_development":
        # 客户发展：覆盖 + KOL
        return _get_customer_development(db, tenant_id, user_id, scope_id, period_end)
    elif perspective == "report":
        # 报告与指令：效果追踪 + 公告
        return _get_report_data(db, tenant_id, user_id, scope_id, period_end)
    return {}


def _get_customer_development(db: Session, tenant_id: str, user_id: int,
                              scope_id: int, period_end: str) -> dict:
    pe = _parse_period_end(period_end)
    q = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
    )
    if scope_id:
        users = _users_in_scope(db, tenant_id, scope_id)
        if users:
            q = q.filter(VisitRecord.user_id.in_(users))
    else:
        q = q.filter(VisitRecord.user_id == user_id)
    if pe is not None:
        q = q.filter(VisitRecord.visit_date <= pe)
    records = q.all()
    # 按医院聚合
    hospital_stats = {}
    for r in records:
        hid = r.hospital_id
        if hid not in hospital_stats:
            hospital_stats[hid] = {"hospital_id": hid, "visits": 0, "doctors": set()}
        hospital_stats[hid]["visits"] += 1
        if r.doctor_id:
            hospital_stats[hid]["doctors"].add(r.doctor_id)
    items = [{"hospital_id": k, "visits": v["visits"], "doctor_count": len(v["doctors"])}
             for k, v in hospital_stats.items()]
    items.sort(key=lambda x: x["visits"], reverse=True)
    return {
        "perspective": "customer_development",
        "scope_id": scope_id,
        "period_end": period_end,
        "hospital_count": len(items),
        "top_hospitals": items[:10],
    }


def _get_report_data(db: Session, tenant_id: str, user_id: int,
                     scope_id: int, period_end: str) -> dict:
    pe = _parse_period_end(period_end)
    # 反馈数
    fb_q = db.query(VisitFeedback).filter(
        VisitFeedback.tenant_id == tenant_id,
        VisitFeedback.is_deleted == 0,
    )
    if pe is not None:
        fb_q = fb_q.filter(VisitFeedback.created_at <= pe)
    feedback_count = fb_q.count()
    return {
        "perspective": "report",
        "scope_id": scope_id,
        "period_end": period_end,
        "feedback_count": feedback_count,
    }
