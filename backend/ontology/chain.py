"""关系链推理引擎（L2）— 跨对象归因核心。

职责：
1. 基于 ontology/links.py 注册表，沿 Link 做有界多跳遍历，构建对象关联子图
2. 结合 Link cardinality 与跳数衰减计算每跳传播权重与累计贡献度
3. 定位「根因对象 → 目标指标」的可解释关系链（路径：节点序列 + 经过的 Link + 贡献度）
4. 纯规则产出，无 LLM 依赖；自然语言摘要由模板生成（ai_generated=False）

这是 OAG 区别于 RAG 的根本能力：推理不是「检索相似文本」，而是沿
业务本体关系网做结构化、可解释的跨对象传导归因。
"""
import logging
from typing import Optional

# 读运行时权威源（psp_ontology.db → registry 缓存），非 seed 常量
from ontology.registry import LINKS, OBJECTS, OBJECT_MAP, get_link

logger = logging.getLogger("ontology_chain")

# 默认最大跳数，防止指数爆炸（ontology 对象约 40，图规模可控）
DEFAULT_MAX_DEPTH = 4

# cardinality → 单跳基础传播系数（1:1 最强，N:N 最弱，符合业务直觉）
_CARDINALITY_WEIGHT = {
    "1:1": 0.95,
    "1:N": 0.80,
    "N:1": 0.70,
    "N:N": 0.55,
}


def _build_adjacency() -> dict:
    """构建无向邻接（保留方向信息），用于多跳遍历。

    返回：{object_name: [ {neighbor, link_name, direction('out'|'in')}, ... ]}
    """
    adj: dict[str, list] = {}
    for obj in OBJECTS:
        adj.setdefault(obj["name"], [])
    for link in LINKS:
        src = link["source_object"]
        tgt = link["target_object"]
        adj.setdefault(src, []).append(
            {"neighbor": tgt, "link": link["name"], "direction": "out"}
        )
        adj.setdefault(tgt, []).append(
            {"neighbor": src, "link": link["name"], "direction": "in"}
        )
    return adj


def _object_display(name: str) -> str:
    obj = OBJECT_MAP.get(name) or {}
    return obj.get("display_name", name)


def _object_domain(name: str) -> str:
    obj = OBJECT_MAP.get(name) or {}
    return obj.get("domain", "unknown")


def _link_base_weight(link_name: str) -> float:
    link = get_link(link_name) or {}
    card = link.get("cardinality", "N:N")
    return _CARDINALITY_WEIGHT.get(card, 0.5)


def _depth_decay(depth: int) -> float:
    """跳数衰减：每多一跳贡献度打 0.82 折，弱化远距离传导噪声。"""
    return 0.82 ** (depth - 1) if depth >= 1 else 1.0


def infer_relation_chain(
    root_type: str,
    root_id: Optional[int] = None,
    target_type: Optional[str] = None,
    domain: Optional[str] = None,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> dict:
    """沿注册表做一次有界多跳关系链推理（确定性规则）。

    参数：
        root_type: 根对象类型（如 User / Hospital / Doctor）
        root_id:   根对象实例 id（可选，仅用于展示）
        target_type: 目标对象类型（如 KPIValue / Diagnosis）。若给定，则
                     返回从 root 能传导到 target 的路径（即归因链）；
                     若不给定，则返回从 root 出发的全 N 跳邻居子图。
        domain:    域过滤（仅保留该域对象参与遍历，None=全域）
        max_depth: 最大跳数

    返回：
        {
          "root_type", "root_id", "target_type", "domain",
          "max_depth", "ai_generated": False,
          "paths": [ {nodes:[...], links:[...], depth, contribution, arrived_prob} ],  # 若指定 target
          "subgraph": {nodes:[...], edges:[...]},                                       # 若未指定 target
          "root_cause": {object, display, reason, contribution} | None,
          "summary": <模板生成的自然语言摘要>,
        }
    """
    adj = _build_adjacency()
    visited_paths = _bfs(
        adj=adj,
        root_type=root_type,
        target_type=target_type,
        domain=domain,
        max_depth=max_depth,
    )

    if target_type:
        # 归因模式：返回能到达 target 的路径，按到达概率排序
        paths = sorted(visited_paths, key=lambda p: p["arrived_prob"], reverse=True)
        root_cause = _locate_root_cause(paths)
        summary = _render_summary_chain(root_type, root_id, target_type, paths, root_cause)
        return {
            "root_type": root_type,
            "root_id": root_id,
            "target_type": target_type,
            "domain": domain,
            "max_depth": max_depth,
            "ai_generated": False,
            "paths": paths,
            "root_cause": root_cause,
            "summary": summary,
        }

    # 探索模式：返回 N 跳邻居子图
    nodes, edges = _subgraph_from_paths(visited_paths)
    summary = _render_summary_explore(root_type, root_id, nodes, edges)
    return {
        "root_type": root_type,
        "root_id": root_id,
        "target_type": None,
        "domain": domain,
        "max_depth": max_depth,
        "ai_generated": False,
        "subgraph": {"nodes": nodes, "edges": edges},
        "root_cause": None,
        "summary": summary,
    }


def _bfs(adj, root_type, target_type, domain, max_depth) -> list:
    """广度优先多跳遍历，收集所有路径（含到达 target 的路径与邻居子图）。"""
    domain_set = None
    if domain:
        domain_set = {o["name"] for o in OBJECTS if o.get("domain") == domain}

    results: list[dict] = []
    # 队列项: (current_node, path_nodes, path_links, depth, cumulative_weight)
    queue = [(root_type, [root_type], [], 0, 1.0)]
    seen_node_in_path = set()

    while queue:
        node, path_nodes, path_links, depth, cum_weight = queue.pop(0)
        if depth >= max_depth:
            continue
        for edge in adj.get(node, []):
            nbr = edge["neighbor"]
            if domain_set is not None and nbr not in domain_set:
                continue
            link_name = edge["link"]
            base = _link_base_weight(link_name)
            step_weight = base * _depth_decay(depth + 1)
            new_cum = cum_weight * step_weight
            new_nodes = path_nodes + [nbr]
            new_links = path_links + [link_name]
            path_key = (nbr, depth + 1)
            if path_key in seen_node_in_path:
                continue
            seen_node_in_path.add(path_key)

            results.append({
                "nodes": new_nodes,
                "links": [{
                    "name": ln,
                    "display_name": (get_link(ln) or {}).get("display_name", ln),
                    "relation": (get_link(ln) or {}).get("description", ""),
                } for ln in new_links],
                "depth": depth + 1,
                "contribution": round(step_weight, 4),
                "arrived_prob": round(new_cum, 4),
                "target_reached": nbr == target_type,
                "terminal": nbr,
            })

            if nbr == target_type:
                continue  # 到达目标即终止该支线（不再继续向下传导，避免噪声）
            queue.append((nbr, new_nodes, new_links, depth + 1, new_cum))

    if target_type:
        results = [r for r in results if r["target_reached"]]
    return results


def _direction_for(link_name, src, tgt) -> str:
    link = get_link(link_name) or {}
    if link.get("source_object") == src and link.get("target_object") == tgt:
        return "out"
    return "in"


def _subgraph_from_paths(visited_paths: list) -> tuple:
    """从遍历结果中抽取去重节点与边，构造展示子图。"""
    node_set: dict[str, dict] = {}
    edge_set: set[tuple] = set()
    edges: list[dict] = []

    def _ensure_node(name):
        if name not in node_set:
            node_set[name] = {
                "name": name,
                "display_name": _object_display(name),
                "domain": _object_domain(name),
            }

    for p in visited_paths:
        nodes = p["nodes"]
        links = p["links"]
        for n in nodes:
            _ensure_node(n)
        for link_item in links:
            link_name = link_item["name"] if isinstance(link_item, dict) else link_item
            link = get_link(link_name) or {}
            src = link.get("source_object")
            tgt = link.get("target_object")
            key = (src, tgt, link_name)
            if key not in edge_set:
                edge_set.add(key)
                _ensure_node(src)
                _ensure_node(tgt)
                edges.append({
                    "source": src,
                    "target": tgt,
                    "source_display": _object_display(src),
                    "target_display": _object_display(tgt),
                    "link": link_name,
                    "display_name": link.get("display_name", link_name),
                    "relation": link.get("description", ""),
                    "cardinality": link.get("cardinality", "N:N"),
                })
    return list(node_set.values()), edges


def _locate_root_cause(paths: list) -> Optional[dict]:
    """根因定位：在到达 target 的路径中，取传播贡献度（到达概率）最高路径的
    倒数第二跳（即最接近 target 的传导源）作为直接根因；若有多条，取最高。"""
    if not paths:
        return None
    best = max(paths, key=lambda p: p["arrived_prob"])
    nodes = best["nodes"]
    # 根因为路径中除 root 与 target 外，对 target 传导最直接的上一节点
    if len(nodes) >= 2:
        cause_node = nodes[-2]
    else:
        cause_node = nodes[0]
    return {
        "object": cause_node,
        "display_name": _object_display(cause_node),
        "domain": _object_domain(cause_node),
        "contribution": best["arrived_prob"],
        "reason": f"沿关系链传导至 {_object_display(best['nodes'][-1])} 的累计到达概率最高（{best['arrived_prob']:.2%}）",
    }


def _render_summary_chain(root_type, root_id, target_type, paths, root_cause) -> str:
    root_d = _object_display(root_type)
    tgt_d = _object_display(target_type)
    if not paths:
        return (
            f"未找到从「{root_d}」沿本体关系链传导到「{tgt_d}」的路径"
            f"（最大跳数 {DEFAULT_MAX_DEPTH}，可能需放宽深度或调整域范围）。"
        )
    best = paths[0]
    chain_disp = " → ".join(_object_display(n) for n in best["nodes"])
    base = (
        f"关系链推理（确定性规则）：从「{root_d}」出发，经 "
        f"{best['depth']} 跳沿本体关系链传导至「{tgt_d}」。"
        f"路径：{chain_disp}。"
        f"累计到达概率 {best['arrived_prob']:.2%}。"
    )
    if root_cause:
        base += (
            f"定位根因为「{root_cause['display_name']}」"
            f"（{root_cause['domain']} 域），对目标指标贡献度 {root_cause['contribution']:.2%}。"
        )
    base += "（无 LLM key，规则降级生成，ai_generated=False）"
    return base


def _render_summary_explore(root_type, root_id, nodes, edges) -> str:
    root_d = _object_display(root_type)
    if not nodes:
        return f"「{root_d}」在限定范围内无可达关系链邻居。"
    return (
        f"关系链探索：从「{root_d}」出发共发现 {len(nodes)} 个关联对象、"
        f"{len(edges)} 条关系边（含双向）。可据此展开跨对象归因分析。"
        f"（规则降级生成，ai_generated=False）"
    )
