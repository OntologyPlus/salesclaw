"""
随访闭环服务 — 串联 诊断建议→执行→效果验证→判定闭环→范式沉淀 全链路

参考2 随访闭环核心理念:
  "系统最核心的不是把数据图表化给你诊断找问题——不重要。
   重要的是这个问题解决了没有，解决了是用什么有效办法，
   这些办法能不能形成通用范式。"

全链路状态机:
  [诊断建议] → confirmed → [执行中] → completed → [效果验证] → verified →
  [闭环判定] → closed/partial/unresolved → 若closed且高效 → [范式沉淀]

下游依赖:
  - effect_tracking_service.create_execution / compute_effectiveness
  - closure_review_service.judge_closure (Task 级闭合判定)

遵循架构约束:
  - 不新建DB表, Paradigm 从 DecisionExecution 高效记录中衍生
  - 不自动执行 — 所有状态变更需 API 触发（合规要求）
  - 下游出口明确标注在输出中
"""

from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from database import DecisionExecution, SuggestionAction, Task, ClosureReviewCycle


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

PARADIGM_MIN_EFFECTIVENESS = 70  # 有效性 >=70 分才可沉淀为范式


def _now():
    return datetime.utcnow()


# ---------------------------------------------------------------------------
# 1. 确认诊断建议 → 创建执行记录
# ---------------------------------------------------------------------------

def confirm_diagnosis_action(
    db: Session,
    tenant_id: str,
    rep_id: int,
    domain: str,
    suggestion: Dict[str, Any],
    user_id: int,
) -> Dict[str, Any]:
    """
    用户确认一条诊断建议，创建执行记录并进入随访闭环。

    suggestion 结构（来自 diagnosis_loop_service 输出）:
      { dimension, reason, recommended_courses[], baseline_metrics, target_metrics }

    Returns:
      { execution_id, tasks[], status: "confirmed", next_step: "..." }
    """
    dimension = suggestion.get("dimension", domain)
    title = f"【{dimension}】{suggestion.get('reason', '诊断建议执行')}"
    description = suggestion.get("reason", "")
    baseline_metrics = suggestion.get("baseline_metrics", {})
    target_metrics = suggestion.get("target_metrics", {})

    # 通过 effect_tracking_service 创建执行记录 (注意参数顺序)
    from services.effect_tracking_service import effect_tracking_service

    result = effect_tracking_service.create_execution(
        user_id=rep_id,
        tenant_id=tenant_id,
        db=db,
        decision_type=domain,
        title=title,
        description=description,
        baseline=baseline_metrics,
        target=target_metrics,
    )

    if "error" in result:
        return {"error": result["error"], "detail": result.get("detail", "")}

    # 查询回 ORM 对象以修改状态
    execution = (
        db.query(DecisionExecution)
        .filter(
            DecisionExecution.tenant_id == tenant_id,
            DecisionExecution.id == result["id"],
        )
        .first()
    )
    if not execution:
        return {"error": "execution_created_but_not_found"}

    execution.status = "confirmed"
    db.commit()
    db.refresh(execution)

    # 关联培训课程（如有）
    recommended_courses = suggestion.get("recommended_courses", [])
    tasks_created = []
    for course in recommended_courses:
        task = Task(
            tenant_id=tenant_id,
            assignee_id=rep_id,
            creator_id=user_id,
            title=f"完成培训: {course.get('title', '未命名课程')}",
            task_type="training",
            status="pending",
            priority="medium",
            due_date=(_now() + timedelta(days=30)).date(),
            related_type="DecisionExecution",
            related_id=execution.id,
        )
        db.add(task)
        tasks_created.append({
            "title": course.get("title"),
            "course_id": course.get("course_id"),
            "due_days": 30,
        })

    db.commit()

    return {
        "execution_id": execution.id,
        "status": execution.status,
        "domain": domain,
        "dimension": dimension,
        "tasks": tasks_created,
        "created_at": execution.created_at.isoformat() if execution.created_at else None,
        "next_step": f"执行完成后调用 POST /v1/decision/loop/complete/{execution.id}",
        "downstream_exit":
            "→ effect_tracking_service.compute_effectiveness → closure_review_service.judge_closure",
    }


# ---------------------------------------------------------------------------
# 2. 追踪随访全链路状态
# ---------------------------------------------------------------------------

def track_followup_chain(
    db: Session,
    tenant_id: str,
    execution_id: int,
) -> Dict[str, Any]:
    """
    获取一次随访执行的全链路状态快照。

    Returns:
      { execution, chain_steps[], tasks[], can_complete, can_extract_paradigm, next_action }
    """
    execution = (
        db.query(DecisionExecution)
        .filter(
            DecisionExecution.tenant_id == tenant_id,
            DecisionExecution.id == execution_id,
        )
        .first()
    )

    if not execution:
        return {"error": f"执行记录 {execution_id} 不存在", "execution_id": execution_id}

    # 关联的任务 (通过 related_type + related_id)
    tasks = (
        db.query(Task)
        .filter(
            Task.tenant_id == tenant_id,
            Task.is_deleted == 0,
            Task.related_type == "DecisionExecution",
            Task.related_id == execution_id,
        )
        .all()
    )

    # 关联的闭环审查批次
    review = None
    rid = getattr(execution, "review_cycle_id", None)
    if rid:
        review = (
            db.query(ClosureReviewCycle)
            .filter(
                ClosureReviewCycle.tenant_id == tenant_id,
                ClosureReviewCycle.id == rid,
            )
            .first()
        )

    chain_steps = _build_chain_steps(execution, tasks, review)

    # 关联的 SuggestionAction
    suggestion_actions = (
        db.query(SuggestionAction)
        .filter(
            SuggestionAction.tenant_id == tenant_id,
            SuggestionAction.user_id == execution.user_id,
            SuggestionAction.action_type == "accepted",
        )
        .order_by(SuggestionAction.acted_at.desc())
        .limit(3)
        .all()
    )

    can_complete = execution.status in ("confirmed", "executing")
    can_extract_paradigm = (
        execution.status == "closed"
        and (execution.effectiveness_score or 0) >= PARADIGM_MIN_EFFECTIVENESS
    )

    return {
        "execution": {
            "id": execution.id,
            "title": execution.title,
            "description": execution.description,
            "domain": execution.decision_type,
            "status": execution.status,
            "rep_id": execution.user_id,
            "created_at": execution.created_at.isoformat() if execution.created_at else None,
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
        },
        "chain_steps": chain_steps,
        "baseline_metrics": execution.baseline_metrics or {},
        "target_metrics": execution.target_metrics or {},
        "actual_metrics": execution.actual_metrics or {},
        "effectiveness_score": execution.effectiveness_score,
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status,
                "closure_state": t.closure_state,
                "appeal_state": t.appeal_state,
            }
            for t in tasks
        ],
        "suggestion_actions": [
            {
                "suggestion_id": sa.suggestion_id,
                "action_type": sa.action_type,
                "acted_at": sa.acted_at.isoformat() if sa.acted_at else None,
                "outcome_metric": sa.outcome_metric,
                "outcome_value": sa.outcome_value,
                "feedback_score": sa.feedback_score,
            }
            for sa in suggestion_actions
        ],
        "review_cycle": {
            "id": review.id,
            "cycle_month": review.cycle_month,
            "status": review.status,
        } if review else None,
        "can_complete": can_complete,
        "can_extract_paradigm": can_extract_paradigm,
        "next_action": _next_action_text(execution, can_complete, can_extract_paradigm),
    }


def _build_chain_steps(
    execution: DecisionExecution,
    tasks: list,
    review,
) -> List[Dict[str, Any]]:
    """构建 5 步链式进度"""
    status = execution.status or "planned"

    terminal = {"closed", "partial", "unresolved"}

    def step_state_for(expected_done_states, active_states=None):
        if status in expected_done_states:
            return "done"
        if active_states and status in active_states:
            return "active"
        return "pending"

    return [
        {
            "step": "diagnosis",
            "label": "诊断归因",
            "status": "done",
            "detail": f"领域: {execution.decision_type} | 基线指标已捕获",
        },
        {
            "step": "confirmation",
            "label": "确认执行",
            "status": "done" if status not in ("planned",) else "pending",
            "detail": (
                f"确认时间: {execution.started_at}"
                if execution.started_at else "待确认"
            ),
        },
        {
            "step": "execution",
            "label": "执行中",
            "status": step_state_for(
                {"completed", "verified"}.union(terminal),
                active_states={"executing"},
            ),
            "detail": (
                f"关联任务 {len(tasks)} 项 | 完成: {execution.completed_at}"
                if execution.completed_at
                else "进行中..."
            ),
        },
        {
            "step": "verification",
            "label": "效果验证",
            "status": (
                "done" if execution.effectiveness_score is not None
                else ("active" if status == "completed" else "pending")
            ),
            "detail": (
                f"有效性评分: {execution.effectiveness_score}/100"
                if execution.effectiveness_score is not None
                else "待验证"
            ),
        },
        {
            "step": "closure_judgment",
            "label": "判定闭环",
            "status": "done" if status in terminal else "pending",
            "detail": (
                f"判定结果: {status}"
                if status in terminal
                else "待判定"
            ),
        },
    ]


def _next_action_text(
    execution: DecisionExecution,
    can_complete: bool,
    can_extract_paradigm: bool,
) -> str:
    eid = execution.id
    if can_complete:
        return f"确认执行完成并提交实际指标: POST /v1/decision/loop/complete/{eid}"
    if can_extract_paradigm:
        return f"已完成闭环，可提取范式: GET /v1/decision/loop/paradigms?execution_id={eid}"
    return f"当前状态: {execution.status}，查看全链状态 GET /v1/decision/loop/followup/{eid}"


# ---------------------------------------------------------------------------
# 3. 完成执行 → 效果验证 → 闭环判定
# ---------------------------------------------------------------------------

def complete_and_review(
    db: Session,
    tenant_id: str,
    execution_id: int,
    actual_metrics: Optional[Dict[str, Any]] = None,
    force_closure_state: Optional[str] = None,
) -> Dict[str, Any]:
    """
    完成一次执行并自动串联 效果验证 + 闭环判定。

    流程:
      1. 更新 actual_metrics → completed
      2. 调用 effect_tracking_service.compute_effectiveness (注意参数顺序)
      3. 内置信号消除矩阵判定（与 closure_review_service.judge_closure 同逻辑）
      4. 返回全链路结果 + 范式提取建议

    Args:
      actual_metrics: 实际指标字典, 如 {"visit_completion_rate": 0.92}
      force_closure_state: 强制指定 [closed|partial|unresolved]
    """
    # 1. 更新执行记录
    execution = (
        db.query(DecisionExecution)
        .filter(
            DecisionExecution.tenant_id == tenant_id,
            DecisionExecution.id == execution_id,
        )
        .first()
    )

    if not execution:
        return {"error": f"执行记录 {execution_id} 不存在"}

    execution.actual_metrics = actual_metrics or {}
    execution.completed_at = _now()

    # 2. 效果验证 — effect_tracking_service.compute_effectiveness
    from services.effect_tracking_service import effect_tracking_service

    try:
        effectiveness_result = effect_tracking_service.compute_effectiveness(
            execution_id,
            tenant_id,
            db,
        )
        execution.effectiveness_score = effectiveness_result.get("score", 0)
    except Exception:
        execution.effectiveness_score = _simple_effectiveness(
            execution.baseline_metrics, execution.actual_metrics
        )

    # 3. 闭环判定 — 信号消除矩阵
    now = _now()
    if force_closure_state:
        closure_state = force_closure_state
        closure_reason = "人工指定闭环状态"
    else:
        closure_state, closure_reason = _judge_execution_closure(
            execution, signal_cleared=(execution.effectiveness_score or 0) >= 60
        )

    # 4. 关联月度审查批次
    month_label = now.strftime("%Y-%m")
    review_cycle = (
        db.query(ClosureReviewCycle)
        .filter(
            ClosureReviewCycle.tenant_id == tenant_id,
            ClosureReviewCycle.cycle_month == month_label,
        )
        .first()
    )
    if not review_cycle:
        review_cycle = ClosureReviewCycle(
            tenant_id=tenant_id,
            cycle_month=month_label,
            status="pending",
        )
        db.add(review_cycle)
        db.flush()

    # 关联到批次
    execution.review_cycle_id = review_cycle.id

    # 也更新关联 Task 的 review_cycle_id
    related_tasks = (
        db.query(Task)
        .filter(
            Task.tenant_id == tenant_id,
            Task.is_deleted == 0,
            Task.related_type == "DecisionExecution",
            Task.related_id == execution_id,
        )
        .all()
    )
    for t in related_tasks:
        t.review_cycle_id = review_cycle.id

    # 也尝试对每个 Task 做闭环判定
    for t in related_tasks:
        try:
            from services.closure_review_service import judge_closure
            judge_closure(
                db=db,
                tenant_id=tenant_id,
                task_id=t.id,
                signal_cleared=(execution.effectiveness_score or 0) >= 60,
            )
        except Exception:
            pass

    execution.status = closure_state
    db.commit()
    db.refresh(execution)

    # 5. 范式提取资格
    paradigm_eligible = (
        closure_state == "closed"
        and (execution.effectiveness_score or 0) >= PARADIGM_MIN_EFFECTIVENESS
    )

    # 6. unresolved 滚动建议
    rollover_advice = None
    if closure_state == "unresolved":
        rollover_advice = {
            "action": "建议将此问题滚动至下月审查周期",
            "next_month": (
                now.replace(day=1) + timedelta(days=32)
            ).strftime("%Y-%m"),
            "escalation": "如连续2月 unresolved，建议升级至区域经理",
            "remaining_gap": _compute_gap(
                execution.target_metrics, execution.actual_metrics
            ),
        }

    return {
        "execution_id": execution.id,
        "status": execution.status,
        "closure_state": closure_state,
        "closure_reason": closure_reason,
        "effectiveness": {
            "score": execution.effectiveness_score,
            "baseline": execution.baseline_metrics,
            "target": execution.target_metrics,
            "actual": execution.actual_metrics,
        },
        "paradigm_eligible": paradigm_eligible,
        "rollover_advice": rollover_advice,
        "next_action": (
            f"闭环成功！可提取通用范式: GET /v1/decision/loop/paradigms?execution_id={execution.id}"
            if paradigm_eligible
            else (
                f"部分闭环 G:ET /v1/decision/loop/followup/{execution.id}"
                if closure_state == "partial"
                else f"未解决: {rollover_advice['action'] if rollover_advice else '需人工介入'}"
            )
        ),
        "downstream_exit":
            "→ 已串联 effect_tracking.compute_effectiveness + 信号消除矩阵判定"
            "→ 建议确认后可经 closure_review 判定闭环",
    }


def _judge_execution_closure(
    execution: DecisionExecution,
    signal_cleared: bool,
) -> tuple:
    """
    内置信号消除矩阵判定。

    矩阵逻辑 (参考2 §7.5):
      achievement_rate × signal_cleared → closure_state

    DecisionExecution 层面:
      - effectiveness_score >= 80 + signal_cleared → closed
      - effectiveness_score >= 50 → partial
      - 否则 → unresolved
    """
    score = execution.effectiveness_score or 0
    if score >= 80 and signal_cleared:
        return "closed", "目标达成(>=80) + 信号消除 → 闭环"
    elif score >= 80:
        return "partial", "目标达成但信号未消除 → 部分闭环"
    elif score >= 50:
        return "partial", f"有效性{score}(>=50) → 部分闭环，剩余滚入下月"
    else:
        return "unresolved", f"有效性{score}(<50) → 未解决，升级+滚入下月"


def _simple_effectiveness(baseline: Optional[Dict], actual: Optional[Dict]) -> int:
    """简单有效性评分（降级方案）"""
    if not baseline or not actual:
        return 0
    scores = []
    for key, target_val in baseline.items():
        if key in actual and isinstance(target_val, (int, float)) and target_val != 0:
            actual_val = actual.get(key, 0)
            ratio = actual_val / target_val
            scores.append(min(ratio, 1.5) / 1.5 * 100)
    if not scores:
        return 0
    return int(sum(scores) / len(scores))


def _compute_gap(
    target: Optional[Dict],
    actual: Optional[Dict],
) -> Dict[str, Any]:
    """计算目标与实际之间的差距"""
    if not target or not actual:
        return {}
    gaps = {}
    for key, t_val in target.items():
        a_val = actual.get(key)
        if isinstance(t_val, (int, float)) and isinstance(a_val, (int, float)):
            gaps[key] = {
                "target": t_val,
                "actual": a_val,
                "delta": t_val - a_val,
                "achievement_rate": round(a_val / t_val * 100, 1) if t_val != 0 else 0,
            }
    return gaps


# ---------------------------------------------------------------------------
# 4. 范式沉淀 — 从成功闭环中提取通用范式
# ---------------------------------------------------------------------------

def extract_paradigms(
    db: Session,
    tenant_id: str,
    execution_id: Optional[int] = None,
    domain: Optional[str] = None,
    min_effectiveness: int = PARADIGM_MIN_EFFECTIVENESS,
) -> Dict[str, Any]:
    """
    从成功闭环的执行记录中提取通用范式。

    范式结构 (参考2 一人一院知识沉淀模型):
      { problem_type, solution_method, effectiveness_score, domain,
        source_rep_id, applicable_scenarios, key_actions }
    """
    query = db.query(DecisionExecution).filter(
        DecisionExecution.tenant_id == tenant_id,
        DecisionExecution.status == "closed",
        DecisionExecution.effectiveness_score >= min_effectiveness,
    )

    if execution_id:
        query = query.filter(DecisionExecution.id == execution_id)

    if domain:
        query = query.filter(DecisionExecution.decision_type == domain)

    executions = query.order_by(DecisionExecution.effectiveness_score.desc()).all()

    paradigms = [_build_paradigm_from_execution(db, tenant_id, ex) for ex in executions]
    merged = _merge_similar_paradigms(paradigms)

    return {
        "total": len(merged),
        "source_executions": len(executions),
        "domain_distribution": _domain_distribution(merged),
        "paradigms": merged,
        "note": (
            "范式从 DecisionExecution 成功闭环记录中衍生，无需新建表；"
            "相似范式已按问题类型合并"
        ),
    }


def _build_paradigm_from_execution(
    db: Session,
    tenant_id: str,
    execution: DecisionExecution,
) -> Dict[str, Any]:
    """从一条执行记录构建范式条目"""
    tasks = (
        db.query(Task)
        .filter(
            Task.tenant_id == tenant_id,
            Task.is_deleted == 0,
            Task.related_type == "DecisionExecution",
            Task.related_id == execution.id,
        )
        .all()
    )

    key_actions = [t.title for t in tasks if t.title]

    solution_method = _analyze_solution(
        execution.baseline_metrics or {},
        execution.target_metrics or {},
        execution.actual_metrics or {},
        key_actions,
    )

    applicable_scenarios = _infer_scenarios(
        execution.decision_type or "",
        execution.baseline_metrics or {},
    )

    return {
        "execution_id": execution.id,
        "domain": execution.decision_type,
        "problem_type": execution.title,
        "problem_description": execution.description,
        "solution_method": solution_method,
        "effectiveness_score": execution.effectiveness_score,
        "source_rep_id": execution.user_id,
        "key_actions": key_actions,
        "applicable_scenarios": applicable_scenarios,
        "baseline_metrics": execution.baseline_metrics,
        "target_metrics": execution.target_metrics,
        "actual_metrics": execution.actual_metrics,
        "achieved_at": (
            execution.completed_at.isoformat() if execution.completed_at else None
        ),
        "similarity_key": f"{execution.decision_type}::{execution.title}",
    }


def _analyze_solution(
    baseline: Dict,
    target: Dict,
    actual: Dict,
    actions: List[str],
) -> str:
    """分析解决方法描述"""
    improvements = []
    for key in target:
        t_val = target.get(key)
        b_val = baseline.get(key)
        a_val = actual.get(key)
        if isinstance(t_val, (int, float)) and isinstance(b_val, (int, float)):
            if isinstance(a_val, (int, float)):
                improvement = a_val - b_val
                if improvement > 0:
                    improvements.append(
                        f"{key} 提升 +{improvement:.1f} (基线{b_val}→实际{a_val})"
                    )

    if actions:
        method = "通过以下行动达成: " + "; ".join(actions[:3])
        if improvements:
            method += "。效果: " + "; ".join(improvements[:3])
        return method
    elif improvements:
        return "指标改善: " + "; ".join(improvements[:3])
    else:
        return "已确认闭环,详细指标参见执行记录"


def _infer_scenarios(domain: str, baseline: Dict) -> List[str]:
    """推断适用场景"""
    domain_scenarios = {
        "合规": [
            "合规培训不足的代表", "有合规预警记录的团队",
            "新入职代表合规意识培养",
        ],
        "学术": [
            "学术拜访频率低的代表", "产品知识评分低的团队",
            "科室会覆盖不足的区域",
        ],
        "拜访": [
            "拜访频次不达标的代表", "重点医院拜访覆盖率低",
            "新市场开拓期",
        ],
        "执行": [
            "执行力考核排名靠后的代表", "任务完成率低于80%",
            "关键项目推进迟缓",
        ],
    }
    return domain_scenarios.get(domain, ["通用场景"])


def _domain_distribution(paradigms: List[Dict]) -> Dict[str, int]:
    """领域分布统计"""
    dist: Dict[str, int] = {}
    for p in paradigms:
        d = p.get("domain", "未知")
        dist[d] = dist.get(d, 0) + 1
    return dist


def _merge_similar_paradigms(paradigms: List[Dict]) -> List[Dict]:
    """合并相似范式（同 domain + 同 problem_type）"""
    seen: Dict[str, int] = {}
    merged: List[Dict] = []

    for p in paradigms:
        key = p.get("similarity_key", p.get("problem_type", ""))
        if key in seen:
            idx = seen[key]
            existing_score = merged[idx].get("effectiveness_score", 0)
            new_score = p.get("effectiveness_score", 0)
            if new_score > existing_score:
                p["merged_from"] = merged[idx].get("execution_id")
                p["merge_count"] = merged[idx].get("merge_count", 1) + 1
                merged[idx] = p
            else:
                merged[idx]["merge_count"] = merged[idx].get("merge_count", 1) + 1
        else:
            seen[key] = len(merged)
            p["merge_count"] = 1
            merged.append(p)

    return merged


# ---------------------------------------------------------------------------
# 5. 一人一院 — 代表随访历史
# ---------------------------------------------------------------------------

def get_rep_followup_history(
    db: Session,
    tenant_id: str,
    rep_id: int,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    获取单个代表的随访闭环历史（一人一院知识沉淀）。

    参考2: "一人一院特异化知识库" — 每个代表沉淀个性化诊断和解决方法。
    """
    executions = (
        db.query(DecisionExecution)
        .filter(
            DecisionExecution.tenant_id == tenant_id,
            DecisionExecution.user_id == rep_id,
        )
        .order_by(DecisionExecution.created_at.desc())
        .limit(limit)
        .all()
    )

    history = []
    closed_count = partial_count = unresolved_count = 0
    scores = []

    for ex in executions:
        history.append({
            "execution_id": ex.id,
            "domain": ex.decision_type,
            "title": ex.title,
            "status": ex.status,
            "effectiveness_score": ex.effectiveness_score,
            "created_at": ex.created_at.isoformat() if ex.created_at else None,
            "completed_at": ex.completed_at.isoformat() if ex.completed_at else None,
            "baseline_metrics": ex.baseline_metrics,
            "actual_metrics": ex.actual_metrics,
        })
        if ex.status == "closed":
            closed_count += 1
        elif ex.status == "partial":
            partial_count += 1
        elif ex.status == "unresolved":
            unresolved_count += 1
        if ex.effectiveness_score is not None:
            scores.append(ex.effectiveness_score)

    # 领域分布
    domain_breakdown: Dict[str, Dict[str, int]] = {}
    for ex in executions:
        d = ex.decision_type or "未知"
        if d not in domain_breakdown:
            domain_breakdown[d] = {"total": 0, "closed": 0, "partial": 0, "unresolved": 0}
        domain_breakdown[d]["total"] += 1
        if ex.status == "closed":
            domain_breakdown[d]["closed"] += 1
        elif ex.status == "partial":
            domain_breakdown[d]["partial"] += 1
        elif ex.status == "unresolved":
            domain_breakdown[d]["unresolved"] += 1

    # 个人范式
    rep_paradigms = extract_paradigms(
        db=db, tenant_id=tenant_id, min_effectiveness=PARADIGM_MIN_EFFECTIVENESS,
    )
    own_paradigms = [
        p for p in rep_paradigms.get("paradigms", [])
        if p.get("source_rep_id") == rep_id
    ]

    total = len(executions)
    return {
        "rep_id": rep_id,
        "summary": {
            "total_executions": total,
            "closed": closed_count,
            "partial": partial_count,
            "unresolved": unresolved_count,
            "closure_rate": (
                round(closed_count / total * 100, 1) if total > 0 else 0
            ),
            "avg_effectiveness": (
                round(sum(scores) / len(scores), 1) if scores else 0
            ),
            "trend": (
                "improving"
                if scores and len(scores) >= 2 and scores[-1] > scores[0]
                else "stable"
            ),
        },
        "domain_breakdown": domain_breakdown,
        "followup_history": history,
        "rep_paradigms": own_paradigms,
    }


# ---------------------------------------------------------------------------
# 6. 批量闭环审查 — 月度团队闭环面板
# ---------------------------------------------------------------------------

def team_closure_panel(
    db: Session,
    tenant_id: str,
    region: Optional[str] = None,
    month_label: Optional[str] = None,
) -> Dict[str, Any]:
    """
    团队闭环面板 — 参考2 信号消除矩阵的团队视角。
    """
    month_label = month_label or _now().strftime("%Y-%m")

    start_of_month = datetime.strptime(month_label + "-01", "%Y-%m-%d")
    end_of_month = (
        start_of_month.replace(day=28) + timedelta(days=4)
    ).replace(day=1)

    query = db.query(DecisionExecution).filter(
        DecisionExecution.tenant_id == tenant_id,
        DecisionExecution.created_at >= start_of_month,
        DecisionExecution.created_at < end_of_month,
    )

    executions = query.all()

    total = len(executions)
    closed = sum(1 for e in executions if e.status == "closed")
    partial = sum(1 for e in executions if e.status == "partial")
    unresolved = sum(1 for e in executions if e.status == "unresolved")
    in_progress = total - closed - partial - unresolved

    # 各领域闭环率
    domain_stats: Dict[str, Dict] = {}
    for ex in executions:
        d = ex.decision_type or "未知"
        if d not in domain_stats:
            domain_stats[d] = {"total": 0, "closed": 0, "partial": 0, "unresolved": 0}
        domain_stats[d]["total"] += 1
        if ex.status == "closed":
            domain_stats[d]["closed"] += 1
        elif ex.status == "partial":
            domain_stats[d]["partial"] += 1
        elif ex.status == "unresolved":
            domain_stats[d]["unresolved"] += 1

    for stats in domain_stats.values():
        stats["closure_rate"] = (
            round(stats["closed"] / stats["total"] * 100, 1)
            if stats["total"] > 0 else 0
        )

    # 未解决问题
    unresolved_items = [
        {
            "execution_id": e.id,
            "rep_id": e.user_id,
            "domain": e.decision_type,
            "title": e.title,
            "effectiveness_score": e.effectiveness_score,
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "escalation": (
                "建议升级至区域经理"
                if (e.effectiveness_score or 0) < 30
                else "持续追踪"
            ),
        }
        for e in executions if e.status == "unresolved"
    ]

    # 范式库概览
    paradigms = extract_paradigms(db=db, tenant_id=tenant_id)

    return {
        "month_label": month_label,
        "region": region,
        "total_executions": total,
        "status_distribution": {
            "closed": closed,
            "partial": partial,
            "unresolved": unresolved,
            "in_progress": in_progress,
        },
        "signal_elimination_rate": (
            round(closed / total * 100, 1) if total > 0 else 0
        ),
        "domain_breakdown": domain_stats,
        "unresolved_items": unresolved_items,
        "paradigm_library": {
            "total_paradigms": paradigms.get("total", 0),
            "distribution": paradigms.get("domain_distribution", {}),
        },
        "reference_2_matrix": {
            "concept": (
                "信号消除矩阵 — achievement_rate × signal_cleared × appeal "
                "→ closed/partial/unresolved"
            ),
            "closed_definition": "目标达成 + 预警信号清除 + 无申诉",
            "partial_definition": "部分达成 + 信号减弱 + 有申诉但无争议",
            "unresolved_definition": "未达成 + 信号持续 + 有争议申诉",
        },
    }
