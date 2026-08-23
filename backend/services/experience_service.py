"""经验值体系服务（N+2 Step4）

仅训战模式（source=train）累积经验值；练习模式不累积。
支持月度 Top20 排行榜（按品种分组）。
"""
import logging
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from core.exceptions import NotFoundError, ValidationError
from core.pagination import PageParams, paginate
from database import ExperiencePoint, User, Product, PracticeScenario, PracticeSession

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 经验值发放
# ──────────────────────────────────────────────

def award_points(db: Session, tenant_id: str, user_id: int, scenario_id: int,
                 activity_id: int, points: int, source: str = "train") -> dict:
    """发放经验值

    规则：
    - source=train 才计入排行；practice 仅记录
    - points 由调用方根据训战得分档位映射（如 90+ → 100, 80-89 → 80, 60-79 → 60）
    """
    if source not in ("train", "practice"):
        raise ValidationError("source 取值 train/practice")
    if points < 0:
        raise ValidationError("points 不能为负")
    ep = ExperiencePoint(
        tenant_id=tenant_id,
        user_id=user_id,
        scenario_id=scenario_id,
        activity_id=activity_id,
        points=points,
        source=source,
        earned_at=datetime.utcnow(),
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return _serialize_point(ep)


def score_to_points(score: int) -> int:
    """训战得分档位映射为经验值"""
    if score >= 90:
        return 100
    if score >= 80:
        return 80
    if score >= 60:
        return 60
    return 30


# ──────────────────────────────────────────────
# 查询
# ──────────────────────────────────────────────

def get_user_points(db: Session, tenant_id: str, user_id: int) -> dict:
    """获取用户经验值汇总（仅 train 累计）"""
    total = db.query(func.sum(ExperiencePoint.points)).filter(
        ExperiencePoint.tenant_id == tenant_id,
        ExperiencePoint.is_deleted == 0,
        ExperiencePoint.user_id == user_id,
        ExperiencePoint.source == "train",
    ).scalar() or 0
    # 本月累计
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_points = db.query(func.sum(ExperiencePoint.points)).filter(
        ExperiencePoint.tenant_id == tenant_id,
        ExperiencePoint.is_deleted == 0,
        ExperiencePoint.user_id == user_id,
        ExperiencePoint.source == "train",
        ExperiencePoint.earned_at >= month_start,
    ).scalar() or 0
    # 排名
    rank = _get_user_rank(db, tenant_id, user_id)
    return {
        "user_id": user_id,
        "total_points": total,
        "month_points": month_points,
        "rank": rank,
    }


def list_user_experience(db: Session, tenant_id: str, user_id: int,
                         page_params: PageParams = None) -> dict:
    """查询用户经验值记录"""
    q = db.query(ExperiencePoint).filter(
        ExperiencePoint.tenant_id == tenant_id,
        ExperiencePoint.is_deleted == 0,
        ExperiencePoint.user_id == user_id,
    )
    total = q.count()
    q = q.order_by(ExperiencePoint.id.desc())
    if page_params:
        q = q.offset(page_params.offset()).limit(page_params.effective_page_size())
    items = []
    for ep in q.all():
        items.append(_serialize_point(ep))
    return paginate(items, total, page_params or PageParams())


def get_monthly_top20(db: Session, tenant_id: str, year_month: str = None,
                      product_id: int = None) -> dict:
    """月度 Top20 排行榜

    Args:
        year_month: 格式 YYYY-MM，默认当月
        product_id: 按品种过滤（None=全部品种混合）
    """
    if not year_month:
        year_month = datetime.utcnow().strftime("%Y-%m")
    # 解析月份范围
    try:
        y, m = year_month.split("-")
        start = datetime(int(y), int(m), 1)
        if int(m) == 12:
            end = datetime(int(y) + 1, 1, 1)
        else:
            end = datetime(int(y), int(m) + 1, 1)
    except (ValueError, IndexError):
        raise ValidationError("year_month 格式应为 YYYY-MM")

    q = db.query(
        ExperiencePoint.user_id,
        func.sum(ExperiencePoint.points).label("total_points"),
        func.count(ExperiencePoint.id).label("session_count"),
    ).filter(
        ExperiencePoint.tenant_id == tenant_id,
        ExperiencePoint.is_deleted == 0,
        ExperiencePoint.source == "train",
        ExperiencePoint.earned_at >= start,
        ExperiencePoint.earned_at < end,
    )
    if product_id:
        # 通过 scenario 关联 product
        q = q.join(PracticeScenario, PracticeScenario.id == ExperiencePoint.scenario_id).filter(
            PracticeScenario.product_id == product_id,
        )
    q = q.group_by(ExperiencePoint.user_id).order_by(func.sum(ExperiencePoint.points).desc()).limit(20)
    rows = q.all()

    # 补充用户名
    user_ids = [r[0] for r in rows]
    users = {}
    if user_ids:
        user_list = db.query(User).filter(User.id.in_(user_ids)).all()
        users = {u.id: u for u in user_list}

    items = []
    for idx, (uid, pts, cnt) in enumerate(rows, 1):
        u = users.get(uid)
        items.append({
            "rank": idx,
            "user_id": uid,
            "username": u.username if u else f"用户{uid}",
            "real_name": getattr(u, "real_name", None) if u else None,
            "total_points": int(pts or 0),
            "session_count": int(cnt or 0),
        })
    return {"year_month": year_month, "product_id": product_id, "items": items}


def _get_user_rank(db: Session, tenant_id: str, user_id: int) -> int:
    """计算用户当月排名"""
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # 查询所有用户当月 train 总分
    rows = db.query(
        ExperiencePoint.user_id,
        func.sum(ExperiencePoint.points).label("total"),
    ).filter(
        ExperiencePoint.tenant_id == tenant_id,
        ExperiencePoint.is_deleted == 0,
        ExperiencePoint.source == "train",
        ExperiencePoint.earned_at >= month_start,
    ).group_by(ExperiencePoint.user_id).all()
    # 排序
    sorted_users = sorted(rows, key=lambda r: r[1] or 0, reverse=True)
    for idx, (uid, _) in enumerate(sorted_users, 1):
        if uid == user_id:
            return idx
    return len(sorted_users) + 1


def _serialize_point(ep: ExperiencePoint) -> dict:
    return {
        "id": ep.id,
        "user_id": ep.user_id,
        "scenario_id": ep.scenario_id,
        "activity_id": ep.activity_id,
        "points": ep.points,
        "source": ep.source,
        "earned_at": ep.earned_at.strftime("%Y-%m-%d %H:%M:%S") if ep.earned_at else None,
    }
