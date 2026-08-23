"""学术推广活动服务层（v2.2 Phase 2）

对应《医药代表管理办法》第 19-22 条学术推广活动管理 + 第 21 条传递信息/协助合理用药/收集反馈。
全生命周期：立项→审批→协议→签到→费用→反馈→归档

合规要点：
- 学术活动发起前必须通过 check_onboarding_gate（上岗三件套校验）
- 关键节点（立项/审批/签到/费用）触发 22 项禁止行为规则校验
- 所有写入操作同步追加链式 AuditLog
"""
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from core.exceptions import NotFoundError, ValidationError
from database import AcademicActivity, PartnerOrganization, AuthorizationLetter, ManagementAgreement
from services import compliance_service
from services.compliance_service import (
    check_onboarding_gate,
    check_violations,
    SCENE_ACTIVITY_CREATE,
    SCENE_ACTIVITY_CHECKIN,
    SCENE_ACTIVITY_EXPENSE,
    append_compliance_audit_log,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 学术活动 CRUD + 全生命周期
# ──────────────────────────────────────────────

def list_activities(
    db: Session, tenant_id: str,
    status: str = None, activity_type: str = None,
    pharma_rep_user_id: int = None,
    page: int = 1, page_size: int = 20,
) -> dict:
    """学术活动列表"""
    q = db.query(AcademicActivity).filter(
        AcademicActivity.tenant_id == tenant_id,
        AcademicActivity.is_deleted == 0,
    )
    if status:
        q = q.filter(AcademicActivity.status == status)
    if activity_type:
        q = q.filter(AcademicActivity.activity_type == activity_type)
    if pharma_rep_user_id:
        q = q.filter(AcademicActivity.pharma_rep_user_id == pharma_rep_user_id)
    total = q.count()
    items = q.order_by(AcademicActivity.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {
        "items": [_serialize_activity(a) for a in items],
        "total": total, "page": page, "page_size": page_size,
    }


def get_activity(db: Session, tenant_id: str, activity_id: int) -> dict:
    """学术活动详情"""
    a = _get_or_raise(db, tenant_id, activity_id)
    return _serialize_activity(a)


def create_activity(db: Session, tenant_id: str, user_id: int, user_role: str, data: dict) -> dict:
    """立项：创建学术活动

    合规校验：
    1. 医药代表发起前必须通过上岗三件套校验（第 9、10 条）
    2. 触发 SCENE_ACTIVITY_CREATE 场景的 22 项规则校验
    """
    if not data.get("title"):
        raise ValidationError("title 不能为空")
    if not data.get("activity_type"):
        raise ValidationError("activity_type 不能为空")

    pharma_rep_user_id = data.get("pharma_rep_user_id") or user_id

    # 上岗准入校验：医药代表必须完成三件套
    check_onboarding_gate(db, tenant_id, pharma_rep_user_id, raise_on_fail=True)

    # 运行时规则校验
    violations = check_violations(
        db, tenant_id, SCENE_ACTIVITY_CREATE,
        context={
            "title": data.get("title", ""),
            "text": data.get("description", "") + " " + " ".join(data.get("agenda") or []),
            "action": "create_activity",
            "role": user_role,
        },
        actor_id=user_id,
        actor_role=user_role,
        entity_type="academic_activity",
    )
    if violations:
        # 高严重度违规直接拒绝立项
        critical = [v for v in violations if v["severity"] == "critical"]
        if critical:
            raise ValidationError(
                f"学术活动立项触发 critical 违规：{critical[0]['rule_code']} "
                f"{critical[0]['description']}（对应第 11/24 条）"
            )

    activity = AcademicActivity(
        tenant_id=tenant_id,
        title=data["title"],
        activity_type=data["activity_type"],
        organizer_id=data.get("organizer_id"),
        co_organizers=data.get("co_organizers") or [],
        planned_at=data.get("planned_at"),
        location=data.get("location"),
        province=data.get("province"),
        city=data.get("city"),
        target_audience=data.get("target_audience"),
        expected_attendees=data.get("expected_attendees", 0),
        pharma_rep_user_id=pharma_rep_user_id,
        partner_org_id=data.get("partner_org_id"),
        agreement_id=data.get("agreement_id"),
        authorization_letter_id=data.get("authorization_letter_id"),
        product_ids=data.get("product_ids") or [],
        therapeutic_areas=data.get("therapeutic_areas") or [],
        agenda=data.get("agenda") or [],
        materials=data.get("materials") or [],
        status="draft",
        current_step="step1_create",
        gates_passed=["G1"],
        onboarding_checked=1,
        violation_count=len(violations),
    )
    db.add(activity)
    db.flush()
    # 写入审计日志
    append_compliance_audit_log(
        db, tenant_id, user_id, user_role,
        action="academic_activity.create",
        target="academic_activity",
        target_id=activity.id,
        detail={
            "title": activity.title, "activity_type": activity.activity_type,
            "violations": violations,
        },
        is_compliance_critical=1,
    )
    db.commit()
    db.refresh(activity)
    return _serialize_activity(activity)


def approve_activity(db: Session, tenant_id: str, activity_id: int,
                     approver_id: int, approver_role: str,
                     approval_id: int = None, comment: str = None) -> dict:
    """审批通过：从 draft 推进到 approved 状态"""
    a = _get_or_raise(db, tenant_id, activity_id)
    if a.status not in ("draft", "pending_approval"):
        raise ValidationError(f"当前状态 {a.status} 不允许审批")
    a.status = "approved"
    a.approval_id = approval_id
    a.current_step = "step2_approved"
    a.gates_passed = (a.gates_passed or []) + ["G2"]
    append_compliance_audit_log(
        db, tenant_id, approver_id, approver_role,
        action="academic_activity.approve",
        target="academic_activity", target_id=a.id,
        detail={"approval_id": approval_id, "comment": comment},
        is_compliance_critical=1,
    )
    db.commit()
    db.refresh(a)
    return _serialize_activity(a)


def attach_protocol(db: Session, tenant_id: str, activity_id: int,
                    user_id: int, user_role: str,
                    protocol: dict) -> dict:
    """附加会议协议（第 21 条三流合一：协议流）"""
    a = _get_or_raise(db, tenant_id, activity_id)
    if a.status != "approved":
        raise ValidationError(f"当前状态 {a.status} 不允许附加协议")
    if not protocol.get("protocol_no"):
        raise ValidationError("protocol.protocol_no 不能为空")
    a.meeting_protocol = protocol
    a.current_step = "step3_protocol"
    a.gates_passed = (a.gates_passed or []) + ["G3"]
    append_compliance_audit_log(
        db, tenant_id, user_id, user_role,
        action="academic_activity.attach_protocol",
        target="academic_activity", target_id=a.id,
        detail={"protocol_no": protocol.get("protocol_no")},
    )
    db.commit()
    db.refresh(a)
    return _serialize_activity(a)


def checkin(db: Session, tenant_id: str, activity_id: int,
            user_id: int, user_role: str,
            checkin_evidence: dict) -> dict:
    """现场签到（第 21 条三流合一：签到流）

    合规校验：触发 SCENE_ACTIVITY_CHECKIN 场景的 22 项规则
    """
    a = _get_or_raise(db, tenant_id, activity_id)
    if a.status not in ("approved", "ongoing"):
        raise ValidationError(f"当前状态 {a.status} 不允许签到")

    # 运行时规则校验
    violations = check_violations(
        db, tenant_id, SCENE_ACTIVITY_CHECKIN,
        context={
            "text": str(checkin_evidence),
            "action": "checkin",
            "role": user_role,
        },
        actor_id=user_id, actor_role=user_role,
        entity_type="academic_activity", entity_id=a.id,
    )
    if any(v["severity"] == "critical" for v in violations):
        raise ValidationError("签到触发 critical 违规，禁止完成签到")

    existing = list(a.checkin_evidence or [])
    existing.append({
        **checkin_evidence,
        "checked_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "checked_by": user_id,
    })
    a.checkin_evidence = existing
    a.actual_attendees = len(existing)
    a.status = "ongoing"
    a.current_step = "step4_checkin"
    a.gates_passed = (a.gates_passed or []) + ["G4"]
    a.violation_count = (a.violation_count or 0) + len(violations)
    append_compliance_audit_log(
        db, tenant_id, user_id, user_role,
        action="academic_activity.checkin",
        target="academic_activity", target_id=a.id,
        detail={"actual_attendees": a.actual_attendees, "violations": violations},
        is_compliance_critical=1,
    )
    db.commit()
    db.refresh(a)
    return _serialize_activity(a)


def submit_expense(db: Session, tenant_id: str, activity_id: int,
                   user_id: int, user_role: str,
                   expense_voucher: dict) -> dict:
    """费用核销（第 21 条三流合一：费用流）

    合规校验：触发 SCENE_ACTIVITY_EXPENSE 场景的 22 项规则
    """
    a = _get_or_raise(db, tenant_id, activity_id)
    if a.status not in ("ongoing", "completed"):
        raise ValidationError(f"当前状态 {a.status} 不允许费用核销")

    if not expense_voucher.get("amount"):
        raise ValidationError("expense_voucher.amount 不能为空")

    # 运行时规则校验
    violations = check_violations(
        db, tenant_id, SCENE_ACTIVITY_EXPENSE,
        context={
            "text": str(expense_voucher),
            "action": "submit_expense",
            "amount": expense_voucher.get("amount", 0),
            "role": user_role,
        },
        actor_id=user_id, actor_role=user_role,
        entity_type="academic_activity", entity_id=a.id,
    )
    if any(v["severity"] == "critical" for v in violations):
        raise ValidationError("费用核销触发 critical 违规，禁止提交")

    existing = list(a.expense_vouchers or [])
    existing.append({
        **expense_voucher,
        "submitted_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "submitted_by": user_id,
    })
    a.expense_vouchers = existing
    a.total_expense = (a.total_expense or 0) + int(expense_voucher.get("amount", 0))
    a.current_step = "step5_expense"
    a.gates_passed = (a.gates_passed or []) + ["G5"]
    a.violation_count = (a.violation_count or 0) + len(violations)
    append_compliance_audit_log(
        db, tenant_id, user_id, user_role,
        action="academic_activity.expense",
        target="academic_activity", target_id=a.id,
        detail={
            "amount": expense_voucher.get("amount"),
            "total_expense": a.total_expense,
            "violations": violations,
        },
        is_compliance_critical=1,
    )
    db.commit()
    db.refresh(a)
    return _serialize_activity(a)


def submit_feedback(db: Session, tenant_id: str, activity_id: int,
                    user_id: int, user_role: str,
                    feedback: str, adverse_reactions: list = None) -> dict:
    """提交反馈（第 21 条第（三）项：收集不良反应反馈）"""
    a = _get_or_raise(db, tenant_id, activity_id)
    a.feedback_summary = feedback
    if adverse_reactions:
        existing = list(a.adverse_reaction_reported or [])
        for ar in adverse_reactions:
            ar.setdefault("reported_at", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
            existing.append(ar)
        a.adverse_reaction_reported = existing
    a.status = "completed"
    a.ended_at = datetime.utcnow()
    a.current_step = "step6_feedback"
    a.gates_passed = (a.gates_passed or []) + ["G6"]
    append_compliance_audit_log(
        db, tenant_id, user_id, user_role,
        action="academic_activity.feedback",
        target="academic_activity", target_id=a.id,
        detail={"adverse_reactions_count": len(adverse_reactions or [])},
        is_compliance_critical=1 if adverse_reactions else 0,
    )
    db.commit()
    db.refresh(a)
    return _serialize_activity(a)


def archive_activity(db: Session, tenant_id: str, activity_id: int,
                     user_id: int, user_role: str) -> dict:
    """归档：完成全生命周期"""
    a = _get_or_raise(db, tenant_id, activity_id)
    if a.status != "completed":
        raise ValidationError(f"当前状态 {a.status} 不允许归档")
    a.status = "archived"
    a.current_step = "step7_archived"
    a.gates_passed = (a.gates_passed or []) + ["G7"]
    append_compliance_audit_log(
        db, tenant_id, user_id, user_role,
        action="academic_activity.archive",
        target="academic_activity", target_id=a.id,
        detail={"final_violation_count": a.violation_count},
    )
    db.commit()
    db.refresh(a)
    return _serialize_activity(a)


def cancel_activity(db: Session, tenant_id: str, activity_id: int,
                    user_id: int, user_role: str, reason: str) -> dict:
    """取消学术活动"""
    a = _get_or_raise(db, tenant_id, activity_id)
    a.status = "cancelled"
    append_compliance_audit_log(
        db, tenant_id, user_id, user_role,
        action="academic_activity.cancel",
        target="academic_activity", target_id=a.id,
        detail={"reason": reason},
    )
    db.commit()
    db.refresh(a)
    return _serialize_activity(a)


# ──────────────────────────────────────────────
# 内部辅助
# ──────────────────────────────────────────────

def _get_or_raise(db: Session, tenant_id: str, activity_id: int) -> AcademicActivity:
    a = db.query(AcademicActivity).filter(
        AcademicActivity.tenant_id == tenant_id,
        AcademicActivity.is_deleted == 0,
        AcademicActivity.id == activity_id,
    ).first()
    if not a:
        raise NotFoundError("学术活动不存在")
    return a


def _serialize_activity(a: AcademicActivity) -> dict:
    return {
        "id": a.id,
        "title": a.title,
        "activity_type": a.activity_type,
        "organizer_id": a.organizer_id,
        "co_organizers": a.co_organizers or [],
        "planned_at": a.planned_at.strftime("%Y-%m-%d %H:%M:%S") if a.planned_at else None,
        "ended_at": a.ended_at.strftime("%Y-%m-%d %H:%M:%S") if a.ended_at else None,
        "location": a.location,
        "province": a.province,
        "city": a.city,
        "target_audience": a.target_audience,
        "expected_attendees": a.expected_attendees,
        "actual_attendees": a.actual_attendees,
        "pharma_rep_user_id": a.pharma_rep_user_id,
        "partner_org_id": a.partner_org_id,
        "agreement_id": a.agreement_id,
        "authorization_letter_id": a.authorization_letter_id,
        "meeting_id": a.meeting_id,
        "approval_id": a.approval_id,
        "product_ids": a.product_ids or [],
        "therapeutic_areas": a.therapeutic_areas or [],
        "agenda": a.agenda or [],
        "materials": a.materials or [],
        "meeting_protocol": a.meeting_protocol or {},
        "checkin_evidence": a.checkin_evidence or [],
        "expense_vouchers": a.expense_vouchers or [],
        "adverse_reaction_reported": a.adverse_reaction_reported or [],
        "feedback_summary": a.feedback_summary,
        "status": a.status,
        "current_step": a.current_step,
        "gates_passed": a.gates_passed or [],
        "onboarding_checked": bool(a.onboarding_checked),
        "violation_count": a.violation_count,
        "total_expense": a.total_expense,
        "created_at": a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else None,
    }
