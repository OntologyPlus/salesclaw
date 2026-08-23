"""合规管理服务层（v2.1 合规适配，对应《医药代表管理办法》2026-08-01 施行）

提供以下能力：
1. 医药代表资质档案管理（第 14-18 条备案管理）
2. 合规承诺书签署闭环（第 9、10、15 条培训考核承诺）
3. 链式证据 AuditLog（第 26 条全过程留痕 + 不可篡改证据链）
4. 22 项禁止行为规则校验（第 11、12、24、25 条）
5. 30 日时效检查（第 17 条备案信息变更/停止授权 30 日内）
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta, date
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import (
    PharmaRepProfile, ComplianceCommitment, AuditLog,
    Course, CourseEnrollment, ExamRecord, User, Role,
)
from core.exceptions import NotFoundError, ValidationError, DataConflictError

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 常量定义
# ──────────────────────────────────────────────

# 医药代表角色代码（与 Role.code 对齐）
PHARMA_REP_ROLE_CODE = "pharma_rep"

# 医药代表备案状态
REGISTRATION_STATUS = {
    "draft": "草稿",
    "submitted": "已提交备案平台",
    "confirmed": "备案平台已确认",
    "revoked": "已撤销",
    "deleted": "已删除",
}

# 合规承诺书类型
COMMITMENT_TYPE = {
    "onboarding": "上岗承诺",
    "annual": "年度承诺",
    "specific": "专项承诺",
}

# 22 项禁止行为清单（对应第 11、12、24、25 条）
# 规则代码 = 条款号 + 序号，例如 A11_3 = 第 11 条第（三）项
FORBIDDEN_BEHAVIORS = [
    # 第 11 条 持有人 4 项
    {"code": "A11_1", "article": "第十一条第（一）项", "subject": "持有人",
     "description": "聘用或者授权不符合条件的、存在商业贿赂记录的医药代表"},
    {"code": "A11_2", "article": "第十一条第（二）项", "subject": "持有人",
     "description": "指使、纵容医药代表从事违法行为"},
    {"code": "A11_3", "article": "第十一条第（三）项", "subject": "持有人",
     "description": "向医药代表分配药品销售任务，要求医药代表实施收款和处理购销票据等销售行为"},
    {"code": "A11_4", "article": "第十一条第（四）项", "subject": "持有人",
     "description": "法律、行政法规禁止的其他行为"},
    # 第 12 条 CSO 4 项
    {"code": "A12_1", "article": "第十二条第（一）项", "subject": "CSO",
     "description": "聘用不符合条件的、存在商业贿赂记录的医药代表"},
    {"code": "A12_2", "article": "第十二条第（二）项", "subject": "CSO",
     "description": "指使、纵容医药代表进行商业贿赂、诈骗等违法犯罪行为"},
    {"code": "A12_3", "article": "第十二条第（三）项", "subject": "CSO",
     "description": "指使、纵容医药代表违规开展药品学术推广活动"},
    {"code": "A12_4", "article": "第十二条第（四）项", "subject": "CSO",
     "description": "法律、行政法规禁止的其他行为"},
    # 第 24 条 医药代表 9 项
    {"code": "A24_1", "article": "第二十四条第（一）项", "subject": "医药代表",
     "description": "未经备案、登记从事药品学术推广活动"},
    {"code": "A24_2", "article": "第二十四条第（二）项", "subject": "医药代表",
     "description": "未经医疗卫生机构同意开展药品学术推广活动"},
    {"code": "A24_3", "article": "第二十四条第（三）项", "subject": "医药代表",
     "description": "承担药品销售任务，实施收款和处理购销票据等销售行为"},
    {"code": "A24_4", "article": "第二十四条第（四）项", "subject": "医药代表",
     "description": "参与统计或者委托医疗卫生机构工作人员等统计医生个人开具的药品处方数量"},
    {"code": "A24_5", "article": "第二十四条第（五）项", "subject": "医药代表",
     "description": "以附加销售条件提供捐赠、资助、赞助，或给予礼品、礼金、消费卡、有价证券、股权等"},
    {"code": "A24_6", "article": "第二十四条第（六）项", "subject": "医药代表",
     "description": "给予回扣、利益输送（含亲属/特定关系人）"},
    {"code": "A24_7", "article": "第二十四条第（七）项", "subject": "医药代表",
     "description": "误导用药、夸大疗效、隐匿不良反应信息"},
    {"code": "A24_8", "article": "第二十四条第（八）项", "subject": "医药代表",
     "description": "非法收集、使用和传播患者信息以及医疗卫生机构内部信息"},
    {"code": "A24_9", "article": "第二十四条第（九）项", "subject": "医药代表",
     "description": "实施药品上市许可持有人授权之外药品的学术推广活动"},
    # 第 25 条 医疗机构 5 项（部分适用于药企侧自查）
    {"code": "A25_1", "article": "第二十五条第（一）项", "subject": "医疗机构",
     "description": "与未经备案、登记的医药代表开展药品学术推广活动"},
    {"code": "A25_2", "article": "第二十五条第（二）项", "subject": "医疗机构",
     "description": "违反规定统计药品使用量"},
    {"code": "A25_3", "article": "第二十五条第（三）项", "subject": "医疗机构",
     "description": "接受附加销售条件的捐赠/资助/赞助，或礼品/礼金/有价证券等"},
    {"code": "A25_4", "article": "第二十五条第（四）项", "subject": "医疗机构",
     "description": "工作人员接受回扣/利益输送，参加医药代表安排的宴请/旅游/健身/娱乐等"},
    {"code": "A25_5", "article": "第二十五条第（五）项", "subject": "医疗机构",
     "description": "法律、行政法规禁止的其他行为"},
]

# 对医药代表角色硬性屏蔽的工具清单（对应 A11_3 / A24_3 禁止行为）
# 这些工具本质属于"销售任务"范畴，医药代表角色不得调用
FORBIDDEN_TOOLS_FOR_PHARMA_REP = {
    "compute_roi",           # ROI 计算 = 销售指标
    "compute_kpi",           # KPI 看板 = 销售指标
    "compute_coverage_gap",  # 覆盖空白 = 销售覆盖任务
    # 行为积分相关（销售激励）
    "list_behavior_point_rules",
    "create_behavior_point_record",
    "list_instruction_point_rules",
    "create_instruction_point_record",
}


# ──────────────────────────────────────────────
# 链式证据 AuditLog
# ──────────────────────────────────────────────

def _compute_record_hash(payload: dict, prev_hash: Optional[str]) -> str:
    """计算 AuditLog 记录的 SHA-256 哈希

    hash = SHA-256(prev_hash || actor_id || action || target || target_id || ts || detail_json)
    """
    raw = json.dumps({
        "prev_hash": prev_hash,
        "actor_id": payload.get("actor_id"),
        "action": payload.get("action"),
        "target": payload.get("target"),
        "target_id": payload.get("target_id"),
        "ts": payload.get("ts"),
        "detail": payload.get("detail") or {},
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def append_compliance_audit_log(
    db: Session,
    tenant_id: str,
    actor_id: int,
    actor_role: str,
    action: str,
    target: str,
    target_id: Optional[int],
    detail: dict,
    is_compliance_critical: bool = True,
) -> AuditLog:
    """追加合规关键审计日志（自动构造链式哈希）

    对应《医药代表管理办法》第 26 条全过程留痕 + 不可篡改证据链。

    Args:
        actor_role: 操作者角色（pharma_rep / sales_manager / compliance_officer 等）
        action: 操作类型（如 pharma_rep.register / commitment.sign）
        target: 目标对象类型（如 pharma_rep_profile / compliance_commitment）
        target_id: 目标对象 ID
        detail: 详情（JSON）
        is_compliance_critical: 是否合规关键操作（默认 True）
    """
    # 取上一条 AuditLog 的 hash 作为 prev_hash
    last_log = db.query(AuditLog).filter(
        AuditLog.tenant_id == tenant_id,
        AuditLog.is_deleted == 0,
    ).order_by(desc(AuditLog.id)).first()

    prev_hash = last_log.record_hash if last_log else None
    ts = datetime.utcnow()

    payload = {
        "actor_id": actor_id,
        "action": action,
        "target": target,
        "target_id": target_id,
        "ts": ts.isoformat(),
        "detail": detail,
    }
    record_hash = _compute_record_hash(payload, prev_hash)

    log = AuditLog(
        tenant_id=tenant_id,
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        target=target,
        target_id=target_id,
        detail=detail,
        ts=ts,
        prev_hash=prev_hash,
        record_hash=record_hash,
        is_compliance_critical=1 if is_compliance_critical else 0,
    )
    db.add(log)
    db.flush()
    return log


def verify_audit_log_chain(db: Session, tenant_id: str, limit: int = 100) -> dict:
    """验证 AuditLog 链式证据完整性

    逐条重算 record_hash，与存储的 hash 比对，识别被篡改的记录。

    Returns:
        {"total": N, "verified": M, "tampered": [...], "broken_chain": [...]}
    """
    logs = db.query(AuditLog).filter(
        AuditLog.tenant_id == tenant_id,
        AuditLog.is_deleted == 0,
        AuditLog.record_hash.isnot(None),
    ).order_by(AuditLog.id).limit(limit).all()

    verified = 0
    tampered = []
    broken_chain = []
    expected_prev = None

    for log in logs:
        # 链式连续性检查
        if log.prev_hash != expected_prev:
            broken_chain.append({
                "log_id": log.id,
                "expected_prev": expected_prev,
                "actual_prev": log.prev_hash,
            })

        # 重新计算 hash
        payload = {
            "actor_id": log.actor_id,
            "action": log.action,
            "target": log.target,
            "target_id": log.target_id,
            "ts": log.ts.isoformat() if log.ts else None,
            "detail": log.detail or {},
        }
        recomputed = _compute_record_hash(payload, log.prev_hash)

        if recomputed == log.record_hash:
            verified += 1
        else:
            tampered.append({
                "log_id": log.id,
                "stored_hash": log.record_hash,
                "recomputed_hash": recomputed,
            })

        expected_prev = log.record_hash

    return {
        "total": len(logs),
        "verified": verified,
        "tampered_count": len(tampered),
        "broken_chain_count": len(broken_chain),
        "tampered": tampered[:10],
        "broken_chain": broken_chain[:10],
    }


# ──────────────────────────────────────────────
# 医药代表资质档案管理（第 14-18 条备案管理）
# ──────────────────────────────────────────────

def get_profile(db: Session, tenant_id: str, user_id: int) -> Optional[PharmaRepProfile]:
    """只读查询资质档案（不落库；GET 路径请用本函数，避免读请求抢写锁）"""
    return db.query(PharmaRepProfile).filter(
        PharmaRepProfile.tenant_id == tenant_id,
        PharmaRepProfile.is_deleted == 0,
        PharmaRepProfile.user_id == user_id,
    ).first()


def get_or_create_profile(db: Session, tenant_id: str, user_id: int) -> PharmaRepProfile:
    """获取或创建医药代表资质档案（仅限写路径使用）"""
    profile = db.query(PharmaRepProfile).filter(
        PharmaRepProfile.tenant_id == tenant_id,
        PharmaRepProfile.is_deleted == 0,
        PharmaRepProfile.user_id == user_id,
    ).first()
    if not profile:
        profile = PharmaRepProfile(
            tenant_id=tenant_id,
            user_id=user_id,
            registration_status="draft",
        )
        db.add(profile)
        db.flush()
    return profile


def update_profile(db: Session, tenant_id: str, user_id: int, actor_id: int, actor_role: str, data: dict) -> dict:
    """更新医药代表资质档案（触发 30 日变更时效预警）

    对应第 17 条：医药代表已备案的信息有变更的，药品上市许可持有人应当在 30 日内完成备案信息变更。
    """
    profile = get_or_create_profile(db, tenant_id, user_id)

    # 可更新字段白名单
    updatable_fields = [
        "id_card_type", "id_card_no", "gender", "photo_url",
        "education_level", "major",
        "contract_start", "contract_end",
        "drug_categories", "therapeutic_areas", "authorized_regions",
        "authenticity_statement",
        "has_bribery_record", "bribery_record_detail",
    ]
    updated = []
    for field in updatable_fields:
        if field in data:
            old_val = getattr(profile, field)
            new_val = data[field]
            if old_val != new_val:
                setattr(profile, field, new_val)
                updated.append(field)

    if updated:
        profile.last_change_at = datetime.utcnow()
        # 若已备案（submitted 状态），需在 30 日内重新提交变更
        # 对应第 17 条：信息变更 30 日内完成
        if profile.registration_status == "submitted":
            profile.registration_status = "pending_change"

        # 写入审计日志
        append_compliance_audit_log(
            db, tenant_id, actor_id, actor_role,
            action="pharma_rep.profile_update",
            target="pharma_rep_profile",
            target_id=profile.id,
            detail={"updated_fields": updated, "registration_status": profile.registration_status},
        )
        db.commit()

    return _serialize_profile(profile)


def submit_registration(db: Session, tenant_id: str, user_id: int, actor_id: int, actor_role: str) -> dict:
    """提交备案（生成备案号）

    对应第 16 条：取得具有唯一备案号的医药代表备案信息表。
    本系统生成临时备案号（前缀 PR-），实际备案号需同步至国家药监局备案平台。
    """
    profile = get_or_create_profile(db, tenant_id, user_id)

    # 校验必填项
    missing = _validate_registration_completeness(profile)
    if missing:
        raise ValidationError(f"备案信息不完整，缺失：{', '.join(missing)}")

    # 校验合规承诺书已签署
    if not profile.commitment_id:
        raise ValidationError("未签署合规承诺书，无法提交备案")

    # 校验无商业贿赂记录
    if profile.has_bribery_record:
        raise ValidationError("存在商业贿赂记录，禁止备案（对应第 11 条第（一）项）")

    # 生成临时备案号
    if not profile.registration_no:
        ts_str = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        profile.registration_no = f"PR-{tenant_id}-{user_id}-{ts_str}"

    profile.registration_status = "submitted"
    profile.registered_at = datetime.utcnow()

    append_compliance_audit_log(
        db, tenant_id, actor_id, actor_role,
        action="pharma_rep.register_submit",
        target="pharma_rep_profile",
        target_id=profile.id,
        detail={
            "registration_no": profile.registration_no,
            "status": "submitted",
        },
    )
    db.commit()
    return _serialize_profile(profile)


def revoke_registration(db: Session, tenant_id: str, user_id: int, actor_id: int, actor_role: str, reason: str) -> dict:
    """撤销备案（停止授权，30 日内删除）

    对应第 17 条：对不再从事相关工作或者停止授权的医药代表，药品上市许可持有人应当在 30 日内删除其备案信息。
    对应第 26 条：终止授权 + 删除备案 + 公示。
    """
    profile = get_or_create_profile(db, tenant_id, user_id)
    profile.registration_status = "revoked"
    profile.revoke_scheduled_at = datetime.utcnow() + timedelta(days=30)

    append_compliance_audit_log(
        db, tenant_id, actor_id, actor_role,
        action="pharma_rep.register_revoke",
        target="pharma_rep_profile",
        target_id=profile.id,
        detail={"reason": reason, "revoke_scheduled_at": profile.revoke_scheduled_at.isoformat()},
    )
    db.commit()
    return _serialize_profile(profile)


def list_pending_revokes(db: Session, tenant_id: str) -> list:
    """查询待删除备案（30 日时效预警）

    Returns:
        [{"profile_id": N, "user_id": N, "revoke_scheduled_at": "...", "days_left": N}, ...]
    """
    now = datetime.utcnow()
    profiles = db.query(PharmaRepProfile).filter(
        PharmaRepProfile.tenant_id == tenant_id,
        PharmaRepProfile.is_deleted == 0,
        PharmaRepProfile.registration_status == "revoked",
        PharmaRepProfile.revoke_scheduled_at.isnot(None),
    ).all()

    result = []
    for p in profiles:
        days_left = max(0, (p.revoke_scheduled_at - now).days) if p.revoke_scheduled_at else 30
        result.append({
            "profile_id": p.id,
            "user_id": p.user_id,
            "registration_no": p.registration_no,
            "revoke_scheduled_at": p.revoke_scheduled_at.isoformat() if p.revoke_scheduled_at else None,
            "days_left": days_left,
        })
    return result


# ──────────────────────────────────────────────
# 合规承诺书签署闭环（第 9、10、15 条）
# ──────────────────────────────────────────────

def sign_commitment(
    db: Session,
    tenant_id: str,
    user_id: int,
    commitment_type: str,
    commitment_text: str,
    version: str,
    course_id: Optional[int] = None,
    exam_record_id: Optional[int] = None,
    signer_ip: Optional[str] = None,
    signer_ua: Optional[str] = None,
) -> dict:
    """签署合规承诺书（培训-考核-承诺闭环的最后一环）

    对应第 9 条：建立培训考核制度
    对应第 10 条：经培训并考核合格
    对应第 15 条第（八）项：合规承诺书

    闭环校验：
    1. 若指定 course_id，必须是 is_compliance=1 的课程
    2. 若指定 exam_record_id，必须 is_passed=1
    3. 自动写入链式 AuditLog
    4. 自动关联到 PharmaRepProfile.commitment_id
    """
    if commitment_type not in COMMITMENT_TYPE:
        raise ValidationError(f"无效的承诺书类型：{commitment_type}")

    # 校验合规培训课程
    if course_id:
        course = db.query(Course).filter(
            Course.tenant_id == tenant_id,
            Course.is_deleted == 0,
            Course.id == course_id,
        ).first()
        if not course:
            raise NotFoundError("课程不存在")
        if not course.is_compliance:
            raise ValidationError("关联的课程不是合规培训课程（is_compliance=0）")

    # 校验考核合格
    if exam_record_id:
        exam_record = db.query(ExamRecord).filter(
            ExamRecord.tenant_id == tenant_id,
            ExamRecord.is_deleted == 0,
            ExamRecord.id == exam_record_id,
            ExamRecord.user_id == user_id,
        ).first()
        if not exam_record:
            raise NotFoundError("考核记录不存在")
        if not exam_record.passed:
            raise ValidationError("考核未通过，无法签署承诺书")

    # 计算不可篡改签名 hash
    signed_at = datetime.utcnow()
    sig_payload = json.dumps({
        "user_id": user_id,
        "commitment_type": commitment_type,
        "commitment_text": commitment_text,
        "version": version,
        "signed_at": signed_at.isoformat(),
        "course_id": course_id,
        "exam_record_id": exam_record_id,
    }, sort_keys=True, ensure_ascii=False)
    signature_hash = hashlib.sha256(sig_payload.encode("utf-8")).hexdigest()

    # 写入承诺书记录
    commitment = ComplianceCommitment(
        tenant_id=tenant_id,
        user_id=user_id,
        commitment_type=commitment_type,
        course_id=course_id,
        exam_record_id=exam_record_id,
        commitment_text=commitment_text,
        version=version,
        signed_at=signed_at,
        signer_ip=signer_ip,
        signer_ua=signer_ua,
        signature_hash=signature_hash,
        status="signed",
        # 年度承诺书默认 1 年过期
        expires_at=signed_at + timedelta(days=365) if commitment_type == "annual" else None,
    )
    db.add(commitment)
    db.flush()

    # 写入链式 AuditLog
    audit_log = append_compliance_audit_log(
        db, tenant_id, user_id, "pharma_rep",
        action="commitment.sign",
        target="compliance_commitment",
        target_id=commitment.id,
        detail={
            "commitment_type": commitment_type,
            "version": version,
            "signature_hash": signature_hash,
            "course_id": course_id,
            "exam_record_id": exam_record_id,
        },
    )
    commitment.audit_log_id = audit_log.id

    # 关联到医药代表档案
    profile = get_or_create_profile(db, tenant_id, user_id)
    profile.commitment_id = commitment.id

    db.commit()
    return _serialize_commitment(commitment)


def check_onboarding_ready(db: Session, tenant_id: str, user_id: int) -> dict:
    """检查医药代表上岗三件套是否齐备（培训-考核-承诺闭环）

    只读校验：档案不存在视为「未签承诺」，不自动建档（GET 请求
    不应产生写事务；否则会在 SQLite 上抢写锁，见 WAL 优化记录）。

    Returns:
        {"ready": bool, "training_done": bool, "exam_passed": bool, "commitment_signed": bool,
         "missing": [...], "details": {...}}
    """
    profile = get_profile(db, tenant_id, user_id)

    # 检查是否完成合规培训
    mandatory_courses = db.query(Course).filter(
        Course.tenant_id == tenant_id,
        Course.is_deleted == 0,
        Course.is_compliance == 1,
        Course.is_mandatory == 1,
    ).all()
    mandatory_course_ids = {c.id for c in mandatory_courses}

    enrollments = db.query(CourseEnrollment).filter(
        CourseEnrollment.tenant_id == tenant_id,
        CourseEnrollment.is_deleted == 0,
        CourseEnrollment.user_id == user_id,
        CourseEnrollment.course_id.in_(mandatory_course_ids) if mandatory_course_ids else False,
    ).all() if mandatory_course_ids else []
    enrolled_course_ids = {e.course_id for e in enrollments}
    training_done = mandatory_course_ids.issubset(enrolled_course_ids)

    # 检查考核是否通过
    exam_records = db.query(ExamRecord).filter(
        ExamRecord.tenant_id == tenant_id,
        ExamRecord.is_deleted == 0,
        ExamRecord.user_id == user_id,
    ).all()
    exam_passed = any(er.passed for er in exam_records)

    # 检查承诺书是否签署（档案不存在 → 未签署）
    commitment_signed = bool(profile and profile.commitment_id)

    missing = []
    if not training_done:
        missing.append("mandatory_training")
    if not exam_passed:
        missing.append("exam_passed")
    if not commitment_signed:
        missing.append("commitment_signed")

    return {
        "ready": len(missing) == 0,
        "training_done": training_done,
        "exam_passed": exam_passed,
        "commitment_signed": commitment_signed,
        "missing": missing,
        "details": {
            "mandatory_courses_total": len(mandatory_course_ids),
            "mandatory_courses_completed": len(enrolled_course_ids),
            "exam_records_count": len(exam_records),
            "commitment_id": profile.commitment_id if profile else None,
        },
    }


# ──────────────────────────────────────────────
# 工具 RBAC 校验（医药代表禁止调用销售类工具）
# ──────────────────────────────────────────────

def is_tool_forbidden_for_role(tool_name: str, user_role: str) -> bool:
    """检查工具是否被角色禁止调用

    对应第 11 条第（三）项 + 第 24 条第（三）项：
    医药代表不得承担药品销售任务，禁止调用 ROI/KPI/积分等销售工具。
    """
    if user_role == PHARMA_REP_ROLE_CODE:
        return tool_name in FORBIDDEN_TOOLS_FOR_PHARMA_REP
    return False


def get_user_role(db: Session, user_id: int) -> str:
    """获取用户角色代码（基于 Role.code）

    Returns:
        role_code（如 "pharma_rep" / "sales_manager" / "compliance_officer"）；
        若用户未关联角色，返回空字符串。
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.role_id:
        return ""
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return role.code if role else ""


# ──────────────────────────────────────────────
# 22 项禁止行为查询
# ──────────────────────────────────────────────

def list_forbidden_behaviors(subject: Optional[str] = None) -> list:
    """查询 22 项禁止行为清单

    Args:
        subject: 主体过滤（持有人 / CSO / 医药代表 / 医疗机构），None 返回全部
    """
    if subject:
        return [b for b in FORBIDDEN_BEHAVIORS if b["subject"] == subject]
    return FORBIDDEN_BEHAVIORS


# ──────────────────────────────────────────────
# 序列化
# ──────────────────────────────────────────────

def _serialize_profile(p: PharmaRepProfile) -> dict:
    return {
        "id": p.id,
        "user_id": p.user_id,
        "id_card_type": p.id_card_type,
        "id_card_no": p.id_card_no,
        "gender": p.gender,
        "photo_url": p.photo_url,
        "education_level": p.education_level,
        "major": p.major,
        "contract_start": p.contract_start.isoformat() if p.contract_start else None,
        "contract_end": p.contract_end.isoformat() if p.contract_end else None,
        "drug_categories": p.drug_categories or [],
        "therapeutic_areas": p.therapeutic_areas or [],
        "authorized_regions": p.authorized_regions or [],
        "authenticity_statement": p.authenticity_statement,
        "statement_signed_at": p.statement_signed_at.isoformat() if p.statement_signed_at else None,
        "commitment_id": p.commitment_id,
        "registration_no": p.registration_no,
        "registration_status": p.registration_status,
        "registration_status_label": REGISTRATION_STATUS.get(p.registration_status, p.registration_status),
        "registered_at": p.registered_at.isoformat() if p.registered_at else None,
        "last_change_at": p.last_change_at.isoformat() if p.last_change_at else None,
        "revoke_scheduled_at": p.revoke_scheduled_at.isoformat() if p.revoke_scheduled_at else None,
        "has_bribery_record": p.has_bribery_record,
        "bribery_record_detail": p.bribery_record_detail,
    }


def _serialize_commitment(c: ComplianceCommitment) -> dict:
    return {
        "id": c.id,
        "user_id": c.user_id,
        "commitment_type": c.commitment_type,
        "commitment_type_label": COMMITMENT_TYPE.get(c.commitment_type, c.commitment_type),
        "course_id": c.course_id,
        "exam_record_id": c.exam_record_id,
        "commitment_text": c.commitment_text,
        "version": c.version,
        "signed_at": c.signed_at.isoformat() if c.signed_at else None,
        "signer_ip": c.signer_ip,
        "signer_ua": c.signer_ua,
        "signature_hash": c.signature_hash,
        "audit_log_id": c.audit_log_id,
        "status": c.status,
        "expires_at": c.expires_at.isoformat() if c.expires_at else None,
    }


# ──────────────────────────────────────────────
# 内部辅助
# ──────────────────────────────────────────────

def _validate_registration_completeness(profile: PharmaRepProfile) -> list:
    """校验备案信息完整性（对应第 15 条 8 项内容）"""
    missing = []
    if not profile.id_card_no:
        missing.append("身份证号")
    if not profile.education_level:
        missing.append("学历")
    if not profile.major:
        missing.append("专业")
    if not profile.contract_start:
        missing.append("合同起始日期")
    if not (profile.drug_categories or []):
        missing.append("推广药品类别")
    if not (profile.authorized_regions or []):
        missing.append("推广区域")
    if not profile.authenticity_statement:
        missing.append("真实性声明")
    return missing


# ════════════════════════════════════════════════════════════════
# v2.2 Phase 2 扩展：22 项禁止行为规则引擎 + 违规事件 + 30 日时效预警
# ════════════════════════════════════════════════════════════════

from database import (
    ComplianceViolationRule,
    ComplianceViolationEvent,
    ComplianceAlert,
    PartnerOrganization,
    ManagementAgreement,
    AuthorizationLetter,
    AcademicActivity,
)


# ──────────────────────────────────────────────
# 22 项禁止行为规则 seed（对应第 11/12/24/25 条）
# ──────────────────────────────────────────────

# 触发场景常量
SCENE_ACTIVITY_CREATE = "academic_activity.create"
SCENE_ACTIVITY_CHECKIN = "academic_activity.checkin"
SCENE_ACTIVITY_EXPENSE = "academic_activity.expense"
SCENE_VISIT_SUBMIT = "visit_record.submit"
SCENE_COMMITMENT_SIGN = "commitment.sign"

_VIOLATION_RULES_SEED = [
    # 第 11 条 持有人 4 项
    {"code": "A11_1", "article": "第 11 条", "subject": "持有人",
     "description": "向医药代表分配药品销售任务", "severity": "critical",
     "trigger_scenes": [SCENE_ACTIVITY_CREATE, SCENE_VISIT_SUBMIT],
     "check_type": "role_blacklist", "check_config": {"roles": ["pharma_rep"], "blocked_actions": ["assign_sales_quota"]}},
    {"code": "A11_2", "article": "第 11 条", "subject": "持有人",
     "description": "向医药代表下达药品销售目标", "severity": "critical",
     "trigger_scenes": [SCENE_ACTIVITY_CREATE, SCENE_VISIT_SUBMIT],
     "check_type": "role_blacklist", "check_config": {"roles": ["pharma_rep"], "blocked_actions": ["assign_kpi_target"]}},
    {"code": "A11_3", "article": "第 11 条", "subject": "持有人",
     "description": "要求医药代表承担药品销售收款和处理购销票据等销售行为", "severity": "critical",
     "trigger_scenes": [SCENE_ACTIVITY_EXPENSE, SCENE_VISIT_SUBMIT],
     "check_type": "role_blacklist", "check_config": {"roles": ["pharma_rep"], "blocked_actions": ["collect_payment", "process_invoice"]}},
    {"code": "A11_4", "article": "第 11 条", "subject": "持有人",
     "description": "与医药代表订立销售任务目标责任书", "severity": "critical",
     "trigger_scenes": [SCENE_COMMITMENT_SIGN],
     "check_type": "role_blacklist", "check_config": {"roles": ["pharma_rep"], "blocked_actions": ["sign_sales_quota_contract"]}},
    # 第 12 条 CSO 4 项
    {"code": "A12_1", "article": "第 12 条", "subject": "CSO",
     "description": "指使医药代表从事商业贿赂等违法活动", "severity": "critical",
     "trigger_scenes": [SCENE_ACTIVITY_EXPENSE, SCENE_VISIT_SUBMIT],
     "check_type": "forbidden_action", "check_config": {"keywords": ["回扣", "贿赂", "商业贿赂", "红包"]}},
    {"code": "A12_2", "article": "第 12 条", "subject": "CSO",
     "description": "指使医药代表实施违规推广行为", "severity": "high",
     "trigger_scenes": [SCENE_ACTIVITY_CREATE, SCENE_VISIT_SUBMIT],
     "check_type": "forbidden_action", "check_config": {"keywords": ["夸大疗效", "适应症外推", "虚假宣传"]}},
    {"code": "A12_3", "article": "第 12 条", "subject": "CSO",
     "description": "与持有人订立药品销售任务目标责任书", "severity": "critical",
     "trigger_scenes": [SCENE_COMMITMENT_SIGN],
     "check_type": "forbidden_action", "check_config": {"keywords": ["销售任务", "销售目标", "销售回款"]}},
    {"code": "A12_4", "article": "第 12 条", "subject": "CSO",
     "description": "与医药代表订立药品销售任务目标责任书", "severity": "critical",
     "trigger_scenes": [SCENE_COMMITMENT_SIGN],
     "check_type": "forbidden_action", "check_config": {"keywords": ["销售任务", "销售目标", "销售回款"]}},
    # 第 24 条 医药代表 9 项
    {"code": "A24_1", "article": "第 24 条", "subject": "医药代表",
     "description": "承担药品销售任务，实施收款和处理购销票据等销售行为", "severity": "critical",
     "trigger_scenes": [SCENE_ACTIVITY_CREATE, SCENE_ACTIVITY_EXPENSE, SCENE_VISIT_SUBMIT],
     "check_type": "role_blacklist", "check_config": {"roles": ["pharma_rep"], "blocked_actions": ["collect_payment", "process_invoice", "sign_sales_contract"]}},
    {"code": "A24_2", "article": "第 24 条", "subject": "医药代表",
     "description": "采用抛撒代币、有奖销售、附赠物品等方式引导医疗、使用", "severity": "high",
     "trigger_scenes": [SCENE_ACTIVITY_CREATE, SCENE_ACTIVITY_CHECKIN],
     "check_type": "forbidden_action", "check_config": {"keywords": ["代币", "有奖销售", "附赠", "赠品", "抽奖"]}},
    {"code": "A24_3", "article": "第 24 条", "subject": "医药代表",
     "description": "以占领市场为目的召开学术会议、举办宣传活动", "severity": "high",
     "trigger_scenes": [SCENE_ACTIVITY_CREATE],
     "check_type": "keyword", "check_config": {"keywords": ["占领市场", "抢占市场", "市场份额目标"]}},
    {"code": "A24_4", "article": "第 24 条", "subject": "医药代表",
     "description": "干预医疗机构部门、科室及人员合理使用药品", "severity": "high",
     "trigger_scenes": [SCENE_ACTIVITY_CREATE, SCENE_VISIT_SUBMIT],
     "check_type": "forbidden_action", "check_config": {"keywords": ["干预用药", "干预处方", "强制开方"]}},
    {"code": "A24_5", "article": "第 24 条", "subject": "医药代表",
     "description": "干预医疗机构工作人员的招录、职务晋升", "severity": "high",
     "trigger_scenes": [SCENE_ACTIVITY_CREATE],
     "check_type": "forbidden_action", "check_config": {"keywords": ["招录", "晋升", "提拔"]}},
    {"code": "A24_6", "article": "第 24 条", "subject": "医药代表",
     "description": "在推广活动中将自境外或海南自由贸易港未经审批上市的药品向境内医疗机构介绍", "severity": "high",
     "trigger_scenes": [SCENE_ACTIVITY_CREATE, SCENE_ACTIVITY_CHECKIN],
     "check_type": "forbidden_action", "check_config": {"keywords": ["境外", "未审批", "未上市", "海南自贸港"]}},
    {"code": "A24_7", "article": "第 24 条", "subject": "医药代表",
     "description": "以侵占市场为目的单独召开会议、举办宣传活动", "severity": "high",
     "trigger_scenes": [SCENE_ACTIVITY_CREATE],
     "check_type": "keyword", "check_config": {"keywords": ["侵占市场", "侵占", "垄断市场"]}},
    {"code": "A24_8", "article": "第 24 条", "subject": "医药代表",
     "description": "伪造、变造备案信息、资质证明、学籍学历等文件材料", "severity": "critical",
     "trigger_scenes": [SCENE_COMMITMENT_SIGN, SCENE_ACTIVITY_CREATE],
     "check_type": "forbidden_action", "check_config": {"keywords": ["伪造", "变造", "假学历", "假资质"]}},
    {"code": "A24_9", "article": "第 24 条", "subject": "医药代表",
     "description": "以营利为目的擅自收集个人信息、敏感个人信息", "severity": "high",
     "trigger_scenes": [SCENE_ACTIVITY_CHECKIN, SCENE_ACTIVITY_CREATE],
     "check_type": "forbidden_action", "check_config": {"keywords": ["个人信息收集", "敏感信息", "医生联系方式售卖"]}},
    # 第 25 条 医疗机构 5 项
    {"code": "A25_1", "article": "第 25 条", "subject": "医疗机构",
     "description": "未经备案及代表授权开展学术推广活动", "severity": "critical",
     "trigger_scenes": [SCENE_ACTIVITY_CREATE, SCENE_ACTIVITY_CHECKIN],
     "check_type": "forbidden_action", "check_config": {"check": "pharma_rep_registration"}},
    {"code": "A25_2", "article": "第 25 条", "subject": "医疗机构",
     "description": "在购销药品过程中索取或收受财物", "severity": "critical",
     "trigger_scenes": [SCENE_ACTIVITY_EXPENSE, SCENE_VISIT_SUBMIT],
     "check_type": "forbidden_action", "check_config": {"keywords": ["索取", "收受", "回扣", "好处费"]}},
    {"code": "A25_3", "article": "第 25 条", "subject": "医疗机构",
     "description": "违规参与或干预医药代表的学术推广活动", "severity": "high",
     "trigger_scenes": [SCENE_ACTIVITY_CREATE, SCENE_ACTIVITY_CHECKIN],
     "check_type": "forbidden_action", "check_config": {"keywords": ["违规干预", "强制要求", "指定药品"]}},
    {"code": "A25_4", "article": "第 25 条", "subject": "医疗机构",
     "description": "在采购、使用药品过程中违反法律法规规定收受财物", "severity": "critical",
     "trigger_scenes": [SCENE_ACTIVITY_EXPENSE],
     "check_type": "forbidden_action", "check_config": {"keywords": ["采购回扣", "使用回扣"]}},
    {"code": "A25_5", "article": "第 25 条", "subject": "医疗机构",
     "description": "干涉医药代表的备案、考核及学术推广工作", "severity": "high",
     "trigger_scenes": [SCENE_ACTIVITY_CREATE, SCENE_ACTIVITY_CHECKIN],
     "check_type": "forbidden_action", "check_config": {"keywords": ["干涉备案", "阻碍考核"]}},
]


def seed_violation_rules(db: Session) -> int:
    """幂等 seed 22 项禁止行为规则

    F5 增强：seed 时显式设置 version=1.0.0 / release_state=published / effective_start=今天，
    便于历史回放（bind_rule_at_time）正确返回。

    Returns:
        写入的规则数量（已存在则返回 0）
    """
    if db.query(ComplianceViolationRule).count() > 0:
        return 0
    today = date.today()
    for rule_def in _VIOLATION_RULES_SEED:
        db.add(ComplianceViolationRule(
            tenant_id="default",  # 规则全局共享
            code=rule_def["code"],
            article=rule_def["article"],
            subject=rule_def["subject"],
            description=rule_def["description"],
            severity=rule_def["severity"],
            trigger_scenes=rule_def["trigger_scenes"],
            check_type=rule_def["check_type"],
            check_config=rule_def["check_config"],
            is_active=1,
            # F5: 版本化字段
            version="1.0.0",
            release_state="published",
            effective_start=today,
            effective_end=None,
            parent_rule_id=None,
        ))
    db.flush()
    return len(_VIOLATION_RULES_SEED)


# ──────────────────────────────────────────────
# 22 项规则查询
# ──────────────────────────────────────────────

def list_violation_rules(db: Session, subject: Optional[str] = None, active_only: bool = True,
                          effective_at: Optional[date] = None) -> list:
    """查询违规规则列表

    F5 增强（借鉴诊断体系 §6.5、§7.4）：
    - effective_at 参数支持历史回放：传入时间点时查询当时生效的版本
    - 默认查当前 published 版本

    Args:
        subject: 主体过滤（持有人/CSO/医药代表/医疗机构）
        active_only: 是否仅查启用规则（effective_at 传入时此参数忽略）
        effective_at: 历史回放时间点（默认 None = 当前生效版本）
    """
    if effective_at is not None:
        # 历史回放模式：查询时间点当时生效的版本
        from services.rule_version_service import bind_rule_at_time
        all_codes = db.query(ComplianceViolationRule.code).filter(
            ComplianceViolationRule.is_deleted == 0,
        ).distinct().all()
        rules = []
        for (code,) in all_codes:
            rule = bind_rule_at_time(db, code, effective_at)
            if rule and (subject is None or rule.subject == subject):
                rules.append(rule)
        return [_serialize_violation_rule(r) for r in rules]

    q = db.query(ComplianceViolationRule).filter(ComplianceViolationRule.is_deleted == 0)
    if active_only:
        q = q.filter(ComplianceViolationRule.is_active == 1)
    if subject:
        q = q.filter(ComplianceViolationRule.subject == subject)
    # F5: 默认仅返回 published 版本（draft/shadow 不返回）
    q = q.filter(ComplianceViolationRule.release_state == "published")
    rules = q.order_by(ComplianceViolationRule.code).all()
    return [_serialize_violation_rule(r) for r in rules]


def get_violation_rule(db: Session, code: str) -> Optional[dict]:
    """按 code 查询单条规则"""
    r = db.query(ComplianceViolationRule).filter(
        ComplianceViolationRule.code == code,
        ComplianceViolationRule.is_deleted == 0,
    ).first()
    return _serialize_violation_rule(r) if r else None


# 全局基线租户标识：规则库中以 tenant_id="default" 存储共享基线，
# 各租户可通过 parent_rule_id 指向基线规则 id 进行覆盖（基线+覆盖两层模型）。
BASELINE_TENANT_ID = "default"


def get_effective_rules(db: Session, tenant_id: Optional[str] = None,
                        subject: Optional[str] = None,
                        active_only: bool = True) -> list:
    """取「基线 + 租户覆盖」合并后的生效规则集（闭环跨租户边界）

    模型说明（借鉴 M11 project_version 归属范式）：
    - 基线规则：tenant_id=BASELINE_TENANT_ID("default")，所有租户可继承。
    - 覆盖规则：tenant_id=<真实租户>，parent_rule_id 指向被覆盖的基线规则 id；
      同一 code 下若租户存在覆盖版本，则覆盖版本优先于基线版本。
    - 未传 tenant_id 时仅返回基线（保持历史「全局共享」行为，向后兼容）。

    Returns:
        list[dict]：合并去重后的生效规则（覆盖优先）
    """
    q = db.query(ComplianceViolationRule).filter(
        ComplianceViolationRule.is_deleted == 0,
        ComplianceViolationRule.release_state == "published",
    )
    if active_only:
        q = q.filter(ComplianceViolationRule.is_active == 1)
    if subject:
        q = q.filter(ComplianceViolationRule.subject == subject)

    if tenant_id is None or tenant_id == BASELINE_TENANT_ID:
        # 仅基线
        rules = q.filter(ComplianceViolationRule.tenant_id == BASELINE_TENANT_ID).all()
        return [_serialize_violation_rule(r) for r in rules]

    # 基线 + 本租户覆盖
    rules = q.filter(
        ComplianceViolationRule.tenant_id.in_([BASELINE_TENANT_ID, tenant_id])
    ).all()

    # 以 code 为键合并：租户覆盖版本优先于基线版本
    by_code: dict = {}
    override_ids = set()
    for r in rules:
        if r.tenant_id == tenant_id and r.parent_rule_id is not None:
            override_ids.add(r.parent_rule_id)
        key = r.code
        existing = by_code.get(key)
        if existing is None or r.tenant_id == tenant_id:
            by_code[key] = r
    merged = [by_code[k] for k in sorted(by_code.keys())]
    result = [_serialize_violation_rule(r) for r in merged]
    # 标注每条规则来源（基线继承 / 租户覆盖），便于前端展示与审计
    id_to_override = {r.id: r for r in rules if r.tenant_id == tenant_id}
    for item in result:
        item["source"] = "tenant_override" if item["id"] in id_to_override else "baseline"
    return result


def list_violation_rules(db: Session, subject: Optional[str] = None, active_only: bool = True,
                          effective_at: Optional[date] = None,
                          tenant_id: Optional[str] = None) -> list:
    """查询违规规则列表（基线 + 可选租户覆盖）

    F5 增强（借鉴诊断体系 §6.5、§7.4）：
    - effective_at 参数支持历史回放：传入时间点时查询当时生效的版本
    - 默认查当前 published 版本
    - tenant_id 参数支持「基线 + 租户覆盖」两层模型（None=仅基线，向后兼容）

    Args:
        subject: 主体过滤（持有人/CSO/医药代表/医疗机构）
        active_only: 是否仅查启用规则（effective_at 传入时此参数忽略）
        effective_at: 历史回放时间点（默认 None = 当前生效版本）
        tenant_id: 租户 ID（默认 None = 仅返回全局基线规则）
    """
    if effective_at is not None:
        # 历史回放模式：查询时间点当时生效的版本
        from services.rule_version_service import bind_rule_at_time
        all_codes = db.query(ComplianceViolationRule.code).filter(
            ComplianceViolationRule.is_deleted == 0,
        ).distinct().all()
        rules = []
        for (code,) in all_codes:
            rule = bind_rule_at_time(db, code, effective_at)
            if rule and (subject is None or rule.subject == subject):
                rules.append(rule)
        return [_serialize_violation_rule(r) for r in rules]

    return get_effective_rules(db, tenant_id=tenant_id, subject=subject, active_only=active_only)


def _serialize_violation_rule(r: ComplianceViolationRule) -> dict:
    return {
        "id": r.id,
        "code": r.code,
        "article": r.article,
        "subject": r.subject,
        "description": r.description,
        "severity": r.severity,
        "trigger_scenes": r.trigger_scenes or [],
        "check_type": r.check_type,
        "check_config": r.check_config or {},
        "is_active": bool(r.is_active),
        # F5: 版本化字段（借鉴诊断体系 §6.5、§7.4）
        "version": r.version,
        "release_state": r.release_state,
        "effective_start": r.effective_start.isoformat() if r.effective_start else None,
        "effective_end": r.effective_end.isoformat() if r.effective_end else None,
        "parent_rule_id": r.parent_rule_id,
    }


# ──────────────────────────────────────────────
# 运行时规则校验
# ──────────────────────────────────────────────

def check_violations(
    db: Session,
    tenant_id: str,
    scene: str,
    context: dict,
    actor_id: Optional[int] = None,
    actor_role: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
) -> list:
    """运行时校验：扫描匹配 scene 的规则，对 context 执行检查逻辑

    Args:
        scene: 触发场景（SCENE_* 常量）
        context: 校验上下文 {text, action, amount, role, ...}
        actor_id, actor_role: 违规主体
        entity_type, entity_id: 业务实体关联

    Returns:
        触发的违规事件列表 [{rule_code, severity, description, event_id}]
    """
    # 加载该 scene 的活跃规则（F5: 仅 published 版本参与运行时校验，draft/shadow 不生效）
    # 基线 + 租户覆盖两层模型：只加载 default 基线与该租户覆盖，避免跨租户规则互相污染。
    baseline_ids = {
        r.id for r in db.query(ComplianceViolationRule).filter(
            ComplianceViolationRule.tenant_id == BASELINE_TENANT_ID,
            ComplianceViolationRule.is_deleted == 0,
            ComplianceViolationRule.is_active == 1,
            ComplianceViolationRule.release_state == "published",
        ).all()
    }
    override_rows = db.query(ComplianceViolationRule).filter(
        ComplianceViolationRule.tenant_id == tenant_id,
        ComplianceViolationRule.is_deleted == 0,
        ComplianceViolationRule.is_active == 1,
        ComplianceViolationRule.release_state == "published",
    ).all()
    # 覆盖规则 parent_rule_id 指向被覆盖的基线 id，需从生效集中剔除被覆盖的基线
    overridden_baseline_ids = {r.parent_rule_id for r in override_rows if r.parent_rule_id is not None}
    effective_ids = (baseline_ids - overridden_baseline_ids) | {r.id for r in override_rows}
    all_candidates = db.query(ComplianceViolationRule).filter(
        ComplianceViolationRule.id.in_(effective_ids),
    ).all()
    rules = [r for r in all_candidates if scene in (r.trigger_scenes or [])]

    triggered = []
    for rule in rules:
        scenes = rule.trigger_scenes or []
        if scene not in scenes:
            continue
        hit = _apply_rule_check(rule, context, actor_role)
        if not hit:
            continue
        # 记录违规事件
        evt = ComplianceViolationEvent(
            tenant_id=tenant_id,
            rule_code=rule.code,
            rule_article=rule.article,
            rule_subject=rule.subject,
            severity=rule.severity,
            actor_id=actor_id,
            actor_role=actor_role,
            entity_type=entity_type,
            entity_id=entity_id,
            description=rule.description,
            # F5: 在证据载荷中绑定精确版本，便于事后回放/审计
            evidence_payload={
                **(context if isinstance(context, dict) else {}),
                "_rule_version": rule.version,
                "_rule_id": rule.id,
                "_rule_release_state": rule.release_state,
            },
            status="open",
        )
        db.add(evt)
        db.flush()
        # 自动生成合规预警
        alert = ComplianceAlert(
            tenant_id=tenant_id,
            alert_type="violation",
            severity=rule.severity,
            title=f"违规预警：{rule.code} {rule.description[:80]}",
            description=f"规则 {rule.code}（{rule.article} {rule.subject}）在场景 {scene} 触发",
            actor_id=actor_id,
            actor_role=actor_role,
            entity_type=entity_type,
            entity_id=entity_id,
            rule_code=rule.code,
            violation_event_id=evt.id,
            status="open",
            is_compliance_critical=1 if rule.severity == "critical" else 0,
        )
        db.add(alert)
        db.flush()
        evt.alert_id = alert.id
        triggered.append({
            "rule_code": rule.code,
            "severity": rule.severity,
            "description": rule.description,
            "event_id": evt.id,
            "alert_id": alert.id,
        })
    db.commit()
    return triggered


def _apply_rule_check(rule: ComplianceViolationRule, context: dict, actor_role: Optional[str]) -> bool:
    """对单条规则执行检查逻辑

    返回 True 表示违规
    """
    check_type = rule.check_type
    cfg = rule.check_config or {}

    if check_type == "keyword":
        keywords = cfg.get("keywords", [])
        text = (context.get("text") or "") + " " + (context.get("title") or "")
        return any(k in text for k in keywords)

    if check_type == "forbidden_action":
        keywords = cfg.get("keywords", [])
        action = context.get("action", "")
        text = context.get("text", "")
        target = (action or "") + " " + (text or "")
        return any(k in target for k in keywords)

    if check_type == "role_blacklist":
        roles = cfg.get("roles", [])
        blocked_actions = cfg.get("blocked_actions", [])
        action = context.get("action", "")
        if actor_role in roles and action in blocked_actions:
            return True
        # 也支持通过 context.role 校验
        ctx_role = context.get("role", "")
        if ctx_role in roles and action in blocked_actions:
            return True
        return False

    if check_type == "amount_limit":
        max_amount = cfg.get("max_amount", 0)
        amount = context.get("amount", 0) or 0
        return amount > max_amount

    return False


# ──────────────────────────────────────────────
# 违规事件查询
# ──────────────────────────────────────────────

def list_violation_events(
    db: Session, tenant_id: str,
    status: Optional[str] = None, severity: Optional[str] = None,
    page: int = 1, page_size: int = 20,
) -> dict:
    """违规事件列表"""
    q = db.query(ComplianceViolationEvent).filter(
        ComplianceViolationEvent.tenant_id == tenant_id,
        ComplianceViolationEvent.is_deleted == 0,
    )
    if status:
        q = q.filter(ComplianceViolationEvent.status == status)
    if severity:
        q = q.filter(ComplianceViolationEvent.severity == severity)
    total = q.count()
    items = q.order_by(ComplianceViolationEvent.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {
        "items": [_serialize_violation_event(e) for e in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def handle_violation_event(
    db: Session, tenant_id: str, event_id: int,
    handler_id: int, result: str, status: str = "resolved",
) -> dict:
    """处置违规事件"""
    evt = db.query(ComplianceViolationEvent).filter(
        ComplianceViolationEvent.tenant_id == tenant_id,
        ComplianceViolationEvent.is_deleted == 0,
        ComplianceViolationEvent.id == event_id,
    ).first()
    if not evt:
        raise NotFoundError("违规事件不存在")
    evt.handled_by = handler_id
    evt.handled_at = datetime.utcnow()
    evt.handling_result = result
    evt.status = status
    # 同步关闭预警
    if evt.alert_id:
        alert = db.query(ComplianceAlert).filter(ComplianceAlert.id == evt.alert_id).first()
        if alert:
            alert.handled_by = handler_id
            alert.handled_at = datetime.utcnow()
            alert.handling_result = result
            alert.status = "resolved" if status == "resolved" else alert.status
    db.commit()
    db.refresh(evt)
    return _serialize_violation_event(evt)


def _serialize_violation_event(e: ComplianceViolationEvent) -> dict:
    return {
        "id": e.id,
        "rule_code": e.rule_code,
        "rule_article": e.rule_article,
        "rule_subject": e.rule_subject,
        "severity": e.severity,
        "actor_id": e.actor_id,
        "actor_role": e.actor_role,
        "entity_type": e.entity_type,
        "entity_id": e.entity_id,
        "description": e.description,
        "evidence_payload": e.evidence_payload or {},
        "status": e.status,
        "handled_by": e.handled_by,
        "handled_at": e.handled_at.strftime("%Y-%m-%d %H:%M:%S") if e.handled_at else None,
        "handling_result": e.handling_result,
        "alert_id": e.alert_id,
        "created_at": e.created_at.strftime("%Y-%m-%d %H:%M:%S") if e.created_at else None,
    }


# ──────────────────────────────────────────────
# 合规预警查询
# ──────────────────────────────────────────────

def list_alerts(
    db: Session, tenant_id: str,
    status: Optional[str] = None, severity: Optional[str] = None,
    alert_type: Optional[str] = None,
    page: int = 1, page_size: int = 20,
) -> dict:
    """合规预警列表"""
    q = db.query(ComplianceAlert).filter(
        ComplianceAlert.tenant_id == tenant_id,
        ComplianceAlert.is_deleted == 0,
    )
    if status:
        q = q.filter(ComplianceAlert.status == status)
    if severity:
        q = q.filter(ComplianceAlert.severity == severity)
    if alert_type:
        q = q.filter(ComplianceAlert.alert_type == alert_type)
    total = q.count()
    items = q.order_by(ComplianceAlert.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {
        "items": [_serialize_alert(a) for a in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def handle_alert(
    db: Session, tenant_id: str, alert_id: int,
    handler_id: int, result: str, status: str = "resolved",
) -> dict:
    """处置预警"""
    alert = db.query(ComplianceAlert).filter(
        ComplianceAlert.tenant_id == tenant_id,
        ComplianceAlert.is_deleted == 0,
        ComplianceAlert.id == alert_id,
    ).first()
    if not alert:
        raise NotFoundError("预警不存在")
    alert.handled_by = handler_id
    alert.handled_at = datetime.utcnow()
    alert.handling_result = result
    alert.status = status
    db.commit()
    db.refresh(alert)
    return _serialize_alert(alert)


def _serialize_alert(a: ComplianceAlert) -> dict:
    return {
        "id": a.id,
        "alert_type": a.alert_type,
        "severity": a.severity,
        "title": a.title,
        "description": a.description,
        "actor_id": a.actor_id,
        "actor_role": a.actor_role,
        "entity_type": a.entity_type,
        "entity_id": a.entity_id,
        "rule_code": a.rule_code,
        "violation_event_id": a.violation_event_id,
        "deadline_at": a.deadline_at.strftime("%Y-%m-%d %H:%M:%S") if a.deadline_at else None,
        "days_remaining": a.days_remaining,
        "status": a.status,
        "handled_by": a.handled_by,
        "handled_at": a.handled_at.strftime("%Y-%m-%d %H:%M:%S") if a.handled_at else None,
        "handling_result": a.handling_result,
        "is_compliance_critical": bool(a.is_compliance_critical),
        "created_at": a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else None,
    }


# ──────────────────────────────────────────────
# 30 日时效扫描（对应第 17 条备案信息变更/停止授权 30 日内）
# ──────────────────────────────────────────────

DEADLINE_DAYS = 30


def scan_deadline_alerts(db: Session, tenant_id: str) -> dict:
    """扫描即将到期或已到期的备案变更/撤销任务，生成 ComplianceAlert

    Returns:
        {scanned, new_alerts, upcoming_expires, overdue}
    """
    now = datetime.utcnow()
    soon_threshold = now + timedelta(days=7)  # 7 日内到期视为紧急

    # 1. 扫描备案变更中（registration_status='pending_change'）的档案
    profiles_change = db.query(PharmaRepProfile).filter(
        PharmaRepProfile.tenant_id == tenant_id,
        PharmaRepProfile.is_deleted == 0,
        PharmaRepProfile.registration_status == "pending_change",
        PharmaRepProfile.last_change_at.isnot(None),
    ).all()

    # 2. 扫描待撤销（revoke_scheduled_at 已设置）的档案
    profiles_revoke = db.query(PharmaRepProfile).filter(
        PharmaRepProfile.tenant_id == tenant_id,
        PharmaRepProfile.is_deleted == 0,
        PharmaRepProfile.revoke_scheduled_at.isnot(None),
    ).all()

    new_alerts = 0
    upcoming = 0
    overdue = 0

    # 已存在的预警去重（按 actor_id + alert_type + entity_id）
    existing_keys = set()
    for a in db.query(ComplianceAlert).filter(
        ComplianceAlert.tenant_id == tenant_id,
        ComplianceAlert.is_deleted == 0,
        ComplianceAlert.alert_type.in_(["deadline", "expiry"]),
    ).all():
        existing_keys.add((a.actor_id, a.alert_type, a.entity_id))

    # 处理 pending_change
    for p in profiles_change:
        if p.last_change_at is None:
            continue
        deadline = p.last_change_at + timedelta(days=DEADLINE_DAYS)
        days_remaining = (deadline - now).days
        if days_remaining < 0:
            status = "open"
            severity = "critical"
            overdue += 1
        elif days_remaining <= 7:
            status = "open"
            severity = "high"
            upcoming += 1
        else:
            continue  # 距离截止日还早，无需预警
        key = (p.user_id, "deadline", None)
        if key in existing_keys:
            continue
        title = f"医药代表(user_id={p.user_id})备案信息变更 30 日时效预警"
        desc = f"变更时间：{p.last_change_at.strftime('%Y-%m-%d %H:%M:%S')}；截止：{deadline.strftime('%Y-%m-%d')}；剩余 {days_remaining} 天"
        alert = ComplianceAlert(
            tenant_id=tenant_id,
            alert_type="deadline",
            severity=severity,
            title=title,
            description=desc,
            actor_id=p.user_id,
            actor_role="pharma_rep",
            entity_type="pharma_rep_profile",
            entity_id=p.id,
            deadline_at=deadline,
            days_remaining=days_remaining,
            status=status,
            is_compliance_critical=1 if severity == "critical" else 0,
        )
        db.add(alert)
        new_alerts += 1

    # 处理 revoke_scheduled
    for p in profiles_revoke:
        if p.revoke_scheduled_at is None:
            continue
        deadline = p.revoke_scheduled_at
        days_remaining = (deadline - now).days
        if days_remaining < 0:
            severity = "critical"
            overdue += 1
        elif days_remaining <= 7:
            severity = "high"
            upcoming += 1
        else:
            continue
        key = (p.user_id, "expiry", p.id)
        if key in existing_keys:
            continue
        title = f"医药代表(user_id={p.user_id})备案撤销 30 日时效预警"
        desc = f"撤销计划时间：{deadline.strftime('%Y-%m-%d')}；剩余 {days_remaining} 天（第 17 条要求 30 日内完成）"
        alert = ComplianceAlert(
            tenant_id=tenant_id,
            alert_type="expiry",
            severity=severity,
            title=title,
            description=desc,
            actor_id=p.user_id,
            actor_role="pharma_rep",
            entity_type="pharma_rep_profile",
            entity_id=p.id,
            deadline_at=deadline,
            days_remaining=days_remaining,
            status="open",
            is_compliance_critical=1 if severity == "critical" else 0,
        )
        db.add(alert)
        new_alerts += 1

    db.commit()
    return {
        "scanned": len(profiles_change) + len(profiles_revoke),
        "new_alerts": new_alerts,
        "upcoming_expires": upcoming,
        "overdue": overdue,
    }


# ──────────────────────────────────────────────
# 学术活动发起前的上岗准入强制校验
# ──────────────────────────────────────────────

def check_onboarding_gate(
    db: Session, tenant_id: str, user_id: int,
    raise_on_fail: bool = False,
) -> dict:
    """学术活动发起前的上岗准入强制校验

    对应《医药代表管理办法》第 9、10 条：
    医药代表上岗前必须完成"合规培训+考核合格+承诺书签署"三件套。
    若未完成三件套，不得发起学术活动。
    """
    result = check_onboarding_ready(db, tenant_id, user_id)
    if not result["ready"] and raise_on_fail:
        missing_desc = ", ".join(result.get("missing", []))
        raise ValidationError(
            f"医药代表上岗准入校验未通过：缺少 {missing_desc}。"
            f"对应《医药代表管理办法》第 9、10 条培训-考核-承诺闭环。"
        )
    return {
        "ready": result["ready"],
        "missing": result.get("missing", []),
        "details": result.get("details", {}),
    }
