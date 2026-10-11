"""合规稽查包 — 将活动/违规/备案相关证据打包为可导出结构。

面向稽查/内审：一次导出即可回答「依据哪条、谁确认、关联哪场活动」。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def build_audit_pack(
    db: Session,
    tenant_id: str,
    *,
    activity_id: Optional[int] = None,
    violation_event_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> dict[str, Any]:
    """组装稽查包 dict（可 JSON 下载）。"""
    from database import (
        AcademicActivity,
        AuditLog,
        ComplianceViolationEvent,
        ComplianceCommitment,
        PharmaRepProfile,
    )

    pack: dict[str, Any] = {
        "pack_version": "1.0",
        "tenant_id": tenant_id,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "scope": {},
        "activity": None,
        "streams": {"protocol": None, "checkin": [], "expense": []},
        "violation_events": [],
        "rep_profile": None,
        "commitments": [],
        "audit_logs": [],
        "summary": [],
    }

    if activity_id:
        pack["scope"]["activity_id"] = activity_id
        act = db.query(AcademicActivity).filter(
            AcademicActivity.tenant_id == tenant_id,
            AcademicActivity.is_deleted == 0,
            AcademicActivity.id == activity_id,
        ).first()
        if act:
            from services.academic_activity_service import _serialize_activity
            pack["activity"] = _serialize_activity(act)
            pack["streams"]["protocol"] = act.meeting_protocol or {}
            pack["streams"]["checkin"] = act.checkin_evidence or []
            pack["streams"]["expense"] = act.expense_vouchers or []
            pack["summary"].append(
                f"活动#{act.id}「{act.title}」状态={act.status}，"
                f"签到{(len(act.checkin_evidence or []))}条，"
                f"费用{(len(act.expense_vouchers or []))}条，"
                f"违规计数={act.violation_count}"
            )
            if user_id is None:
                user_id = act.pharma_rep_user_id

            # 关联违规事件
            events = db.query(ComplianceViolationEvent).filter(
                ComplianceViolationEvent.tenant_id == tenant_id,
                ComplianceViolationEvent.is_deleted == 0,
                ComplianceViolationEvent.entity_type == "academic_activity",
                ComplianceViolationEvent.entity_id == activity_id,
            ).order_by(ComplianceViolationEvent.id.desc()).limit(50).all()
            pack["violation_events"] = [_ser_violation(e) for e in events]

    if violation_event_id:
        pack["scope"]["violation_event_id"] = violation_event_id
        ev = db.query(ComplianceViolationEvent).filter(
            ComplianceViolationEvent.tenant_id == tenant_id,
            ComplianceViolationEvent.is_deleted == 0,
            ComplianceViolationEvent.id == violation_event_id,
        ).first()
        if ev:
            pack["violation_events"] = [_ser_violation(ev)]
            pack["summary"].append(
                f"违规事件#{ev.id} severity={ev.severity} status={ev.status} "
                f"rule={ev.rule_code}"
            )
            if user_id is None and ev.actor_id:
                user_id = ev.actor_id
            # 若关联学术活动，附带活动
            if ev.entity_type == "academic_activity" and ev.entity_id and not pack["activity"]:
                return build_audit_pack(
                    db, tenant_id,
                    activity_id=ev.entity_id,
                    violation_event_id=violation_event_id,
                    user_id=user_id,
                )

    if user_id:
        pack["scope"]["user_id"] = user_id
        profile = db.query(PharmaRepProfile).filter(
            PharmaRepProfile.tenant_id == tenant_id,
            PharmaRepProfile.is_deleted == 0,
            PharmaRepProfile.user_id == user_id,
        ).first()
        if profile:
            pack["rep_profile"] = {
                "user_id": profile.user_id,
                "registration_no": profile.registration_no,
                "registration_status": profile.registration_status,
                "authorized_regions": profile.authorized_regions or [],
                "education_level": profile.education_level,
                "major": profile.major,
            }
            pack["summary"].append(
                f"代表 user_id={user_id} 备案号={pack['rep_profile'].get('registration_no')}"
            )

        commits = db.query(ComplianceCommitment).filter(
            ComplianceCommitment.tenant_id == tenant_id,
            ComplianceCommitment.is_deleted == 0,
            ComplianceCommitment.user_id == user_id,
        ).order_by(ComplianceCommitment.id.desc()).limit(10).all()
        pack["commitments"] = [
            {
                "id": c.id,
                "commitment_type": getattr(c, "commitment_type", None),
                "version": getattr(c, "version", None),
                "signed_at": c.signed_at.strftime("%Y-%m-%d %H:%M:%S") if getattr(c, "signed_at", None) else None,
            }
            for c in commits
        ]

    # 近期关键审计日志（租户级抽样）
    q = db.query(AuditLog).filter(
        AuditLog.tenant_id == tenant_id,
        AuditLog.is_deleted == 0,
    )
    if activity_id:
        try:
            logs = q.order_by(AuditLog.id.desc()).limit(80).all()
            filtered = []
            for log in logs:
                blob = json.dumps({
                    "action": log.action,
                    "target": log.target,
                    "target_id": log.target_id,
                    "detail": log.detail,
                }, ensure_ascii=False, default=str)
                if (
                    str(activity_id) in blob
                    or "academic" in blob.lower()
                    or "compliance" in blob.lower()
                    or bool(log.is_compliance_critical)
                ):
                    filtered.append(log)
                if len(filtered) >= 30:
                    break
            logs = filtered
        except Exception:
            logs = q.order_by(AuditLog.id.desc()).limit(20).all()
    else:
        logs = q.filter(AuditLog.is_compliance_critical == 1).order_by(
            AuditLog.id.desc()
        ).limit(20).all()
        if not logs:
            logs = q.order_by(AuditLog.id.desc()).limit(20).all()

    pack["audit_logs"] = [
        {
            "id": log.id,
            "action": log.action,
            "target": log.target,
            "target_id": log.target_id,
            "actor_id": log.actor_id,
            "actor_role": log.actor_role,
            "record_hash": log.record_hash,
            "prev_hash": log.prev_hash,
            "is_compliance_critical": bool(log.is_compliance_critical),
            "ts": log.ts.strftime("%Y-%m-%d %H:%M:%S") if log.ts else None,
        }
        for log in logs
    ]

    if not pack["summary"]:
        pack["summary"].append("未匹配到活动/违规主体；仅导出近期审计日志抽样")

    pack["integrity_note"] = (
        "本包为系统生成的稽查证据快照。链式 AuditLog 的 record_hash/prev_hash "
        "可用于完整性核验；外发前请由合规官复核。"
    )
    return pack


def _ser_violation(e) -> dict:
    return {
        "id": e.id,
        "rule_code": e.rule_code,
        "rule_article": e.rule_article,
        "rule_subject": e.rule_subject,
        "severity": e.severity,
        "status": e.status,
        "entity_type": e.entity_type,
        "entity_id": e.entity_id,
        "actor_id": e.actor_id,
        "actor_role": e.actor_role,
        "description": e.description,
        "evidence_payload": e.evidence_payload or {},
        "handling_result": e.handling_result,
        "created_at": e.created_at.strftime("%Y-%m-%d %H:%M:%S") if e.created_at else None,
    }


__all__ = ["build_audit_pack"]
