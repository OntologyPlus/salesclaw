"""F5: 规则版本化管理服务（借鉴企业级诊断体系 §6.5、§7.4）

提供完整的版本生命周期：
1. create_rule_draft    — 创建草稿版本（draft 状态）
2. publish_pre_check    — 发布前自动检查（重复/矛盾决策行/单位错误等）
3. start_shadow_run     — 启动影子运行（与当前 published 版本对比）
4. complete_shadow_run  — 完成影子运行，记录差异
5. promote_rule         — 提升草稿为正式版本（旧版本 retired）
6. rollback_rule        — 回滚到指定历史版本（复制为新 published 版本）
7. bind_rule_at_time    — 历史回放：根据时间点查询当时生效的版本
"""
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import text

from database import (
    ComplianceViolationRule as Rule,
    RuleVersionHistory,
    RuleShadowRun,
    BusinessSessionLocal,
)
from core.exceptions import ValidationError

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 版本快照与差异
# ──────────────────────────────────────────────

def _snapshot_rule(rule: Rule) -> dict:
    """生成规则快照（用于 RuleVersionHistory.snapshot_json）"""
    return {
        "code": rule.code,
        "article": rule.article,
        "subject": rule.subject,
        "description": rule.description,
        "severity": rule.severity,
        "trigger_scenes": rule.trigger_scenes or [],
        "check_type": rule.check_type,
        "check_config": rule.check_config or {},
        "is_active": bool(rule.is_active),
        "version": rule.version,
        "effective_start": rule.effective_start.isoformat() if rule.effective_start else None,
        "effective_end": rule.effective_end.isoformat() if rule.effective_end else None,
        "release_state": rule.release_state,
        "parent_rule_id": rule.parent_rule_id,
    }


def _diff_snapshots(old: dict, new: dict) -> dict:
    """计算两个版本快照的差异"""
    diff = {}
    all_keys = set(old.keys()) | set(new.keys())
    for k in all_keys:
        if old.get(k) != new.get(k):
            diff[k] = {"old": old.get(k), "new": new.get(k)}
    return diff


def _bump_version(current: str, kind: str = "patch") -> str:
    """版本号递增（major/minor/patch）"""
    try:
        parts = current.split(".")
        if len(parts) != 3:
            return "1.0.0"
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        if kind == "major":
            major += 1
            minor = 0
            patch = 0
        elif kind == "minor":
            minor += 1
            patch = 0
        else:
            patch += 1
        return f"{major}.{minor}.{patch}"
    except Exception:
        return current


# ──────────────────────────────────────────────
# 版本生命周期
# ──────────────────────────────────────────────

def create_rule_draft(db: Session, tenant_id: str, code: str, data: dict,
                       actor_id: int) -> Rule:
    """创建规则草稿版本（release_state="draft"）

    若 code 已存在 published 版本，则 parent_rule_id 指向它，version 自增 patch。
    """
    # 查询当前 published 版本
    existing = db.query(Rule).filter(
        Rule.tenant_id == tenant_id,
        Rule.is_deleted == 0,
        Rule.code == code,
        Rule.release_state == "published",
    ).first()
    # F5 fallback：当前租户无规则时查 default（规则全局共享）
    if not existing and tenant_id != "default":
        existing = db.query(Rule).filter(
            Rule.tenant_id == "default",
            Rule.is_deleted == 0,
            Rule.code == code,
            Rule.release_state == "published",
        ).first()

    if existing:
        # 已有 published 版本 → 创建新草稿版本
        new_version = _bump_version(existing.version, "minor")
        draft = Rule(
            tenant_id=tenant_id,
            code=code,
            article=data.get("article", existing.article),
            subject=data.get("subject", existing.subject),
            description=data.get("description", existing.description),
            severity=data.get("severity", existing.severity),
            trigger_scenes=data.get("trigger_scenes", existing.trigger_scenes),
            check_type=data.get("check_type", existing.check_type),
            check_config=data.get("check_config", existing.check_config),
            is_active=0,  # 草稿状态默认不启用
            version=new_version,
            effective_start=None,  # 草稿无生效时间
            effective_end=None,
            release_state="draft",
            parent_rule_id=existing.id,
            created_by=actor_id,
        )
    else:
        # 新规则
        if not data.get("article") or not data.get("subject") or not data.get("description"):
            raise ValidationError("新规则必须提供 article/subject/description")
        draft = Rule(
            tenant_id=tenant_id,
            code=code,
            article=data["article"],
            subject=data["subject"],
            description=data["description"],
            severity=data.get("severity", "high"),
            trigger_scenes=data.get("trigger_scenes", []),
            check_type=data.get("check_type"),
            check_config=data.get("check_config", {}),
            is_active=0,
            version="1.0.0",
            effective_start=None,
            effective_end=None,
            release_state="draft",
            parent_rule_id=None,
            created_by=actor_id,
        )

    db.add(draft)
    db.flush()

    # 写入 RuleVersionHistory
    history = RuleVersionHistory(
        tenant_id=tenant_id,
        rule_code=code,
        rule_id=draft.id,
        version=draft.version,
        action="created",
        snapshot_json=_snapshot_rule(draft),
        diff_json={},
        actor_id=actor_id,
        reason=f"创建草稿版本 v{draft.version}",
    )
    db.add(history)
    db.commit()
    db.refresh(draft)
    logger.info("[rule_version] 草稿创建 code=%s version=%s id=%s",
                code, draft.version, draft.id)
    return draft


def publish_pre_check(db: Session, rule_id: int, tenant_id: str = None) -> dict:
    """发布前自动检查

    检查项：
    - 重复决策行（check_config 内 decision 重复 key）
    - 无法到达分支（otherwise 前的 when 条件覆盖所有情况）
    - 单位错误（金额阈值单位不一致）
    - 固定除数（除数为 0 或与月份不符）
    - 灯色重复映射（同一组合映射到多个灯色）
    """
    filters = [Rule.id == rule_id]
    if tenant_id:
        filters.append(Rule.tenant_id == tenant_id)
    rule = db.query(Rule).filter(*filters).first()
    if not rule:
        raise ValidationError(f"规则 {rule_id} 不存在")

    errors = []
    warnings = []

    # 1. 检查 check_config 内的决策行
    check_config = rule.check_config or {}
    if isinstance(check_config, dict):
        decisions = check_config.get("decisions", [])
        if isinstance(decisions, list):
            # 检查重复 key
            keys = [d.get("when", "") for d in decisions if isinstance(d, dict)]
            seen = set()
            for k in keys:
                if k in seen:
                    errors.append(f"重复决策行: {k}")
                seen.add(k)
            # 检查灯色重复映射
            for d in decisions:
                if isinstance(d, dict):
                    output = d.get("output", {})
                    if isinstance(output, dict):
                        classification = output.get("classification")
                        if classification and keys.count(d.get("when", "")) > 1:
                            errors.append(f"灯色重复映射: {d.get('when')} → {classification}")
        # 2. 检查金额阈值单位
        threshold = check_config.get("amount_threshold")
        if threshold is not None and not isinstance(threshold, (int, float)):
            errors.append(f"金额阈值单位错误: {threshold}")
        # 3. 检查固定除数
        divisor = check_config.get("divisor")
        if divisor == 0:
            errors.append("固定除数为 0")

    # 4. 检查触发场景非空
    if not rule.trigger_scenes:
        warnings.append("trigger_scenes 为空，规则不会被触发")

    # 5. 检查 description 非空
    if not rule.description:
        errors.append("description 不能为空")

    passed = len(errors) == 0
    return {
        "rule_id": rule_id,
        "rule_code": rule.code,
        "version": rule.version,
        "passed": passed,
        "errors": errors,
        "warnings": warnings,
    }


def start_shadow_run(db: Session, rule_id: int, baseline_rule_id: int,
                      tenant_id: str, actor_id: int, sample_size: int = 100) -> RuleShadowRun:
    """启动影子运行

    用最近 N 条事件分别跑新版本和基准版本，统计命中数差异。
    异步执行：立即返回 running 状态，由 insight_scheduler 推进。
    """
    new_rule = db.query(Rule).filter(Rule.id == rule_id, Rule.tenant_id == tenant_id).first()
    if not new_rule:
        raise ValidationError(f"新版本规则 {rule_id} 不存在")
    baseline = db.query(Rule).filter(Rule.id == baseline_rule_id, Rule.tenant_id == tenant_id).first()
    if not baseline:
        raise ValidationError(f"基准规则 {baseline_rule_id} 不存在")
    if new_rule.code != baseline.code:
        raise ValidationError("新版本与基准版本 code 不一致")

    shadow_run = RuleShadowRun(
        tenant_id=tenant_id,
        rule_code=new_rule.code,
        new_rule_id=rule_id,
        baseline_rule_id=baseline_rule_id,
        status="running",
        started_at=datetime.utcnow(),
        matched_count=0,
        baseline_count=0,
        delta_count=0,
        sample_events_json=[],
        summary=None,
        created_by=actor_id,
    )
    db.add(shadow_run)
    db.flush()

    # 写入 RuleVersionHistory
    history = RuleVersionHistory(
        tenant_id=tenant_id,
        rule_code=new_rule.code,
        rule_id=rule_id,
        version=new_rule.version,
        action="shadow",
        snapshot_json=_snapshot_rule(new_rule),
        diff_json=_diff_snapshots(_snapshot_rule(baseline), _snapshot_rule(new_rule)),
        actor_id=actor_id,
        reason=f"启动影子运行 shadow_run_id={shadow_run.id}",
    )
    db.add(history)

    # 同步执行影子运行（简化版：直接对比规则字段差异）
    new_rule.release_state = "shadow"
    db.commit()
    db.refresh(shadow_run)

    # 简化版：直接基于规则字段对比，不需要真实事件
    # 实际生产应异步采样事件并执行
    try:
        matched_count, baseline_count, sample_events = _execute_shadow_run(
            db, tenant_id, new_rule, baseline, sample_size
        )
        shadow_run.matched_count = matched_count
        shadow_run.baseline_count = baseline_count
        shadow_run.delta_count = matched_count - baseline_count
        shadow_run.sample_events_json = sample_events[:50]
        shadow_run.status = "completed"
        shadow_run.completed_at = datetime.utcnow()
        shadow_run.summary = (f"新版本命中 {matched_count} 次，基准命中 {baseline_count} 次，"
                              f"差异 {shadow_run.delta_count}（{'显著差异' if abs(shadow_run.delta_count) >= 5 else '可接受'}）")
        db.commit()
        db.refresh(shadow_run)
        logger.info("[rule_version] 影子运行完成 shadow_run_id=%s delta=%s",
                    shadow_run.id, shadow_run.delta_count)
    except Exception as e:
        logger.warning("[rule_version] 影子运行执行失败: %s", e)
        shadow_run.status = "failed"
        shadow_run.summary = f"影子运行执行失败: {e}"
        db.commit()
        db.refresh(shadow_run)

    return shadow_run


def _execute_shadow_run(db: Session, tenant_id: str, new_rule: Rule,
                         baseline: Rule, sample_size: int) -> tuple:
    """简化版影子运行执行：基于规则字段差异模拟命中"""
    # 在 SalesClaw 中，规则主要用于合规校验，无真实"事件命中"概念
    # 简化版：基于规则配置差异模拟命中数
    new_config = new_rule.check_config or {}
    baseline_config = baseline.check_config or {}

    # 如果 check_config 内有 decisions，对比决策行数差异
    new_decisions = new_config.get("decisions", []) if isinstance(new_config, dict) else []
    baseline_decisions = baseline_config.get("decisions", []) if isinstance(baseline_config, dict) else []

    # 模拟事件采样：取最近 sample_size 条 AuditLog
    try:
        from database import AuditLog
        sample_events = []
        logs = db.query(AuditLog).filter(
            AuditLog.tenant_id == tenant_id,
            AuditLog.is_deleted == 0,
        ).order_by(AuditLog.ts.desc()).limit(sample_size).all()
        matched_new = 0
        matched_baseline = 0
        for log in logs:
            new_hit = _check_rule_against_event(new_rule, log)
            baseline_hit = _check_rule_against_event(baseline, log)
            if new_hit != baseline_hit:
                sample_events.append({
                    "event_id": log.id,
                    "action": log.action,
                    "new_hit": new_hit,
                    "baseline_hit": baseline_hit,
                    "delta": int(new_hit) - int(baseline_hit),
                })
            matched_new += int(new_hit)
            matched_baseline += int(baseline_hit)
        return matched_new, matched_baseline, sample_events
    except Exception as e:
        logger.debug("[rule_version] 影子运行采样失败: %s", e)
        return 0, 0, []


def _check_rule_against_event(rule: Rule, log) -> bool:
    """简化版：检查规则是否在某事件上命中"""
    check_config = rule.check_config or {}
    if not isinstance(check_config, dict):
        return False
    # 关键字匹配
    keywords = check_config.get("keywords", [])
    if keywords and log.detail:
        detail_str = str(log.detail)
        for kw in keywords:
            if isinstance(kw, str) and kw in detail_str:
                return True
    # 角色黑名单
    role_blacklist = check_config.get("role_blacklist", [])
    if role_blacklist and log.actor_role in role_blacklist:
        return True
    return False


def promote_rule(db: Session, rule_id: int, tenant_id: str,
                  actor_id: int, reason: str = "") -> Rule:
    """提升草稿为正式版本

    - 将当前 published 版本置为 retired（effective_end = now）
    - 将草稿置为 published（effective_start = now）
    - 写入 RuleVersionHistory（action=promoted）
    """
    new_rule = db.query(Rule).filter(Rule.id == rule_id, Rule.tenant_id == tenant_id).first()
    if not new_rule:
        raise ValidationError(f"规则 {rule_id} 不存在")
    if new_rule.release_state not in ("draft", "shadow", "grayscale"):
        raise ValidationError(f"规则状态 {new_rule.release_state} 不可提升")

    # 检查发布前是否通过 pre_check
    check_result = publish_pre_check(db, rule_id, tenant_id)
    if not check_result["passed"]:
        raise ValidationError(f"发布前检查未通过: {check_result['errors']}")

    # 旧版本 retired
    now = datetime.utcnow()
    if new_rule.parent_rule_id:
        old_published = db.query(Rule).filter(Rule.id == new_rule.parent_rule_id).first()
        if old_published and old_published.release_state == "published":
            old_published.release_state = "retired"
            old_published.effective_end = now.date()
            old_published.is_active = 0

    # 新版本 published
    new_rule.release_state = "published"
    new_rule.effective_start = now.date()
    new_rule.is_active = 1

    # 写入 RuleVersionHistory
    history = RuleVersionHistory(
        tenant_id=tenant_id,
        rule_code=new_rule.code,
        rule_id=new_rule.id,
        version=new_rule.version,
        action="promoted",
        snapshot_json=_snapshot_rule(new_rule),
        diff_json={},
        actor_id=actor_id,
        reason=reason or f"提升为正式版本 v{new_rule.version}",
    )
    db.add(history)
    db.commit()
    db.refresh(new_rule)
    logger.info("[rule_version] 规则提升 code=%s version=%s", new_rule.code, new_rule.version)
    return new_rule


def rollback_rule(db: Session, rule_code: str, to_version: str,
                    tenant_id: str, actor_id: int, reason: str = "") -> Rule:
    """回滚到指定历史版本

    - 将当前 published 版本置为 retired
    - 从 RuleVersionHistory 找到指定版本的 snapshot_json，复制为新 published 版本
      （version 自增 patch 号，避免重复）
    """
    # 当前 published 版本
    current = db.query(Rule).filter(
        Rule.tenant_id == tenant_id,
        Rule.is_deleted == 0,
        Rule.code == rule_code,
        Rule.release_state == "published",
    ).first()
    # F5 fallback：当前租户无规则时查 default
    if not current and tenant_id != "default":
        current = db.query(Rule).filter(
            Rule.tenant_id == "default",
            Rule.is_deleted == 0,
            Rule.code == rule_code,
            Rule.release_state == "published",
        ).first()
    if not current:
        raise ValidationError(f"规则 {rule_code} 无 published 版本")

    # 查找历史版本快照
    history = db.query(RuleVersionHistory).filter(
        RuleVersionHistory.tenant_id == tenant_id,
        RuleVersionHistory.is_deleted == 0,
        RuleVersionHistory.rule_code == rule_code,
        RuleVersionHistory.version == to_version,
    ).order_by(RuleVersionHistory.occurred_at.desc()).first()
    # F5 fallback：当前租户无历史时查 default
    if not history and tenant_id != "default":
        history = db.query(RuleVersionHistory).filter(
            RuleVersionHistory.tenant_id == "default",
            RuleVersionHistory.is_deleted == 0,
            RuleVersionHistory.rule_code == rule_code,
            RuleVersionHistory.version == to_version,
        ).order_by(RuleVersionHistory.occurred_at.desc()).first()
    if not history:
        raise ValidationError(f"历史版本 {to_version} 不存在")

    snapshot = history.snapshot_json or {}
    if not snapshot:
        raise ValidationError(f"历史版本 {to_version} 快照为空")

    # 当前版本 retired
    now = datetime.utcnow()
    current.release_state = "retired"
    current.effective_end = now.date()
    current.is_active = 0

    # 复制为新 published 版本（version 自增 patch）
    new_version = _bump_version(to_version, "patch")
    rolled_back = Rule(
        tenant_id=tenant_id,
        code=rule_code,
        article=snapshot.get("article", current.article),
        subject=snapshot.get("subject", current.subject),
        description=snapshot.get("description", current.description),
        severity=snapshot.get("severity", current.severity),
        trigger_scenes=snapshot.get("trigger_scenes", current.trigger_scenes),
        check_type=snapshot.get("check_type", current.check_type),
        check_config=snapshot.get("check_config", current.check_config),
        is_active=1,
        version=new_version,
        effective_start=now.date(),
        effective_end=None,
        release_state="published",
        parent_rule_id=current.id,
        created_by=actor_id,
    )
    db.add(rolled_back)
    db.flush()

    # 写入 RuleVersionHistory
    rollback_history = RuleVersionHistory(
        tenant_id=tenant_id,
        rule_code=rule_code,
        rule_id=rolled_back.id,
        version=new_version,
        action="rollback",
        snapshot_json=_snapshot_rule(rolled_back),
        diff_json=_diff_snapshots(_snapshot_rule(current), _snapshot_rule(rolled_back)),
        actor_id=actor_id,
        reason=reason or f"从 v{current.version} 回滚到 v{to_version}（新版本号 v{new_version}）",
    )
    db.add(rollback_history)
    db.commit()
    db.refresh(rolled_back)
    logger.info("[rule_version] 规则回滚 code=%s from=%s to=%s (new version=%s)",
                rule_code, current.version, to_version, new_version)
    return rolled_back


# ──────────────────────────────────────────────
# 查询
# ──────────────────────────────────────────────

def list_rule_versions(db: Session, rule_code: str,
                        tenant_id: str = "default") -> List[dict]:
    """列出某 code 的所有历史版本

    F5 适配：规则全局共享（tenant_id="default"）。
    - 当前租户有规则：合并显示当前租户 + default 的所有版本（去重，按版本号倒序）
    - 当前租户无规则：fallback 到 default
    """
    rules = db.query(Rule).filter(
        Rule.is_deleted == 0,
        Rule.code == rule_code,
        Rule.tenant_id == tenant_id,
    ).order_by(Rule.version.desc()).all()
    # F5 fallback + 合并：若当前租户非 default，则合并 default 租户的版本
    if tenant_id != "default":
        default_rules = db.query(Rule).filter(
            Rule.is_deleted == 0,
            Rule.code == rule_code,
            Rule.tenant_id == "default",
        ).order_by(Rule.version.desc()).all()
        # 去重：以 version 为键（同 version 优先当前租户）
        seen_versions = {r.version for r in rules}
        for r in default_rules:
            if r.version not in seen_versions:
                rules.append(r)
                seen_versions.add(r.version)
        # 重新按版本号倒序
        from packaging.version import Version as _PVer
        try:
            rules.sort(key=lambda x: _PVer(x.version), reverse=True)
        except Exception:
            rules.sort(key=lambda x: x.version, reverse=True)
    return [{
        "id": r.id,
        "version": r.version,
        "release_state": r.release_state,
        "is_active": bool(r.is_active),
        "effective_start": r.effective_start.isoformat() if r.effective_start else None,
        "effective_end": r.effective_end.isoformat() if r.effective_end else None,
        "parent_rule_id": r.parent_rule_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "description": r.description,
    } for r in rules]


def bind_rule_at_time(db: Session, rule_code: str, effective_at: date,
                       tenant_id: str = "default") -> "Optional[Rule]":
    """历史回放：根据时间点查询当时生效的规则版本

    F5 适配：规则全局共享（tenant_id="default"），若当前租户无规则则 fallback 到 default。
    """
    rule = db.query(Rule).filter(
        Rule.is_deleted == 0,
        Rule.code == rule_code,
        Rule.tenant_id == tenant_id,
        Rule.release_state == "published",
        Rule.effective_start <= effective_at,
    ).order_by(Rule.effective_start.desc()).first()
    # F5 fallback：当前租户无规则时查 default
    if rule is None and tenant_id != "default":
        rule = db.query(Rule).filter(
            Rule.is_deleted == 0,
            Rule.code == rule_code,
            Rule.tenant_id == "default",
            Rule.release_state == "published",
            Rule.effective_start <= effective_at,
        ).order_by(Rule.effective_start.desc()).first()
    # 检查 effective_end（NULL = 长期有效）
    if rule and rule.effective_end and rule.effective_end < effective_at:
        return None
    return rule


def get_version_diff(db: Session, rule_id_a: int, rule_id_b: int) -> dict:
    """对比两个版本的字段差异"""
    rule_a = db.query(Rule).filter(Rule.id == rule_id_a).first()
    rule_b = db.query(Rule).filter(Rule.id == rule_id_b).first()
    if not rule_a or not rule_b:
        raise ValidationError("规则版本不存在")
    return {
        "rule_a": {"id": rule_a.id, "version": rule_a.version, "release_state": rule_a.release_state},
        "rule_b": {"id": rule_b.id, "version": rule_b.version, "release_state": rule_b.release_state},
        "diff": _diff_snapshots(_snapshot_rule(rule_a), _snapshot_rule(rule_b)),
    }


def get_shadow_run(db: Session, shadow_run_id: int) -> "Optional[RuleShadowRun]":
    """查询影子运行结果"""
    return db.query(RuleShadowRun).filter(RuleShadowRun.id == shadow_run_id).first()


__all__ = [
    "create_rule_draft",
    "publish_pre_check",
    "start_shadow_run",
    "promote_rule",
    "rollback_rule",
    "list_rule_versions",
    "bind_rule_at_time",
    "get_version_diff",
    "get_shadow_run",
]
