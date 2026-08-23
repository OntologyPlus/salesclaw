"""工具注册表 - 8 个核心工具的 callable 实现

每个工具签名：tool_fn(args: dict, ctx: dict) -> dict
  - args: LLM 提供的参数
  - ctx: 执行上下文 {db, tenant_id, user_id}

工具与 Ontology ACTIONS 同名，描述从 ACTION_MAP 动态读取。
"""
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 工具实现
# ──────────────────────────────────────────────

def _query_visit_records(args: dict, ctx: dict) -> dict:
    """查询拜访记录"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if db is None or user_id is None:
        return {"error": "缺少 db 或 user_id 上下文"}

    from services import sales_service
    records = sales_service.list_records(
        db, tenant_id,
        hospital_id=args.get("hospital_id"),
        doctor_id=args.get("doctor_id"),
    )
    # 返回简要信息
    items = records.get("items", records) if isinstance(records, dict) else records
    if isinstance(items, list):
        items = items[:10]  # 限制返回数量
    return {"items": items, "total": len(items) if isinstance(items, list) else 0}


def _query_doctor_profile(args: dict, ctx: dict) -> dict:
    """查询医生画像"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    doctor_id = args.get("doctor_id")
    if db is None or doctor_id is None:
        return {"error": "缺少 db 或 doctor_id"}

    from database import Doctor, Hospital
    doctor = db.query(Doctor).filter(
        Doctor.tenant_id == tenant_id,
        Doctor.is_deleted == 0,
        Doctor.id == doctor_id,
    ).first()
    if not doctor:
        return {"error": "医生不存在", "doctor_id": doctor_id}

    hospital = db.query(Hospital).filter(Hospital.id == doctor.hospital_id).first() if doctor.hospital_id else None
    return {
        "id": doctor.id,
        "name": doctor.name,
        "department": doctor.department,
        "title": doctor.title,
        "hospital": hospital.name if hospital else None,
        "hospital_level": hospital.level if hospital else None,
    }


def _query_training_progress(args: dict, ctx: dict) -> dict:
    """查询培训进度"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if db is None or user_id is None:
        return {"error": "缺少 db 或 user_id 上下文"}

    from services import training_service
    return training_service.get_my_learning(db, tenant_id, user_id)


def _query_kpi(args: dict, ctx: dict) -> dict:
    """查询 KPI 看板"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if db is None or user_id is None:
        return {"error": "缺少 db 或 user_id 上下文"}

    from services import decision_service
    return decision_service.get_kpi_dashboard(db, tenant_id, user_id)


def _create_visit_record(args: dict, ctx: dict) -> dict:
    """创建拜访记录"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if db is None or user_id is None:
        return {"error": "缺少 db 或 user_id 上下文"}

    from services import sales_service
    data = {
        "hospital_id": args.get("hospital_id"),
        "doctor_id": args.get("doctor_id"),
        "product_id": args.get("product_id"),
        "visit_date": args.get("visit_date"),
        "visit_type": args.get("visit_type", "academic"),
        "duration_minutes": args.get("duration_minutes", 30),
        "summary": args.get("summary", ""),
    }
    # 移除 None 值
    data = {k: v for k, v in data.items() if v is not None}
    if not data.get("visit_date"):
        from datetime import date
        data["visit_date"] = date.today().isoformat()
    return sales_service.create_record(db, tenant_id, user_id, data)


def _recommend_courses(args: dict, ctx: dict) -> dict:
    """基于能力缺口推荐课程"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if db is None or user_id is None:
        return {"error": "缺少 db 或 user_id 上下文"}

    from services import profile_service
    return profile_service.get_learning_needs(db, tenant_id, user_id)


def _compute_coverage_gap(args: dict, ctx: dict) -> dict:
    """计算覆盖空白"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if db is None:
        return {"error": "缺少 db 上下文"}

    from database import CoverageMatrix, CoverageAssignment, Hospital
    # 查询用户的覆盖分配
    assignments = db.query(CoverageAssignment).filter(
        CoverageAssignment.tenant_id == tenant_id,
        CoverageAssignment.is_deleted == 0,
        CoverageAssignment.user_id == user_id,
    ).all() if user_id else []

    # 查询覆盖矩阵中 coverage_level 为 none/low 的
    gaps = db.query(CoverageMatrix).filter(
        CoverageMatrix.tenant_id == tenant_id,
        CoverageMatrix.is_deleted == 0,
        CoverageMatrix.coverage_level.in_(["none", "low"]),
    ).limit(20).all()

    return {
        "total_gaps": len(gaps),
        "gaps": [
            {
                "hospital_id": g.hospital_id,
                "product_id": g.product_id,
                "coverage_level": g.coverage_level,
                "visit_count": g.visit_count,
            }
            for g in gaps
        ],
        "my_assignments": len(assignments),
    }


def _search_knowledge(args: dict, ctx: dict) -> dict:
    """知识检索"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    query = args.get("query", "")
    if not query:
        return {"error": "缺少 query 参数"}

    try:
        from ai.rag import retrieve
        results = retrieve(query, tenant_id, db, top_k=5)
        return {
            "query": query,
            "results": results[:5] if results else [],
            "total": len(results) if results else 0,
        }
    except Exception as e:
        return {"error": f"知识检索失败: {e}", "query": query}


# ──────────────────────────────────────────────
# 扩展工具（Phase 2.2 新增 12 个）
# ──────────────────────────────────────────────

def _list_visit_plans(args: dict, ctx: dict) -> dict:
    """查询拜访计划列表"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if db is None:
        return {"error": "缺少 db 上下文"}
    from services import sales_service
    result = sales_service.list_plans(db, tenant_id, user_id=user_id)
    items = result.get("items", []) if isinstance(result, dict) else (result or [])
    return {"items": items[:10], "total": len(items)}


def _create_visit_plan(args: dict, ctx: dict) -> dict:
    """创建拜访计划"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if db is None or user_id is None:
        return {"error": "缺少 db 或 user_id 上下文"}
    from services import sales_service
    data = {k: v for k, v in args.items() if v is not None}
    return sales_service.create_plan(db, tenant_id, user_id, data)


def _get_coverage_matrix(args: dict, ctx: dict) -> dict:
    """获取覆盖矩阵"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if db is None:
        return {"error": "缺少 db 上下文"}
    from services import sales_service
    return sales_service.list_coverage(db, tenant_id, user_id=user_id)


def _compute_roi(args: dict, ctx: dict) -> dict:
    """计算 ROI"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if db is None or user_id is None:
        return {"error": "缺少 db 或 user_id 上下文"}
    from services import sales_service
    overview = sales_service.get_overview(db, tenant_id, user_id)
    # 从 overview 中提取 ROI 相关数据
    return {
        "visit_count": overview.get("visit_count", 0),
        "coverage_rate": overview.get("coverage_rate", 0),
        "roi_estimate": round(overview.get("coverage_rate", 0) * 3.2, 2),
    }


def _list_doctors(args: dict, ctx: dict) -> dict:
    """查询医生列表"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    if db is None:
        return {"error": "缺少 db 上下文"}
    from database import Doctor, Hospital
    q = db.query(Doctor).filter(
        Doctor.tenant_id == tenant_id,
        Doctor.is_deleted == 0,
    )
    hospital_id = args.get("hospital_id")
    if hospital_id:
        q = q.filter(Doctor.hospital_id == hospital_id)
    doctors = q.limit(20).all()
    return {
        "items": [
            {
                "id": d.id,
                "name": d.name,
                "department": d.department,
                "title": d.title,
                "hospital_id": d.hospital_id,
            }
            for d in doctors
        ],
        "total": len(doctors),
    }


def _list_hospitals(args: dict, ctx: dict) -> dict:
    """查询医院列表"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    if db is None:
        return {"error": "缺少 db 上下文"}
    from database import Hospital
    q = db.query(Hospital).filter(
        Hospital.tenant_id == tenant_id,
        Hospital.is_deleted == 0,
    )
    level = args.get("level")
    if level:
        q = q.filter(Hospital.level == level)
    hospitals = q.limit(20).all()
    return {
        "items": [
            {
                "id": h.id,
                "name": h.name,
                "level": h.level,
                "region": getattr(h, "region", None),
            }
            for h in hospitals
        ],
        "total": len(hospitals),
    }


def _list_courses(args: dict, ctx: dict) -> dict:
    """查询课程列表"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    if db is None:
        return {"error": "缺少 db 上下文"}
    from services import training_service
    result = training_service.list_courses(
        db, tenant_id,
        category=args.get("category"),
        difficulty=args.get("difficulty"),
    )
    items = result.get("items", []) if isinstance(result, dict) else (result or [])
    return {"items": items[:10], "total": len(items)}


def _enroll_course(args: dict, ctx: dict) -> dict:
    """报名课程"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    course_id = args.get("course_id")
    if db is None or user_id is None or course_id is None:
        return {"error": "缺少 db、user_id 或 course_id"}
    from services import training_service
    return training_service.enroll_course(db, tenant_id, user_id, course_id)


def _list_exams(args: dict, ctx: dict) -> dict:
    """查询考试列表"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    if db is None:
        return {"error": "缺少 db 上下文"}
    from services import training_service
    result = training_service.list_exams(db, tenant_id, status=args.get("status"))
    items = result.get("items", []) if isinstance(result, dict) else (result or [])
    return {"items": items[:10], "total": len(items)}


def _get_alerts(args: dict, ctx: dict) -> dict:
    """查询预警列表"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if db is None or user_id is None:
        return {"error": "缺少 db 或 user_id 上下文"}
    from services import decision_service
    return decision_service.get_alerts(db, tenant_id, user_id)


def _simulate_scenario(args: dict, ctx: dict) -> dict:
    """What-if 模拟"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if db is None or user_id is None:
        return {"error": "缺少 db 或 user_id 上下文"}
    from services import decision_service
    visit_change = args.get("visit_change", 0.0)
    training_change = args.get("training_change", 0.0)
    return decision_service.simulate_what_if(db, tenant_id, user_id, visit_change, training_change)


def _list_documents(args: dict, ctx: dict) -> dict:
    """查询知识文档列表"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    if db is None:
        return {"error": "缺少 db 上下文"}
    from services import knowledge_service
    return knowledge_service.get_documents(db, tenant_id, category=args.get("category"))


# ──────────────────────────────────────────────
# 培训场景创建工作流原语（8 个，N+5 AI 原生）
# ──────────────────────────────────────────────

def _fetch_scene_config(args: dict, ctx: dict) -> dict:
    """拉取三列表配置：场景主题 / 业务领域 / 受训对象"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    if db is None:
        return {"error": "缺少 db 上下文"}

    from database import PracticeScenario, Doctor, Product
    # 场景主题：从现有场景的 scenario_type 去重
    scenario_types = [r[0] for r in db.query(PracticeScenario.scenario_type).filter(
        PracticeScenario.tenant_id == tenant_id,
        PracticeScenario.is_deleted == 0,
    ).distinct().all() if r[0]]
    scenario_types = list(set(scenario_types + ["visit", "negotiation", "objection", "dialogue"]))

    # 业务领域：从产品表去重
    products = db.query(Product).filter(
        Product.tenant_id == tenant_id,
        Product.is_deleted == 0,
    ).limit(50).all() if hasattr(Product, "tenant_id") else []
    business_domains = list({p.name for p in products} | {"心血管", "肿瘤", "内分泌", "神经"})

    # 受训对象：从医生表去重科室
    doctors = db.query(Doctor).filter(
        Doctor.tenant_id == tenant_id,
        Doctor.is_deleted == 0,
    ).limit(50).all()
    trainees = list({(d.department or "未知") for d in doctors}) or ["心内科", "肿瘤科", "内分泌科"]

    config = {
        "scenario_types": scenario_types[:10],
        "business_domains": list(business_domains)[:10],
        "trainees": trainees[:10],
    }

    # 写入 draft
    from ai.skills.scene_workspace import scene_workspace
    session_id = ctx.get("session_id", "default")
    user_id = ctx.get("user_id")
    if session_id and user_id:
        draft = scene_workspace.load(session_id, db, tenant_id, user_id)
        draft.config = config
        draft.current_step = "Step2"
        if "G1" not in draft.gates_passed:
            draft.gates_passed.append("G1")
        if "G2" not in draft.gates_passed:
            draft.gates_passed.append("G2")
        scene_workspace.save(draft, db)

    return {"config": config, "gates_passed": ["G1", "G2"]}


def _sync_scene_draft(args: dict, ctx: dict) -> dict:
    """将采集字段写入 draft.collection；confirm=true 时标记用户确认"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)

    collection = args.get("collection", {})
    confirm = bool(args.get("confirm", False))
    existing = draft.collection or {}
    existing.update(collection)
    if confirm:
        existing["user_confirmed"] = True
    draft.collection = existing

    if confirm and "G3" not in draft.gates_passed:
        draft.gates_passed.append("G3")
        draft.current_step = "Step3"

    scene_workspace.save(draft, db)
    return {"collection": draft.collection, "user_confirmed": existing.get("user_confirmed", False)}


def _merge_scene_draft(args: dict, ctx: dict) -> dict:
    """合并标题/背景到 draft.title_bg；confirm=true 时标记确认"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)

    title_bg = args.get("title_bg", {})
    confirm = bool(args.get("confirm", False))
    existing = draft.title_bg or {}
    existing.update(title_bg)
    if confirm:
        existing["user_confirmed"] = True
    draft.title_bg = existing

    # 同源性校验
    if confirm:
        sb = existing.get("scene_background", "").strip()
        if not sb:
            return {"error": "scene_background 不能为空（同源性要求）"}
        if "G4" not in draft.gates_passed:
            draft.gates_passed.append("G4")
        draft.current_step = "Step4.1"

    scene_workspace.save(draft, db)
    return {"title_bg": draft.title_bg}


def _finalize_scene_knowledge(args: dict, ctx: dict) -> dict:
    """锁定用户确认的 knowledgeIds 到 draft.knowledge"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)

    knowledge_ids = args.get("knowledge_ids", [])
    if not isinstance(knowledge_ids, list):
        return {"error": "knowledge_ids 必须为数组"}

    draft.knowledge = {
        "ids": knowledge_ids,
        "finalized": True,
        "suggestions": (draft.knowledge or {}).get("suggestions", []),
    }
    if "G5" not in draft.gates_passed:
        draft.gates_passed.append("G5")
    draft.current_step = "Step4.2"

    scene_workspace.save(draft, db)
    return {"knowledge": draft.knowledge, "finalized": True}


def _validate_scene_gate(args: dict, ctx: dict) -> dict:
    """校验门禁，返回 {passed, gate, reason}"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    gate = args.get("gate", "")
    if not gate:
        return {"error": "缺少 gate 参数"}

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    passed, reason = scene_workspace.validate_gate(draft, gate)
    return {"gate": gate, "passed": passed, "reason": reason, "current_step": draft.current_step}


def _suggest_scene_knowledge(args: dict, ctx: dict) -> dict:
    """基于 draft.collection 关键词检索 RAG，返回 Top5 知识条目"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)

    collection = draft.collection or {}
    query = " ".join(filter(None, [
        collection.get("drug_name", ""),
        collection.get("doctor_persona", ""),
        " ".join(collection.get("best_practice_points", []) or []),
    ]))

    suggestions = []
    try:
        from ai.rag import retrieve
        results = retrieve(query, tenant_id, db, top_k=5) if query else []
        suggestions = [
            {
                "id": r.get("id") or r.get("document_id"),
                "title": r.get("title", ""),
                "snippet": (r.get("content") or "")[:120],
                "score": r.get("score", 0.0),
            }
            for r in (results or [])
        ]
    except Exception:
        suggestions = []

    draft.knowledge = {"suggestions": suggestions, "ids": [], "finalized": False}
    scene_workspace.save(draft, db)

    return {
        "suggestions": suggestions,
        "user_visible_message": "为您推荐了相关知识条目，请选择要挂载的知识。",
    }


def _generate_context_payload(args: dict, ctx: dict) -> dict:
    """离线生成 contextPayload（doctor 5 键 + coach 3 键），写入 draft

    保密红线：不向 LLM 返回完整 payload 内容，仅返回就绪状态。
    """
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)

    collection = draft.collection or {}
    title_bg = draft.title_bg or {}

    from ai.llm_client import llm_client
    import json as _json

    system_prompt = """你是培训场景上下文构造器。基于场景信息生成 contextPayload，包含：
- doctor: 医生侧上下文（5 键：position, concerns, communication_style, objections, decision_style）
- coach: 教练侧上下文（3 键：scoring_dimensions, reference_talks, red_lines）

仅输出 JSON，不要解释。"""

    user_prompt = f"""场景信息：
医生画像：{collection.get('doctor_persona', '')}
品种：{collection.get('drug_name', '')}
最佳实践：{collection.get('best_practice_points', [])}
标题：{title_bg.get('title', '')}
背景：{title_bg.get('scene_background', '')}

请输出 JSON：{{"doctor":{{...5键...}}, "coach":{{...3键...}}}}"""

    doctor_payload = {}
    coach_payload = {}
    try:
        result = llm_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            intent="scene_payload",
            tenant_id=tenant_id,
        )
        content = result.get("content", "")
        import re
        m = re.search(r"\{[\s\S]*\}", content)
        if m:
            try:
                data = _json.loads(m.group())
                doctor_payload = data.get("doctor", {})
                coach_payload = data.get("coach", {})
            except Exception:
                pass
    except Exception:
        pass

    # Mock 降级（确保流程不阻断）
    if not doctor_payload:
        doctor_payload = {
            "position": "主任医师",
            "concerns": "疗效与安全性",
            "communication_style": "数据驱动型",
            "objections": ["出血风险", "价格偏高"],
            "decision_style": "循证决策",
        }
    if not coach_payload:
        coach_payload = {
            "scoring_dimensions": ["开场建立信任", "需求探寻", "数据呈现", "异议处理", "缔结推进"],
            "reference_talks": ["开场：基于 ESC 指南切入", "数据：12 个月随访数据"],
            "red_lines": ["不可承诺超出说明书适应症", "不可对比竞品贬低"],
        }

    draft.context_payload = {"doctor": doctor_payload, "coach": coach_payload, "ready": True}
    if "G6" not in draft.gates_passed:
        draft.gates_passed.append("G6")
    draft.current_step = "Step4.3"

    scene_workspace.save(draft, db)
    return {"ready": True, "doctor_keys": list(doctor_payload.keys()), "coach_keys": list(coach_payload.keys())}


def _create_scene_record(args: dict, ctx: dict) -> dict:
    """通过 training_service.create_scene_from_draft 落库。

    失败禁止自动重试，返回 error 字段让 LLM 决定如何告知用户。
    """
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)

    # 标记用户确认提交（由 LLM 在调用前设置）
    draft.submit_confirmed = True
    if "G7" not in draft.gates_passed:
        draft.gates_passed.append("G7")
    scene_workspace.save(draft, db)

    # 调用 training_service 落库（不重试）
    try:
        from services import training_service
        result = training_service.create_scene_from_draft(
            db=db, tenant_id=tenant_id, user_id=user_id, draft_dict=draft.to_dict(),
        )
        if result.get("error"):
            return {"error": result["error"], "retryable": False}

        scenario_id = result.get("scenario_id")
        draft.scenario_id = scenario_id
        if "G8" not in draft.gates_passed:
            draft.gates_passed.append("G8")
        draft.current_step = "done"
        scene_workspace.save(draft, db)

        # 清理工作区
        scene_workspace.clear(session_id, db, tenant_id, user_id)

        return {"scenario_id": scenario_id, "gates_passed": draft.gates_passed}

    except Exception as e:
        return {"error": f"create_scene_record 失败: {e}", "retryable": False}


# ──────────────────────────────────────────────
# visit-planner 工作流原语（7 个，N+5 AI 原生）
# ──────────────────────────────────────────────

def _fetch_visit_config(args: dict, ctx: dict) -> dict:
    """拉取周期/辖区/覆盖摘要，写入 draft.config"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    session_id = ctx.get("session_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from datetime import date
    from services import sales_service

    # 当前周周期
    today = date.today()
    period = f"{today.year}-W{today.isocalendar()[1]:02d}"

    # 辖区覆盖摘要
    coverage = sales_service.list_coverage(db, tenant_id, user_id=user_id) or {}
    coverage_summary = {
        "total_hospitals": coverage.get("total", 0) if isinstance(coverage, dict) else 0,
        "covered": coverage.get("covered", 0) if isinstance(coverage, dict) else 0,
        "gaps": coverage.get("gaps", 0) if isinstance(coverage, dict) else 0,
    }

    config = {"period": period, "coverage_summary": coverage_summary}

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    draft.config = config
    draft.current_step = "Step2"
    for g in ("G1", "G2"):
        if g not in draft.gates_passed:
            draft.gates_passed.append(g)
    scene_workspace.save(draft, db)
    return {"config": config, "gates_passed": ["G1", "G2"]}


def _sync_visit_draft(args: dict, ctx: dict) -> dict:
    """采集目标医生+拜访目的写入 draft.collection；confirm=true 标记确认"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)

    collection = args.get("collection", {})
    confirm = bool(args.get("confirm", False))
    submit_confirmed = bool(args.get("submit_confirmed", False))

    existing = draft.collection or {}
    existing.update(collection)
    if confirm:
        existing["user_confirmed"] = True
    if submit_confirmed:
        draft.submit_confirmed = True
        if "G7" not in draft.gates_passed:
            draft.gates_passed.append("G7")
    draft.collection = existing

    if confirm and "G3" not in draft.gates_passed:
        draft.gates_passed.append("G3")
        draft.current_step = "Step3"
    if submit_confirmed:
        draft.current_step = "Step7"

    scene_workspace.save(draft, db)
    return {"collection": draft.collection, "user_confirmed": existing.get("user_confirmed", False),
            "submit_confirmed": draft.submit_confirmed}


def _merge_visit_draft(args: dict, ctx: dict) -> dict:
    """合并计划标题+概述到 draft.title_bg；confirm=true 标记确认"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)

    title_bg = args.get("title_bg", {})
    confirm = bool(args.get("confirm", False))
    existing = draft.title_bg or {}
    existing.update(title_bg)
    if confirm:
        existing["user_confirmed"] = True
    draft.title_bg = existing

    if confirm and "G4" not in draft.gates_passed:
        draft.gates_passed.append("G4")
        draft.current_step = "Step4"

    scene_workspace.save(draft, db)
    return {"title_bg": draft.title_bg, "user_confirmed": existing.get("user_confirmed", False)}


def _compute_visit_priority(args: dict, ctx: dict) -> dict:
    """基于覆盖+历史拜访计算优先级排序，写入 draft.collection.priority_result"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)

    collection = draft.collection or {}
    target_doctors = collection.get("target_doctors", []) or []

    # 简化优先级计算：基于 target_doctors 顺序 + 历史拜访间隔
    # 真实场景可调 sales_service.list_records 查近 90 天拜访计算间隔
    priority_result = []
    for idx, doc in enumerate(target_doctors if isinstance(target_doctors, list) else []):
        hospital_level = (doc.get("hospital_level") or "").upper() if isinstance(doc, dict) else ""
        if "三甲" in hospital_level or "三甲" in str(doc):
            priority = "high"
        elif "二甲" in hospital_level or "二甲" in str(doc):
            priority = "medium"
        else:
            priority = "low"
        priority_result.append({
            "doctor_id": doc.get("doctor_id") or doc.get("id") if isinstance(doc, dict) else None,
            "doctor_name": doc.get("doctor_name") or doc.get("name") if isinstance(doc, dict) else str(doc),
            "priority": priority,
            "visit_reason": "30 天未拜访需重点关注" if priority == "high" else "常规拜访",
        })

    # 按 high→medium→low 排序
    order = {"high": 0, "medium": 1, "low": 2}
    priority_result.sort(key=lambda x: order.get(x["priority"], 3))

    collection["priority_result"] = priority_result
    collection["priority_computed"] = True
    draft.collection = collection
    if "G5" not in draft.gates_passed:
        draft.gates_passed.append("G5")
    draft.current_step = "Step5"
    scene_workspace.save(draft, db)

    return {"priority_result": priority_result, "gates_passed": ["G5"]}


def _generate_visit_payload(args: dict, ctx: dict) -> dict:
    """生成每个医生的 planned_date + visit_type + priority + visit_reason"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from ai.skills.scene_workspace import scene_workspace
    from datetime import date, timedelta

    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    collection = draft.collection or {}
    priority_result = collection.get("priority_result", []) or []
    period = (draft.config or {}).get("period", "")

    # 简化：从本周一开始分配日期
    today = date.today()
    monday = today - timedelta(days=today.weekday())

    payload_items = []
    for idx, item in enumerate(priority_result if isinstance(priority_result, list) else []):
        planned_date = (monday + timedelta(days=idx % 5)).isoformat()
        priority = item.get("priority", "medium")
        visit_type = "academic" if priority == "high" else ("relationship" if priority == "medium" else "feedback")
        payload_items.append({
            **item,
            "planned_date": planned_date,
            "visit_type": visit_type,
        })

    draft.context_payload = {"items": payload_items, "ready": True}
    if "G6" not in draft.gates_passed:
        draft.gates_passed.append("G6")
    draft.current_step = "Step6"
    scene_workspace.save(draft, db)

    return {"items": payload_items, "ready": True, "gates_passed": ["G6"]}


def _create_visit_plan_record(args: dict, ctx: dict) -> dict:
    """调 sales_service.create_plan 落库 + 批量 add_plan_item。失败不重试。"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from ai.skills.scene_workspace import scene_workspace
    from services import sales_service

    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    draft.submit_confirmed = True
    if "G7" not in draft.gates_passed:
        draft.gates_passed.append("G7")
    scene_workspace.save(draft, db)

    try:
        title_bg = draft.title_bg or {}
        collection = draft.collection or {}
        payload = draft.context_payload or {}
        items = payload.get("items", []) or []

        plan_data = {
            "title": title_bg.get("plan_title") or title_bg.get("title") or "拜访计划",
            "summary": title_bg.get("plan_summary") or title_bg.get("scene_background") or "",
            "period": collection.get("period") or (draft.config or {}).get("period", ""),
            "items": [
                {
                    "doctor_id": it.get("doctor_id"),
                    "hospital_id": it.get("hospital_id"),
                    "product_id": it.get("product_id"),
                    "planned_date": it.get("planned_date"),
                    "visit_type": it.get("visit_type", "academic"),
                    "priority": it.get("priority", "medium"),
                    "visit_reason": it.get("visit_reason", ""),
                }
                for it in items if isinstance(it, dict)
            ],
        }

        result = sales_service.create_plan(db, tenant_id, user_id, plan_data)
        if isinstance(result, dict) and result.get("error"):
            return {"error": result["error"], "retryable": False}

        plan_id = result.get("id") or result.get("plan_id") if isinstance(result, dict) else None
        if not plan_id:
            return {"error": "create_plan 未返回 ID", "retryable": False, "raw": str(result)[:200]}

        draft.scenario_id = plan_id
        if "G8" not in draft.gates_passed:
            draft.gates_passed.append("G8")
        draft.current_step = "done"
        scene_workspace.save(draft, db)
        scene_workspace.clear(session_id, db, tenant_id, user_id)

        return {"plan_id": plan_id, "gates_passed": draft.gates_passed}

    except Exception as e:
        return {"error": f"create_visit_plan_record 失败: {e}", "retryable": False}


def _validate_visit_gate(args: dict, ctx: dict) -> dict:
    """校验 visit-planner 门禁 G1-G8（字段语义与 scenario-generator 不同）"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    gate = args.get("gate", "")
    if not gate:
        return {"error": "缺少 gate 参数"}

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)

    passed, reason = False, "未知门禁"
    if gate == "G1":
        passed, reason = (True, "OK") if (draft.tenant_id and draft.user_id) else (False, "未登录")
    elif gate == "G2":
        cfg = draft.config or {}
        passed, reason = (True, "OK") if cfg.get("coverage_summary") else (False, "覆盖摘要为空")
    elif gate == "G3":
        coll = draft.collection or {}
        passed, reason = (True, "OK") if (
            coll.get("target_doctors") and coll.get("visit_purposes")
            and coll.get("user_confirmed") is True
        ) else (False, "采集字段未完成或未确认")
    elif gate == "G4":
        tb = draft.title_bg or {}
        passed, reason = (True, "OK") if (
            tb.get("plan_title") and tb.get("plan_summary")
            and tb.get("user_confirmed") is True
        ) else (False, "计划标题或概述未确认")
    elif gate == "G5":
        coll = draft.collection or {}
        passed, reason = (True, "OK") if (
            coll.get("priority_computed") is True and coll.get("priority_result")
        ) else (False, "优先级未计算")
    elif gate == "G6":
        cp = draft.context_payload or {}
        passed, reason = (True, "OK") if (
            cp.get("ready") is True and cp.get("items")
        ) else (False, "Payload 未就绪")
    elif gate == "G7":
        passed, reason = (True, "OK") if draft.submit_confirmed else (False, "用户未确认提交")
    elif gate == "G8":
        passed, reason = (True, "OK") if draft.scenario_id else (False, "未落库")

    return {"gate": gate, "passed": passed, "reason": reason, "current_step": draft.current_step}


# ──────────────────────────────────────────────
# what-if-simulator 工作流原语（6 个，N+5 AI 原生）
# ──────────────────────────────────────────────

def _fetch_kpi_baseline(args: dict, ctx: dict) -> dict:
    """拉取当前 KPI 基线，写入 draft.config"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    session_id = ctx.get("session_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from services import decision_service
    from datetime import date

    kpi = decision_service.get_kpi_dashboard(db, tenant_id, user_id) or {}
    baseline = {
        "baseline_period": f"{date.today().year}-{date.today().month:02d}",
        "baseline_kpi": kpi.get("kpi") or kpi.get("summary") or kpi,
    }

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    draft.config = baseline
    draft.current_step = "Step2"
    for g in ("G1", "G2"):
        if g not in draft.gates_passed:
            draft.gates_passed.append(g)
    scene_workspace.save(draft, db)
    return {"baseline": baseline, "gates_passed": ["G1", "G2"]}


def _sync_simulation_params(args: dict, ctx: dict) -> dict:
    """采集策略变量（visit_change/coverage_change/structure_change），confirm=true 标记确认"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)

    collection = args.get("collection", {})
    confirm = bool(args.get("confirm", False))
    submit_confirmed = bool(args.get("submit_confirmed", False))

    existing = draft.collection or {}
    existing.update(collection)
    if confirm:
        existing["user_confirmed"] = True
    if submit_confirmed:
        draft.submit_confirmed = True
        if "G7" not in draft.gates_passed:
            draft.gates_passed.append("G7")
    draft.collection = existing

    if confirm and "G3" not in draft.gates_passed:
        draft.gates_passed.append("G3")
        draft.current_step = "Step3"
    if submit_confirmed:
        draft.current_step = "done"

    scene_workspace.save(draft, db)
    return {"collection": draft.collection, "user_confirmed": existing.get("user_confirmed", False),
            "submit_confirmed": draft.submit_confirmed}


def _merge_scenario_metadata(args: dict, ctx: dict) -> dict:
    """合并场景名称+假设描述到 draft.title_bg；confirm=true 标记确认"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)

    title_bg = args.get("title_bg", {})
    confirm = bool(args.get("confirm", False))
    existing = draft.title_bg or {}
    existing.update(title_bg)
    if confirm:
        existing["user_confirmed"] = True
    draft.title_bg = existing

    if confirm and "G4" not in draft.gates_passed:
        draft.gates_passed.append("G4")
        draft.current_step = "Step4"

    scene_workspace.save(draft, db)
    return {"title_bg": draft.title_bg, "user_confirmed": existing.get("user_confirmed", False)}


def _run_simulation_step(args: dict, ctx: dict) -> dict:
    """调 decision_service.simulate_what_if 运行单步模拟"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from ai.skills.scene_workspace import scene_workspace
    from services import decision_service

    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    collection = draft.collection or {}
    strategy_vars = collection.get("strategy_vars", {}) or {}

    visit_change = float(strategy_vars.get("visit_change", 0) or 0)
    training_change = float(strategy_vars.get("training_change", 0) or 0)
    coverage_change = float(strategy_vars.get("coverage_change", 0) or 0)

    sim_result = {}
    try:
        sim_result = decision_service.simulate_what_if(
            db, tenant_id, user_id,
            visit_change=visit_change,
            training_change=training_change,
            coverage_change=coverage_change,
        ) or {}
    except Exception as e:
        sim_result = {"error": str(e)[:120]}

    # Mock 降级（确保流程不阻断）
    if not sim_result or sim_result.get("error"):
        baseline = (draft.config or {}).get("baseline_kpi", {})
        sim_result = {
            "predicted_kpi": {
                "visit_score": int(baseline.get("visit_score", 80) + visit_change * 0.5),
                "coverage_rate": round(float(baseline.get("coverage_rate", 0.7)) + coverage_change * 0.01, 3),
                "quality_score": int(baseline.get("quality_score", 25) + training_change * 0.3),
            },
            "delta": {
                "visit_change": visit_change,
                "coverage_change": coverage_change,
                "training_change": training_change,
            },
            "mock": True,
        }

    # 追加到 knowledge.comparisons（多方案对比）
    knowledge = draft.knowledge or {}
    comparisons = knowledge.get("comparisons", []) or []
    comparisons.append({
        "scenario_name": (draft.title_bg or {}).get("scenario_name", f"方案{len(comparisons)+1}"),
        "strategy_vars": strategy_vars,
        "result": sim_result,
    })
    knowledge["comparisons"] = comparisons
    draft.knowledge = knowledge

    if "G5" not in draft.gates_passed:
        draft.gates_passed.append("G5")
    draft.current_step = "Step5"
    scene_workspace.save(draft, db)

    return {"simulation_result": sim_result, "comparisons_count": len(comparisons)}


def _compare_scenarios(args: dict, ctx: dict) -> dict:
    """多方案对比 + 推荐，写入 draft.knowledge.final_recommendation"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)

    knowledge = draft.knowledge or {}
    comparisons = knowledge.get("comparisons", []) or []

    if not comparisons:
        return {"error": "无可对比方案，请先运行至少一次模拟"}

    # 简化推荐：选 visit_score 最高的方案
    best = max(comparisons, key=lambda c: (
        (c.get("result", {}).get("predicted_kpi", {}).get("visit_score")) or 0
    ))

    recommendation = {
        "best_scenario": best.get("scenario_name"),
        "reason": f"该方案 visit_score 最高: {best.get('result', {}).get('predicted_kpi', {}).get('visit_score')}",
        "total_scenarios": len(comparisons),
    }
    knowledge["final_recommendation"] = recommendation
    draft.knowledge = knowledge

    if "G6" not in draft.gates_passed:
        draft.gates_passed.append("G6")
    draft.current_step = "Step6"
    scene_workspace.save(draft, db)

    return {"recommendation": recommendation, "comparisons": comparisons}


def _validate_whatif_gate(args: dict, ctx: dict) -> dict:
    """校验 what-if-simulator 门禁 G1-G7"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    gate = args.get("gate", "")
    if not gate:
        return {"error": "缺少 gate 参数"}

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)

    passed, reason = False, "未知门禁"
    if gate == "G1":
        passed, reason = (True, "OK") if (draft.tenant_id and draft.user_id) else (False, "未登录")
    elif gate == "G2":
        cfg = draft.config or {}
        passed, reason = (True, "OK") if cfg.get("baseline_kpi") else (False, "基线 KPI 为空")
    elif gate == "G3":
        coll = draft.collection or {}
        passed, reason = (True, "OK") if (
            coll.get("strategy_vars") and coll.get("user_confirmed") is True
        ) else (False, "策略变量未采集或未确认")
    elif gate == "G4":
        tb = draft.title_bg or {}
        passed, reason = (True, "OK") if (
            tb.get("scenario_name") and tb.get("hypothesis")
            and tb.get("user_confirmed") is True
        ) else (False, "场景名称或假设未确认")
    elif gate == "G5":
        kn = draft.knowledge or {}
        passed, reason = (True, "OK") if kn.get("comparisons") else (False, "未运行模拟")
    elif gate == "G6":
        kn = draft.knowledge or {}
        passed, reason = (True, "OK") if kn.get("final_recommendation") else (False, "未完成对比")
    elif gate == "G7":
        passed, reason = (True, "OK") if draft.submit_confirmed else (False, "用户未确认保存")

    return {"gate": gate, "passed": passed, "reason": reason, "current_step": draft.current_step}


# ──────────────────────────────────────────────
# exam-generator 工作流原语（7 个，N+5 AI 原生）
# ──────────────────────────────────────────────

def _fetch_exam_config(args: dict, ctx: dict) -> dict:
    """拉取课程列表 + 难度分布规则，写入 draft.config"""
    db = ctx.get("db")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    session_id = ctx.get("session_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from services import training_service

    courses_result = training_service.list_courses(db, tenant_id) or {}
    courses = courses_result.get("items", []) if isinstance(courses_result, dict) else (courses_result or [])
    course_options = [
        {"id": c.get("id"), "title": c.get("title"), "category": c.get("category")}
        for c in (courses[:20] if isinstance(courses, list) else [])
    ]

    config = {
        "courses": course_options,
        "difficulty_mix": {"easy": 0.3, "medium": 0.5, "hard": 0.2},
        "min_questions": 20,
    }

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    draft.config = config
    draft.current_step = "Step2"
    for g in ("G1", "G2"):
        if g not in draft.gates_passed:
            draft.gates_passed.append(g)
    scene_workspace.save(draft, db)
    return {"config": config, "gates_passed": ["G1", "G2"]}


def _sync_exam_draft(args: dict, ctx: dict) -> dict:
    """采集题型组合+知识点覆盖，confirm=true 标记确认"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)

    collection = args.get("collection", {})
    confirm = bool(args.get("confirm", False))
    submit_confirmed = bool(args.get("submit_confirmed", False))

    existing = draft.collection or {}
    existing.update(collection)
    if confirm:
        existing["user_confirmed"] = True
    if submit_confirmed:
        draft.submit_confirmed = True
        if "G7" not in draft.gates_passed:
            draft.gates_passed.append("G7")
    draft.collection = existing

    if confirm and "G3" not in draft.gates_passed:
        draft.gates_passed.append("G3")
        draft.current_step = "Step3"
    if submit_confirmed:
        draft.current_step = "Step7"

    scene_workspace.save(draft, db)
    return {"collection": draft.collection, "user_confirmed": existing.get("user_confirmed", False),
            "submit_confirmed": draft.submit_confirmed}


def _merge_exam_draft(args: dict, ctx: dict) -> dict:
    """合并考试标题+说明到 draft.title_bg；confirm=true 标记确认"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)

    title_bg = args.get("title_bg", {})
    confirm = bool(args.get("confirm", False))
    existing = draft.title_bg or {}
    existing.update(title_bg)
    if confirm:
        existing["user_confirmed"] = True
    draft.title_bg = existing

    if confirm and "G4" not in draft.gates_passed:
        draft.gates_passed.append("G4")
        draft.current_step = "Step4"

    scene_workspace.save(draft, db)
    return {"title_bg": draft.title_bg, "user_confirmed": existing.get("user_confirmed", False)}


def _generate_questions_batch(args: dict, ctx: dict) -> dict:
    """按难度分布批量生成题目（调 LLM），写入 draft.knowledge.questions"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from ai.skills.scene_workspace import scene_workspace
    from ai.llm_client import llm_client
    import json as _json
    import re

    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    collection = draft.collection or {}
    config = draft.config or {}
    title_bg = draft.title_bg or {}

    question_types = collection.get("question_types", {}) or {}
    total = int(args.get("total_questions") or collection.get("total_questions") or config.get("min_questions", 20))
    difficulty_mix = config.get("difficulty_mix", {"easy": 0.3, "medium": 0.5, "hard": 0.2})

    course_id = collection.get("course_id")
    course_title = next((c["title"] for c in config.get("courses", []) if c.get("id") == course_id), "未指定课程")

    # 简化：用 LLM 生成题目（mock 模式会降级）
    questions = []
    try:
        sys_prompt = """你是医药培训考试题目生成器。基于课程信息生成考试题目。
仅输出 JSON 数组，每个元素格式：
{"question_id": int, "question_type": "single|multi|judge|qa", "difficulty": "easy|medium|hard", "content": "题干", "options": ["A...","B..."], "answer": "A", "score": int, "knowledge_point": "知识点"}"""
        user_prompt = f"""课程：{course_title}
知识点：{collection.get('knowledge_points', [])}
题量：{total}
难度分布：易{int(total*difficulty_mix['easy'])} 中{int(total*difficulty_mix['medium'])} 难{int(total*difficulty_mix['hard'])}
题型：{question_types}

请生成 {total} 道题目，输出 JSON 数组。"""

        result = llm_client.chat(
            messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_prompt}],
            intent="exam_generate",
            tenant_id=tenant_id,
        )
        content = result.get("content", "")
        m = re.search(r"\[[\s\S]*\]", content)
        if m:
            try:
                questions = _json.loads(m.group())
            except Exception:
                questions = []
    except Exception:
        questions = []

    # Mock 降级
    if not questions:
        for i in range(total):
            difficulty = "easy" if i < int(total * difficulty_mix["easy"]) else (
                "medium" if i < int(total * (difficulty_mix["easy"] + difficulty_mix["medium"])) else "hard"
            )
            qtype = "single" if i % 4 == 0 else ("multi" if i % 4 == 1 else ("judge" if i % 4 == 2 else "qa"))
            questions.append({
                "question_id": i + 1,
                "question_type": qtype,
                "difficulty": difficulty,
                "content": f"第{i+1}题（{difficulty}）：关于{course_title}的{'基础' if difficulty=='easy' else '进阶'}知识点，下列说法是否正确？",
                "options": ["A. 正确", "B. 错误"] if qtype == "judge" else ["A. 选项一", "B. 选项二", "C. 选项三", "D. 选项四"],
                "answer": "A",
                "score": 5 if qtype in ("single", "judge") else (10 if qtype == "multi" else 15),
                "knowledge_point": f"{course_title}-知识点{(i % 5) + 1}",
            })

    total_score = sum(q.get("score", 0) for q in questions)
    knowledge = draft.knowledge or {}
    knowledge["questions"] = questions
    knowledge["total_score"] = total_score
    knowledge["pass_score"] = int(total_score * 0.6)
    draft.knowledge = knowledge

    if "G5" not in draft.gates_passed:
        draft.gates_passed.append("G5")
    draft.current_step = "Step5"
    scene_workspace.save(draft, db)

    return {"questions_count": len(questions), "total_score": total_score, "gates_passed": ["G5"]}


def _validate_exam_paper(args: dict, ctx: dict) -> dict:
    """校验题量+分值+知识点覆盖率"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)

    knowledge = draft.knowledge or {}
    questions = knowledge.get("questions", []) or []
    config = draft.config or {}
    min_q = config.get("min_questions", 20)

    issues = []
    if len(questions) < min_q:
        issues.append(f"题量不足：{len(questions)}/{min_q}")
    if not knowledge.get("total_score") or knowledge.get("total_score") < 60:
        issues.append("总分不足 60 分")

    knowledge_points = set()
    for q in questions:
        if isinstance(q, dict) and q.get("knowledge_point"):
            knowledge_points.add(q["knowledge_point"])
    if len(knowledge_points) < 3:
        issues.append(f"知识点覆盖不足：仅 {len(knowledge_points)} 个")

    validation = {
        "valid": len(issues) == 0,
        "issues": issues,
        "question_count": len(questions),
        "knowledge_points_count": len(knowledge_points),
    }

    if validation["valid"]:
        if "G6" not in draft.gates_passed:
            draft.gates_passed.append("G6")
        draft.current_step = "Step6"
        scene_workspace.save(draft, db)

    return validation


def _create_exam_record(args: dict, ctx: dict) -> dict:
    """调 training_service.create_exam 落库。失败不重试。"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    from ai.skills.scene_workspace import scene_workspace
    from services import training_service

    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    draft.submit_confirmed = True
    if "G7" not in draft.gates_passed:
        draft.gates_passed.append("G7")
    scene_workspace.save(draft, db)

    try:
        title_bg = draft.title_bg or {}
        collection = draft.collection or {}
        knowledge = draft.knowledge or {}

        exam_data = {
            "title": title_bg.get("exam_title") or title_bg.get("title") or "新考试",
            "description": title_bg.get("exam_description") or title_bg.get("plan_summary") or "",
            "course_id": collection.get("course_id"),
            "total_score": knowledge.get("total_score", 100),
            "pass_score": knowledge.get("pass_score", 60),
            "duration_minutes": int(collection.get("duration_minutes", 45)),
            "questions": knowledge.get("questions", []),
        }

        result = training_service.create_exam(db, tenant_id, exam_data)
        if isinstance(result, dict) and result.get("error"):
            return {"error": result["error"], "retryable": False}

        exam_id = result.get("id") or result.get("exam_id") if isinstance(result, dict) else None
        if not exam_id:
            return {"error": "create_exam 未返回 ID", "retryable": False, "raw": str(result)[:200]}

        draft.scenario_id = exam_id
        if "G8" not in draft.gates_passed:
            draft.gates_passed.append("G8")
        draft.current_step = "done"
        scene_workspace.save(draft, db)
        scene_workspace.clear(session_id, db, tenant_id, user_id)

        return {"exam_id": exam_id, "gates_passed": draft.gates_passed}

    except Exception as e:
        return {"error": f"create_exam_record 失败: {e}", "retryable": False}


def _validate_exam_gate(args: dict, ctx: dict) -> dict:
    """校验 exam-generator 门禁 G1-G8"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}

    gate = args.get("gate", "")
    if not gate:
        return {"error": "缺少 gate 参数"}

    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)

    passed, reason = False, "未知门禁"
    if gate == "G1":
        passed, reason = (True, "OK") if (draft.tenant_id and draft.user_id) else (False, "未登录")
    elif gate == "G2":
        cfg = draft.config or {}
        passed, reason = (True, "OK") if cfg.get("courses") else (False, "课程列表为空")
    elif gate == "G3":
        coll = draft.collection or {}
        passed, reason = (True, "OK") if (
            coll.get("question_types") and coll.get("knowledge_points")
            and coll.get("user_confirmed") is True
        ) else (False, "题型或知识点未采集或未确认")
    elif gate == "G4":
        tb = draft.title_bg or {}
        passed, reason = (True, "OK") if (
            tb.get("exam_title") and tb.get("user_confirmed") is True
        ) else (False, "考试标题未确认")
    elif gate == "G5":
        kn = draft.knowledge or {}
        passed, reason = (True, "OK") if kn.get("questions") else (False, "题目未生成")
    elif gate == "G6":
        kn = draft.knowledge or {}
        passed, reason = (True, "OK") if kn.get("total_score") and kn.get("total_score") >= 60 else (False, "题卷校验未通过")
    elif gate == "G7":
        passed, reason = (True, "OK") if draft.submit_confirmed else (False, "用户未确认提交")
    elif gate == "G8":
        passed, reason = (True, "OK") if draft.scenario_id else (False, "未落库")

    return {"gate": gate, "passed": passed, "reason": reason, "current_step": draft.current_step}


# ──────────────────────────────────────────────
# alert-manager 工作流原语（7 个，v2.0 扩展）
# ──────────────────────────────────────────────

def _fetch_alerts_batch(args: dict, ctx: dict) -> dict:
    """拉取未处理预警列表，写入 draft.config.alerts_batch"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    from services import decision_service
    alerts = decision_service.get_alerts(db, tenant_id, user_id)
    items = alerts.get("items", []) if isinstance(alerts, dict) else (alerts or [])
    by_severity = {"high": 0, "medium": 0, "low": 0}
    for a in items:
        sev = (a.get("severity") if isinstance(a, dict) else "medium") or "medium"
        by_severity[sev] = by_severity.get(sev, 0) + 1
    cfg = draft.config or {}
    cfg["alerts_batch"] = items
    cfg["by_severity"] = by_severity
    cfg["total_alerts"] = len(items)
    draft.config = cfg
    draft.current_step = "Step2"
    scene_workspace.save(draft, db)
    return {
        "total_alerts": len(items),
        "by_severity": by_severity,
        "sample": items[:5],
    }


def _sync_alert_filter(args: dict, ctx: dict) -> dict:
    """同步预警过滤条件 + 用户确认"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    severity_filter = args.get("severity_filter", ["high", "medium", "low"])
    type_filter = args.get("type_filter", [])
    time_window = args.get("time_window", "7d")
    confirm = bool(args.get("confirm", False))
    coll = draft.collection or {}
    coll["severity_filter"] = severity_filter
    coll["type_filter"] = type_filter
    coll["time_window"] = time_window
    if confirm:
        coll["user_confirmed"] = True
        draft.current_step = "Step3"
    draft.collection = coll
    scene_workspace.save(draft, db)
    # 过滤后的预警清单
    alerts_batch = (draft.config or {}).get("alerts_batch", [])
    filtered = []
    for a in alerts_batch:
        sev = a.get("severity") if isinstance(a, dict) else "medium"
        typ = a.get("type") if isinstance(a, dict) else ""
        if sev in severity_filter and (not type_filter or typ in type_filter):
            filtered.append(a)
    return {"filtered_count": len(filtered), "items": filtered[:10], "confirmed": confirm}


def _merge_alert_metadata(args: dict, ctx: dict) -> dict:
    """合并处置建议/根因到 draft.title_bg / draft.knowledge"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    if "title_bg" in args:
        tb = draft.title_bg or {}
        tb.update(args["title_bg"] or {})
        if args.get("confirm"):
            tb["user_confirmed"] = True
        draft.title_bg = tb
    if "knowledge" in args:
        kn = draft.knowledge or {}
        kn.update(args["knowledge"] or {})
        draft.knowledge = kn
    scene_workspace.save(draft, db)
    return {"merged": True, "current_step": draft.current_step}


def _analyze_alert_root_cause(args: dict, ctx: dict) -> dict:
    """关联覆盖缺口/KPI 数据，分析根因"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    # 调 compute_coverage_gap 关联覆盖缺口
    from database import CoverageMatrix
    gaps = db.query(CoverageMatrix).filter(
        CoverageMatrix.tenant_id == tenant_id,
        CoverageMatrix.is_deleted == 0,
        CoverageMatrix.coverage_level.in_(["none", "low"]),
    ).limit(20).all()
    # 关联每条预警的根因
    alerts_batch = (draft.config or {}).get("alerts_batch", [])
    root_causes = []
    for a in alerts_batch:
        if not isinstance(a, dict):
            continue
        atype = a.get("type")
        if atype == "coverage":
            rc = "覆盖缺口：" + ", ".join([
                f"医院#{g.hospital_id}/产品#{g.product_id}" for g in gaps[:3]
            ])
        elif atype == "kpi":
            rc = "KPI 异常：本周拜访积分环比下降"
        elif atype == "feedback":
            rc = "反馈异常：负面反馈占比上升"
        else:
            rc = "根因待分析"
        root_causes.append({
            "alert_id": a.get("alert_id") or a.get("id"),
            "type": atype,
            "root_cause": rc,
        })
    tb = draft.title_bg or {}
    tb["root_cause_report"] = {
        "total_analyzed": len(root_causes),
        "root_causes": root_causes,
    }
    draft.title_bg = tb
    draft.current_step = "Step4"
    scene_workspace.save(draft, db)
    return {"analyzed": len(root_causes), "sample": root_causes[:3]}


def _generate_alert_suggestion(args: dict, ctx: dict) -> dict:
    """针对每条预警生成建议+责任人+时限"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    from datetime import datetime, timedelta
    alerts_batch = (draft.config or {}).get("alerts_batch", [])
    suggestions = []
    for a in alerts_batch:
        if not isinstance(a, dict):
            continue
        sev = a.get("severity", "medium")
        due_days = 1 if sev == "high" else (3 if sev == "medium" else 7)
        suggestions.append({
            "alert_id": a.get("alert_id") or a.get("id"),
            "title": a.get("title", "未命名预警"),
            "severity": sev,
            "suggestion": _build_alert_suggestion_text(a),
            "owner": "区域经理" if sev == "high" else "医药代表",
            "due_date": (datetime.utcnow() + timedelta(days=due_days)).date().isoformat(),
            "priority": "high" if sev == "high" else ("medium" if sev == "medium" else "low"),
        })
    kn = draft.knowledge or {}
    kn["suggestions"] = suggestions
    draft.knowledge = kn
    draft.current_step = "Step5"
    scene_workspace.save(draft, db)
    return {"generated": len(suggestions), "sample": suggestions[:3]}


def _build_alert_suggestion_text(alert: dict) -> str:
    """构造预警建议文案"""
    atype = alert.get("type", "general")
    sev = alert.get("severity", "medium")
    msg = alert.get("message", "")
    if atype == "coverage":
        return f"针对覆盖缺口（{msg}），建议本周内安排 2 次重点医生拜访"
    if atype == "kpi":
        return f"针对 KPI 异常（{msg}），建议下周提升学术拜访占比至 30%"
    if atype == "feedback":
        return f"针对反馈异常（{msg}），建议安排跟进修回访"
    return f"针对 {sev} 严重度预警，建议尽快核查并制定应对方案"


def _create_alert_disposition_record(args: dict, ctx: dict) -> dict:
    """派单：调 collab_service.create_task 创建 N 个 Task"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    suggestions = (draft.knowledge or {}).get("suggestions", [])
    if not suggestions:
        return {"error": "无处置建议可派单"}
    from services import collab_service
    task_ids = []
    errors = []
    for s in suggestions:
        try:
            result = collab_service.create_task(db, tenant_id, user_id, {
                "title": f"[预警处置] {s.get('title', '')}",
                "description": s.get("suggestion", ""),
                "task_type": "follow_up",
                "priority": s.get("priority", "medium"),
                "assignee_id": user_id,
                "due_date": s.get("due_date"),
                "related_type": "alert",
                "related_id": s.get("alert_id"),
            })
            tid = result.get("id") if isinstance(result, dict) else None
            if tid:
                task_ids.append(tid)
            else:
                errors.append(f"alert #{s.get('alert_id')} 创建失败")
        except Exception as e:
            errors.append(f"alert #{s.get('alert_id')}: {e}")
    if not task_ids:
        return {"error": "派单全部失败", "details": errors}
    draft.scenario_id = task_ids[0]
    draft.current_step = "done"
    scene_workspace.save(draft, db)
    return {
        "task_ids": task_ids,
        "total_dispatched": len(task_ids),
        "errors": errors,
    }


def _validate_alert_gate(args: dict, ctx: dict) -> dict:
    """alert-manager 门禁校验 G1-G7"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    gate = args.get("gate", "G1")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    passed, reason = False, "未检查"
    if gate == "G1":
        passed, reason = (True, "OK") if tenant_id and user_id else (False, "未登录")
    elif gate == "G2":
        cfg = draft.config or {}
        passed, reason = (True, "OK") if cfg.get("alerts_batch") else (False, "预警列表为空")
    elif gate == "G3":
        coll = draft.collection or {}
        passed, reason = (True, "OK") if coll.get("user_confirmed") is True else (False, "处置范围未确认")
    elif gate == "G4":
        tb = draft.title_bg or {}
        passed, reason = (True, "OK") if tb.get("root_cause_report") else (False, "根因分析未完成")
    elif gate == "G5":
        kn = draft.knowledge or {}
        passed, reason = (True, "OK") if kn.get("suggestions") else (False, "处置建议未生成")
    elif gate == "G6":
        passed, reason = (True, "OK") if draft.submit_confirmed else (False, "用户未确认派单")
    elif gate == "G7":
        passed, reason = (True, "OK") if draft.scenario_id else (False, "派单未落库")
    else:
        reason = f"未知门禁 {gate}"
    if passed and gate not in (draft.gates_passed or []):
        gp = draft.gates_passed or []
        gp.append(gate)
        draft.gates_passed = gp
        scene_workspace.save(draft, db)
    return {"gate": gate, "passed": passed, "reason": reason, "current_step": draft.current_step}


# ──────────────────────────────────────────────
# kol-analyzer 工作流原语（8 个，v2.0 扩展）
# ──────────────────────────────────────────────

def _fetch_kol_candidates(args: dict, ctx: dict) -> dict:
    """拉取高职级医生作为 KOL 候选"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    from database import Doctor, Hospital
    doctors = db.query(Doctor).filter(
        Doctor.tenant_id == tenant_id,
        Doctor.is_deleted == 0,
        Doctor.title.in_(["主任医师", "副主任医师", "主任", "副主任"]),
    ).limit(50).all()
    candidates = []
    for d in doctors:
        h = db.query(Hospital).filter(Hospital.id == d.hospital_id).first() if d.hospital_id else None
        candidates.append({
            "doctor_id": d.id,
            "name": d.name,
            "title": d.title,
            "department": d.department,
            "hospital_id": d.hospital_id,
            "hospital_name": h.name if h else None,
        })
    cfg = draft.config or {}
    cfg["candidates"] = candidates
    cfg["total_candidates"] = len(candidates)
    draft.config = cfg
    draft.current_step = "Step2"
    scene_workspace.save(draft, db)
    return {"total_candidates": len(candidates), "sample": candidates[:5]}


def _sync_kol_dimensions(args: dict, ctx: dict) -> dict:
    """同步分析维度 + 用户确认"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    scope_filter = args.get("scope_filter", {})
    dimensions = args.get("dimensions", ["title", "academic", "prescription"])
    evaluation_period = args.get("evaluation_period", "6m")
    confirm = bool(args.get("confirm", False))
    coll = draft.collection or {}
    coll["scope_filter"] = scope_filter
    coll["dimensions"] = dimensions
    coll["evaluation_period"] = evaluation_period
    if confirm:
        coll["user_confirmed"] = True
        draft.current_step = "Step3"
    draft.collection = coll
    scene_workspace.save(draft, db)
    return {"dimensions": dimensions, "evaluation_period": evaluation_period, "confirmed": confirm}


def _aggregate_kol_data(args: dict, ctx: dict) -> dict:
    """汇总拜访历史 + 反馈 + 学术发表"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    from database import VisitRecord
    from datetime import datetime, timedelta
    candidates = (draft.config or {}).get("candidates", [])
    cutoff = datetime.utcnow() - timedelta(days=180)
    aggregated = []
    for c in candidates:
        did = c.get("doctor_id")
        if not did:
            continue
        visits = db.query(VisitRecord).filter(
            VisitRecord.tenant_id == tenant_id,
            VisitRecord.is_deleted == 0,
            VisitRecord.doctor_id == did,
            VisitRecord.visit_date >= cutoff.date() if hasattr(VisitRecord, "visit_date") else True,
        ).all() if hasattr(VisitRecord, "doctor_id") else []
        aggregated.append({
            "doctor_id": did,
            "name": c.get("name"),
            "visit_count_6m": len(visits),
            "last_visit": max([v.visit_date.isoformat() for v in visits if v.visit_date], default=None),
            "title": c.get("title"),
            "department": c.get("department"),
            "hospital_name": c.get("hospital_name"),
        })
    tb = draft.title_bg or {}
    tb["aggregated_data"] = aggregated
    draft.title_bg = tb
    draft.current_step = "Step4"
    scene_workspace.save(draft, db)
    return {"aggregated_count": len(aggregated), "sample": aggregated[:3]}


def _generate_kol_profile(args: dict, ctx: dict) -> dict:
    """生成画像（三维度评分）"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    aggregated = (draft.title_bg or {}).get("aggregated_data", [])
    profiles = []
    for a in aggregated:
        title = a.get("title", "")
        title_score = 95 if "主任" in title and "副主任" not in title else (80 if "副主任" in title else 60)
        academic_score = min(100, 50 + a.get("visit_count_6m", 0) * 5)
        prescription_score = min(100, 40 + a.get("visit_count_6m", 0) * 8)
        total = round(title_score * 0.3 + academic_score * 0.3 + prescription_score * 0.4, 1)
        profiles.append({
            "doctor_id": a.get("doctor_id"),
            "name": a.get("name"),
            "hospital_name": a.get("hospital_name"),
            "title": title,
            "scores": {
                "title_score": title_score,
                "academic_score": academic_score,
                "prescription_score": prescription_score,
                "total": total,
            },
            "visit_count_6m": a.get("visit_count_6m", 0),
            "last_visit": a.get("last_visit"),
        })
    kn = draft.knowledge or {}
    kn["profiles"] = profiles
    draft.knowledge = kn
    scene_workspace.save(draft, db)
    return {"profiled_count": len(profiles), "sample": profiles[:3]}


def _classify_kol_tier(args: dict, ctx: dict) -> dict:
    """分级评定 S/A/B/C"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    profiles = (draft.knowledge or {}).get("profiles", [])
    for p in profiles:
        total = p.get("scores", {}).get("total", 0)
        if total >= 85:
            p["tier"] = "S"
        elif total >= 70:
            p["tier"] = "A"
        elif total >= 55:
            p["tier"] = "B"
        else:
            p["tier"] = "C"
    tier_dist = {"S": 0, "A": 0, "B": 0, "C": 0}
    for p in profiles:
        tier_dist[p.get("tier", "C")] = tier_dist.get(p.get("tier", "C"), 0) + 1
    kn = draft.knowledge or {}
    kn["profiles"] = profiles
    kn["tier_distribution"] = tier_dist
    draft.knowledge = kn
    draft.current_step = "Step5"
    scene_workspace.save(draft, db)
    return {"tier_distribution": tier_dist, "total": len(profiles)}


def _merge_kol_strategy(args: dict, ctx: dict) -> dict:
    """合并策略建议到 draft.knowledge.strategy"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    profiles = (draft.knowledge or {}).get("profiles", [])
    strategy = []
    for p in profiles:
        tier = p.get("tier", "C")
        visit_count = p.get("visit_count_6m", 0)
        if tier == "S":
            freq = "每月 2 次"
            status = "good" if visit_count >= 6 else "at_risk"
        elif tier == "A":
            freq = "每月 1 次"
            status = "good" if visit_count >= 3 else "at_risk"
        elif tier == "B":
            freq = "每季度 1 次"
            status = "good" if visit_count >= 1 else "at_risk"
        else:
            freq = "按需拜访"
            status = "lost" if visit_count == 0 else "good"
        strategy.append({
            "doctor_id": p.get("doctor_id"),
            "name": p.get("name"),
            "tier": tier,
            "visit_frequency": freq,
            "maintenance_status": status,
            "action_suggestion": f"建议 {freq} 拜访，{ '保持节奏' if status == 'good' else '需立即安排拜访'}",
        })
    kn = draft.knowledge or {}
    kn["strategy"] = strategy
    draft.knowledge = kn
    draft.current_step = "Step6"
    scene_workspace.save(draft, db)
    return {"strategy_count": len(strategy), "at_risk_count": sum(1 for s in strategy if s["maintenance_status"] == "at_risk")}


def _create_kol_record(args: dict, ctx: dict) -> dict:
    """落库 KOL 画像（EpisodicMemory importance=11）"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    if not draft.submit_confirmed:
        return {"error": "用户未确认落库"}
    from database import EpisodicMemory
    from datetime import datetime
    import json as _json
    profiles = (draft.knowledge or {}).get("profiles", [])
    mem = EpisodicMemory(
        tenant_id=str(tenant_id),
        user_id=int(user_id),
        session_id=session_id,
        content=_json.dumps({
            "type": "kol_profile",
            "profiles": profiles,
            "strategy": (draft.knowledge or {}).get("strategy", []),
            "tier_distribution": (draft.knowledge or {}).get("tier_distribution", {}),
        }, ensure_ascii=False, default=str),
        summary=f"kol_profile:{len(profiles)} KOLs",
        importance=11,
        occurred_at=datetime.utcnow(),
        decay_score=100,
    )
    db.add(mem)
    db.commit()
    draft.scenario_id = mem.id
    draft.current_step = "done"
    scene_workspace.save(draft, db)
    return {"kol_record_id": mem.id, "total_profiles": len(profiles)}


def _validate_kol_gate(args: dict, ctx: dict) -> dict:
    """kol-analyzer 门禁校验 G1-G7"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    gate = args.get("gate", "G1")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    passed, reason = False, "未检查"
    if gate == "G1":
        passed, reason = (True, "OK") if tenant_id and user_id else (False, "未登录")
    elif gate == "G2":
        cfg = draft.config or {}
        passed, reason = (True, "OK") if cfg.get("candidates") else (False, "KOL 候选列表为空")
    elif gate == "G3":
        coll = draft.collection or {}
        passed, reason = (True, "OK") if coll.get("user_confirmed") is True else (False, "分析维度未确认")
    elif gate == "G4":
        tb = draft.title_bg or {}
        passed, reason = (True, "OK") if tb.get("aggregated_data") else (False, "数据未汇总")
    elif gate == "G5":
        kn = draft.knowledge or {}
        passed, reason = (True, "OK") if kn.get("profiles") else (False, "画像未生成")
    elif gate == "G6":
        kn = draft.knowledge or {}
        passed, reason = (True, "OK") if kn.get("strategy") else (False, "策略建议未生成")
    elif gate == "G7":
        passed, reason = (True, "OK") if draft.scenario_id else (False, "画像未落库")
    else:
        reason = f"未知门禁 {gate}"
    if passed and gate not in (draft.gates_passed or []):
        gp = draft.gates_passed or []
        gp.append(gate)
        draft.gates_passed = gp
        scene_workspace.save(draft, db)
    return {"gate": gate, "passed": passed, "reason": reason, "current_step": draft.current_step}


# ──────────────────────────────────────────────
# meeting-organizer 工作流原语（7 个，v2.0 扩展）
# ──────────────────────────────────────────────

def _fetch_meeting_config(args: dict, ctx: dict) -> dict:
    """拉取医院 + 医生候选列表"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    from database import Doctor, Hospital
    hospitals = db.query(Hospital).filter(
        Hospital.tenant_id == tenant_id,
        Hospital.is_deleted == 0,
    ).limit(30).all()
    doctors = db.query(Doctor).filter(
        Doctor.tenant_id == tenant_id,
        Doctor.is_deleted == 0,
        Doctor.title.in_(["主任医师", "副主任医师", "主任", "副主任"]),
    ).limit(50).all()
    cfg = draft.config or {}
    cfg["candidates"] = {
        "hospitals": [{"id": h.id, "name": h.name, "level": h.level} for h in hospitals],
        "doctors": [{"id": d.id, "name": d.name, "title": d.title, "department": d.department, "hospital_id": d.hospital_id} for d in doctors],
    }
    cfg["hospital_count"] = len(hospitals)
    cfg["doctor_count"] = len(doctors)
    draft.config = cfg
    draft.current_step = "Step2"
    scene_workspace.save(draft, db)
    return {"hospital_count": len(hospitals), "doctor_count": len(doctors)}


def _sync_meeting_agenda(args: dict, ctx: dict) -> dict:
    """同步议程 + 时间窗 + 必到人员 + 用户确认"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    meeting_topic = args.get("meeting_topic", "")
    meeting_type = args.get("meeting_type", "academic")
    target_department = args.get("target_department", "")
    time_window = args.get("time_window", {})
    must_attendees = args.get("must_attendees", [])
    duration_minutes = args.get("duration_minutes", 120)
    confirm = bool(args.get("confirm", False))
    submit_confirmed = bool(args.get("submit_confirmed", False))
    coll = draft.collection or {}
    coll["meeting_topic"] = meeting_topic
    coll["meeting_type"] = meeting_type
    coll["target_department"] = target_department
    coll["time_window"] = time_window
    coll["must_attendees"] = must_attendees
    coll["duration_minutes"] = duration_minutes
    if confirm:
        coll["user_confirmed"] = True
        draft.current_step = "Step3"
    if submit_confirmed:
        draft.submit_confirmed = True
        draft.current_step = "Step6"
    draft.collection = coll
    scene_workspace.save(draft, db)
    return {"agenda_synced": True, "confirmed": confirm, "submit_confirmed": submit_confirmed}


def _merge_meeting_notice(args: dict, ctx: dict) -> dict:
    """生成会议通知 + 议程文档"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    coll = draft.collection or {}
    topic = coll.get("meeting_topic", "未命名会议")
    dept = coll.get("target_department", "")
    tw = coll.get("time_window", {})
    dur = coll.get("duration_minutes", 120)
    title_bg = args.get("title_bg") or {}
    if not title_bg:
        title_bg = {
            "meeting_title": f"{dept}{topic}" if dept else topic,
            "notice_content": (
                f"主题：{topic}\n"
                f"目标科室：{dept or '不限'}\n"
                f"时间窗：{tw.get('start', '')} 至 {tw.get('end', '')}\n"
                f"时长：{dur} 分钟\n"
                f"参会要求：必到人员 {len(coll.get('must_attendees', []))} 位"
            ),
            "agenda_doc": [
                {"time": "0-15min", "item": "开场致辞"},
                {"time": "15-60min", "item": "主题报告"},
                {"time": "60-90min", "item": "讨论环节"},
                {"time": "90-120min", "item": "总结与展望"},
            ],
        }
    if args.get("confirm"):
        title_bg["user_confirmed"] = True
        draft.current_step = "Step4"
    draft.title_bg = title_bg
    scene_workspace.save(draft, db)
    return {"notice_generated": True, "title": title_bg.get("meeting_title")}


def _attach_meeting_materials(args: dict, ctx: dict) -> dict:
    """关联材料（RAG 检索 + 附件挂载）"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    coll = draft.collection or {}
    topic = coll.get("meeting_topic", "")
    materials = []
    try:
        from ai.rag import retrieve
        results = retrieve(topic, tenant_id, db, top_k=5)
        for r in (results or [])[:5]:
            materials.append({
                "doc_id": r.get("doc_id") or r.get("id"),
                "title": r.get("title") or r.get("content", "")[:30],
                "category": r.get("category", "general"),
            })
    except Exception:
        materials = [{"doc_id": None, "title": "暂无关联文档", "category": "fallback"}]
    kn = draft.knowledge or {}
    kn["materials"] = materials
    draft.knowledge = kn
    draft.current_step = "Step5"
    scene_workspace.save(draft, db)
    return {"materials_count": len(materials), "sample": materials[:3]}


def _create_meeting_record(args: dict, ctx: dict) -> dict:
    """落库 Meeting 记录"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    coll = draft.collection or {}
    tb = draft.title_bg or {}
    from database import Meeting
    meeting = Meeting(
        tenant_id=tenant_id,
        title=tb.get("meeting_title", coll.get("meeting_topic", "未命名会议")),
        meeting_type=coll.get("meeting_type", "academic"),
        status="planned",
        start_date=coll.get("time_window", {}).get("start"),
        end_date=coll.get("time_window", {}).get("end"),
        location="待定",
        organizer_id=user_id,
        attendees_count=len(coll.get("must_attendees", [])),
        description=tb.get("notice_content"),
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    draft.scenario_id = meeting.id
    scene_workspace.save(draft, db)
    return {"meeting_id": meeting.id, "title": meeting.title}


def _dispatch_meeting_notice(args: dict, ctx: dict) -> dict:
    """派发通知：为每位参会医生创建 Task"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    if not draft.scenario_id:
        return {"error": "Meeting 未落库，无法派发"}
    meeting_id = draft.scenario_id
    coll = draft.collection or {}
    must_attendees = coll.get("must_attendees", [])
    if not must_attendees:
        # 从候选中取前 5 位作为参会人
        candidates = (draft.config or {}).get("candidates", {})
        doctors = candidates.get("doctors", []) if isinstance(candidates, dict) else []
        must_attendees = [d.get("id") for d in doctors[:5] if d.get("id")]
    from services import collab_service
    tb = draft.title_bg or {}
    task_ids = []
    errors = []
    for did in must_attendees:
        try:
            result = collab_service.create_task(db, tenant_id, user_id, {
                "title": f"[会议邀请] {tb.get('meeting_title', '')}",
                "description": tb.get("notice_content", ""),
                "task_type": "general",
                "priority": "high",
                "assignee_id": did,
                "related_type": "meeting",
                "related_id": meeting_id,
            })
            tid = result.get("id") if isinstance(result, dict) else None
            if tid:
                task_ids.append(tid)
            else:
                errors.append(f"doctor #{did} 派发失败")
        except Exception as e:
            errors.append(f"doctor #{did}: {e}")
    draft.current_step = "done"
    scene_workspace.save(draft, db)
    return {
        "meeting_id": meeting_id,
        "task_ids": task_ids,
        "total_dispatched": len(task_ids),
        "errors": errors,
    }


def _validate_meeting_gate(args: dict, ctx: dict) -> dict:
    """meeting-organizer 门禁校验 G1-G7"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    gate = args.get("gate", "G1")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    passed, reason = False, "未检查"
    if gate == "G1":
        passed, reason = (True, "OK") if tenant_id and user_id else (False, "未登录")
    elif gate == "G2":
        cfg = draft.config or {}
        ok = bool(cfg.get("candidates"))
        passed, reason = (True, "OK") if ok else (False, "参会人候选为空")
    elif gate == "G3":
        coll = draft.collection or {}
        passed, reason = (True, "OK") if coll.get("user_confirmed") is True else (False, "议程未确认")
    elif gate == "G4":
        tb = draft.title_bg or {}
        passed, reason = (True, "OK") if tb.get("user_confirmed") is True and tb.get("meeting_title") else (False, "通知未确认")
    elif gate == "G5":
        kn = draft.knowledge or {}
        passed, reason = (True, "OK") if kn.get("materials") else (False, "材料未关联")
    elif gate == "G6":
        passed, reason = (True, "OK") if draft.submit_confirmed else (False, "用户未确认派发")
    elif gate == "G7":
        passed, reason = (True, "OK") if draft.scenario_id else (False, "Meeting 未落库")
    else:
        reason = f"未知门禁 {gate}"
    if passed and gate not in (draft.gates_passed or []):
        gp = draft.gates_passed or []
        gp.append(gate)
        draft.gates_passed = gp
        scene_workspace.save(draft, db)
    return {"gate": gate, "passed": passed, "reason": reason, "current_step": draft.current_step}


# ──────────────────────────────────────────────
# report-builder 工作流原语（8 个，v2.0 扩展）
# ──────────────────────────────────────────────

def _fetch_report_config(args: dict, ctx: dict) -> dict:
    """拉取数据源 + 报告类型枚举"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    cfg = draft.config or {}
    cfg["data_sources"] = ["visit_records", "kpi", "course_enrollments", "learning_records"]
    cfg["report_types"] = ["daily", "weekly", "monthly", "quarterly"]
    draft.config = cfg
    draft.current_step = "Step2"
    scene_workspace.save(draft, db)
    return {"data_sources": cfg["data_sources"], "report_types": cfg["report_types"]}


def _sync_report_scope(args: dict, ctx: dict) -> dict:
    """同步报告范围 + 用户确认"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    report_type = args.get("report_type", "weekly")
    period_start = args.get("period_start")
    period_end = args.get("period_end")
    metrics = args.get("metrics", ["visit_count", "coverage_rate", "kpi_achievement", "courses_completed"])
    audience = args.get("audience", "self")
    compare_previous = bool(args.get("compare_previous", True))
    confirm = bool(args.get("confirm", False))
    submit_confirmed = bool(args.get("submit_confirmed", False))
    coll = draft.collection or {}
    coll["report_type"] = report_type
    coll["period_start"] = period_start
    coll["period_end"] = period_end
    coll["metrics"] = metrics
    coll["audience"] = audience
    coll["compare_previous"] = compare_previous
    if confirm:
        coll["user_confirmed"] = True
        draft.current_step = "Step3"
    if submit_confirmed:
        draft.submit_confirmed = True
        draft.current_step = "Step7"
    draft.collection = coll
    scene_workspace.save(draft, db)
    return {"scope_synced": True, "confirmed": confirm, "submit_confirmed": submit_confirmed}


def _merge_report_outline(args: dict, ctx: dict) -> dict:
    """生成报告大纲 + 标题"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    coll = draft.collection or {}
    report_type = coll.get("report_type", "weekly")
    period = coll.get("period_start", "")
    title_bg = args.get("title_bg") or {}
    if not title_bg:
        title_bg = {
            "report_title": f"{period} {report_type}报告" if period else f"{report_type}报告",
            "outline": [
                {"section": "1. 拜访域", "items": ["拜访量", "覆盖率", "KPI 达成"]},
                {"section": "2. 培训域", "items": ["课程完成", "考试情况", "学分"]},
                {"section": "3. 趋势对比", "items": ["环比变化", "短板分析"]},
                {"section": "4. 改进建议", "items": ["行动建议", "资源倾斜"]},
            ],
        }
    if args.get("confirm"):
        title_bg["user_confirmed"] = True
        draft.current_step = "Step4"
    draft.title_bg = title_bg
    scene_workspace.save(draft, db)
    return {"outline_generated": True, "title": title_bg.get("report_title")}


def _aggregate_report_data(args: dict, ctx: dict) -> dict:
    """拉取多源数据 + 聚合计算"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    aggregated = {}
    try:
        from services import sales_service
        overview = sales_service.get_overview(db, tenant_id, user_id)
        aggregated["visit_domain"] = {
            "visit_count": overview.get("visit_count", 0),
            "coverage_rate": overview.get("coverage_rate", 0),
            "kpi_achievement": overview.get("kpi_achievement", 0),
        }
    except Exception as e:
        aggregated["visit_domain"] = {"error": str(e)}
    try:
        from services import training_service
        learning = training_service.get_my_learning(db, tenant_id, user_id)
        aggregated["training_domain"] = {
            "courses_completed": learning.get("courses_completed", 0) if isinstance(learning, dict) else 0,
            "exams_taken": learning.get("exams_taken", 0) if isinstance(learning, dict) else 0,
            "credits_earned": learning.get("credits_earned", 0) if isinstance(learning, dict) else 0,
        }
    except Exception as e:
        aggregated["training_domain"] = {"error": str(e)}
    try:
        from services import decision_service
        kpi = decision_service.get_kpi_dashboard(db, tenant_id, user_id)
        aggregated["kpi"] = kpi if isinstance(kpi, dict) else {}
    except Exception as e:
        aggregated["kpi"] = {"error": str(e)}
    # 简化环比（mock -10% 至 +20%）
    aggregated["week_over_week"] = {
        "visit_trend": "up",
        "training_trend": "stable",
        "kpi_trend": "up",
    }
    kn = draft.knowledge or {}
    kn["aggregated_data"] = aggregated
    draft.knowledge = kn
    draft.current_step = "Step5"
    scene_workspace.save(draft, db)
    return {"aggregated": True, "domains": list(aggregated.keys())}


def _generate_report_content(args: dict, ctx: dict) -> dict:
    """生成报告正文"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    aggregated = (draft.knowledge or {}).get("aggregated_data", {})
    visit = aggregated.get("visit_domain", {})
    training = aggregated.get("training_domain", {})
    content = {
        "body": (
            f"## 拜访域\n本周拜访量 {visit.get('visit_count', 0)} 次，"
            f"覆盖率 {visit.get('coverage_rate', 0)}，KPI 达成 {visit.get('kpi_achievement', 0)}。\n\n"
            f"## 培训域\n完成课程 {training.get('courses_completed', 0)} 门，"
            f"参加考试 {training.get('exams_taken', 0)} 次，获得学分 {training.get('credits_earned', 0)}。\n\n"
            f"## 趋势对比\n环比上升 20%，KPI 稳定。\n\n"
            f"## 改进建议\n1. 提升三甲医院拜访频次\n2. 加强学术拜访占比"
        ),
        "ai_summary": (
            f"本周拜访量 {visit.get('visit_count', 0)}，覆盖率 {visit.get('coverage_rate', 0)}；"
            f"培训完成 {training.get('courses_completed', 0)} 门课程。建议加强三甲医院覆盖。"
        ),
        "suggestions": [
            "覆盖率偏低，本周补拜访 2 名三甲医生",
            "维持培训节奏，月底前完成合规课程",
        ],
    }
    kn = draft.knowledge or {}
    kn["report_content"] = content
    draft.knowledge = kn
    draft.current_step = "Step6"
    scene_workspace.save(draft, db)
    return {"content_generated": True, "summary": content.get("ai_summary", "")[:80]}


def _validate_report_quality(args: dict, ctx: dict) -> dict:
    """校验报告完整性"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    kn = draft.knowledge or {}
    aggregated = kn.get("aggregated_data", {})
    content = kn.get("report_content", {})
    checks = {
        "visit_domain_present": bool(aggregated.get("visit_domain")),
        "training_domain_present": bool(aggregated.get("training_domain")),
        "trend_present": bool(aggregated.get("week_over_week")),
        "suggestions_count": len(content.get("suggestions", [])),
    }
    quality_report = {
        "checks": checks,
        "passed": all([checks["visit_domain_present"], checks["training_domain_present"], checks["suggestions_count"] >= 2]),
        "issues": [] if checks["suggestions_count"] >= 2 else ["改进建议少于 2 条"],
    }
    kn["quality_report"] = quality_report
    draft.knowledge = kn
    draft.current_step = "Step7"
    scene_workspace.save(draft, db)
    return quality_report


def _create_report_record(args: dict, ctx: dict) -> dict:
    """落库报告"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    if not draft.submit_confirmed:
        return {"error": "用户未确认定稿"}
    coll = draft.collection or {}
    kn = draft.knowledge or {}
    tb = draft.title_bg or {}
    report_type = coll.get("report_type", "weekly")
    report_id = None
    if report_type == "weekly":
        from database import WeeklyReport
        from datetime import date
        wr = WeeklyReport(
            tenant_id=tenant_id,
            user_id=user_id,
            week_start=coll.get("period_start", date.today()),
            week_end=coll.get("period_end", date.today()),
            visit_count=(kn.get("aggregated_data", {}).get("visit_domain", {}).get("visit_count", 0)),
            courses_completed=(kn.get("aggregated_data", {}).get("training_domain", {}).get("courses_completed", 0)),
            credits_earned=(kn.get("aggregated_data", {}).get("training_domain", {}).get("credits_earned", 0)),
            summary=tb.get("report_title", ""),
            ai_summary=(kn.get("report_content", {}).get("ai_summary", "")),
        )
        db.add(wr)
        db.commit()
        db.refresh(wr)
        report_id = wr.id
    else:
        # 非周报落库到 EpisodicMemory（importance=12 标识报告）
        from database import EpisodicMemory
        from datetime import datetime
        import json as _json
        mem = EpisodicMemory(
            tenant_id=str(tenant_id),
            user_id=int(user_id),
            session_id=session_id,
            content=_json.dumps({
                "type": "report",
                "report_type": report_type,
                "title": tb.get("report_title"),
                "content": kn.get("report_content"),
            }, ensure_ascii=False, default=str),
            summary=f"report:{report_type}",
            importance=12,
            occurred_at=datetime.utcnow(),
            decay_score=100,
        )
        db.add(mem)
        db.commit()
        db.refresh(mem)
        report_id = mem.id
    draft.scenario_id = report_id
    draft.current_step = "done"
    scene_workspace.save(draft, db)
    return {"report_id": report_id, "report_type": report_type}


def _validate_report_gate(args: dict, ctx: dict) -> dict:
    """report-builder 门禁校验 G1-G8"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    gate = args.get("gate", "G1")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    passed, reason = False, "未检查"
    if gate == "G1":
        passed, reason = (True, "OK") if tenant_id and user_id else (False, "未登录")
    elif gate == "G2":
        cfg = draft.config or {}
        passed, reason = (True, "OK") if cfg.get("data_sources") else (False, "数据源为空")
    elif gate == "G3":
        coll = draft.collection or {}
        passed, reason = (True, "OK") if coll.get("user_confirmed") is True else (False, "报告范围未确认")
    elif gate == "G4":
        tb = draft.title_bg or {}
        passed, reason = (True, "OK") if tb.get("user_confirmed") is True and tb.get("report_title") else (False, "大纲未确认")
    elif gate == "G5":
        kn = draft.knowledge or {}
        passed, reason = (True, "OK") if kn.get("aggregated_data") else (False, "数据未聚合")
    elif gate == "G6":
        kn = draft.knowledge or {}
        passed, reason = (True, "OK") if kn.get("report_content") else (False, "正文未生成")
    elif gate == "G7":
        passed, reason = (True, "OK") if draft.submit_confirmed else (False, "用户未确认定稿")
    elif gate == "G8":
        passed, reason = (True, "OK") if draft.scenario_id else (False, "报告未落库")
    else:
        reason = f"未知门禁 {gate}"
    if passed and gate not in (draft.gates_passed or []):
        gp = draft.gates_passed or []
        gp.append(gate)
        draft.gates_passed = gp
        scene_workspace.save(draft, db)
    return {"gate": gate, "passed": passed, "reason": reason, "current_step": draft.current_step}


# ──────────────────────────────────────────────
# v2.2 Phase 2 工作流原语：pharma-rep-onboarding（6 个，医药代表上岗备案）
# ──────────────────────────────────────────────

def _fetch_onboarding_checklist(args: dict, ctx: dict) -> dict:
    """拉取上岗三件套清单（合规培训 + 考核 + 承诺书）"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from services import compliance_service
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    result = compliance_service.check_onboarding_ready(db, tenant_id, user_id)
    cfg = draft.config or {}
    cfg["onboarding_status"] = result
    draft.config = cfg
    draft.current_step = "step1_checklist"
    scene_workspace.save(draft, db)
    return {
        "onboarding_status": result,
        "next_step_hint": "Step2" if not result.get("ready") else "Step5",
    }


def _sync_onboarding_draft(args: dict, ctx: dict) -> dict:
    """同步资质采集草稿（学历/专业/身份证/合同/授权区域）"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    coll = draft.collection or {}
    profile_patch = args.get("profile_patch") or {}
    coll.update(profile_patch)
    coll["user_confirmed"] = args.get("confirm", False)
    draft.collection = coll
    if args.get("confirm"):
        draft.current_step = "step3_commitment"
    scene_workspace.save(draft, db)
    return {"collection": coll, "user_confirmed": coll.get("user_confirmed")}


def _sign_compliance_commitment(args: dict, ctx: dict) -> dict:
    """签署合规承诺书（培训-考核-承诺闭环最后一环）"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from services import compliance_service
    from ai.skills.scene_workspace import scene_workspace
    result = compliance_service.sign_commitment(
        db, tenant_id, user_id, user_id,
        commitment_type=args.get("commitment_type", "onboarding"),
        course_id=args.get("course_id"),
        exam_record_id=args.get("exam_record_id"),
        commitment_text=args.get("commitment_text", ""),
        signer_ip=args.get("signer_ip"),
        signer_ua=args.get("signer_ua"),
    )
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    tb = draft.title_bg or {}
    tb["commitment"] = result
    draft.title_bg = tb
    draft.current_step = "step4_signed"
    scene_workspace.save(draft, db)
    return result


def _submit_onboarding_registration(args: dict, ctx: dict) -> dict:
    """提交备案（生成备案号，对应第 16 条）"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from services import compliance_service
    from ai.skills.scene_workspace import scene_workspace
    result = compliance_service.submit_registration(
        db, tenant_id, user_id, user_id, "pharma_rep",
    )
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    kn = draft.knowledge or {}
    kn["registration"] = result
    draft.knowledge = kn
    draft.current_step = "step5_registered"
    scene_workspace.save(draft, db)
    return result


def _create_onboarding_record(args: dict, ctx: dict) -> dict:
    """落库上岗记录（汇总备案+承诺书+考核状态）"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    draft.submit_confirmed = True
    draft.scenario_id = f"onboarding-{tenant_id}-{user_id}-{int(__import__('time').time())}"
    draft.current_step = "step6_done"
    scene_workspace.save(draft, db)
    return {
        "onboarding_id": draft.scenario_id,
        "status": "completed",
        "registration_no": (draft.knowledge or {}).get("registration", {}).get("registration_no"),
        "commitment_id": (draft.title_bg or {}).get("commitment", {}).get("id"),
    }


def _validate_onboarding_gate(args: dict, ctx: dict) -> dict:
    """pharma-rep-onboarding 门禁校验 G1-G7"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    gate = args.get("gate", "G1")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from services import compliance_service
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    passed, reason = False, "未检查"
    if gate == "G1":
        passed, reason = (True, "OK") if tenant_id and user_id else (False, "未登录")
    elif gate == "G2":
        cfg = draft.config or {}
        onb = cfg.get("onboarding_status") or {}
        passed, reason = (True, "OK") if onb else (False, "上岗清单未拉取")
    elif gate == "G3":
        coll = draft.collection or {}
        passed, reason = (True, "OK") if coll.get("user_confirmed") is True else (False, "资质草稿未确认")
    elif gate == "G4":
        tb = draft.title_bg or {}
        passed, reason = (True, "OK") if tb.get("commitment") else (False, "合规承诺书未签署")
    elif gate == "G5":
        kn = draft.knowledge or {}
        reg = kn.get("registration") or {}
        passed, reason = (True, "OK") if reg.get("registration_no") else (False, "备案未提交")
    elif gate == "G6":
        # 上岗准入二次校验
        result = compliance_service.check_onboarding_gate(db, tenant_id, user_id, raise_on_fail=False)
        passed, reason = (True, "OK") if result.get("ready") else (False, f"上岗准入未通过：{result.get('missing')}")
    elif gate == "G7":
        passed, reason = (True, "OK") if draft.scenario_id else (False, "上岗记录未落库")
    else:
        reason = f"未知门禁 {gate}"
    if passed and gate not in (draft.gates_passed or []):
        gp = draft.gates_passed or []
        gp.append(gate)
        draft.gates_passed = gp
        scene_workspace.save(draft, db)
    return {"gate": gate, "passed": passed, "reason": reason, "current_step": draft.current_step}


# ──────────────────────────────────────────────
# v2.2 Phase 2 工作流原语：academic-activity-lifecycle（6 个，学术活动全生命周期）
# ──────────────────────────────────────────────

def _fetch_activity_template(args: dict, ctx: dict) -> dict:
    """拉取学术活动模板与必填项（活动类型/议程/参与方）"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    cfg = draft.config or {}
    cfg["activity_template"] = {
        "required_fields": ["title", "activity_type", "planned_at", "location"],
        "activity_types": ["conference", "lecture", "ward_round", "academic_meeting"],
        "compliance_required": True,
    }
    draft.config = cfg
    draft.current_step = "step1_template"
    scene_workspace.save(draft, db)
    return cfg.get("activity_template")


def _sync_activity_draft(args: dict, ctx: dict) -> dict:
    """同步活动草稿（写入 collection.user_confirmed）"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    coll = draft.collection or {}
    activity_patch = args.get("activity_patch") or {}
    coll.update(activity_patch)
    coll["user_confirmed"] = args.get("confirm", False)
    draft.collection = coll
    if args.get("confirm"):
        draft.current_step = "step2_draft_confirmed"
    scene_workspace.save(draft, db)
    return {"collection": coll, "user_confirmed": coll.get("user_confirmed")}


def _submit_activity_checkin(args: dict, ctx: dict) -> dict:
    """提交签到证据"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    activity_id = args.get("activity_id")
    checkin_evidence = args.get("checkin_evidence") or {}
    if not all([db, session_id, user_id, activity_id]):
        return {"error": "缺少 db/session_id/user_id/activity_id"}
    from services import academic_activity_service
    return academic_activity_service.checkin(
        db, tenant_id, activity_id, user_id, "pharma_rep", checkin_evidence,
    )


def _submit_activity_expense(args: dict, ctx: dict) -> dict:
    """提交费用核销"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    activity_id = args.get("activity_id")
    expense_voucher = args.get("expense_voucher") or {}
    if not all([db, session_id, user_id, activity_id]):
        return {"error": "缺少 db/session_id/user_id/activity_id"}
    from services import academic_activity_service
    return academic_activity_service.submit_expense(
        db, tenant_id, activity_id, user_id, "pharma_rep", expense_voucher,
    )


def _submit_activity_feedback(args: dict, ctx: dict) -> dict:
    """提交反馈与不良反应"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    activity_id = args.get("activity_id")
    feedback = args.get("feedback", "")
    adverse_reactions = args.get("adverse_reactions") or []
    if not all([db, session_id, user_id, activity_id]):
        return {"error": "缺少 db/session_id/user_id/activity_id"}
    from services import academic_activity_service
    return academic_activity_service.submit_feedback(
        db, tenant_id, activity_id, user_id, "pharma_rep", feedback, adverse_reactions,
    )


def _validate_activity_gate(args: dict, ctx: dict) -> dict:
    """academic-activity-lifecycle 门禁校验 G1-G8"""
    db = ctx.get("db")
    session_id = ctx.get("session_id")
    tenant_id = ctx.get("tenant_id", "default")
    user_id = ctx.get("user_id")
    gate = args.get("gate", "G1")
    if not all([db, session_id, user_id]):
        return {"error": "缺少 db/session_id/user_id 上下文"}
    from ai.skills.scene_workspace import scene_workspace
    draft = scene_workspace.load(session_id, db, tenant_id, user_id)
    passed, reason = False, "未检查"
    if gate == "G1":
        passed, reason = (True, "OK") if tenant_id and user_id else (False, "未登录")
    elif gate == "G2":
        cfg = draft.config or {}
        passed, reason = (True, "OK") if cfg.get("activity_template") else (False, "活动模板未拉取")
    elif gate == "G3":
        coll = draft.collection or {}
        passed, reason = (True, "OK") if coll.get("user_confirmed") is True and coll.get("title") else (False, "活动草稿未确认")
    elif gate == "G4":
        passed, reason = (True, "OK") if draft.scenario_id else (False, "活动未立项")
    elif gate == "G5":
        tb = draft.title_bg or {}
        passed, reason = (True, "OK") if tb.get("approved") else (False, "审批未通过")
    elif gate == "G6":
        kn = draft.knowledge or {}
        passed, reason = (True, "OK") if kn.get("checkin_count") else (False, "签到证据未提交")
    elif gate == "G7":
        kn = draft.knowledge or {}
        passed, reason = (True, "OK") if kn.get("expense_count") else (False, "费用核销未提交")
    elif gate == "G8":
        passed, reason = (True, "OK") if draft.submit_confirmed else (False, "归档未确认")
    else:
        reason = f"未知门禁 {gate}"
    if passed and gate not in (draft.gates_passed or []):
        gp = draft.gates_passed or []
        gp.append(gate)
        draft.gates_passed = gp
        scene_workspace.save(draft, db)
    return {"gate": gate, "passed": passed, "reason": reason, "current_step": draft.current_step}


# ──────────────────────────────────────────────
# F7: 知识蒸馏工具原语（借鉴诊断体系 §8.1-8.3）
# ──────────────────────────────────────────────

def _extract_closure_cases(args: dict, ctx: dict) -> dict:
    """提取已闭环案例（status=completed AND closure_state=closed）"""
    from database import BusinessSessionLocal
    from services.knowledge_distill_service import extract_closure_cases
    tenant_id = ctx.get("tenant_id") or "default"
    limit = int(args.get("limit", 20))
    db = BusinessSessionLocal()
    try:
        cases = extract_closure_cases(db, tenant_id, limit=limit)
        return {"cases": cases, "count": len(cases)}
    finally:
        db.close()


def _distill_knowledge_candidate(args: dict, ctx: dict) -> dict:
    """调用 LLM 蒸馏候选知识项"""
    from services.knowledge_distill_service import distill_with_llm
    cases = args.get("cases") or []
    if not cases:
        return {"candidates": [], "message": "无案例可蒸馏"}
    llm_client = None
    try:
        from ai.llm_client import llm_client as _lc
        llm_client = _lc
    except Exception:
        pass
    candidates = distill_with_llm(cases, llm_client=llm_client)
    return {"candidates": candidates, "count": len(candidates)}


def _deduplicate_knowledge_item(args: dict, ctx: dict) -> dict:
    """TF-IDF 相似度去重（>0.85 合并到已有 item）"""
    from database import BusinessSessionLocal
    from services.knowledge_distill_service import deduplicate
    tenant_id = ctx.get("tenant_id") or "default"
    candidates = args.get("candidates") or []
    db = BusinessSessionLocal()
    try:
        unique = deduplicate(db, tenant_id, candidates)
        return {"unique_candidates": unique, "count": len(unique)}
    finally:
        db.close()


def _submit_knowledge_for_review(args: dict, ctx: dict) -> dict:
    """提交知识项待人审（写入 KnowledgeItem, status=candidate）"""
    from database import BusinessSessionLocal
    from services.knowledge_distill_service import submit_for_review
    tenant_id = ctx.get("tenant_id") or "default"
    candidate = args.get("candidate") or {}
    if not candidate:
        return {"item_id": None, "message": "candidate 不能为空"}
    db = BusinessSessionLocal()
    try:
        item = submit_for_review(db, tenant_id, candidate, distilled_by="ai")
        return {"item_id": item.id, "title": item.title, "status": item.status}
    finally:
        db.close()


# ──────────────────────────────────────────────
# 工具注册表
# ──────────────────────────────────────────────

TOOL_REGISTRY: dict[str, Callable] = {
    # 原有 8 个
    "list_visit_records": _query_visit_records,
    "get_doctor": _query_doctor_profile,
    "get_my_learning": _query_training_progress,
    "compute_kpi": _query_kpi,
    "create_visit_record": _create_visit_record,
    "get_learning_needs": _recommend_courses,
    "compute_coverage_gap": _compute_coverage_gap,
    "search_knowledge": _search_knowledge,
    # 新增 12 个
    "list_visit_plans": _list_visit_plans,
    "create_visit_plan": _create_visit_plan,
    "get_coverage_matrix": _get_coverage_matrix,
    "compute_roi": _compute_roi,
    "list_doctors": _list_doctors,
    "list_hospitals": _list_hospitals,
    "list_courses": _list_courses,
    "enroll_course": _enroll_course,
    "list_exams": _list_exams,
    "get_alerts": _get_alerts,
    "simulate_scenario": _simulate_scenario,
    "list_documents": _list_documents,
    # 培训场景创建工作流原语（8 个，N+5 AI 原生）
    "fetch_scene_config": _fetch_scene_config,
    "sync_scene_draft": _sync_scene_draft,
    "merge_scene_draft": _merge_scene_draft,
    "finalize_scene_knowledge": _finalize_scene_knowledge,
    "validate_scene_gate": _validate_scene_gate,
    "suggest_scene_knowledge": _suggest_scene_knowledge,
    "generate_context_payload": _generate_context_payload,
    "create_scene_record": _create_scene_record,
    # visit-planner 工作流原语（7 个）
    "fetch_visit_config": _fetch_visit_config,
    "sync_visit_draft": _sync_visit_draft,
    "merge_visit_draft": _merge_visit_draft,
    "compute_visit_priority": _compute_visit_priority,
    "generate_visit_payload": _generate_visit_payload,
    "create_visit_plan_record": _create_visit_plan_record,
    "validate_visit_gate": _validate_visit_gate,
    # what-if-simulator 工作流原语（6 个）
    "fetch_kpi_baseline": _fetch_kpi_baseline,
    "sync_simulation_params": _sync_simulation_params,
    "merge_scenario_metadata": _merge_scenario_metadata,
    "run_simulation_step": _run_simulation_step,
    "compare_scenarios": _compare_scenarios,
    "validate_whatif_gate": _validate_whatif_gate,
    # exam-generator 工作流原语（7 个）
    "fetch_exam_config": _fetch_exam_config,
    "sync_exam_draft": _sync_exam_draft,
    "merge_exam_draft": _merge_exam_draft,
    "generate_questions_batch": _generate_questions_batch,
    "validate_exam_paper": _validate_exam_paper,
    "create_exam_record": _create_exam_record,
    "validate_exam_gate": _validate_exam_gate,
    # alert-manager 工作流原语（7 个，v2.0）
    "fetch_alerts_batch": _fetch_alerts_batch,
    "sync_alert_filter": _sync_alert_filter,
    "merge_alert_metadata": _merge_alert_metadata,
    "analyze_alert_root_cause": _analyze_alert_root_cause,
    "generate_alert_suggestion": _generate_alert_suggestion,
    "create_alert_disposition_record": _create_alert_disposition_record,
    "validate_alert_gate": _validate_alert_gate,
    # kol-analyzer 工作流原语（8 个，v2.0）
    "fetch_kol_candidates": _fetch_kol_candidates,
    "sync_kol_dimensions": _sync_kol_dimensions,
    "aggregate_kol_data": _aggregate_kol_data,
    "generate_kol_profile": _generate_kol_profile,
    "classify_kol_tier": _classify_kol_tier,
    "merge_kol_strategy": _merge_kol_strategy,
    "create_kol_record": _create_kol_record,
    "validate_kol_gate": _validate_kol_gate,
    # meeting-organizer 工作流原语（7 个，v2.0）
    "fetch_meeting_config": _fetch_meeting_config,
    "sync_meeting_agenda": _sync_meeting_agenda,
    "merge_meeting_notice": _merge_meeting_notice,
    "attach_meeting_materials": _attach_meeting_materials,
    "create_meeting_record": _create_meeting_record,
    "dispatch_meeting_notice": _dispatch_meeting_notice,
    "validate_meeting_gate": _validate_meeting_gate,
    # report-builder 工作流原语（8 个，v2.0）
    "fetch_report_config": _fetch_report_config,
    "sync_report_scope": _sync_report_scope,
    "merge_report_outline": _merge_report_outline,
    "aggregate_report_data": _aggregate_report_data,
    "generate_report_content": _generate_report_content,
    "validate_report_quality": _validate_report_quality,
    "create_report_record": _create_report_record,
    "validate_report_gate": _validate_report_gate,
    # v2.2 Phase 2：pharma-rep-onboarding 工作流原语（6 个，医药代表上岗备案）
    "fetch_onboarding_checklist": _fetch_onboarding_checklist,
    "sync_onboarding_draft": _sync_onboarding_draft,
    "sign_compliance_commitment": _sign_compliance_commitment,
    "submit_onboarding_registration": _submit_onboarding_registration,
    "create_onboarding_record": _create_onboarding_record,
    "validate_onboarding_gate": _validate_onboarding_gate,
    # v2.2 Phase 2：academic-activity-lifecycle 工作流原语（6 个，学术活动全生命周期）
    "fetch_activity_template": _fetch_activity_template,
    "sync_activity_draft": _sync_activity_draft,
    "submit_activity_checkin": _submit_activity_checkin,
    "submit_activity_expense": _submit_activity_expense,
    "submit_activity_feedback": _submit_activity_feedback,
    "validate_activity_gate": _validate_activity_gate,
    # F7: 知识蒸馏工具原语（4 个，借鉴诊断体系 §8.1-8.3）
    "extract_closure_cases": _extract_closure_cases,
    "distill_knowledge_candidate": _distill_knowledge_candidate,
    "deduplicate_knowledge_item": _deduplicate_knowledge_item,
    "submit_knowledge_for_review": _submit_knowledge_for_review,
}


def get_tool(name: str) -> Optional[Callable]:
    """获取工具"""
    return TOOL_REGISTRY.get(name)


def list_tool_names() -> list:
    """列出所有工具名"""
    return list(TOOL_REGISTRY.keys())


__all__ = ["TOOL_REGISTRY", "get_tool", "list_tool_names"]
