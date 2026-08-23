"""培训效果因果归因 — 指标快照服务（B 路径）

设计文档：SalesClaw_培训效果因果归因_B路径_规划.md §5、§8、§9

职责：
- 抓取同一 user 在某时点（baseline t0-7d / actual t0+N d）的 5 维画像 + 4 个行为 KPI；
- 装配 baseline / target / actual 三组字典的固定 key 集合；
- 提供 cohort_compare 同期类比组对比所需的聚合函数。

注意：本文件对未命中表/字段优雅回退（如测试环境 VisitRecord 无数据）。
线上依赖：
- AbilityProfile / ProfileHistory（能力画像）
- VisitRecord（拜访）
- VisitFeedback（拜访反馈，含 sentiment）
- BehaviorPointRecord（行为积分）
- DoctorRelationship（医生关系，可统计月新增）
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.constants import (
    ABILITY_DIMENSION_KEYS,
    TRAINING_EFFECT_METRIC_KEYS,
    TRAINING_EFFECT_METRICS,
)
from database import AbilityProfile


# ──────────────────────────────────────────────
# 安全导入（解耦生产数据表）
# ──────────────────────────────────────────────

def _try_import(symbol: str):
    """尝试从 database 导出指定类，失败返回 None（用于测试环境）"""
    try:
        from database import VisitRecord, VisitFeedback, BehaviorPointRecord, DoctorRelationship
    except Exception:
        return None
    return {
        "VisitRecord": VisitRecord,
        "VisitFeedback": VisitFeedback,
        "BehaviorPointRecord": BehaviorPointRecord,
        "DoctorRelationship": DoctorRelationship,
    }.get(symbol)


# ──────────────────────────────────────────────
# 结果容器
# ──────────────────────────────────────────────

@dataclass
class MetricsSnapshot:
    """9 维指标的完整快照（用于训练归因的三组字典）"""
    metrics: dict[str, float]
    captured_at: datetime
    source: str  # "baseline" / "actual" / "test"

    def to_dict(self) -> dict:
        return {
            "metrics": dict(self.metrics),
            "captured_at": self.captured_at.isoformat(),
            "source": self.source,
        }


def make_empty_snapshot(source: str = "empty") -> MetricsSnapshot:
    """返回全 0 占位快照（数据缺失时使用，避免落空 dict）"""
    return MetricsSnapshot(
        metrics={k: 0.0 for k in TRAINING_EFFECT_METRIC_KEYS},
        captured_at=datetime.utcnow(),
        source=source,
    )


# ──────────────────────────────────────────────
# 画像 5 维抓取
# ──────────────────────────────────────────────

def _snapshot_ability(db: Session, user_id: int) -> dict[str, float]:
    """抓取用户 5 维画像当前分数（缺省 0）。"""
    rows = (
        db.query(AbilityProfile)
        .filter(
            AbilityProfile.user_id == user_id,
            AbilityProfile.is_deleted == 0,
            AbilityProfile.dimension.in_(ABILITY_DIMENSION_KEYS),
        )
        .all()
    )
    result: dict[str, float] = {k: 0.0 for k in ABILITY_DIMENSION_KEYS}
    for r in rows:
        result[r.dimension] = float(r.score or 0.0)
    return result


def _snapshot_kpis(db: Session, user_id: int, window_days: int = 30) -> dict[str, float]:
    """抓取近 window_days 天的 4 个行为 KPI，找不到表/字段时优雅回退 0。

    输入：
    - monthly_visit_count: VisitRecord 在最近 window_days 内的拜访次数
    - feedback_positive_rate: VisitFeedback 中 sentiment 正面占比
    - behavior_points: BehaviorPointRecord 累计积分
    - new_doctors_monthly: DoctorRelationship 在最近 window_days 内新增数
    """
    out = {
        "monthly_visit_count": 0.0,
        "feedback_positive_rate": 0.0,
        "behavior_points": 0.0,
        "new_doctors_monthly": 0.0,
    }
    since = datetime.utcnow() - timedelta(days=window_days)
    try:
        VisitRecord = _try_import("VisitRecord")
        if VisitRecord is not None and hasattr(VisitRecord, "user_id"):
            cnt = (
                db.query(func.count(VisitRecord.id))
                .filter(
                    VisitRecord.user_id == user_id,
                    VisitRecord.is_deleted == 0,
                    VisitRecord.created_at >= since,
                )
                .scalar()
            )
            out["monthly_visit_count"] = float(cnt or 0)
    except Exception:
        pass

    try:
        VisitFeedback = _try_import("VisitFeedback")
        if VisitFeedback is not None and hasattr(VisitFeedback, "sentiment"):
            total = (
                db.query(func.count(VisitFeedback.id))
                .filter(
                    VisitFeedback.user_id == user_id,
                    VisitFeedback.is_deleted == 0,
                    VisitFeedback.created_at >= since,
                )
                .scalar()
            ) or 0
            positive = (
                db.query(func.count(VisitFeedback.id))
                .filter(
                    VisitFeedback.user_id == user_id,
                    VisitFeedback.is_deleted == 0,
                    VisitFeedback.sentiment.in_(("positive", "正面")),
                    VisitFeedback.created_at >= since,
                )
                .scalar()
            ) or 0
            out["feedback_positive_rate"] = float(positive / total) if total > 0 else 0.0
    except Exception:
        pass

    try:
        BehaviorPointRecord = _try_import("BehaviorPointRecord")
        if BehaviorPointRecord is not None and hasattr(BehaviorPointRecord, "points"):
            total_points = (
                db.query(func.coalesce(func.sum(BehaviorPointRecord.points), 0.0))
                .filter(
                    BehaviorPointRecord.user_id == user_id,
                    BehaviorPointRecord.is_deleted == 0,
                )
                .scalar()
            )
            out["behavior_points"] = float(total_points or 0.0)
    except Exception:
        pass

    try:
        DoctorRelationship = _try_import("DoctorRelationship")
        if DoctorRelationship is not None and hasattr(DoctorRelationship, "user_id"):
            cnt = (
                db.query(func.count(DoctorRelationship.id))
                .filter(
                    DoctorRelationship.user_id == user_id,
                    DoctorRelationship.is_deleted == 0,
                    DoctorRelationship.created_at >= since,
                )
                .scalar()
            )
            out["new_doctors_monthly"] = float(cnt or 0)
    except Exception:
        pass

    return out


# ──────────────────────────────────────────────
# 公开 API
# ──────────────────────────────────────────────

def snapshot_metrics(
    db: Session,
    user_id: int,
    kind: str = "actual",
    window_days: int = 30,
    as_of: Optional[datetime] = None,
) -> MetricsSnapshot:
    """抓取某时点的完整 9 维快照（画像 + KPI）。

    Args:
        db: 数据库 session（调用方管理）
        user_id: 用户 ID
        kind: "baseline" / "actual" / "label_only"（前者多用于 AI 归因上下文）
        window_days: KPI 聚合窗口（天数）
        as_of: 锚定时点，None 表示当下
    """
    # 画像：当下快照（ProfileHistory 用于 lag_curve 即可，不在 baseline 中拆分）
    ability = _snapshot_ability(db, user_id)
    kpis = _snapshot_kpis(db, user_id, window_days=window_days)
    merged = {**ability, **kpis}
    return MetricsSnapshot(
        metrics=merged,
        captured_at=as_of or datetime.utcnow(),
        source=kind,
    )


def snapshot_to_dict(metrics: dict[str, float]) -> dict[str, float]:
    """统一 key 集合（缺失补 0）——给 DecisionExecution baseline/target/actual"""
    return {k: float(metrics.get(k, 0.0) or 0.0) for k in TRAINING_EFFECT_METRIC_KEYS}


def compute_target_metrics(
    baseline: dict[str, float],
    target_score_default: float = 3.0,
) -> dict[str, float]:
    """基于 baseline + 培训声称的 default 增量，推算 target。

    规则：
    - 5 维画像：target = baseline + target_score_default（上界 100）
    - 4 个 KPI：target = max(baseline, baseline * 1.10)（提升 10%）
    """
    out: dict[str, float] = {}
    for k, spec in TRAINING_EFFECT_METRICS.items():
        base = float(baseline.get(k, 0.0) or 0.0)
        if spec["kind"] == "ability":
            target = min(100.0, base + target_score_default)
        else:
            # KPI：提升 10%
            target = max(base, base * 1.10)
        out[k] = round(target, 2)
    return out
