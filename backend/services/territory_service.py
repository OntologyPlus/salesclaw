"""辖区数据查询服务（N+3 Step4）

解析自然语言辖区查询，应用辖区权限过滤，聚合指标。
如"朝阳01辖区本周达成率多少？"→ 解析辖区 + 时间 → 聚合 → 自然语言回答。
"""
import re
import logging
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_

from database import Zone, CoverageAssignment, VisitRecord, VisitPlan, BehaviorPointRecord, Hospital
from services import sales_service

logger = logging.getLogger(__name__)


# 时间词解析
PERIOD_PATTERNS = [
    (r"本周|这周|本周内", "this_week"),
    (r"上周|上一周", "last_week"),
    (r"本月|这个月|当月", "this_month"),
    (r"上月|上个月|上个月", "last_month"),
    (r"本季度|这季度", "this_quarter"),
    (r"上季度|上季度", "last_quarter"),
    (r"本年|今年|年度", "this_year"),
]


def parse_period(text: str) -> tuple:
    """解析时间词为 (start_date, end_date, label)"""
    now = date.today()
    for pattern, key in PERIOD_PATTERNS:
        if re.search(pattern, text):
            if key == "this_week":
                start = now - timedelta(days=now.weekday())
                return start, now, "本周"
            if key == "last_week":
                end = now - timedelta(days=now.weekday() + 1)
                start = end - timedelta(days=6)
                return start, end, "上周"
            if key == "this_month":
                start = now.replace(day=1)
                return start, now, "本月"
            if key == "last_month":
                if now.month == 1:
                    start = now.replace(year=now.year - 1, month=12, day=1)
                else:
                    start = now.replace(month=now.month - 1, day=1)
                end = now.replace(day=1) - timedelta(days=1)
                return start, end, "上月"
            if key == "this_quarter":
                q_start_month = (now.month - 1) // 3 * 3 + 1
                start = now.replace(month=q_start_month, day=1)
                return start, now, "本季度"
            if key == "last_quarter":
                q_start_month = (now.month - 1) // 3 * 1
                if q_start_month == 0:
                    start = now.replace(year=now.year - 1, month=10, day=1)
                else:
                    start = now.replace(month=q_start_month, day=1)
                end = start + timedelta(days=89)
                return start, end, "上季度"
            if key == "this_year":
                start = now.replace(month=1, day=1)
                return start, now, "本年"
    # 默认本月
    start = now.replace(day=1)
    return start, now, "本月"


def match_zone(db: Session, tenant_id: str, text: str):
    """从文本匹配辖区"""
    zones = db.query(Zone).filter(
        Zone.tenant_id == tenant_id,
        Zone.is_deleted == 0,
    ).all()
    for z in zones:
        if z.name and z.name in text:
            return z
    # 模糊匹配名称片段
    for z in zones:
        if z.name and any(kw in text for kw in [z.name[:2], z.name[-2:]] if len(kw) >= 2):
            return z
    return zones[0] if zones else None


async def query_territory(db: Session, tenant_id: str, user_id: int, question: str) -> dict:
    """辖区数据自然语言查询"""
    start, end, label = parse_period(question)
    zone = match_zone(db, tenant_id, question)

    if not zone:
        return {
            "found": False,
            "summary": "未找到匹配的辖区，请明确辖区名称。",
            "question": question,
        }

    # 查询该辖区下有效覆盖的用户
    assignments = sales_service.get_effective_coverage(
        db, tenant_id, user_id, effective_date=end
    )
    user_ids = list({a["user_id"] for a in assignments if a.get("user_id")})
    if not user_ids:
        user_ids = [user_id]

    # 拜访数
    visit_q = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id.in_(user_ids),
        VisitRecord.visit_date >= start,
        VisitRecord.visit_date <= end,
    )
    visit_count = visit_q.count()

    # 计划数
    plan_q = db.query(VisitPlan).filter(
        VisitPlan.tenant_id == tenant_id,
        VisitPlan.is_deleted == 0,
        VisitPlan.user_id.in_(user_ids),
    )
    plan_count = plan_q.count()

    # 达成率
    achievement_rate = round(visit_count / plan_count * 100, 1) if plan_count > 0 else 0

    # 覆盖率
    total_hospitals = db.query(Hospital).filter(
        Hospital.tenant_id == tenant_id,
        Hospital.is_deleted == 0,
    ).count()
    covered = db.query(VisitRecord.hospital_id).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
        VisitRecord.user_id.in_(user_ids),
        VisitRecord.visit_date >= start,
        VisitRecord.visit_date <= end,
    ).distinct().count()
    coverage_rate = round(covered / total_hospitals * 100, 1) if total_hospitals > 0 else 0

    # 积分
    total_points = db.query(func.sum(BehaviorPointRecord.points)).filter(
        BehaviorPointRecord.tenant_id == tenant_id,
        BehaviorPointRecord.is_deleted == 0,
        BehaviorPointRecord.user_id.in_(user_ids),
    ).scalar() or 0

    # 风险提示
    risks = []
    if achievement_rate < 80:
        risks.append(f"达成率 {achievement_rate}% 低于 80% 目标")
    if coverage_rate < 70:
        risks.append(f"覆盖率 {coverage_rate}% 低于均值")
    if visit_count == 0:
        risks.append("本周期内零拜访记录")

    summary = (
        f"{zone.name}{label}拜访达成率 {achievement_rate}%，"
        f"覆盖率 {coverage_rate}%，积分 {total_points}。"
    )
    if risks:
        summary += "建议关注：" + "；".join(risks) + "。"

    return {
        "found": True,
        "zone_name": zone.name,
        "zone_id": zone.id,
        "period": label,
        "period_start": str(start),
        "period_end": str(end),
        "metrics": {
            "visit_count": visit_count,
            "plan_count": plan_count,
            "achievement_rate": achievement_rate,
            "coverage_rate": coverage_rate,
            "total_points": int(total_points),
        },
        "summary": summary,
        "risks": risks,
        "question": question,
    }
