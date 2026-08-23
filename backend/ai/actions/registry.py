"""AI Action Registry - 优先真实执行 + Mock 降级

执行策略：
1. 优先调用真实业务服务（sales_service/training_service/decision_service 等）
2. 真实执行失败时降级到 Mock（根据 output_schema 生成假数据）
3. L4 高风险操作标记 needs_human_confirm=True
"""
from typing import Optional

# 读运行时权威源（psp_ontology.db → OntologyRegistry 缓存），支持热更新
from ontology.registry import ACTIONS, ACTION_MAP, list_actions, get_action


async def execute(name: str, input: dict, user=None, db=None) -> dict:
    """执行 Action - 优先真实业务服务，失败降级到 Mock

    Args:
        name: Action 名称
        input: 入参
        user: 调用者（用于权限校验）
        db: 数据库 session（真实执行必需）

    Returns:
        {
            action: str,
            status: "ok" | "error",
            risk_level: str,
            output: dict,
            mock: bool,           # 是否 Mock 数据
            degraded: bool,       # 是否降级（真实执行失败）
            needs_human_confirm: bool,
        }
    """
    action = ACTION_MAP.get(name)
    if not action:
        return {
            "action": name,
            "status": "error",
            "error": f"Action '{name}' 不存在",
        }

    risk_level = action.get("risk_level", "L1")

    # 优先真实执行
    if db is not None:
        try:
            output = await _dispatch_real_action(name, input, user, db)
            return {
                "action": name,
                "status": "ok",
                "risk_level": risk_level,
                "output": output,
                "mock": False,
                "needs_human_confirm": risk_level == "L4",
            }
        except Exception as e:
            # 真实执行失败，降级到 Mock
            output = _generate_mock_output(name, action, input)
            return {
                "action": name,
                "status": "ok",
                "risk_level": risk_level,
                "output": output,
                "mock": True,
                "degraded": True,
                "error": str(e),
                "needs_human_confirm": risk_level == "L4",
            }

    # 无 db 参数：纯 Mock 模式
    output = _generate_mock_output(name, action, input)
    return {
        "action": name,
        "status": "ok",
        "risk_level": risk_level,
        "output": output,
        "mock": True,
        "needs_human_confirm": risk_level == "L4",
    }


async def _dispatch_real_action(name: str, input: dict, user, db) -> dict:
    """根据 Action 名称路由到真实业务服务

    已实现的 Action：
    - list_visit_plans → sales_service.list_plans
    - create_visit_record → sales_service.create_record
    - list_courses → training_service.list_courses
    - compute_kpi → decision_service.get_kpi_dashboard
    - compute_coverage_gap → sales_service.get_coverage_matrix
    - extract_feedback → sales_service.list_feedback

    其他 Action 抛 NotImplementedError，由 execute() 降级到 Mock
    """
    tenant_id = getattr(user, "tenant_id", "default") if user else "default"
    user_id = getattr(user, "id", None) if user else None

    # ── 销售域 Action ──
    if name == "list_visit_plans":
        from services import sales_service
        result = sales_service.list_plans(db, tenant_id, user_id,
                                          page=input.get("page", 1),
                                          page_size=input.get("page_size", 20))
        return {"items": result.get("items", []), "total": result.get("total", 0)}

    if name == "create_visit_record":
        from services import sales_service
        record = sales_service.create_record(db, tenant_id, user_id, input)
        return record

    if name == "compute_coverage_gap":
        from services import sales_service
        matrix = sales_service.get_coverage_matrix(db, tenant_id, user_id)
        return matrix

    if name == "extract_feedback":
        from services import sales_service
        result = sales_service.list_feedback(db, tenant_id, user_id,
                                             page=input.get("page", 1),
                                             page_size=input.get("page_size", 20))
        return {"items": result.get("items", []), "total": result.get("total", 0)}

    # ── 培训域 Action ──
    if name == "list_courses":
        from services import training_service
        result = training_service.list_courses(db, tenant_id, user_id,
                                               page=input.get("page", 1),
                                               page_size=input.get("page_size", 20))
        return {"items": result.get("items", []), "total": result.get("total", 0)}

    # ── 决策域 Action ──
    if name == "compute_kpi":
        from services import decision_service
        kpi = decision_service.get_kpi_dashboard(db, tenant_id, user_id)
        return kpi

    # ── 本体论 + AI 原生改造：AI 诊断/归因 Action（真实路由到 ai_diagnosis_service）──
    if name == "diagnose":
        from services import decision_service
        return decision_service.ai_diagnose(
            db, tenant_id, user_id or input.get("rep_id"),
            domain=input.get("domain", "coverage"),
            target_type=input.get("target_type"),
            target_id=input.get("target_id"),
            user=str(user) if user else None,
        )

    if name == "rerun_diagnosis":
        from services import decision_service
        return decision_service.ai_diagnose(
            db, tenant_id, user_id or input.get("rep_id"),
            domain=input.get("domain", "coverage"),
            target_type=input.get("target_type"),
            target_id=input.get("target_id"),
            user=str(user) if user else None,
        )

    if name == "confirm_diagnosis":
        from services import decision_service
        return decision_service.confirm_diagnosis(
            db, tenant_id, input.get("diagnosis_id"),
            user=str(user) if user else None,
        )

    if name == "extract_signal":
        # 信号在诊断推理时已一并落库；此处返回该代表最新诊断的信号列表
        from services import ai_diagnosis_service
        diags = ai_diagnosis_service.list_diagnoses(db, tenant_id, user_id)
        signals = diags[0]["signals"] if diags else []
        return {"diagnosis_id": diags[0]["id"] if diags else None, "signals": signals}

    if name == "derive_paradigm":
        from services import ai_paradigm_service
        return ai_paradigm_service.derive_paradigm(
            db, tenant_id, input.get("execution_id"), input.get("domain", "coverage"))

    # 未实现的 Action
    raise NotImplementedError(f"Action '{name}' 暂未接入真实业务服务")


def _generate_mock_output(name: str, action: dict, input: dict) -> dict:
    """根据 Action 生成 Mock 输出（降级时使用）"""
    output_schema = action.get("output_schema", {})

    output = {}
    for key, type_hint in output_schema.items():
        if type_hint == "int":
            output[key] = 1
        elif type_hint == "float":
            output[key] = 0.85
        elif type_hint == "bool":
            output[key] = True
        elif type_hint == "str":
            output[key] = f"mock_{key}"
        elif type_hint == "list":
            output[key] = []
        elif type_hint == "dict":
            output[key] = {}
        else:
            output[key] = None

    # 特殊处理一些 Action
    if name.startswith("list_"):
        output = {"items": [], "total": 0}
    elif name.startswith("get_") and "id" in input:
        output = {"id": input.get("id"), "mock": True}
    elif name.startswith("create_"):
        output = {"id": 1, "status": "created"}
    elif name.startswith("delete_"):
        output = {"status": "deleted"}
    elif name == "compute_kpi":
        output = {"value": 87.5}
    elif name == "compute_coverage_gap":
        output = {"gaps": [], "total": 0}
    elif name == "extract_feedback":
        output = {"feedback_id": 1, "sentiment": "positive"}

    return output


__all__ = ["list_actions", "get_action", "execute", "ACTIONS", "ACTION_MAP"]
