"""活动数据看板服务层

按部门/场景/学员三个维度聚合活动训练数据。
数据源：PracticeSession（含 activity_id）+ ActivityScenarioRel + PracticeScenario + User + Zone
"""
import logging
import csv
import io
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from core.exceptions import NotFoundError
from database import (
    TrainingActivity, ActivityScenarioRel, PracticeScenario,
    PracticeSession, User, Zone,
)

logger = logging.getLogger(__name__)


def _fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


# ──────────────────────────────────────────────
# KPI 概览
# ──────────────────────────────────────────────

def get_kpi_summary(db: Session, tenant_id: str, activity_id: int) -> dict:
    activity = db.query(TrainingActivity).filter(
        TrainingActivity.tenant_id == tenant_id,
        TrainingActivity.is_deleted == 0,
        TrainingActivity.id == activity_id,
    ).first()
    if not activity:
        raise NotFoundError("活动不存在")

    # 关联场景数
    scenario_count = db.query(func.count(ActivityScenarioRel.id)).filter(
        ActivityScenarioRel.activity_id == activity_id,
        ActivityScenarioRel.is_deleted == 0,
    ).scalar() or 0

    # 应参与人数（简化：全部活跃用户）
    total_learners = db.query(func.count(User.id)).filter(
        User.tenant_id == tenant_id,
        User.is_deleted == 0,
        User.is_active == 1,
    ).scalar() or 0

    # 练习参与人次（PracticeSession 中 activity_id 关联且 status=completed）
    practice_count = db.query(func.count(PracticeSession.id)).filter(
        PracticeSession.tenant_id == tenant_id,
        PracticeSession.is_deleted == 0,
        PracticeSession.activity_id == activity_id,
        PracticeSession.status == "completed",
    ).scalar() or 0

    # 训战参与人次（同上，不区分练习/训战，当前模型统一计入）
    train_count = practice_count

    # 达标人次（score >= pass_score）
    passed_count = db.query(func.count(PracticeSession.id)).filter(
        PracticeSession.tenant_id == tenant_id,
        PracticeSession.is_deleted == 0,
        PracticeSession.activity_id == activity_id,
        PracticeSession.status == "completed",
        PracticeSession.score >= activity.pass_score,
    ).scalar() or 0

    # 去重参与人数
    practice_users = db.query(func.count(func.distinct(PracticeSession.user_id))).filter(
        PracticeSession.tenant_id == tenant_id,
        PracticeSession.is_deleted == 0,
        PracticeSession.activity_id == activity_id,
        PracticeSession.status == "completed",
    ).scalar() or 0

    participation_rate = round(practice_users / total_learners * 100, 1) if total_learners > 0 else 0
    pass_rate = round(passed_count / train_count * 100, 1) if train_count > 0 else 0

    return {
        "scenario_count": scenario_count,
        "total_learners": total_learners,
        "practice_count": practice_count,
        "train_count": train_count,
        "practice_users": practice_users,
        "passed_count": passed_count,
        "participation_rate": participation_rate,
        "pass_rate": pass_rate,
        "pass_score": activity.pass_score,
    }


# ──────────────────────────────────────────────
# 趋势
# ──────────────────────────────────────────────

def get_trend(db: Session, tenant_id: str, activity_id: int, days: int = 30) -> list:
    now = datetime.utcnow()
    start = now - timedelta(days=days)
    sessions = db.query(PracticeSession).filter(
        PracticeSession.tenant_id == tenant_id,
        PracticeSession.is_deleted == 0,
        PracticeSession.activity_id == activity_id,
        PracticeSession.status == "completed",
        PracticeSession.ended_at >= start,
    ).all()

    trend = {}
    for s in sessions:
        day = s.ended_at.strftime("%Y-%m-%d") if s.ended_at else s.started_at.strftime("%Y-%m-%d")
        if day not in trend:
            trend[day] = {"date": day, "count": 0, "passed": 0}
        trend[day]["count"] += 1
        if s.score and s.score >= 60:
            trend[day]["passed"] += 1

    return sorted(trend.values(), key=lambda x: x["date"])


# ──────────────────────────────────────────────
# 按部门聚合
# ──────────────────────────────────────────────

def aggregate_by_department(db: Session, tenant_id: str, activity_id: int,
                            keyword: str = None) -> list:
    activity = db.query(TrainingActivity).filter(
        TrainingActivity.tenant_id == tenant_id,
        TrainingActivity.is_deleted == 0,
        TrainingActivity.id == activity_id,
    ).first()
    if not activity:
        raise NotFoundError("活动不存在")

    sessions = db.query(PracticeSession).filter(
        PracticeSession.tenant_id == tenant_id,
        PracticeSession.is_deleted == 0,
        PracticeSession.activity_id == activity_id,
        PracticeSession.status == "completed",
    ).all()

    # 按 zone_id 分组（从 user.zone_id 获取部门）
    dept_data = {}
    user_cache = {}
    for s in sessions:
        if s.user_id not in user_cache:
            user = db.query(User).filter(User.id == s.user_id).first()
            user_cache[s.user_id] = user
        user = user_cache[s.user_id]
        zone_id = user.zone_id if user else 0
        if zone_id not in dept_data:
            zone = db.query(Zone).filter(Zone.id == zone_id).first()
            dept_data[zone_id] = {
                "department": zone.name if zone else f"区划{zone_id}",
                "zone_id": zone_id,
                "total_sessions": 0,
                "passed_sessions": 0,
                "total_duration": 0,
                "users": set(),
            }
        d = dept_data[zone_id]
        d["total_sessions"] += 1
        if s.score and s.score >= activity.pass_score:
            d["passed_sessions"] += 1
        if s.started_at and s.ended_at:
            dur = (s.ended_at - s.started_at).total_seconds() / 60
            d["total_duration"] += dur
        d["users"].add(s.user_id)

    result = []
    for zone_id, d in dept_data.items():
        if keyword and keyword not in d["department"]:
            continue
        pass_rate = round(d["passed_sessions"] / d["total_sessions"] * 100, 1) if d["total_sessions"] > 0 else 0
        avg_duration = round(d["total_duration"] / d["total_sessions"], 1) if d["total_sessions"] > 0 else 0
        result.append({
            "department": d["department"],
            "zone_id": zone_id,
            "total_sessions": d["total_sessions"],
            "passed_sessions": d["passed_sessions"],
            "unique_users": len(d["users"]),
            "pass_rate": pass_rate,
            "avg_duration": avg_duration,
        })
    return result


# ──────────────────────────────────────────────
# 按场景聚合
# ──────────────────────────────────────────────

def aggregate_by_scenario(db: Session, tenant_id: str, activity_id: int,
                          keyword: str = None) -> list:
    rels = db.query(ActivityScenarioRel).filter(
        ActivityScenarioRel.tenant_id == tenant_id,
        ActivityScenarioRel.is_deleted == 0,
        ActivityScenarioRel.activity_id == activity_id,
    ).all()

    activity = db.query(TrainingActivity).filter(
        TrainingActivity.id == activity_id,
    ).first()

    result = []
    for rel in rels:
        scenario = db.query(PracticeScenario).filter(
            PracticeScenario.id == rel.scenario_id,
            PracticeScenario.is_deleted == 0,
        ).first()
        if not scenario:
            continue
        if keyword and keyword not in scenario.title:
            continue

        sessions = db.query(PracticeSession).filter(
            PracticeSession.tenant_id == tenant_id,
            PracticeSession.is_deleted == 0,
            PracticeSession.scenario_id == rel.scenario_id,
            PracticeSession.activity_id == activity_id,
            PracticeSession.status == "completed",
        ).all()

        total = len(sessions)
        passed = sum(1 for s in sessions if s.score and s.score >= (activity.pass_score if activity else 60))
        unique_users = len(set(s.user_id for s in sessions))
        valid_users = len(set(s.user_id for s in sessions if s.score and s.score >= (activity.pass_score if activity else 60)))

        result.append({
            "scenario_id": rel.scenario_id,
            "scenario_title": scenario.title,
            "total_sessions": total,
            "unique_users": unique_users,
            "valid_users": valid_users,
            "pass_rate_by_user": round(valid_users / unique_users * 100, 1) if unique_users > 0 else 0,
            "pass_rate_by_session": round(passed / total * 100, 1) if total > 0 else 0,
        })
    return result


# ──────────────────────────────────────────────
# 按学员聚合
# ──────────────────────────────────────────────

def aggregate_by_learner(db: Session, tenant_id: str, activity_id: int,
                         keyword: str = None) -> list:
    activity = db.query(TrainingActivity).filter(
        TrainingActivity.id == activity_id,
    ).first()
    pass_score = activity.pass_score if activity else 60

    sessions = db.query(PracticeSession).filter(
        PracticeSession.tenant_id == tenant_id,
        PracticeSession.is_deleted == 0,
        PracticeSession.activity_id == activity_id,
        PracticeSession.status == "completed",
    ).order_by(PracticeSession.ended_at.desc()).all()

    learner_data = {}
    for s in sessions:
        if s.user_id not in learner_data:
            user = db.query(User).filter(User.id == s.user_id).first()
            name = user.display_name or user.username if user else f"用户{s.user_id}"
            if keyword and keyword not in name:
                continue
            learner_data[s.user_id] = {
                "user_id": s.user_id,
                "user_name": name,
                "latest_score": s.score,
                "best_score": s.score or 0,
                "passed_count": 0,
                "total_count": 0,
            }
        d = learner_data[s.user_id]
        d["total_count"] += 1
        if s.score:
            if d["latest_score"] is None or s.score > d["latest_score"]:
                d["latest_score"] = s.score
            if s.score > d["best_score"]:
                d["best_score"] = s.score
            if s.score >= pass_score:
                d["passed_count"] += 1

    result = []
    for uid, d in learner_data.items():
        d["is_passed"] = d["passed_count"] > 0
        result.append(d)
    return result


# ──────────────────────────────────────────────
# CSV 导出
# ──────────────────────────────────────────────

def export_csv(db: Session, tenant_id: str, activity_id: int, dimension: str) -> str:
    if dimension == "department":
        data = aggregate_by_department(db, tenant_id, activity_id)
        headers = ["部门", "总人次", "达标人次", "参与人数", "通过率", "平均耗时(分钟)"]
        rows = [[d["department"], d["total_sessions"], d["passed_sessions"],
                 d["unique_users"], d["pass_rate"], d["avg_duration"]] for d in data]
    elif dimension == "scenario":
        data = aggregate_by_scenario(db, tenant_id, activity_id)
        headers = ["场景ID", "场景名称", "参与人次", "参与人数", "达标人数", "通过率(人数)", "通过率(人次)"]
        rows = [[d["scenario_id"], d["scenario_title"], d["total_sessions"],
                 d["unique_users"], d["valid_users"], d["pass_rate_by_user"],
                 d["pass_rate_by_session"]] for d in data]
    elif dimension == "learner":
        data = aggregate_by_learner(db, tenant_id, activity_id)
        headers = ["学员ID", "学员姓名", "最新成绩", "最佳成绩", "是否达标", "达标次数", "总次数"]
        rows = [[d["user_id"], d["user_name"], d["latest_score"], d["best_score"],
                 "是" if d["is_passed"] else "否", d["passed_count"], d["total_count"]] for d in data]
    else:
        raise NotFoundError(f"不支持的分析维度: {dimension}")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()
