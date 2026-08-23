"""诊断闭环引擎（吸收参考1 决策闭环 + 参考2 诊断体系）

参考1（决策支持体系）的"感知→建议→洞察→执行"闭环，与
参考2（业务诊断体系）的"11 态 + 3 审批流 + 信号消除矩阵"，
在本系统中此前只落到"诊断（4 色灯）"，缺"归因到个人/团队 + 是否需要培训"的闭环前段。

本服务补全闭环前半段（用户选择：仅诊断 + 建议，符合医药合规人工留痕）：
  诊断(evaluate_diagnosis) → 两级归因(个人 rep / 团队 region) → 培训建议(课程 + baseline/target)

下游出口（显式串联，但**不自动调用**，需经理/代表确认后执行）：
  - 执行：training_service（课程/考试/路径）
  - 验证：effect_tracking_service.compute_effectiveness（baseline/target/actual）
  - 判定：closure_review_service.judge_closure（信号消除矩阵 → closed/partial/unresolved）

设计原则：函数式 service（与 decision_service 一致），经 `from services import` 跨域调用，
不直接 import 业务模型表，保持 ServicePort 解耦；不新增 DB 表。
"""
from collections import defaultdict
from typing import Optional

# 短板维度 → 培训课程 category 映射（供 build_training_advice 匹配 training_service.list_courses）
DIMENSION_COURSE_CATEGORY = {
    "合规": "compliance",
    "学术": "academic",
    "拜访": "visit",
    "执行": "execution",
}

# 合规 rule_code 前缀 → 短板维度
COMPLIANCE_DIMENSION = {
    "A11": "合规",
    "A12": "合规",
    "A24": "合规",
}

# decision_service 告警 category → 短板维度
ALERT_CATEGORY_DIMENSION = {
    "覆盖": "拜访",
    "覆盖率": "拜访",
    "拜访": "拜访",
    "学术": "学术",
    "考试": "学术",
    "合规": "合规",
    "执行": "执行",
}


def _to_dimension(alert_category: str) -> str:
    for key, dim in ALERT_CATEGORY_DIMENSION.items():
        if key in (alert_category or ""):
            return dim
    return "执行"


def run_diagnosis_loop(db, tenant_id: str, scope: str = "all",
                       user_id: Optional[int] = None) -> dict:
    """诊断闭环总入口：4 色灯 + 个人短板榜 + 团队短板 + 各 rep 培训建议

    Args:
        scope: 'all'（全部代表聚合）/ 透传区域等（团队级上卷时由 attribute_to_team 处理）
        user_id: 若指定，则聚焦单代表（等价于 attribute_to_rep）

    Returns:
        {
            light, sla, diagnosis_summary,
            rep_board[], team_summary, dimension_distribution,
            downstream_hint
        }
    """
    from services import decision_service, compliance_service, training_service

    # 1. 诊断（4 色灯）
    diag = decision_service.evaluate_diagnosis(db, tenant_id, user_id)
    light = diag.get("light")
    sla = diag.get("sla")

    # 2. 列举相关代表（去重 user_id）
    rep_ids = _collect_rep_ids(db, tenant_id, user_id)
    rep_board = []
    dimension_counter = defaultdict(int)
    for rid in rep_ids:
        rep = attribute_to_rep(db, tenant_id, rid, training_service)
        rep_board.append(rep)
        for dim in rep["weak_dimensions"]:
            dimension_counter[dim] += 1

    # 3. 团队级上卷
    team_summary = attribute_to_team(db, tenant_id, rep_board)

    # 4. 维度分布
    dimension_distribution = dict(dimension_counter)

    return {
        "light": light,
        "sla": sla,
        "diagnosis_summary": diag.get("summary"),
        "rep_board": sorted(rep_board, key=lambda r: -r["weak_score"]),
        "team_summary": team_summary,
        "dimension_distribution": dimension_distribution,
        "downstream_hint": (
            "以上为诊断与培训建议（仅诊断+建议）。建议确认后可经 "
            "effect_tracking_service 验证、closure_review_service 判定闭环（参考2 信号消除矩阵）。"
        ),
    }


def attribute_to_rep(db, tenant_id: str, rep_id: int, training_service=None) -> dict:
    """个人级归因：代表短板画像 + 推荐课程

    短板维度来源：
    - decision_service.get_alerts 的 category（覆盖/拜访/学术/考试/合规/执行）
    - compliance_service.list_alerts 中 actor_id==rep_id 的 rule_code（合规维度）
    - decision_service.list_recommendations(status='pending', user_id=rep_id)（执行维度）
    """
    from services import decision_service, compliance_service, training_service as _ts

    ts = training_service or _ts

    # 告警短板
    alerts = decision_service.get_alerts(db, tenant_id, rep_id).get("items", [])
    weak_dims = defaultdict(int)
    for a in alerts:
        dim = _to_dimension(a.get("category"))
        weak_dims[dim] += 1 if a.get("level") == "high" else 0.5

    # 合规违规短板
    comp_alerts = compliance_service.list_alerts(db, tenant_id).get("items", [])
    for ca in comp_alerts:
        if ca.get("actor_id") == rep_id:
            code = (ca.get("rule_code") or "")[:3]
            dim = COMPLIANCE_DIMENSION.get(code, "合规")
            weak_dims[dim] += 1

    # 执行短板（建议未落地）
    pending = decision_service.list_recommendations(
        db, user_id=rep_id, tenant_id=tenant_id, status="pending"
    )
    if pending:
        weak_dims["执行"] += min(len(pending), 3) * 0.5

    # 归一为维度列表（按权重降序）
    sorted_dims = sorted(weak_dims.items(), key=lambda x: -x[1])
    weak_dimensions = [d for d, _ in sorted_dims]
    weak_score = round(sum(weak_dims.values()), 1)

    # 生成培训建议
    advices = []
    for dim in weak_dimensions:
        advices.append(build_training_advice(db, tenant_id, rep_id, dim, ts))

    return {
        "rep_id": rep_id,
        "weak_dimensions": weak_dimensions,
        "weak_score": weak_score,
        "alert_count": len(alerts),
        "pending_recommendations": len(pending),
        "trainings": advices,
    }


def attribute_to_team(db, tenant_id: str, rep_board: list) -> dict:
    """团队级上卷：聚合成员短板，输出团队短板与团队培训计划建议

    团队维度无独立 region 表时，按 rep_board 聚合；若 rep 含 region 字段则按 region 分桶。
    """
    if not rep_board:
        return {"member_count": 0, "team_weak_dimensions": [], "team_training_plan": []}

    dim_counter = defaultdict(int)
    region_buckets = defaultdict(list)
    for rep in rep_board:
        for dim in rep.get("weak_dimensions", []):
            dim_counter[dim] += 1
        region = rep.get("region", "default")
        region_buckets[region].append(rep["rep_id"])

    team_weak = sorted(dim_counter.items(), key=lambda x: -x[1])
    team_weak_dimensions = [d for d, _ in team_weak]

    # 团队培训计划 = 高频短板维度对应的课程组合建议（不实际下发）
    plan = []
    from services import training_service
    for dim in team_weak_dimensions[:3]:
        cat = DIMENSION_COURSE_CATEGORY.get(dim)
        if not cat:
            continue
        courses = training_service.list_courses(db, tenant_id, category=cat).get("items", [])[:3]
        plan.append({
            "dimension": dim,
            "recommended_courses": [
                {"id": c.get("id"), "title": c.get("title"), "avg_rating": c.get("avg_rating")}
                for c in courses
            ],
        })

    return {
        "member_count": len(rep_board),
        "team_weak_dimensions": team_weak_dimensions,
        "team_training_plan": plan,
        "region_buckets": {k: len(v) for k, v in region_buckets.items()},
    }


def build_training_advice(db, tenant_id: str, rep_id: int, weak_dimension: str,
                          training_service=None) -> dict:
    """生成单维度培训建议（含推荐课程 + baseline/target，供下游验证）

    Args:
        weak_dimension: 合规 / 学术 / 拜访 / 执行
    Returns:
        {dimension, reason, recommended_courses[], baseline_metrics, target_metrics}
    """
    from services import training_service as _ts
    ts = training_service or _ts
    cat = DIMENSION_COURSE_CATEGORY.get(weak_dimension)
    courses = []
    if cat:
        raw = ts.list_courses(db, tenant_id, category=cat).get("items", [])[:5]
        courses = [
            {"id": c.get("id"), "title": c.get("title"),
             "difficulty": c.get("difficulty"), "avg_rating": c.get("avg_rating"),
             "duration_minutes": c.get("duration_minutes")}
            for c in raw
        ]

    reason_map = {
        "合规": "存在合规违规或红线风险，需强化《医药代表管理办法》合规培训",
        "学术": "学术活动或考试维度不达标，需补充产品知识与学术推广训练",
        "拜访": "医院覆盖或拜访达成不足，需优化拜访策略与辖区管理",
        "执行": "决策建议未落地，需提升执行闭环意识与任务管理",
    }

    # baseline/target 供下游 effect_tracking 验证（本轮仅生成，不自动 create_execution）
    baseline_metrics = {"weak_dimension_score": 1}
    target_metrics = {"weak_dimension_score": 0, "course_completed": 1, "exam_passed": 1}

    return {
        "dimension": weak_dimension,
        "reason": reason_map.get(weak_dimension, "需针对性提升"),
        "recommended_courses": courses,
        "baseline_metrics": baseline_metrics,
        "target_metrics": target_metrics,
        "downstream": "确认后可经 effect_tracking.create_execution(baseline,target) 立验证基线",
    }


# ──────────────────────────────────────────────
# 内部工具
# ──────────────────────────────────────────────

def _collect_rep_ids(db, tenant_id: str, user_id: Optional[int]) -> list:
    """收集相关代表 user_id（去重）

    优先用 VisitRecord.user_id（拜访主体即代表）；若 user_id 指定则仅返回该代表。
    """
    if user_id:
        return [user_id]
    try:
        from database import VisitRecord
        rows = db.query(VisitRecord.user_id).filter(
            VisitRecord.tenant_id == tenant_id,
            VisitRecord.is_deleted == 0,
        ).distinct().all()
        ids = [r[0] for r in rows if r[0]]
        return ids[:200]  # 防御超大数据量
    except Exception:
        return []
