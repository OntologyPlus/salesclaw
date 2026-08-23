"""培训效果因果归因 — 业务门面（B 路径）

设计文档：SalesClaw_培训效果因果归因_B路径_规划.md §5、§6、§7、§9、§10

对应 §4.1 的三种归因方法入口：
- 方法 A → lag_curve()
- 方法 B → cohort_compare()
- 方法 C → ai_attribution()（包装 effect_tracking_service.ai_evaluate）

事件入口：
- handle_training_completed()：由 ai/event_subscribers.on_training_effect_create 调用
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from config import settings
from core.constants import (
    ABILITY_DIMENSION_KEYS,
    TRAINING_EFFECT_METRIC_KEYS,
    TRAINING_EVIDENCE_CLUE_KINDS,
)
from database import AbilityProfile, DecisionExecution, ExamRecord, ProfileHistory, User

from services.effect_tracking_service import effect_tracking_service
from services.training_effect_snapshot import (
    compute_target_metrics,
    snapshot_metrics,
    snapshot_to_dict,
)

logger = logging.getLogger(__name__)

# B 路径常量
DECISION_TYPE_TRAINING = "training"


# ──────────────────────────────────────────────
# 1. 事件入口：建 DecisionExecution(decision_type='training')
# ──────────────────────────────────────────────

def handle_training_completed(
    event_type: str,
    payload: dict,
    tenant_id: str,
    db: Session,
) -> dict:
    """三事件统一入口：建 DecisionExecution(planned)

    入参 payload 形态：
    - course_completed:        {user_id, course_id, ...}
    - practice_session_completed: {user_id, session_id, scenario_type, ...}
    - exam_passed:             {user_id, exam_id, exam_title, score}

    返回：{ok, execution_id} | {ok=False, error}
    """
    user_id = payload.get("user_id")
    if not user_id:
        return {"ok": False, "error": "missing_user_id"}

    # 同 source_id + 同 day 仅建一条（防重）
    source_id = (
        payload.get("course_id")
        or payload.get("session_id")
        or payload.get("exam_id")
    )
    if _already_recorded_today(db, tenant_id=tenant_id, user_id=user_id, source_id=source_id):
        logger.info("training_effect: 已存在同日 execution（跳过）source_id=%s", source_id)
        return {"ok": True, "skipped": True}

    # baseline 快照（当下画像 + 30d KPI）
    snap = snapshot_metrics(db, user_id, kind="baseline", window_days=30)
    baseline_dict = snapshot_to_dict(snap.metrics)

    # target 推算
    target_dict = compute_target_metrics(
        baseline_dict,
        target_score_default=settings.TRAINING_TARGET_SCORE_DEFAULT,
    )

    title = (
        payload.get("exam_title")
        or payload.get("course_title")
        or _title_from_event(event_type, source_id)
    )

    result = effect_tracking_service.create_execution(
        user_id=user_id,
        tenant_id=tenant_id,
        db=db,
        decision_type=DECISION_TYPE_TRAINING,
        title=title,
        description=(
            f"event={event_type}; "
            f"source_id={source_id}; "
            f"course_or_session={payload.get('scenario_type') or payload.get('category') or '-'}"
        ).strip(";"),
        baseline=baseline_dict,
        target=target_dict,
    )
    if "error" in result:
        return {"ok": False, "error": result.get("error"), "detail": result.get("detail")}

    return {"ok": True, "execution_id": result["execution_id"], "skipped": False}


def _already_recorded_today(
    db: Session, tenant_id: str, user_id: int, source_id: Optional[int]
) -> bool:
    """同一 user + 同一 source 当日是否已有 execution（去重）"""
    if source_id is None:
        return False
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    exists = (
        db.query(DecisionExecution)
        .filter(
            DecisionExecution.tenant_id == tenant_id,
            DecisionExecution.user_id == user_id,
            DecisionExecution.decision_type == DECISION_TYPE_TRAINING,
            DecisionExecution.is_deleted == 0,
            DecisionExecution.created_at >= start,
            DecisionExecution.description.contains(f"source_id={source_id}"),
        )
        .first()
    )
    return exists is not None


def _title_from_event(event_type: str, source_id: Optional[int]) -> str:
    return f"培训 #{event_type}#{source_id}"


# ──────────────────────────────────────────────
# 2. 方法 A — 滞后期效果曲线
# ──────────────────────────────────────────────

def lag_curve(
    db: Session,
    user_id: int,
    execution_id: int,
    tenant_id: str,
) -> dict:
    """返回 4 个时间点 [t0, t0+30, t0+90, t0+180] 的同一份指标快照 + 相对 t0 的 delta。

    设计文档 §5.1：baseline 已存在；t0+N 通过 re-snapshot 聚合得到。
    对小样本（实在查不到画像），值取 0，但保证返回完整结构。
    """
    windows = tuple(settings.TRAINING_LAG_WINDOWS)
    record = (
        db.query(DecisionExecution)
        .filter(
            DecisionExecution.id == execution_id,
            DecisionExecution.tenant_id == tenant_id,
            DecisionExecution.user_id == user_id,
            DecisionExecution.is_deleted == 0,
            DecisionExecution.decision_type == DECISION_TYPE_TRAINING,
        )
        .first()
    )
    if record is None:
        return {"error": "not_found", "execution_id": execution_id}

    t0 = record.created_at

    def snap_at(window_days: int) -> dict[str, float]:
        if window_days == 0:
            return dict(record.baseline_metrics or {})
        # t0+N：抓当下画像 + 同期 KPI 聚合（N 本身）
        snap = snapshot_metrics(db, user_id, kind=f"actual_{window_days}d", window_days=window_days)
        return snapshot_to_dict(snap.metrics)

    series: list[dict] = []
    for w in (0,) + windows:
        series.append({
            "t": w,
            "label": "t0_baseline" if w == 0 else f"t0+{w}d",
            "snapshot": snap_at(w),
        })

    # diffs：每个 metric 在 4 个时间点的 delta（相对 t0）
    diffs: dict[str, list[dict]] = {}
    base = series[0]["snapshot"]
    for metric in TRAINING_EFFECT_METRIC_KEYS:
        diffs[metric] = [
            {"t": p["t"], "delta": round((p["snapshot"].get(metric, 0.0) or 0.0)
                                          - (base.get(metric, 0.0) or 0.0), 2)}
            for p in series
        ]

    return {
        "execution_id": execution_id,
        "user_id": user_id,
        "t0": t0.isoformat(),
        "windows": list((0,) + windows),
        "series": series,
        "diffs": diffs,
    }


# ──────────────────────────────────────────────
# 3. 方法 B — 同期类比组（cohort comparison）
# ──────────────────────────────────────────────

def cohort_compare(
    db: Session,
    tenant_id: str,
    cohort_key: str,
    period_days: int = 30,
    min_sample: Optional[int] = None,
) -> dict:
    """同期类比组对比：同 cohort 中"修了某类培训" vs "未修"，差值 + t 检验近似。

    Args:
        cohort_key: "region=East, role=MR, quarter=2026Q3"
        period_days: 同期窗口
        min_sample: 最小样本数（默认走 settings.TRAINING_COHORT_MIN_SAMPLE）

    注：小样本（< min_sample）返回 is_significant=False + warning
    t 检验近似：双样本独立 t = (mean_a - mean_b) / sqrt(var_a/n_a + var_b/n_b)
    """
    min_sample = min_sample or settings.TRAINING_COHORT_MIN_SAMPLE
    # 解析 cohort_key：粗粒度匹配（region / role / dept）
    region, role = _parse_cohort_key(cohort_key)

    # 拉所有该 cohort 的用户
    user_q = db.query(User).filter(
        User.tenant_id == tenant_id,
        User.is_deleted == 0,
    )
    if region and hasattr(User, "region"):
        user_q = user_q.filter(User.region == region)
    if role and hasattr(User, "role"):
        user_q = user_q.filter(User.role == role)
    users = user_q.all()

    treated_ids: list[int] = []
    control_ids: list[int] = []
    cutoff = datetime.utcnow() - timedelta(days=period_days)

    for u in users:
        trained = (
            db.query(DecisionExecution)
            .filter(
                DecisionExecution.tenant_id == tenant_id,
                DecisionExecution.user_id == u.id,
                DecisionExecution.decision_type == DECISION_TYPE_TRAINING,
                DecisionExecution.is_deleted == 0,
                DecisionExecution.created_at >= cutoff,
            )
            .first()
        )
        if trained is not None:
            treated_ids.append(u.id)
        else:
            control_ids.append(u.id)

    # 取一个核心 metric（月拜访量）作为对比
    metric = "monthly_visit_count"
    treated_vals = [_snapshot_metric(db, uid, metric, period_days) for uid in treated_ids]
    control_vals = [_snapshot_metric(db, uid, metric, period_days) for uid in control_ids]

    if len(treated_vals) < min_sample or len(control_vals) < min_sample:
        return {
            "cohort_key": cohort_key,
            "metric": metric,
            "treated_n": len(treated_vals),
            "control_n": len(control_vals),
            "treated_mean": _safe_mean(treated_vals),
            "control_mean": _safe_mean(control_vals),
            "diff": None,
            "p_value": None,
            "ci95": None,
            "is_significant": False,
            "warning": f"样本不足（required={min_sample}）",
        }

    t_mean = _safe_mean(treated_vals)
    c_mean = _safe_mean(control_vals)
    diff = t_mean - c_mean
    t_stat, p_value = _welch_t(treated_vals, control_vals)
    ci95 = _ci95(treated_vals, control_vals)

    return {
        "cohort_key": cohort_key,
        "metric": metric,
        "treated_n": len(treated_vals),
        "control_n": len(control_vals),
        "treated_mean": t_mean,
        "control_mean": c_mean,
        "diff": round(diff, 3),
        "p_value": round(p_value, 4),
        "ci95": [round(ci95[0], 3), round(ci95[1], 3)] if ci95 else None,
        "is_significant": p_value < 0.05,
    }


def _parse_cohort_key(key: str) -> tuple[Optional[str], Optional[str]]:
    if not key:
        return None, None
    region = role = None
    for token in key.split(","):
        token = token.strip()
        if token.startswith("region="):
            region = token[len("region="):]
        elif token.startswith("role="):
            role = token[len("role="):]
    return region, role


def _safe_mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _welch_t(a: list[float], b: list[float]) -> tuple[float, float]:
    """Welch t 检验近似（不依赖 scipy，避免外部依赖）。"""
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return 0.0, 1.0
    m1, m2 = _safe_mean(a), _safe_mean(b)
    v1 = sum((x - m1) ** 2 for x in a) / (n1 - 1)
    v2 = sum((x - m2) ** 2 for x in b) / (n2 - 1)
    se = math.sqrt(v1 / n1 + v2 / n2) if (v1 / n1 + v2 / n2) > 0 else 1e-9
    t = (m1 - m2) / se
    # 用正态近似（lib 不依赖）：p ≈ 2 * (1 - Φ(|t|))
    p = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(t) / math.sqrt(2.0))))
    return t, min(p, 1.0)


def _ci95(a: list[float], b: list[float]) -> Optional[tuple[float, float]]:
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return None
    m1, m2 = _safe_mean(a), _safe_mean(b)
    diff = m1 - m2
    v1 = sum((x - m1) ** 2 for x in a) / (n1 - 1)
    v2 = sum((x - m2) ** 2 for x in b) / (n2 - 1)
    se = math.sqrt(v1 / n1 + v2 / n2)
    return (diff - 1.96 * se, diff + 1.96 * se)


def _snapshot_metric(db: Session, user_id: int, metric: str, window_days: int) -> float:
    """cohort 单用户的某个 metric 取值"""
    snap = snapshot_metrics(db, user_id, kind="cohort", window_days=window_days)
    return float(snap.metrics.get(metric, 0.0) or 0.0)


# ──────────────────────────────────────────────
# 4. 方法 C — AI 归因（含 evidence_clues 装配）
# ──────────────────────────────────────────────

async def ai_attribution(
    db: Session,
    execution_id: int,
    tenant_id: str,
) -> dict:
    """AI 归因（包装 ai_evaluate）—— 自动装配 evidence_clues + training_meta 后调用。"""
    record = (
        db.query(DecisionExecution)
        .filter(
            DecisionExecution.id == execution_id,
            DecisionExecution.tenant_id == tenant_id,
            DecisionExecution.is_deleted == 0,
        )
        .first()
    )
    if record is None:
        return {"error": "not_found", "execution_id": execution_id}

    evidence_clues = _build_evidence_clues(db, record)
    training_meta = _build_training_meta(db, record)

    # ai_evaluate 接收扩展入参；_extra_payload 会在编排器 chat 的 message 中拼接
    return await effect_tracking_service.ai_evaluate(
        execution_id=execution_id,
        tenant_id=tenant_id,
        db=db,
        user=str(record.user_id),
        extra_payload={
            "scenario": "training_effect",
            "evidence_clues": evidence_clues,
            "training_meta": training_meta,
        },
    )


def _build_evidence_clues(db: Session, record: DecisionExecution) -> list[dict]:
    """装配线索：profile_delta / exam_score / behavior_points / collateral_kpi"""
    clues: list[dict] = []
    t0 = record.created_at

    # 1. profile_delta: 画像最近 N 条 source=training 的增量
    rows = (
        db.query(ProfileHistory)
        .filter(
            ProfileHistory.tenant_id == record.tenant_id,
            ProfileHistory.user_id == record.user_id,
            ProfileHistory.source == "training",
            ProfileHistory.occurred_at >= t0,
        )
        .order_by(ProfileHistory.occurred_at.desc())
        .limit(8)
        .all()
    )
    for idx, r in enumerate(rows):
        clues.append({
            "clue_type": "profile_delta",
            "dimension": r.dimension,
            "delta": float(r.delta or 0.0),
            "source": "training",
            "source_id": r.source_id,
            "evidence_at": r.occurred_at.isoformat() if r.occurred_at else None,
            "weight_hint": 0.30,
            "_index": idx,
        })

    # 2. exam_score: 同期最近一次考试
    exam = (
        db.query(ExamRecord)
        .filter(
            ExamRecord.tenant_id == record.tenant_id,
            ExamRecord.user_id == record.user_id,
            ExamRecord.passed == 1,
            ExamRecord.submitted_at >= t0,
        )
        .order_by(ExamRecord.submitted_at.desc())
        .first()
    )
    if exam is not None:
        idx = len(clues)
        clues.append({
            "clue_type": "exam_score",
            "score": float(exam.score or 0.0),
            "passed": True,
            "source_id": exam.exam_id,
            "evidence_at": exam.submitted_at.isoformat() if exam.submitted_at else None,
            "weight_hint": 0.20,
            "_index": idx,
        })

    # 3. collateral_kpi: 同期行为 KPI（取 actual_metrics 中前两个 KPI）
    actual = record.actual_metrics or {}
    for k in ("monthly_visit_count", "feedback_positive_rate", "behavior_points"):
        if k in actual:
            idx = len(clues)
            clues.append({
                "clue_type": "collateral_kpi",
                "metric": k,
                "value": float(actual.get(k) or 0.0),
                "weight_hint": 0.15,
                "_index": idx,
            })

    # 4. 限长 ≤ 12 条（避免 prompt 超长）
    return clues[:12]


def _build_training_meta(db: Session, record: DecisionExecution) -> dict:
    """训练元数据（用于 AI 归因 prompt 上下文）"""
    cohort_key = _infer_cohort_key(db, record)
    return {
        "execution_id": record.id,
        "title": record.title,
        "cohort_key": cohort_key,
    }


def _infer_cohort_key(db: Session, record: DecisionExecution) -> str:
    """从 user 派生粗粒度 cohort_key"""
    u = (
        db.query(User)
        .filter(User.id == record.user_id, User.is_deleted == 0)
        .first()
    )
    if u is None:
        return "unknown"
    parts = []
    if hasattr(u, "region") and u.region:
        parts.append(f"region={u.region}")
    if hasattr(u, "role") and u.role:
        parts.append(f"role={u.role}")
    return ",".join(parts) or "default"


# ──────────────────────────────────────────────
# 5. 看板总览
# ──────────────────────────────────────────────

def overview(db: Session, tenant_id: str, period_days: int = 30) -> dict:
    """CEO 看板总览"""
    cutoff = datetime.utcnow() - timedelta(days=period_days)
    rows = (
        db.query(DecisionExecution)
        .filter(
            DecisionExecution.tenant_id == tenant_id,
            DecisionExecution.decision_type == DECISION_TYPE_TRAINING,
            DecisionExecution.is_deleted == 0,
            DecisionExecution.created_at >= cutoff,
        )
        .all()
    )

    total = len(rows)
    completed = [r for r in rows if r.status == "completed"]
    executing = [r for r in rows if r.status == "executing"]
    planned = [r for r in rows if r.status == "planned"]
    scored = [r.effectiveness_score for r in completed if r.effectiveness_score is not None]
    overall_avg = round(sum(scored) / len(scored), 1) if scored else None
    achievement_rate = round(sum(1 for s in scored if s >= 80) / len(scored), 2) if scored else None

    return {
        "period_days": period_days,
        "completion_count": total,
        "completed_count": len(completed),
        "executing_count": len(executing),
        "planned_count": len(planned),
        "overall_effectiveness_avg": overall_avg,
        "achievement_rate": achievement_rate,
        "by_dimension": _aggregate_by_dimension(completed),
    }


def _aggregate_by_dimension(completed_rows) -> list[dict]:
    """按画像维度聚合 delta（mean + count）"""
    bucket: dict[str, list[float]] = defaultdict(list)
    for r in completed_rows:
        baseline = r.baseline_metrics or {}
        actual = r.actual_metrics or {}
        for k in ABILITY_DIMENSION_KEYS:
            b = baseline.get(k) or 0
            a = actual.get(k) or 0
            delta = (a - b) if (a is not None and b is not None) else 0
            if delta != 0:
                bucket[k].append(delta)
    return [
        {
            "dim": k,
            "n": len(v),
            "mean_delta": round(sum(v) / len(v), 2),
            "achievement_rate": round(sum(1 for x in v if x > 0) / len(v), 2),
        }
        for k, v in sorted(bucket.items(), key=lambda kv: -len(kv[1]))
    ]


# ──────────────────────────────────────────────
# 6. 执行记录列表查询
# ──────────────────────────────────────────────

def list_executions(
    db: Session,
    tenant_id: str,
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    period_days: int = 180,
    limit: int = 50,
) -> list[dict]:
    """列出某 tenant 的 training execution"""
    q = (
        db.query(DecisionExecution)
        .filter(
            DecisionExecution.tenant_id == tenant_id,
            DecisionExecution.decision_type == DECISION_TYPE_TRAINING,
            DecisionExecution.is_deleted == 0,
        )
    )
    if user_id is not None:
        q = q.filter(DecisionExecution.user_id == user_id)
    if status:
        q = q.filter(DecisionExecution.status == status)
    cutoff = datetime.utcnow() - timedelta(days=period_days)
    q = q.filter(DecisionExecution.created_at >= cutoff)
    rows = q.order_by(DecisionExecution.created_at.desc()).limit(limit).all()
    return [_exec_to_dict(r) for r in rows]


def get_execution(db: Session, execution_id: int, tenant_id: str) -> Optional[dict]:
    row = (
        db.query(DecisionExecution)
        .filter(
            DecisionExecution.id == execution_id,
            DecisionExecution.tenant_id == tenant_id,
            DecisionExecution.is_deleted == 0,
        )
        .first()
    )
    return _exec_to_dict(row) if row else None


def _exec_to_dict(record: DecisionExecution) -> dict:
    if record is None:
        return {}
    return {
        "execution_id": record.id,
        "user_id": record.user_id,
        "tenant_id": record.tenant_id,
        "decision_type": record.decision_type,
        "title": record.title,
        "description": record.description,
        "baseline_metrics": record.baseline_metrics or {},
        "target_metrics": record.target_metrics or {},
        "actual_metrics": record.actual_metrics or {},
        "status": record.status,
        "started_at": record.started_at.isoformat() if record.started_at else None,
        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
        "effectiveness_score": record.effectiveness_score,
        "reasoning_chain_id": getattr(record, "reasoning_chain_id", None),
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


__all__ = [
    "DECISION_TYPE_TRAINING",
    "handle_training_completed",
    "lag_curve",
    "cohort_compare",
    "ai_attribution",
    "overview",
    "list_executions",
    "get_execution",
]
