"""Phase 3 合规专项服务（公示 / 监管报送 / 年度审计）。

对应《医药代表管理办法》：
- 第 13 条：备案信息向社会公示，接受监督。
- 第 26 条：药品上市许可持有人应建立合规体系，全过程留痕、配合监管报送。
- 企业年度合规审计：基于不可篡改的 AuditLog 证据链出具年度结论。
"""
from datetime import datetime, date
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from database import (
    PublicDisclosure,
    RegulatorySubmission,
    AnnualComplianceAudit,
    ComplianceViolationEvent,
    AuditLog,
)
from core.exceptions import NotFoundError
from services.compliance_service import (
    verify_audit_log_chain,
    append_compliance_audit_log,
)


# ──────────────────────────────────────────────
# 公示（Public Disclosure）
# ──────────────────────────────────────────────

def create_public_disclosure(
    db: Session, tenant_id: str,
    category: str, title: str, content: dict,
    ref_type: Optional[str] = None, ref_id: Optional[int] = None,
    disclosed_level: str = "internal",
    published_by: Optional[int] = None,
    expired_at: Optional[datetime] = None,
) -> PublicDisclosure:
    """登记一条合规公示（默认草稿态，可后续发布）。"""
    disclosure = PublicDisclosure(
        tenant_id=tenant_id,
        category=category,
        title=title,
        content=content,
        ref_type=ref_type,
        ref_id=ref_id,
        disclosed_level=disclosed_level,
        status="draft",
        published_by=published_by,
        expired_at=expired_at,
    )
    db.add(disclosure)
    db.flush()
    append_compliance_audit_log(
        db, tenant_id, published_by or 0, "compliance_officer",
        "public_disclosure.create", "public_disclosure", disclosure.id,
        {"category": category, "title": title, "disclosed_level": disclosed_level},
    )
    db.commit()
    return disclosure


def publish_public_disclosure(
    db: Session, tenant_id: str, disclosure_id: int,
    published_by: int, expired_at: Optional[datetime] = None,
) -> PublicDisclosure:
    """将草稿态公示发布为对外公示。"""
    d = db.query(PublicDisclosure).filter(
        PublicDisclosure.tenant_id == tenant_id,
        PublicDisclosure.is_deleted == 0,
        PublicDisclosure.id == disclosure_id,
    ).first()
    if not d:
        raise NotFoundError("公示记录不存在")
    d.status = "published"
    d.published_at = datetime.utcnow()
    d.published_by = published_by
    if expired_at:
        d.expired_at = expired_at
    db.commit()
    db.refresh(d)
    return d


def list_public_disclosures(
    db: Session, tenant_id: str,
    category: Optional[str] = None, status: Optional[str] = None,
    disclosed_level: Optional[str] = None,
    page: int = 1, page_size: int = 20,
) -> dict:
    """公示列表（租户隔离）。"""
    q = db.query(PublicDisclosure).filter(
        PublicDisclosure.tenant_id == tenant_id,
        PublicDisclosure.is_deleted == 0,
    )
    if category:
        q = q.filter(PublicDisclosure.category == category)
    if status:
        q = q.filter(PublicDisclosure.status == status)
    if disclosed_level:
        q = q.filter(PublicDisclosure.disclosed_level == disclosed_level)
    total = q.count()
    items = q.order_by(desc(PublicDisclosure.id)).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {
        "items": [_serialize_disclosure(d) for d in items],
        "total": total, "page": page, "page_size": page_size,
    }


def _serialize_disclosure(d: PublicDisclosure) -> dict:
    return {
        "id": d.id,
        "category": d.category,
        "title": d.title,
        "ref_type": d.ref_type,
        "ref_id": d.ref_id,
        "content": d.content or {},
        "disclosed_level": d.disclosed_level,
        "status": d.status,
        "published_at": d.published_at.strftime("%Y-%m-%d %H:%M:%S") if d.published_at else None,
        "expired_at": d.expired_at.strftime("%Y-%m-%d %H:%M:%S") if d.expired_at else None,
        "created_at": d.created_at.strftime("%Y-%m-%d %H:%M:%S") if d.created_at else None,
    }


# ──────────────────────────────────────────────
# 监管报送（Regulatory Submission）
# ──────────────────────────────────────────────

def build_submission_payload(
    db: Session, tenant_id: str,
    period_type: str, period_value: str, submission_type: str,
) -> dict:
    """根据周期与类型聚合监管报送数据包（结构化，便于对接外部监管平台）。"""
    if period_type == "year":
        year = int(period_value)
        start = date(year, 1, 1)
        end = date(year, 12, 31)
    elif period_type == "quarter":
        y, q = period_value.split("-Q")
        year, q = int(y), int(q)
        start_month = (q - 1) * 3 + 1
        start = date(year, start_month, 1)
        end_month = q * 3
        end_day = 31 if end_month in (3, 12) else (30 if end_month == 9 else 28)
        end = date(year, end_month, end_day)
    elif period_type == "month":
        y, m = period_value.split("-")
        year, m = int(y), int(m)
        start = date(year, m, 1)
        end_day = 31 if m in (1, 3, 5, 7, 8, 10, 12) else (30 if m != 2 else 28)
        end = date(year, m, end_day)
    else:
        raise ValueError(f"不支持的周期类型: {period_type}")

    start_dt = datetime(start.year, start.month, start.day)
    end_dt = datetime(end.year, end.month, end.day, 23, 59, 59)

    events = db.query(ComplianceViolationEvent).filter(
        ComplianceViolationEvent.tenant_id == tenant_id,
        ComplianceViolationEvent.is_deleted == 0,
        ComplianceViolationEvent.created_at >= start_dt,
        ComplianceViolationEvent.created_at <= end_dt,
    ).all()

    by_severity = {}
    by_status = {}
    for e in events:
        by_severity[e.severity] = by_severity.get(e.severity, 0) + 1
        by_status[e.status] = by_status.get(e.status, 0) + 1

    payload = {
        "tenant_id": tenant_id,
        "period_type": period_type,
        "period_value": period_value,
        "submission_type": submission_type,
        "generated_at": datetime.utcnow().isoformat(),
        "summary": {
            "violation_total": len(events),
            "by_severity": by_severity,
            "by_status": by_status,
        },
        "violations": [
            {
                "rule_article": e.rule_article,
                "rule_subject": e.rule_subject,
                "severity": e.severity,
                "actor_role": e.actor_role,
                "description": e.description,
                "status": e.status,
                "created_at": e.created_at.strftime("%Y-%m-%d %H:%M:%S") if e.created_at else None,
            }
            for e in events
        ],
    }
    return payload


def create_regulatory_submission(
    db: Session, tenant_id: str,
    period_type: str, period_value: str, submission_type: str,
    fmt: str = "json", submitted_by: Optional[int] = None,
) -> RegulatorySubmission:
    """生成（待报送）监管数据包并记录。"""
    payload = build_submission_payload(db, tenant_id, period_type, period_value, submission_type)
    sub = RegulatorySubmission(
        tenant_id=tenant_id,
        period_type=period_type,
        period_value=period_value,
        submission_type=submission_type,
        payload=payload,
        format=fmt,
        status="pending",
        submitted_by=submitted_by,
    )
    db.add(sub)
    db.flush()
    append_compliance_audit_log(
        db, tenant_id, submitted_by or 0, "compliance_officer",
        "regulatory_submission.create", "regulatory_submission", sub.id,
        {"period_type": period_type, "period_value": period_value,
         "submission_type": submission_type, "format": fmt},
    )
    db.commit()
    return sub


def list_regulatory_submissions(
    db: Session, tenant_id: str,
    period_type: Optional[str] = None, status: Optional[str] = None,
    page: int = 1, page_size: int = 20,
) -> dict:
    q = db.query(RegulatorySubmission).filter(
        RegulatorySubmission.tenant_id == tenant_id,
        RegulatorySubmission.is_deleted == 0,
    )
    if period_type:
        q = q.filter(RegulatorySubmission.period_type == period_type)
    if status:
        q = q.filter(RegulatorySubmission.status == status)
    total = q.count()
    items = q.order_by(desc(RegulatorySubmission.id)).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {
        "items": [
            {
                "id": s.id,
                "period_type": s.period_type,
                "period_value": s.period_value,
                "submission_type": s.submission_type,
                "format": s.format,
                "status": s.status,
                "submitted_at": s.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if s.submitted_at else None,
                "external_ref": s.external_ref,
                "created_at": s.created_at.strftime("%Y-%m-%d %H:%M:%S") if s.created_at else None,
            }
            for s in items
        ],
        "total": total, "page": page, "page_size": page_size,
    }


def mark_submission_submitted(
    db: Session, tenant_id: str, submission_id: int,
    external_ref: Optional[str] = None, submitted_by: Optional[int] = None,
) -> RegulatorySubmission:
    """标记监管数据包已报送（记录回执号）。"""
    s = db.query(RegulatorySubmission).filter(
        RegulatorySubmission.tenant_id == tenant_id,
        RegulatorySubmission.is_deleted == 0,
        RegulatorySubmission.id == submission_id,
    ).first()
    if not s:
        raise NotFoundError("报送记录不存在")
    s.status = "submitted"
    s.submitted_at = datetime.utcnow()
    s.submitted_by = submitted_by
    if external_ref:
        s.external_ref = external_ref
    db.commit()
    db.refresh(s)
    return s


def export_submission(submission: RegulatorySubmission, fmt: Optional[str] = None) -> dict:
    """把报送数据包序列化为可下载格式（json/csv）。"""
    from services.regulatory_adapter import SubmissionExporter
    out_fmt = (fmt or submission.format or "json").lower()
    content = SubmissionExporter.export(submission.payload or {}, out_fmt)
    return {
        "submission_id": submission.id,
        "format": out_fmt,
        "filename": f"regulatory_submission_{submission.period_value}_{submission.submission_type}.{out_fmt}",
        "content": content,
    }


def push_submission_external(
    db: Session, tenant_id: str, submission_id: int,
    submitted_by: Optional[int] = None,
) -> dict:
    """将报送数据包推送到外部监管平台（未配置端点则 dry-run）。

    成功/占位回执写入 RegulatorySubmission.external_ref 并标记 submitted。
    """
    from services.regulatory_adapter import ExternalRegulatoryClient
    s = db.query(RegulatorySubmission).filter(
        RegulatorySubmission.tenant_id == tenant_id,
        RegulatorySubmission.is_deleted == 0,
        RegulatorySubmission.id == submission_id,
    ).first()
    if not s:
        raise NotFoundError("报送记录不存在")
    client = ExternalRegulatoryClient()
    result = client.push(s.payload or {}, s.id)
    s.status = "submitted" if not client.dry_run else "pending"
    s.submitted_at = datetime.utcnow()
    s.submitted_by = submitted_by
    if result.get("external_ref"):
        s.external_ref = result["external_ref"]
    db.commit()
    db.refresh(s)
    return {
        "submission_id": s.id,
        "status": s.status,
        "external_ref": s.external_ref,
        "dry_run": result.get("dry_run", False),
        "detail": result.get("detail", ""),
    }


# ──────────────────────────────────────────────
# 年度合规审计（Annual Compliance Audit）
# ──────────────────────────────────────────────

def generate_annual_audit(
    db: Session, tenant_id: str, year: int,
    scope: Optional[str] = None, audit_by: Optional[int] = None,
) -> AnnualComplianceAudit:
    """基于全年证据链 + 违规记录 + 公示 生成年度合规审计聚合。"""
    start = datetime(year, 1, 1)
    end = datetime(year, 12, 31, 23, 59, 59)

    # 1) 证据链完整性（复用 GxP 链式哈希验证）
    chain = verify_audit_log_chain(db, tenant_id, limit=100000)

    # 2) 全年违规统计
    events = db.query(ComplianceViolationEvent).filter(
        ComplianceViolationEvent.tenant_id == tenant_id,
        ComplianceViolationEvent.is_deleted == 0,
        ComplianceViolationEvent.created_at >= start,
        ComplianceViolationEvent.created_at <= end,
    ).all()
    severity_counts = {}
    for e in events:
        severity_counts[e.severity] = severity_counts.get(e.severity, 0) + 1

    # 3) 全年公示统计
    disclosures = db.query(PublicDisclosure).filter(
        PublicDisclosure.tenant_id == tenant_id,
        PublicDisclosure.is_deleted == 0,
        PublicDisclosure.created_at >= start,
        PublicDisclosure.created_at <= end,
    ).all()
    published_count = sum(1 for d in disclosures if d.status == "published")

    # 4) 合规关键操作计数
    crit_count = db.query(func.count(AuditLog.id)).filter(
        AuditLog.tenant_id == tenant_id,
        AuditLog.is_deleted == 0,
        AuditLog.is_compliance_critical == 1,
        AuditLog.ts >= start,
        AuditLog.ts <= end,
    ).scalar() or 0

    metrics = {
        "violation_total": len(events),
        "violation_by_severity": severity_counts,
        "disclosure_total": len(disclosures),
        "disclosure_published": published_count,
        "compliance_critical_actions": crit_count,
    }

    # 审计结论：证据链完整且无严重未处置违规 → pass；链完整但有违规 → conditional；链断裂 → fail
    chain_ok = chain.get("verified", 0) == chain.get("total", 0) and not chain.get("tampered")
    unresolved_critical = sum(1 for e in events if e.severity in ("RED", "severe") and e.status != "resolved")
    if not chain_ok:
        conclusion = "fail"
    elif unresolved_critical > 0:
        conclusion = "conditional"
    else:
        conclusion = "pass"

    audit = db.query(AnnualComplianceAudit).filter(
        AnnualComplianceAudit.tenant_id == tenant_id,
        AnnualComplianceAudit.is_deleted == 0,
        AnnualComplianceAudit.year == year,
    ).first()
    if not audit:
        audit = AnnualComplianceAudit(tenant_id=tenant_id, year=year)
        db.add(audit)

    audit.scope = scope or f"{year} 年度合规审计（违规处置 + 公示 + 全过程留痕证据链）"
    audit.metrics = metrics
    audit.chain_integrity = {
        "total": chain.get("total", 0),
        "verified": chain.get("verified", 0),
        "tampered": chain.get("tampered", []),
    }
    audit.conclusion = conclusion
    audit.audit_by = audit_by
    audit.audited_at = datetime.utcnow()
    db.commit()
    db.refresh(audit)
    return audit


def list_annual_audits(
    db: Session, tenant_id: str, page: int = 1, page_size: int = 20,
) -> dict:
    q = db.query(AnnualComplianceAudit).filter(
        AnnualComplianceAudit.tenant_id == tenant_id,
        AnnualComplianceAudit.is_deleted == 0,
    )
    total = q.count()
    items = q.order_by(desc(AnnualComplianceAudit.year)).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {
        "items": [
            {
                "id": a.id,
                "year": a.year,
                "scope": a.scope,
                "metrics": a.metrics or {},
                "chain_integrity": a.chain_integrity or {},
                "conclusion": a.conclusion,
                "audited_at": a.audited_at.strftime("%Y-%m-%d %H:%M:%S") if a.audited_at else None,
            }
            for a in items
        ],
        "total": total, "page": page, "page_size": page_size,
    }
