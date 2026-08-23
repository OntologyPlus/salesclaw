"""合规管理 API（v2.1 合规适配，对应《医药代表管理办法》2026-08-01 施行）

提供：
- 医药代表资质档案管理（第 14-18 条备案管理）
- 合规承诺书签署闭环（第 9、10、15 条培训考核承诺）
- 链式证据 AuditLog 校验（第 26 条全过程留痕）
- 22 项禁止行为清单查询（第 11、12、24、25 条）
- 30 日时效预警（第 17 条备案变更/停止授权 30 日内）
"""
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List

from core.response import unified_response
from core.exceptions import ValidationError
from middleware.auth import get_current_user, require_permission
from database import User, get_db
from services import compliance_service

router = APIRouter(prefix="/compliance")


# ──────────────────────────────────────────────
# 请求模型
# ──────────────────────────────────────────────

class ProfileUpdateRequest(BaseModel):
    id_card_type: Optional[str] = None
    id_card_no: Optional[str] = None
    gender: Optional[str] = None
    photo_url: Optional[str] = None
    education_level: Optional[str] = Field(None, description="学历：大专/本科/硕士/博士")
    major: Optional[str] = Field(None, description="所学专业")
    contract_start: Optional[str] = None
    contract_end: Optional[str] = None
    drug_categories: Optional[List[str]] = None
    therapeutic_areas: Optional[List[str]] = None
    authorized_regions: Optional[List[str]] = None
    authenticity_statement: Optional[str] = None
    has_bribery_record: Optional[bool] = None
    bribery_record_detail: Optional[str] = None


class CommitmentSignRequest(BaseModel):
    commitment_type: str = Field(..., description="onboarding/annual/specific")
    commitment_text: str = Field(..., description="承诺书正文")
    version: str = Field(..., description="承诺书版本号")
    course_id: Optional[int] = Field(None, description="关联的合规培训课程 ID")
    exam_record_id: Optional[int] = Field(None, description="关联的考核记录 ID")


class RevokeRequest(BaseModel):
    reason: str = Field(..., description="撤销原因")


# ──────────────────────────────────────────────
# 医药代表资质档案（第 14-18 条备案管理）
# ──────────────────────────────────────────────

@router.get("/profile/{user_id}")
async def get_profile(
    user_id: int,
    current_user: User = Depends(require_permission("compliance.read")),
    db: Session = Depends(get_db),
):
    """获取医药代表资质档案

    只读：档案不存在时返回虚拟草稿（不落库），首次编辑时由
    PUT /profile 建档。GET 请求不应产生写事务（SQLite 写锁问题）。
    """
    profile = compliance_service.get_profile(db, current_user.tenant_id, user_id)
    if profile is None:
        profile = compliance_service.PharmaRepProfile(
            tenant_id=current_user.tenant_id,
            user_id=user_id,
            registration_status="draft",
        )
    return unified_response(compliance_service._serialize_profile(profile))


@router.put("/profile/{user_id}")
async def update_profile(
    user_id: int,
    body: ProfileUpdateRequest,
    current_user: User = Depends(require_permission("compliance.write")),
    db: Session = Depends(get_db),
):
    """更新医药代表资质档案（触发 30 日变更时效预警）

    对应第 17 条：医药代表已备案的信息有变更的，药品上市许可持有人应当在 30 日内完成备案信息变更。
    """
    # 当前用户作为操作者（actor），角色从 Role 表查询
    actor_role = compliance_service.get_user_role(db, current_user.id)
    data = body.model_dump(exclude_none=True)

    # 处理 contract_start/end 字符串转 date
    if "contract_start" in data and isinstance(data["contract_start"], str):
        from datetime import date
        try:
            data["contract_start"] = date.fromisoformat(data["contract_start"])
        except ValueError:
            raise ValidationError("contract_start 格式应为 YYYY-MM-DD")
    if "contract_end" in data and isinstance(data["contract_end"], str):
        from datetime import date
        try:
            data["contract_end"] = date.fromisoformat(data["contract_end"])
        except ValueError:
            raise ValidationError("contract_end 格式应为 YYYY-MM-DD")
    if "has_bribery_record" in data:
        data["has_bribery_record"] = 1 if data["has_bribery_record"] else 0

    result = compliance_service.update_profile(
        db, current_user.tenant_id, user_id,
        actor_id=current_user.id, actor_role=actor_role, data=data,
    )
    return unified_response(result)


@router.post("/profile/{user_id}/submit-registration")
async def submit_registration(
    user_id: int,
    current_user: User = Depends(require_permission("compliance.write")),
    db: Session = Depends(get_db),
):
    """提交备案（生成备案号）

    对应第 16 条：取得具有唯一备案号的医药代表备案信息表。
    本系统生成临时备案号（前缀 PR-），实际备案号需同步至国家药监局备案平台。
    """
    actor_role = compliance_service.get_user_role(db, current_user.id)
    result = compliance_service.submit_registration(
        db, current_user.tenant_id, user_id,
        actor_id=current_user.id, actor_role=actor_role,
    )
    return unified_response(result)


@router.post("/profile/{user_id}/revoke")
async def revoke_registration(
    user_id: int,
    body: RevokeRequest,
    current_user: User = Depends(require_permission("compliance.write")),
    db: Session = Depends(get_db),
):
    """撤销备案（停止授权，30 日内删除）

    对应第 17 条：对不再从事相关工作或者停止授权的医药代表，应当在 30 日内删除其备案信息。
    对应第 26 条：终止授权 + 删除备案 + 公示。
    """
    actor_role = compliance_service.get_user_role(db, current_user.id)
    result = compliance_service.revoke_registration(
        db, current_user.tenant_id, user_id,
        actor_id=current_user.id, actor_role=actor_role,
        reason=body.reason,
    )
    return unified_response(result)


@router.get("/pending-revokes")
async def list_pending_revokes(
    current_user: User = Depends(require_permission("compliance.read")),
    db: Session = Depends(get_db),
):
    """查询待删除备案（30 日时效预警）

    Returns:
        [{"profile_id": N, "user_id": N, "registration_no": "...",
          "revoke_scheduled_at": "...", "days_left": N}, ...]
    """
    result = compliance_service.list_pending_revokes(db, current_user.tenant_id)
    return unified_response(result)


# ──────────────────────────────────────────────
# 合规承诺书签署闭环（第 9、10、15 条）
# ──────────────────────────────────────────────

@router.post("/commitment/sign")
async def sign_commitment(
    body: CommitmentSignRequest,
    request: Request,
    current_user: User = Depends(require_permission("compliance.write")),
    db: Session = Depends(get_db),
):
    """签署合规承诺书（培训-考核-承诺闭环的最后一环）

    对应：
    - 第 9 条：建立培训考核制度
    - 第 10 条：经培训并考核合格
    - 第 15 条第（八）项：合规承诺书
    """
    signer_ip = request.client.host if request.client else None
    signer_ua = request.headers.get("user-agent", "")

    result = compliance_service.sign_commitment(
        db, current_user.tenant_id, current_user.id,
        commitment_type=body.commitment_type,
        commitment_text=body.commitment_text,
        version=body.version,
        course_id=body.course_id,
        exam_record_id=body.exam_record_id,
        signer_ip=signer_ip,
        signer_ua=signer_ua,
    )
    return unified_response(result)


@router.get("/onboarding-check/{user_id}")
async def check_onboarding(
    user_id: int,
    current_user: User = Depends(require_permission("compliance.read")),
    db: Session = Depends(get_db),
):
    """检查医药代表上岗三件套是否齐备

    闭环校验：合规培训 + 考核合格 + 承诺书签署
    """
    result = compliance_service.check_onboarding_ready(db, current_user.tenant_id, user_id)
    return unified_response(result)


# ──────────────────────────────────────────────
# 链式证据 AuditLog（第 26 条）
# ──────────────────────────────────────────────

@router.get("/audit-chain/verify")
async def verify_audit_chain(
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(require_permission("compliance.read")),
    db: Session = Depends(get_db),
):
    """验证 AuditLog 链式证据完整性

    逐条重算 record_hash，与存储的 hash 比对，识别被篡改的记录。
    对应第 26 条全过程留痕 + 不可篡改证据链。
    """
    result = compliance_service.verify_audit_log_chain(db, current_user.tenant_id, limit=limit)
    return unified_response(result)


# ──────────────────────────────────────────────
# 22 项禁止行为清单（第 11、12、24、25 条）
# ──────────────────────────────────────────────

@router.get("/forbidden-behaviors")
async def list_forbidden_behaviors(
    subject: Optional[str] = Query(None, description="主体过滤：持有人/CSO/医药代表/医疗机构"),
    current_user: User = Depends(require_permission("compliance.read")),
):
    """查询 22 项禁止行为清单

    对应：
    - 第 11 条：持有人 4 项禁止行为
    - 第 12 条：CSO 4 项禁止行为
    - 第 24 条：医药代表 9 项禁止行为
    - 第 25 条：医疗机构 5 项禁止行为
    """
    result = compliance_service.list_forbidden_behaviors(subject=subject)
    return unified_response(result)


@router.get("/forbidden-tools")
async def list_forbidden_tools(
    current_user: User = Depends(require_permission("compliance.read")),
):
    """查询医药代表角色禁止调用的工具清单

    对应第 11 条第（三）项 + 第 24 条第（三）项：
    医药代表不得承担药品销售任务，禁止调用 ROI/KPI/积分等销售工具。
    """
    return unified_response({
        "role": compliance_service.PHARMA_REP_ROLE_CODE,
        "forbidden_tools": sorted(compliance_service.FORBIDDEN_TOOLS_FOR_PHARMA_REP),
        "article_reference": "第 11 条第（三）项 + 第 24 条第（三）项",
        "description": "医药代表不得承担药品销售任务，实施收款和处理购销票据等销售行为",
    })


# ──────────────────────────────────────────────
# v2.2 Phase 2 扩展：22 项规则 + 违规事件 + 合规预警 + 30 日时效
# ──────────────────────────────────────────────

@router.get("/violation-rules")
async def list_violation_rules(
    subject: Optional[str] = Query(None, description="按主体过滤：持有人/CSO/医药代表/医疗机构"),
    active_only: bool = Query(True),
    effective_at: Optional[str] = Query(None, description="F5 历史回放时间点，格式 YYYY-MM-DD"),
    tenant_id: Optional[str] = Query(None, description="租户 ID；默认 None=仅全局基线，传值=基线+该租户覆盖"),
    user: User = Depends(require_permission("compliance.read")),
    db: Session = Depends(get_db),
):
    """查询 22 项禁止行为规则

    F5 增强：传入 effective_at 时进入历史回放模式，返回当时生效的规则版本。
    基线+覆盖模型：传入 tenant_id 时返回「全局基线 + 该租户覆盖」合并后的生效规则。
    """
    from datetime import datetime as _dt
    eff_date = None
    if effective_at:
        try:
            eff_date = _dt.strptime(effective_at, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError("effective_at 格式应为 YYYY-MM-DD")
    return unified_response(
        compliance_service.list_violation_rules(db, subject, active_only, eff_date, tenant_id)
    )


@router.get("/violation-rules/{code}")
async def get_violation_rule(
    code: str,
    user: User = Depends(require_permission("compliance.read")),
    db: Session = Depends(get_db),
):
    """查询单条违规规则"""
    result = compliance_service.get_violation_rule(db, code)
    if not result:
        from core.exceptions import NotFoundError
        raise NotFoundError("规则不存在")
    return unified_response(result)


@router.get("/violation-events")
async def list_violation_events(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("compliance.read")),
    db: Session = Depends(get_db),
):
    """违规事件列表"""
    return unified_response(
        compliance_service.list_violation_events(
            db, user.tenant_id, status, severity, page, page_size,
        )
    )


class HandleViolationRequest(BaseModel):
    result: str
    status: str = "resolved"


@router.post("/violation-events/{event_id}/handle")
async def handle_violation_event(
    event_id: int,
    req: HandleViolationRequest,
    user: User = Depends(require_permission("compliance.write")),
    db: Session = Depends(get_db),
):
    """处置违规事件"""
    return unified_response(
        compliance_service.handle_violation_event(
            db, user.tenant_id, event_id, user.id, req.result, req.status,
        )
    )


@router.get("/alerts")
async def list_alerts(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("compliance.read")),
    db: Session = Depends(get_db),
):
    """合规预警列表"""
    return unified_response(
        compliance_service.list_alerts(
            db, user.tenant_id, status, severity, alert_type, page, page_size,
        )
    )


class HandleAlertRequest(BaseModel):
    result: str
    status: str = "resolved"


@router.post("/alerts/{alert_id}/handle")
async def handle_alert(
    alert_id: int,
    req: HandleAlertRequest,
    user: User = Depends(require_permission("compliance.write")),
    db: Session = Depends(get_db),
):
    """处置合规预警"""
    return unified_response(
        compliance_service.handle_alert(
            db, user.tenant_id, alert_id, user.id, req.result, req.status,
        )
    )


@router.post("/deadlines/scan")
async def scan_deadlines(
    user: User = Depends(require_permission("compliance.write")),
    db: Session = Depends(get_db),
):
    """扫描 30 日时效预警（备案变更/停止授权）

    对应第 17 条：信息变更/停止授权 30 日内完成。
    扫描即将到期（≤7 日）或已到期的备案变更/撤销任务，自动生成 ComplianceAlert。
    """
    return unified_response(
        compliance_service.scan_deadline_alerts(db, user.tenant_id)
    )


@router.get("/onboarding-gate/{user_id}")
async def check_onboarding_gate(
    user_id: int,
    user: User = Depends(require_permission("compliance.read")),
    db: Session = Depends(get_db),
):
    """学术活动发起前的上岗准入强制校验

    对应第 9、10 条：医药代表上岗前必须完成"合规培训+考核合格+承诺书签署"三件套。
    若未完成三件套，不得发起学术活动。
    """
    return unified_response(
        compliance_service.check_onboarding_gate(
            db, user.tenant_id, user_id, raise_on_fail=False,
        )
    )


# ──────────────────────────────────────────────
# F4.6: 绩效边界策略管理（借鉴企业级诊断体系 §10.3）
# ──────────────────────────────────────────────

class PerformancePolicyUpdateRequest(BaseModel):
    allow_link_performance: int = Field(..., description="0=禁止联动绩效，1=允许")
    description: Optional[str] = None


@router.get("/performance-policies")
async def list_performance_policies(
    user: User = Depends(require_permission("compliance.read")),
    db: Session = Depends(get_db),
):
    """列出所有绩效边界策略

    返回每个 action_type 是否允许联动绩效。
    默认策略：
    - 允许联动：visit_overdue / feedback_refused / plan_not_submitted / approval_overdue / complete_visit / positive_feedback
    - 禁止联动：light_color_change / business_result_not_achieved / ai_auto_judgment / rule_violation
    """
    from core.performance_policy import list_policies
    return unified_response(list_policies(db, user.tenant_id))


@router.get("/performance-policies/{action_type}")
async def get_performance_policy(
    action_type: str,
    user: User = Depends(require_permission("compliance.read")),
    db: Session = Depends(get_db),
):
    """查询单个绩效边界策略"""
    from core.performance_policy import get_policy
    policy = get_policy(db, user.tenant_id, action_type)
    if not policy:
        raise ValidationError(f"策略 {action_type} 不存在")
    return unified_response(policy)


@router.put("/performance-policies/{action_type}")
async def update_performance_policy(
    action_type: str,
    body: PerformancePolicyUpdateRequest,
    user: User = Depends(require_permission("compliance.write")),
    db: Session = Depends(get_db),
):
    """更新绩效边界策略（运行时调整，无需重启）

    允许运维在不重启服务的情况下，调整某个 action_type 是否允许联动绩效。
    所有调整操作自动写入 AuditLog（由 audit 中间件捕获）。
    """
    from core.performance_policy import update_policy
    updated = update_policy(
        db, user.tenant_id, action_type,
        allow=body.allow_link_performance,
        user_id=user.id,
        description=body.description,
    )
    if not updated:
        raise ValidationError(f"策略 {action_type} 不存在")
    return unified_response(updated)


# ──────────────────────────────────────────────
# F5: 规则版本化管理（借鉴企业级诊断体系 §6.5、§7.4）
# 生命周期：draft → shadow → (pre-check) → published → retired
# ──────────────────────────────────────────────

class RuleDraftCreateRequest(BaseModel):
    code: str = Field(..., description="规则代码，如 A24_3")
    article: Optional[str] = None
    subject: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    trigger_scenes: Optional[List[str]] = None
    check_type: Optional[str] = None
    check_config: Optional[dict] = None


class ShadowRunStartRequest(BaseModel):
    baseline_rule_id: int = Field(..., description="基准版本 ID（通常为当前 published 版本）")
    sample_size: int = Field(100, ge=10, le=500)


class PromoteRuleRequest(BaseModel):
    reason: Optional[str] = None


class RollbackRuleRequest(BaseModel):
    to_version: str = Field(..., description="回滚到的目标版本号，如 1.0.0")
    reason: Optional[str] = None


@router.post("/rules")
async def create_rule_draft(
    body: RuleDraftCreateRequest,
    user: User = Depends(require_permission("compliance.write")),
    db: Session = Depends(get_db),
):
    """创建规则草稿版本（draft 状态）

    若 code 已存在 published 版本，则 parent_rule_id 指向它，version 自增 minor。
    """
    from services import rule_version_service
    draft = rule_version_service.create_rule_draft(
        db, user.tenant_id, body.code,
        body.model_dump(exclude_none=True),
        actor_id=user.id,
    )
    return unified_response(compliance_service._serialize_violation_rule(draft))


@router.post("/rules/{rule_id}/pre-check")
async def pre_check_rule(
    rule_id: int,
    user: User = Depends(require_permission("compliance.write")),
    db: Session = Depends(get_db),
):
    """发布前自动检查（重复决策行/单位错误/灯色重复映射等）"""
    from services import rule_version_service
    return unified_response(rule_version_service.publish_pre_check(db, rule_id))


@router.post("/rules/{rule_id}/shadow-run")
async def start_shadow_run(
    rule_id: int,
    body: ShadowRunStartRequest,
    user: User = Depends(require_permission("compliance.write")),
    db: Session = Depends(get_db),
):
    """启动影子运行：用最近 N 条 AuditLog 事件对比新版本与基准版本命中数差异"""
    from services import rule_version_service
    shadow_run = rule_version_service.start_shadow_run(
        db, rule_id, body.baseline_rule_id,
        user.tenant_id, user.id, body.sample_size,
    )
    return unified_response(_serialize_shadow_run(shadow_run))


@router.get("/rules/shadow-runs/{run_id}")
async def get_shadow_run(
    run_id: int,
    user: User = Depends(require_permission("compliance.read")),
    db: Session = Depends(get_db),
):
    """查询影子运行结果"""
    from services import rule_version_service
    sr = rule_version_service.get_shadow_run(db, run_id)
    if not sr:
        raise ValidationError(f"影子运行 {run_id} 不存在")
    return unified_response(_serialize_shadow_run(sr))


@router.post("/rules/{rule_id}/promote")
async def promote_rule(
    rule_id: int,
    body: PromoteRuleRequest,
    user: User = Depends(require_permission("compliance.write")),
    db: Session = Depends(get_db),
):
    """提升草稿/影子运行版本为正式版本（旧版本自动 retired）"""
    from services import rule_version_service
    promoted = rule_version_service.promote_rule(
        db, rule_id, user.tenant_id, user.id, body.reason or "",
    )
    return unified_response(compliance_service._serialize_violation_rule(promoted))


@router.post("/rules/{code}/rollback")
async def rollback_rule(
    code: str,
    body: RollbackRuleRequest,
    user: User = Depends(require_permission("compliance.write")),
    db: Session = Depends(get_db),
):
    """回滚到指定历史版本（从 RuleVersionHistory 找到 snapshot，复制为新 published 版本）"""
    from services import rule_version_service
    rolled = rule_version_service.rollback_rule(
        db, code, body.to_version, user.tenant_id, user.id, body.reason or "",
    )
    return unified_response(compliance_service._serialize_violation_rule(rolled))


@router.get("/rules/{code}/versions")
async def list_rule_versions(
    code: str,
    user: User = Depends(require_permission("compliance.read")),
    db: Session = Depends(get_db),
):
    """列出某规则 code 的所有历史版本"""
    from services import rule_version_service
    return unified_response(
        rule_version_service.list_rule_versions(db, code, user.tenant_id)
    )


@router.get("/rules/diff")
async def get_version_diff(
    rule_id_a: int = Query(..., description="版本 A 的 rule_id"),
    rule_id_b: int = Query(..., description="版本 B 的 rule_id"),
    user: User = Depends(require_permission("compliance.read")),
    db: Session = Depends(get_db),
):
    """对比两个版本的字段差异"""
    from services import rule_version_service
    return unified_response(
        rule_version_service.get_version_diff(db, rule_id_a, rule_id_b)
    )


def _serialize_shadow_run(sr) -> dict:
    """序列化 RuleShadowRun"""
    return {
        "id": sr.id,
        "rule_code": sr.rule_code,
        "new_rule_id": sr.new_rule_id,
        "baseline_rule_id": sr.baseline_rule_id,
        "status": sr.status,
        "matched_count": sr.matched_count,
        "baseline_count": sr.baseline_count,
        "delta_count": sr.delta_count,
        "summary": sr.summary,
        "started_at": sr.started_at.isoformat() if sr.started_at else None,
        "completed_at": sr.completed_at.isoformat() if sr.completed_at else None,
        "sample_events": sr.sample_events_json or [],
    }


# ──────────────────────────────────────────────
# Phase 3 合规专项：公示 / 监管报送 / 年度审计
# 对应《医药代表管理办法》第 13 条（公示）、第 26 条（报送/留痕）、年度审计
# ──────────────────────────────────────────────

from services import phase3_compliance_service as p3  # noqa: E402


# --- 公示 ---

class PublicDisclosureCreateRequest(BaseModel):
    category: str = Field(..., description="violation_disposal/registration_anomaly/commitment_breach")
    title: str
    content: dict = Field(default_factory=dict)
    ref_type: Optional[str] = None
    ref_id: Optional[int] = None
    disclosed_level: str = "internal"
    expired_at: Optional[str] = None  # ISO 字符串


@router.post("/public-disclosures")
async def create_public_disclosure(
    body: PublicDisclosureCreateRequest,
    user: User = Depends(require_permission("compliance.write")),
    db: Session = Depends(get_db),
):
    """登记合规公示（默认草稿态）"""
    expired = None
    if body.expired_at:
        from datetime import datetime as _dt
        expired = _dt.fromisoformat(body.expired_at)
    disclosure = p3.create_public_disclosure(
        db, user.tenant_id, body.category, body.title, body.content,
        body.ref_type, body.ref_id, body.disclosed_level, user.id, expired,
    )
    return unified_response(p3._serialize_disclosure(disclosure))


@router.post("/public-disclosures/{disclosure_id}/publish")
async def publish_public_disclosure(
    disclosure_id: int,
    user: User = Depends(require_permission("compliance.write")),
    db: Session = Depends(get_db),
):
    """发布公示（草稿 → 对外公示）"""
    d = p3.publish_public_disclosure(db, user.tenant_id, disclosure_id, user.id)
    return unified_response(p3._serialize_disclosure(d))


@router.get("/public-disclosures")
async def list_public_disclosures(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    disclosed_level: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("compliance.read")),
    db: Session = Depends(get_db),
):
    """公示列表（租户隔离）"""
    return unified_response(
        p3.list_public_disclosures(
            db, user.tenant_id, category, status, disclosed_level, page, page_size,
        )
    )


# --- 监管报送 ---

class RegulatorySubmissionCreateRequest(BaseModel):
    period_type: str = Field(..., description="year/quarter/month")
    period_value: str = Field(..., description="如 2026 / 2026-Q2 / 2026-08")
    submission_type: str = Field(..., description="violation_summary/activity_summary/annual")
    format: str = "json"


@router.post("/regulatory-submissions")
async def create_regulatory_submission(
    body: RegulatorySubmissionCreateRequest,
    user: User = Depends(require_permission("compliance.write")),
    db: Session = Depends(get_db),
):
    """生成监管报送数据包（待报送）"""
    sub = p3.create_regulatory_submission(
        db, user.tenant_id, body.period_type, body.period_value,
        body.submission_type, body.format, user.id,
    )
    return unified_response({
        "id": sub.id, "period_type": sub.period_type, "period_value": sub.period_value,
        "submission_type": sub.submission_type, "status": sub.status,
        "payload": sub.payload,
    })


@router.get("/regulatory-submissions")
async def list_regulatory_submissions(
    period_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("compliance.read")),
    db: Session = Depends(get_db),
):
    """监管报送记录列表"""
    return unified_response(
        p3.list_regulatory_submissions(
            db, user.tenant_id, period_type, status, page, page_size,
        )
    )


@router.post("/regulatory-submissions/{submission_id}/submit")
async def submit_regulatory_submission(
    submission_id: int,
    external_ref: Optional[str] = Query(None, description="监管平台回执号"),
    user: User = Depends(require_permission("compliance.write")),
    db: Session = Depends(get_db),
):
    """标记已报送（记录回执号）"""
    s = p3.mark_submission_submitted(db, user.tenant_id, submission_id, external_ref, user.id)
    return unified_response({"id": s.id, "status": s.status, "external_ref": s.external_ref})


@router.get("/regulatory-submissions/preview")
async def preview_regulatory_submission(
    period_type: str = Query(..., description="year/quarter/month"),
    period_value: str = Query(..., description="如 2026 / 2026-Q2 / 2026-08"),
    submission_type: str = Query("violation_summary"),
    user: User = Depends(require_permission("compliance.read")),
    db: Session = Depends(get_db),
):
    """仅预览报送数据包，不落库（用于导出前确认）"""
    payload = p3.build_submission_payload(
        db, user.tenant_id, period_type, period_value, submission_type,
    )
    return unified_response(payload)


@router.get("/regulatory-submissions/{submission_id}/export")
async def export_regulatory_submission(
    submission_id: int,
    fmt: str = Query("json", description="json/csv"),
    user: User = Depends(require_permission("compliance.read")),
    db: Session = Depends(get_db),
):
    """导出报送数据包为文件（json/csv 下载）。"""
    from database import RegulatorySubmission
    s = db.query(RegulatorySubmission).filter(
        RegulatorySubmission.tenant_id == user.tenant_id,
        RegulatorySubmission.is_deleted == 0,
        RegulatorySubmission.id == submission_id,
    ).first()
    if not s:
        raise ValidationError("报送记录不存在")
    out = p3.export_submission(s, fmt)
    media = "application/json" if out["format"] == "json" else "text/csv"
    return Response(
        content=out["content"],
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{out["filename"]}"'},
    )


@router.post("/regulatory-submissions/{submission_id}/push-external")
async def push_regulatory_submission_external(
    submission_id: int,
    user: User = Depends(require_permission("compliance.write")),
    db: Session = Depends(get_db),
):
    """推送报送数据包至外部监管平台（未配置端点则 dry-run 占位回执）。"""
    result = p3.push_submission_external(db, user.tenant_id, submission_id, user.id)
    return unified_response(result)


# --- 年度合规审计 ---

@router.post("/annual-audit/{year}")
async def generate_annual_audit(
    year: int,
    scope: Optional[str] = Query(None),
    user: User = Depends(require_permission("compliance.write")),
    db: Session = Depends(get_db),
):
    """生成指定年度合规审计聚合（基于证据链 + 违规 + 公示）"""
    audit = p3.generate_annual_audit(db, user.tenant_id, year, scope, user.id)
    return unified_response({
        "id": audit.id,
        "year": audit.year,
        "scope": audit.scope,
        "metrics": audit.metrics,
        "chain_integrity": audit.chain_integrity,
        "conclusion": audit.conclusion,
        "audited_at": audit.audited_at.strftime("%Y-%m-%d %H:%M:%S") if audit.audited_at else None,
    })


@router.get("/annual-audits")
async def list_annual_audits(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("compliance.read")),
    db: Session = Depends(get_db),
):
    """年度合规审计列表"""
    return unified_response(
        p3.list_annual_audits(db, user.tenant_id, page, page_size)
    )
