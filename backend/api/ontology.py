"""Ontology API"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.response import unified_response
from database import get_db

logger = logging.getLogger(__name__)


def _log_and_fail(e: Exception, msg: str, items: bool = True):
    """统一异常降级：记录日志并返回明确错误码，避免把 str(e) 泄露给前端"""
    logger.error("%s: %s", msg, e, exc_info=True)
    payload = {"items": []} if items else None
    return unified_response(payload, code=50000, message=msg)
from middleware.auth import get_current_user, require_permission
from database import User, AttributionChainResult, BusinessSessionLocal
from ontology import (
    list_objects, get_object, list_links, get_link, list_actions, get_action, get_graph,
    reload_ontology, registry,
)
from ontology.chain import infer_relation_chain
from services import maturity_service
from logic import build_plan, ActionExecutor
from ingest import get_extractor, LightGraph, TextSplitter
from governance import ActionGate
# 注：候选审核端点（第 14 批起改用 Neo4j Neo4jCandidateStore）在端点内部
# 显式 from governance import create_candidate_store，避免顶部死 import 拖垮模块加载。


router = APIRouter(prefix="/ontology")


@router.get("/objects")
async def objects_list(domain: str = None, user: User = Depends(get_current_user)):
    return unified_response({"items": list_objects(domain, tenant_id=user.tenant_id)})


@router.get("/objects/{name}")
async def get_object_detail(name: str, user: User = Depends(get_current_user)):
    """查询单个 Object 详情（含 fields + actions）"""
    obj = get_object(name, tenant_id=user.tenant_id)
    if not obj:
        return unified_response(None, code=40004, message=f"Object '{name}' not found")
    return unified_response(obj)


@router.get("/links")
async def links_list(user: User = Depends(get_current_user)):
    return unified_response({"items": list_links(tenant_id=user.tenant_id)})


@router.get("/actions")
async def actions_list(domain: str = None, risk_level: str = None, user: User = Depends(get_current_user)):
    return unified_response({"items": list_actions(domain, risk_level, tenant_id=user.tenant_id)})


@router.get("/graph")
async def graph(user: User = Depends(get_current_user)):
    return unified_response(get_graph(tenant_id=user.tenant_id))


@router.post("/reload")
async def reload_registry(user: User = Depends(require_permission("ontology.manage"))):
    """热更新本体缓存：从 psp_ontology.db 重新加载 Object/Link/Action

    本体已 DB 化（DB 为运行时权威源），运营侧修改本体表后调用本端点即可生效，
    无需重启进程。需 ontology.manage 权限。
    """
    try:
        stats = reload_ontology()
        logger.info("[ontology/reload] 由 user=%s 触发，结果=%s", user.id, stats)
        return unified_response(stats)
    except Exception as e:
        return _log_and_fail(e, "本体重载失败", items=False)


@router.get("/registry-status")
async def registry_status(user: User = Depends(get_current_user)):
    """本体注册表状态：用于确认运行时权威源是 DB 还是 seed 降级"""
    return unified_response(registry.load())


@router.get("/maturity")
async def ontology_maturity(user: User = Depends(get_current_user)):
    """本体成熟度评估（吸收参考3 附录C 5 级成熟度模型）

    基于 Object/Link/Action/Permission 四层常量，套用 20 题问卷评分，
    输出 5 级成熟度、各层得分、弱层与升级路径。
    """
    return unified_response(maturity_service.assess(user.tenant_id))


@router.get("/stats")
async def stats(user: User = Depends(get_current_user)):
    """Ontology 整体统计"""
    objects = list_objects(tenant_id=user.tenant_id)
    links = list_links(tenant_id=user.tenant_id)
    actions = list_actions(tenant_id=user.tenant_id)
    domains_set = {obj.get("domain", "unknown") for obj in objects}
    return unified_response({
        "total_objects": len(objects),
        "total_links": len(links),
        "total_actions": len(actions),
        "domains": len(domains_set),
        "domain_list": sorted(domains_set),
    })


@router.get("/graph/explore")
async def graph_explore(
    root: str = None,
    target: str = None,
    mode: str = "stats",
    source: str = "ontology",
    user: User = Depends(get_current_user),
):
    """图探索（邻域/子图/统计形态）。

    把 Object 作为节点、Link 作为边，构建「图」并可被探索：
        - source=ontology(默认): 基于本体权威源（list_objects/list_links）
        - source=candidate: 基于 graph_store 后端（Neo4j/LightGraph 候选层）
        - mode=stats   : 节点/边/类型统计
        - mode=neighbors: 指定 root 的邻域（相连 Link 与对端 Object）
        - mode=subgraph: 指定 root 的 1 跳子图
        - mode=path    : 指定 root→target 的最短关系路径（BFS, max_depth=6）

    零侵入：复用既有 list_objects/list_links，candidate 通过工厂获取后端。
    """
    try:
        from kg_explorer import GraphView, from_graph_store

        if source == "candidate":
            from graph_store import create_graph_store
            store = create_graph_store()
            gv = from_graph_store(store)
        else:
            objects = list_objects(tenant_id=user.tenant_id)
            links = list_links(tenant_id=user.tenant_id)
            nodes = [{"id": o["name"], "name": o["name"], "type": o.get("domain", "object")}
                     for o in objects]
            edges = [
                {"subject": l.get("source_object") or l.get("source"),
                 "predicate": l["name"],
                 "obj": l.get("target_object") or l.get("target")}
                for l in links
                if l.get("source_object") or l.get("source")
            ]
            gv = GraphView(nodes=nodes, edges=edges)

        result = _do_explore(gv, mode=mode, root=root, target=target)
        if source == "candidate":
            from graph_store import backend_name
            if isinstance(result, dict):
                result["source"] = "candidate"
                result["backend"] = backend_name()
        return unified_response(result)
    except Exception as e:
        return _log_and_fail(e, "本体图探索失败")


def _do_explore(gv, *, mode: str, root: str = None, target: str = None):
    """抽取探索逻辑为纯函数，便于复用与测试。"""
    if mode == "stats":
        return gv.stats()
    if mode == "neighbors":
        if not root:
            return {"error": "neighbors 模式需 root 参数"}
        return gv.neighbors(root)
    if mode == "subgraph":
        if not root:
            return {"error": "subgraph 模式需 root 参数"}
        nb = gv.neighbors(root)
        ids = {root} | set(nb.get("neighbor_ids", []))
        return gv.subgraph(ids).stats()
    if mode == "path":
        if not root or not target:
            return {"error": "path 模式需 root 与 target 参数"}
        path = gv.shortest_path(root, target)
        if path is None:
            return {"path": None, "found": False}
        return {"path": path, "found": True}
    return gv.stats()


# ──────────────────────────────────────────────────────────
# 推理（rdflib OWL 推理层，第八批）
# ──────────────────────────────────────────────────────────

@router.get("/reason/explain")
async def reason_explain(
    source_type: str,
    target_type: str,
    user: User = Depends(get_current_user),
):
    """类型层 OWL 推理：从 source_type 到 target_type 是否可达（rdflib + 类型层 BFS）。

    返回 {"direct": bool, "path": [...], "reason": ...}。
    """
    try:
        from reasoning import OntologyReasoner
        r = OntologyReasoner()
        return unified_response(r.explain_link(source_type, target_type))
    except Exception as e:
        return _log_and_fail(e, "类型推理失败", items=False)


@router.get("/reason/reachable")
async def reason_reachable(
    source_type: str,
    max_depth: int = 4,
    user: User = Depends(get_current_user),
):
    """类型层可达性：从 source_type 出发能到达的所有 object 类型（max_depth 跳内）。"""
    try:
        from reasoning import OntologyReasoner
        r = OntologyReasoner()
        return unified_response({
            "source_type": source_type,
            "reachable": r.reachable_types(source_type, max_depth=max_depth),
        })
    except Exception as e:
        return _log_and_fail(e, "可达性推理失败", items=False)



@router.get("/domains")
async def list_domains(user: User = Depends(get_current_user)):
    """列出所有域及其统计（实体数、关系数、Action 数）"""
    objects = list_objects(tenant_id=user.tenant_id)
    links = list_links(tenant_id=user.tenant_id)
    actions = list_actions(tenant_id=user.tenant_id)
    domains: dict[str, dict] = {}
    # 统计每个域的 Object 数
    for obj in objects:
        d = obj.get("domain", "unknown")
        domains.setdefault(d, {"objects": 0, "links": 0, "actions": 0})
        domains[d]["objects"] += 1
    # 统计每个域的 Link 数（通过 source_object 反查域）
    obj_domain_map = {obj.get("name"): obj.get("domain", "unknown") for obj in objects}
    for link in links:
        src = link.get("source_object")
        d = obj_domain_map.get(src, "unknown")
        domains.setdefault(d, {"objects": 0, "links": 0, "actions": 0})
        domains[d]["links"] += 1
    # 统计每个域的 Action 数
    for action in actions:
        d = action.get("domain", "unknown")
        domains.setdefault(d, {"objects": 0, "links": 0, "actions": 0})
        domains[d]["actions"] += 1
    return unified_response({
        "items": [{"domain": k, **v} for k, v in sorted(domains.items())]
    })


@router.get("/search")
async def search(q: str = "", domain: str = None, user: User = Depends(get_current_user)):
    """搜索实体（按名称或显示名模糊匹配）"""
    results = []
    query = q.lower() if q else ""
    for obj in list_objects(tenant_id=user.tenant_id):
        if domain and obj.get("domain") != domain:
            continue
        if query:
            name = obj.get("name", "").lower()
            display = obj.get("display_name", "").lower()
            if query not in name and query not in display:
                continue
        results.append({
            "name": obj.get("name"),
            "display_name": obj.get("display_name"),
            "domain": obj.get("domain"),
            "description": obj.get("description", ""),
        })
    return unified_response({"items": results[:50], "total": len(results)})


@router.get("/relations/{object_name}")
async def get_relations(object_name: str, user: User = Depends(get_current_user)):
    """查询某实体的所有关系（出向 + 入向）"""
    all_links = list_links(tenant_id=user.tenant_id)
    outgoing = [l for l in all_links if l.get("source_object") == object_name]
    incoming = [l for l in all_links if l.get("target_object") == object_name]
    return unified_response({
        "object": object_name,
        "outgoing": outgoing,
        "incoming": incoming,
        "total": len(outgoing) + len(incoming),
    })


@router.get("/chain")
async def relation_chain(
    root_type: str,
    root_id: int = None,
    target_type: str = None,
    domain: str = None,
    max_depth: int = 4,
    user: User = Depends(get_current_user),
):
    """L2 关系链推理：沿 ontology Links 做跨对象归因

    给定 root 对象（与可选 target 指标）：
    - 指定 target_type → 返回从 root 传导到 target 的关系链路径（含每跳贡献度、根因定位）
    - 不指定 target_type → 返回从 root 出发的 N 跳邻居子图（关系链探索）
    确定性规则优先，无 LLM 依赖，结果落库 AttributionChainResult。
    """
    try:
        if max_depth < 1:
            max_depth = 1
        if max_depth > 6:
            max_depth = 6
        result = infer_relation_chain(
            root_type=root_type,
            root_id=root_id,
            target_type=target_type,
            domain=domain,
            max_depth=max_depth,
        )
        # 落库（轻量链路 JSON，不阻断主流程）
        try:
            root_cause = result.get("root_cause") or {}
            with BusinessSessionLocal() as db:
                rec = AttributionChainResult(
                    tenant_id=user.tenant_id,
                    root_type=root_type,
                    root_id=root_id,
                    target_type=target_type,
                    domain=domain,
                    max_depth=max_depth,
                    chain_json=result,
                    summary=result.get("summary"),
                    level="YELLOW" if root_cause else "GREY",
                    confidence=float(root_cause.get("contribution", 0.0) or 0.0),
                    ai_generated=0,
                    trace_id=None,
                )
                db.add(rec)
                db.commit()
        except Exception as e:
            logger.debug("[ontology/chain] 落库失败（已忽略）: %s", e)
        return unified_response(result)
    except Exception as e:
        return _log_and_fail(e, "关系链推理失败", items=False)


@router.get("/graph/neighbors/{object_name}")
async def graph_neighbors(
    object_name: str,
    depth: int = 2,
    domain: str = None,
    user: User = Depends(get_current_user),
):
    """N 跳邻居查询：返回某对象沿注册表的多跳出向/入向邻居子图

    用于图谱可视化与跨对象关系探索。
    """
    try:
        if depth < 1:
            depth = 1
        if depth > 6:
            depth = 6
        result = infer_relation_chain(
            root_type=object_name,
            target_type=None,
            domain=domain,
            max_depth=depth,
        )
        return unified_response({
            "object": object_name,
            "depth": depth,
            "subgraph": result.get("subgraph", {"nodes": [], "edges": []}),
            "summary": result.get("summary"),
        })
    except Exception as e:
        return _log_and_fail(e, "邻居查询失败", items=False)


@router.get("/attribution/risk-graph")
async def attribution_risk_graph(
    min_level: str = "YELLOW",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """反商业贿赂风险图谱（蓝图片段 4.3 / P2）

    从 AttributionChainResult 聚合当前租户的高风险归因链路，返回可可视化的
    节点/边图（代表→客户→利益→活动）。严格按 tenant_id 隔离。
    """
    try:
        from services.attribution_service import build_bribery_risk_graph
        graph = build_bribery_risk_graph(db, tenant_id=user.tenant_id, min_level=min_level)
        return unified_response(graph)
    except Exception as e:
        return _log_and_fail(e, "风险图谱构建失败", items=False)


# ──────────────────────────────────────────────────────────
# Logic 平面：目标 → 规划 → 风险门禁 → 执行（蓝图片段 4.4 / P3）
# 复用 ontology.actions 元数据 + provenance 溯源，零侵入现有运行路径
# ──────────────────────────────────────────────────────────

@router.post("/logic/plan")
async def logic_plan(
    body: dict,
    user: User = Depends(get_current_user),
):
    """为目标构建可执行 Action 序列（仅规划，不执行）。

    body: { goal, domain?, level?, payload? }
        - level 存在 → 走诊断驱动推荐（recommend_actions_for_diagnosis）
        - 否则按 domain 检索并按风险升序编排
    """
    try:
        plan = build_plan(
            goal=body.get("goal", "未命名目标"),
            domain=body.get("domain"),
            level=body.get("level"),
            tenant_id=user.tenant_id,
            payload=body.get("payload", {}),
        )
        return unified_response(plan.to_dict())
    except Exception as e:
        return _log_and_fail(e, "逻辑规划失败", items=False)


@router.post("/logic/execute")
async def logic_execute(
    body: dict,
    user: User = Depends(get_current_user),
):
    """规划并执行一组 Action，带风险门禁与溯源。

    body: {
        goal, domain?, level?, payload?,
        dry_run?: bool=False,        # 仅预览，不派发 handler
        explicit_confirm?: bool=False, # L4 简化放行（离线演示用）
        approval_ticket?: str=None,  # 治理门禁：L4 审批单（生产走 ActionGate）
        use_gate?: bool=False        # 是否启用 governance.ActionGate（权限+审批）
    }
    L4 动作默认被拦截：use_gate=True 时需 approval_ticket；否则需
    dry_run 或 explicit_confirm 放行。
    """
    try:
        plan = build_plan(
            goal=body.get("goal", "未命名目标"),
            domain=body.get("domain"),
            level=body.get("level"),
            tenant_id=user.tenant_id,
            payload=body.get("payload", {}),
        )
        gate = ActionGate() if body.get("use_gate") else None
        executor = ActionExecutor(agent_id=str(user.id), gate=gate)
        result = executor.run(
            plan,
            user=user,
            dry_run=bool(body.get("dry_run", False)),
            explicit_confirm=bool(body.get("explicit_confirm", False)),
            approval_ticket=body.get("approval_ticket"),
        )
        return unified_response(result.to_dict())
    except Exception as e:
        return _log_and_fail(e, "逻辑执行失败", items=False)


# ──────────────────────────────────────────────────────────
# 治理平面：候选审核队列（回流闸口）
# ingest 抽取候选入队 → 此处审核 → 核准后回流本体/业务表
# ──────────────────────────────────────────────────────────

@router.post("/governance/review")
async def governance_review(
    body: dict,
    user: User = Depends(get_current_user),
):
    """候选审核队列操作。

    body:
        action: "list" | "approve" | "reject"
        kind?: "entity" | "relation"     # list 时按类型过滤
        candidate_id?: str               # approve/reject 时必填
        note?: str
    审核决策记入 Neo4j Neo4jCandidateStore（第 14 批起统一 Neo4j 唯一主存），
    核准候选可经回流脚本写回本体。
    """
    try:
        from governance import create_candidate_store
        store, _backend = create_candidate_store()
        action = body.get("action", "list")
        if action == "list":
            items = store.list_pending(kind=body.get("kind"))
            return unified_response([c.to_dict() for c in items])
        if action in ("approve", "reject"):
            cid = body.get("candidate_id")
            if not cid:
                return unified_response({"error": "candidate_id 必填"}, items=False)
            ok = store.decide(
                cid, action, decided_by=str(user.id), note=body.get("note"))
            if not ok:
                return unified_response({"error": "候选不存在或已决策"}, items=False)
            return unified_response({"candidate_id": cid, "status": action})
        return unified_response({"error": f"未知 action: {action}"}, items=False)
    except Exception as e:
        return _log_and_fail(e, "候选审核失败", items=False)


@router.post("/governance/reflow")
async def governance_reflow(
    body: dict,
    user: User = Depends(get_current_user),
):
    """将审核核准的候选回流到本体权威源（写本体库 + reload + 可选快照）。

    body: {
        tenant_id?: str,            # 默认跟随 user.tenant_id
        capture_version?: bool=True # 是否打版本快照（需本体库可读）
    }
    仅回流 store 中 status=approved 的候选；entity→object_definitions，
    relation→link_definitions（两端实体需已核准）。单条失败非阻断。
    """
    try:
        from governance import create_candidate_store, reflow_approved
        from versioning.manager import VersionManager

        store, _backend = create_candidate_store()
        vm = VersionManager()
        result = reflow_approved(
            store,
            tenant_id=body.get("tenant_id", user.tenant_id),
            version_manager=vm,
            capture_version=bool(body.get("capture_version", True)),
        )
        return unified_response(result.to_dict())
    except Exception as e:
        return _log_and_fail(e, "候选回流失败", items=False)


# ──────────────────────────────────────────────────────────
# 跨系统 Cypher 桥接（governance.bridge）
# 跨 4 个 Neo4j 子系统（candidate / provenance / versioning / graph）单次查询
# 返回 entity 全故事 / agent 审计 / candidate 命运 / activity 子图 / 系统快照
# ──────────────────────────────────────────────────────────

@router.get("/bridge/entity-story")
async def bridge_entity_story(
    entity_id: str,
    max_depth: int = 8,
    user: User = Depends(get_current_user),
):
    """某 entity 的完整生命周期：候选→落图→溯源→派生链。"""
    try:
        from governance import entity_story
        return unified_response(entity_story(entity_id, max_depth=max_depth))
    except Exception as e:
        return _log_and_fail(e, "entity_story 查询失败", items=False)


@router.get("/bridge/agent-audit")
async def bridge_agent_audit(
    agent_id: str,
    max_activities: int = 100,
    user: User = Depends(get_current_user),
):
    """某 agent 发起的所有活动 + 涉及的 entity + 产生的版本快照。"""
    try:
        from governance import agent_audit
        return unified_response(
            agent_audit(agent_id, max_activities=max_activities))
    except Exception as e:
        return _log_and_fail(e, "agent_audit 查询失败", items=False)


@router.get("/bridge/candidate-fate")
async def bridge_candidate_fate(
    candidate_id: str,
    user: User = Depends(get_current_user),
):
    """某 candidate 的完整命运：入队→审核→落本体库→触发版本快照。"""
    try:
        from governance import candidate_to_ontology
        return unified_response(candidate_to_ontology(candidate_id))
    except Exception as e:
        return _log_and_fail(e, "candidate_to_ontology 查询失败", items=False)


@router.get("/bridge/activity-subgraph")
async def bridge_activity_subgraph(
    activity_id: str,
    user: User = Depends(get_current_user),
):
    """provenance activity 子图 + 落图层（Entity 节点 + 邻域）。"""
    try:
        from governance import activity_subgraph_extended
        return unified_response(activity_subgraph_extended(activity_id))
    except Exception as e:
        return _log_and_fail(e, "activity_subgraph 查询失败", items=False)


@router.get("/bridge/system-snapshot")
async def bridge_system_snapshot(
    user: User = Depends(get_current_user),
):
    """Neo4j 中各子系统节点/边数量总览（运维监控）。"""
    try:
        from governance import system_snapshot
        return unified_response(system_snapshot())
    except Exception as e:
        return _log_and_fail(e, "system_snapshot 查询失败", items=False)


# ──────────────────────────────────────────────────────────
# Ingest 候选抽取：文本 → 抽取（rule/llm）→ 灌 LightGraph → 图预览
# 复用 kg_explorer 的邻居/子图思路，不写业务库（候选层）
# ──────────────────────────────────────────────────────────

@router.post("/ingest/extract")
async def ingest_extract(
    body: dict,
    user: User = Depends(get_current_user),
):
    """对给定文本执行候选抽取并生成可探索的轻量图。

    body: {
        text: str,                       # 必填
        extractor?: "rule" | "llm",      # 默认 "rule"
        root?: str,                      # 可选：返回该实体的邻居预览
    }
    产物为「候选层」：仅落内存图，不写业务表，可对接 kg_explorer 探索。
    """
    try:
        text = body.get("text")
        if not text:
            return unified_response({"error": "text 必填"}, items=False)
        ext_name = body.get("extractor", "rule")
        try:
            extractor_cls = get_extractor(ext_name)
        except KeyError as e:
            return unified_response({"error": str(e)}, items=False)

        chunks = TextSplitter().split(text, source="api")
        extractor = extractor_cls()
        res = extractor.extract(chunks)

        g = LightGraph()
        for e in res.entities:
            g.add_entity(e)
        for r in res.relations:
            g.add_relation(r)

        out = {"extractor": ext_name, "stats": g.stats()}
        root = body.get("root")
        if root and root in {n.entity_id for n in g.all_nodes()}:
            out["root"] = root
            out["neighbors"] = [
                {"relation_id": e.relation_id, "predicate": e.predicate,
                 "to": e.obj, "from": e.subject}
                for e in g.neighbors(root)
            ]
        return unified_response(out)
    except Exception as e:
        return _log_and_fail(e, "候选抽取失败", items=False)
