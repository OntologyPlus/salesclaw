"""基线数据 Seed - 从 main.py 的 _migrate_* 中剥离出的「数据」职责

重要区分：
  - **Schema 演进**（ALTER TABLE / CREATE INDEX）→ 已全部交给 Alembic
  - **业务基线数据**（默认策略、默认门禁、标准规则）→ 保留在这里

历史上二者混在 main.py 的 `_migrate_*` 函数里，导致「迁移」语义混乱：
既改表结构又塞数据，还无法版本化。现在拆开，各司其职。

本模块所有 seed 均为**幂等 upsert**：已存在则跳过，可安全重复执行。
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def seed_performance_policies() -> int:
    """绩效边界策略：10 条默认策略（1=允许联动绩效 / 0=禁止）

    区分「可控行为」（可联动绩效）与「业务结果/AI 判定」（不可直接联动），
    避免把不可控因素计入个人绩效。
    """
    from database import BusinessSessionLocal, PerformancePolicy

    default_policies = [
        ("visit_overdue", 1, "拜访逾期（可控行为）"),
        ("feedback_refused", 1, "拒不反馈（可控行为）"),
        ("plan_not_submitted", 1, "未提交改进计划（可控行为）"),
        ("approval_overdue", 1, "审批超时（可控行为）"),
        ("light_color_change", 0, "灯色本身变化（业务结果，不联动）"),
        ("business_result_not_achieved", 0, "业务结果未达成（可能受外部影响）"),
        ("ai_auto_judgment", 0, "AI 自动判定（必须人审）"),
        ("rule_violation", 0, "规则违反（需人工确认后才能联动）"),
        ("complete_visit", 1, "完成拜访（可控行为）"),
        ("positive_feedback", 1, "正面反馈（可控行为）"),
    ]
    added = 0
    with BusinessSessionLocal() as db:
        for action_type, allow, desc in default_policies:
            exists = db.query(PerformancePolicy).filter(
                PerformancePolicy.tenant_id == "default",
                PerformancePolicy.is_deleted == 0,
                PerformancePolicy.action_type == action_type,
            ).first()
            if exists:
                continue
            db.add(PerformancePolicy(
                tenant_id="default",
                action_type=action_type,
                allow_link_performance=allow,
                description=desc,
            ))
            added += 1
        db.commit()
    return added


def seed_data_quality_gates() -> int:
    """数据质量门禁：4 个域的默认阈值

    决策矩阵：完整度 < 阈值 → cancel；延迟 > cancel_days → partial_cancel；
             > delay_days → delay；其他 → pass。
    """
    from database import BusinessSessionLocal, DataQualityGate

    # (域, 完整度阈值, 延迟天数, 部分取消天数, 取消天数)
    default_gates = [
        ("sales", 0.60, 3, 7, 7),
        ("training", 0.60, 3, 7, 7),
        ("decision", 0.50, 3, 7, 7),
        ("compliance", 0.70, 2, 5, 7),
    ]
    added = 0
    with BusinessSessionLocal() as db:
        for domain, threshold, delay, partial, cancel in default_gates:
            exists = db.query(DataQualityGate).filter(
                DataQualityGate.tenant_id == "default",
                DataQualityGate.is_deleted == 0,
                DataQualityGate.domain == domain,
            ).first()
            if exists:
                continue
            db.add(DataQualityGate(
                tenant_id="default",
                domain=domain,
                completeness_threshold=threshold,
                timeliness_delay_days=delay,
                timeliness_partial_days=partial,
                timeliness_cancel_days=cancel,
                enabled=1,
            ))
            added += 1
        db.commit()
    return added


def seed_violation_rules() -> int:
    """合规禁止行为规则：22 项标准规则（表为空时才写入）"""
    from database import BusinessSessionLocal, ComplianceViolationRule

    with BusinessSessionLocal() as db:
        if db.query(ComplianceViolationRule).count() > 0:
            return 0
        from services.compliance_service import seed_violation_rules as _seed
        count = _seed(db)
        db.commit()
        return count


# seed 名称 -> 执行函数
SEEDERS = (
    ("performance_policies", seed_performance_policies),
    ("data_quality_gates", seed_data_quality_gates),
    ("compliance_violation_rules", seed_violation_rules),
)


def run_all() -> dict:
    """执行全部基线 seed（幂等）。单个失败不影响其余，也不阻断启动。"""
    results: dict[str, object] = {}
    for name, fn in SEEDERS:
        try:
            added = fn()
            results[name] = added
            if added:
                logger.info("[seed] %s 新增 %d 条", name, added)
        except Exception as e:
            results[name] = f"failed: {e}"
            logger.warning("[seed] %s 失败: %s", name, e)
    return results
