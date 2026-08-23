"""可观测服务层

提供系统运行指标能力。
数据来源：User + VisitRecord + Course + LlmCallLog + AuditLog + SQLAlchemy Inspector。
"""
from datetime import datetime, timedelta
from sqlalchemy import inspect, func
from sqlalchemy.orm import Session

from database import (
    User, VisitRecord, Course, LlmCallLog, AuditLog,
    business_engine,
)


# ──────────────────────────────────────────────
# 系统指标
# ──────────────────────────────────────────────

def get_metrics(db: Session, tenant_id: str) -> dict:
    """系统运行指标"""
    now = datetime.utcnow()

    # uptime_seconds：从最早 AuditLog.ts 计算；没有则回退 0
    first_log = db.query(AuditLog).filter(
        AuditLog.tenant_id == tenant_id,
        AuditLog.is_deleted == 0,
    ).order_by(AuditLog.ts.asc()).first()
    if first_log and first_log.ts:
        uptime_seconds = int((now - first_log.ts).total_seconds())
    else:
        uptime_seconds = 0

    # 用户指标
    total_users = db.query(User).filter(
        User.tenant_id == tenant_id,
        User.is_deleted == 0,
    ).count()

    seven_days_ago = now - timedelta(days=7)
    active_users = db.query(User).filter(
        User.tenant_id == tenant_id,
        User.is_deleted == 0,
        User.last_login_at.isnot(None),
        User.last_login_at >= seven_days_ago,
    ).count()

    # 业务域数据量
    total_visits = db.query(VisitRecord).filter(
        VisitRecord.tenant_id == tenant_id,
        VisitRecord.is_deleted == 0,
    ).count()

    total_courses = db.query(Course).filter(
        Course.tenant_id == tenant_id,
        Course.is_deleted == 0,
    ).count()

    # LLM 调用统计（全租户）
    llm_calls = db.query(LlmCallLog).filter(
        LlmCallLog.tenant_id == tenant_id,
        LlmCallLog.is_deleted == 0,
    ).count()
    llm_success = db.query(LlmCallLog).filter(
        LlmCallLog.tenant_id == tenant_id,
        LlmCallLog.is_deleted == 0,
        LlmCallLog.status == "ok",
    ).count()
    llm_success_rate = round(llm_success / llm_calls * 100, 2) if llm_calls > 0 else 0.0

    # 数据库表数量
    db_table_count = _count_business_tables()

    # 域分布：销售域、培训域、协同域、知识域、AI 域
    domain_distribution = _domain_distribution(db, tenant_id)

    return {
        "uptime_seconds": uptime_seconds,
        "total_users": total_users,
        "active_users": active_users,
        "total_visits": total_visits,
        "total_courses": total_courses,
        "llm_calls": llm_calls,
        "llm_success_rate": llm_success_rate,
        "db_table_count": db_table_count,
        "domain_distribution": domain_distribution,
    }


# ──────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────

def _count_business_tables() -> int:
    """统计业务数据库的表数量"""
    try:
        insp = inspect(business_engine)
        return len(insp.get_table_names())
    except Exception:
        return 0


def _domain_distribution(db: Session, tenant_id: str) -> list:
    """统计各业务域记录数"""
    # 延迟导入以避免循环依赖
    from database import (
        VisitRecord, VisitPlan, CoverageAssignment, BehaviorPointRecord,
        Course, CourseEnrollment, ExamRecord, PracticeSession,
        Task, Approval, Announcement,
        KnowledgeDocument, FaqItem,
        ChatSession, LlmCallLog,
        Meeting, ForumTopic,
    )

    def _count(model) -> int:
        return db.query(model).filter(
            model.tenant_id == tenant_id,
            model.is_deleted == 0,
        ).count()

    try:
        sales_count = _count(VisitRecord) + _count(VisitPlan) + _count(CoverageAssignment) + _count(BehaviorPointRecord)
    except Exception:
        sales_count = 0
    try:
        training_count = _count(Course) + _count(CourseEnrollment) + _count(ExamRecord) + _count(PracticeSession)
    except Exception:
        training_count = 0
    try:
        collab_count = _count(Task) + _count(Approval) + _count(Announcement)
    except Exception:
        collab_count = 0
    try:
        knowledge_count = _count(KnowledgeDocument) + _count(FaqItem)
    except Exception:
        knowledge_count = 0
    try:
        ai_count = _count(ChatSession) + _count(LlmCallLog)
    except Exception:
        ai_count = 0
    try:
        cfm_count = _count(Meeting) + _count(ForumTopic)
    except Exception:
        cfm_count = 0

    return [
        {"domain": "sales", "count": sales_count},
        {"domain": "training", "count": training_count},
        {"domain": "collab", "count": collab_count},
        {"domain": "knowledge", "count": knowledge_count},
        {"domain": "ai", "count": ai_count},
        {"domain": "cfm", "count": cfm_count},
    ]


# ──────────────────────────────────────────────
# 告警（基于真实运行指标派生；阈值配置保留内存态）
# ──────────────────────────────────────────────

_ALERT_CONFIGS = {}

# 告警阈值默认值（可被 config_alerts 覆盖）
_DEFAULT_THRESHOLDS = {
    "llm_fail_rate_warn": 20.0,   # AI 调用失败率(%)，超过则 warning
    "llm_fail_rate_crit": 50.0,   # 超过则 critical
    "delete_burst": 5,             # 24h 内 delete 操作数，超过则 warning
}


def _derive_alerts(db: Session, tenant_id: str) -> list:
    """从真实运行数据派生告警，避免硬编码假数据。

    派生规则：
      - AI 调用失败率（近 7 天）：基于 LlmCallLog.status 真实统计
      - 审计日志中 24h 内 delete 操作突增：基于 AuditLog.action 真实统计
      - 系统冷启动（无任何审计日志）：提示数据尚未积累
    所有告警 ts 取真实最近事件时间或当前时间。
    """
    now = datetime.utcnow()
    thresholds = {**_DEFAULT_THRESHOLDS, **_ALERT_CONFIGS.get(tenant_id, {})}
    alerts: list = []

    # 1. AI 调用失败率（近 7 天）
    seven_days_ago = now - timedelta(days=7)
    total_llm = db.query(LlmCallLog).filter(
        LlmCallLog.tenant_id == tenant_id,
        LlmCallLog.is_deleted == 0,
        LlmCallLog.created_at >= seven_days_ago,
    ).count()
    failed_llm = db.query(LlmCallLog).filter(
        LlmCallLog.tenant_id == tenant_id,
        LlmCallLog.is_deleted == 0,
        LlmCallLog.created_at >= seven_days_ago,
        LlmCallLog.status != "ok",
    ).count()
    if total_llm > 0:
        fail_rate = round(failed_llm / total_llm * 100, 2)
        if fail_rate >= thresholds["llm_fail_rate_crit"]:
            level, status = "critical", "active"
        elif fail_rate >= thresholds["llm_fail_rate_warn"]:
            level, status = "warning", "active"
        else:
            level, status = None, None
        if level:
            last = db.query(LlmCallLog).filter(
                LlmCallLog.tenant_id == tenant_id,
                LlmCallLog.is_deleted == 0,
                LlmCallLog.status != "ok",
            ).order_by(LlmCallLog.created_at.desc()).first()
            alerts.append({
                "id": f"llm_fail_{tenant_id}",
                "level": level,
                "source": "ai",
                "message": f"近 7 天 AI 调用失败率 {fail_rate}%（{failed_llm}/{total_llm}），"
                           f"超过阈值 {thresholds['llm_fail_rate_crit' if level == 'critical' else 'llm_fail_rate_warn']}%",
                "status": status,
                "ts": last.created_at.strftime("%Y-%m-%d %H:%M:%S") if last and last.created_at else now.strftime("%Y-%m-%d %H:%M:%S"),
            })
    else:
        alerts.append({
            "id": f"llm_no_data_{tenant_id}",
            "level": "info",
            "source": "ai",
            "message": "近 7 天暂无 AI 调用记录",
            "status": "active",
            "ts": now.strftime("%Y-%m-%d %H:%M:%S"),
        })

    # 2. 24h 内 delete 操作突增
    day_ago = now - timedelta(days=1)
    delete_cnt = db.query(AuditLog).filter(
        AuditLog.tenant_id == tenant_id,
        AuditLog.is_deleted == 0,
        AuditLog.action == "delete",
        AuditLog.ts >= day_ago,
    ).count()
    if delete_cnt >= thresholds["delete_burst"]:
        last_del = db.query(AuditLog).filter(
            AuditLog.tenant_id == tenant_id,
            AuditLog.is_deleted == 0,
            AuditLog.action == "delete",
        ).order_by(AuditLog.ts.desc()).first()
        alerts.append({
            "id": f"delete_burst_{tenant_id}",
            "level": "warning",
            "source": "audit",
            "message": f"近 24 小时发生 {delete_cnt} 次删除操作，需关注数据安全",
            "status": "active",
            "ts": last_del.ts.strftime("%Y-%m-%d %H:%M:%S") if last_del and last_del.ts else now.strftime("%Y-%m-%d %H:%M:%S"),
        })

    # 3. 系统冷启动提示（无审计数据）
    any_log = db.query(AuditLog).filter(
        AuditLog.tenant_id == tenant_id,
        AuditLog.is_deleted == 0,
    ).first()
    if not any_log:
        alerts.append({
            "id": f"no_activity_{tenant_id}",
            "level": "info",
            "source": "system",
            "message": "系统暂无审计日志，运行数据尚未积累",
            "status": "active",
            "ts": now.strftime("%Y-%m-%d %H:%M:%S"),
        })

    return alerts


def list_alerts(db: Session, tenant_id: str) -> dict:
    """告警列表（基于真实运行指标派生）"""
    items = _derive_alerts(db, tenant_id)
    return {"items": items, "total": len(items)}


def config_alerts(db: Session, tenant_id: str, config: dict) -> dict:
    """告警阈值配置（内存存储；仅影响派生阈值，不影响历史记录）"""
    _ALERT_CONFIGS[tenant_id] = config
    return {"tenant_id": tenant_id, "config": config}
