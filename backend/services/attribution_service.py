"""反商业贿赂风险图谱服务（蓝图片段 4.3 / P2）

复用 ontology 关系链推理落库结果（AttributionChainResult）与本体 Link，
从「代表→客户→利益→活动」的归因链路中聚合高风险路径，供前端可视化。

设计原则：
- 只读 AttributionChainResult，不新增表、不依赖 LLM，零迁移。
- 严格按 tenant_id 隔离（与 main 落库时写入的 tenant 一致），闭环跨租户风险。
- 边权重 = 该 (源, 关系, 目标) 在 YELLOW/RED 链路中的出现次数，体现风险集中度。
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from sqlalchemy.orm import Session

from database import AttributionChainResult


def build_bribery_risk_graph(db: Session, tenant_id: str,
                             min_level: str = "YELLOW") -> dict:
    """聚合租户的反商业贿赂风险图谱。

    Args:
        db: 业务库 session
        tenant_id: 租户隔离键（必填，避免跨租户串图）
        min_level: 纳入图谱的最低风险等级（YELLOW/RED）
    Returns:
        {
          "tenant_id", "node_count", "edge_count", "risk_counts",
          "nodes": [{id,label,type,risk}],
          "edges": [{source,target,relation,weight,level}],
        }
    """
    level_rank = {"GREY": 0, "GREEN": 1, "YELLOW": 2, "RED": 3}
    threshold = level_rank.get(min_level, 2)

    rows = db.query(AttributionChainResult).filter(
        AttributionChainResult.tenant_id == tenant_id,
        AttributionChainResult.is_deleted == 0,
    ).all()

    nodes: dict = {}
    edge_weight: dict = defaultdict(int)
    edge_level: dict = {}
    risk_counts = {"GREEN": 0, "YELLOW": 0, "RED": 0, "GREY": 0}

    for r in rows:
        lvl = r.level or "GREY"
        risk_counts[lvl] = risk_counts.get(lvl, 0) + 1
        if level_rank.get(lvl, 0) < threshold:
            continue
        chain = r.chain_json or {}
        paths = chain.get("paths") or []
        # 兼容探索模式 subgraph
        if not paths:
            subgraph = chain.get("subgraph") or {}
            _ingest_subgraph(subgraph, nodes, edge_weight, edge_level, lvl)
            continue
        for p in paths:
            _ingest_path(p, nodes, edge_weight, edge_level, lvl)

    node_list = [
        {"id": nid, "label": v["label"], "type": v["type"], "risk": v["risk"]}
        for nid, v in nodes.items()
    ]
    edge_list = [
        {"source": k[0], "target": k[2], "relation": k[1],
         "weight": w, "level": edge_level[k]}
        for k, w in edge_weight.items()
    ]
    return {
        "tenant_id": tenant_id,
        "node_count": len(node_list),
        "edge_count": len(edge_list),
        "risk_counts": risk_counts,
        "nodes": node_list,
        "edges": edge_list,
    }


def _node_key(node: dict) -> Optional[str]:
    t = node.get("type") or node.get("object")
    i = node.get("id")
    if not t:
        return None
    return f"{t}:{i}" if i is not None else t


def _ingest_path(path: dict, nodes: dict, edge_weight: dict,
                 edge_level: dict, level: str) -> None:
    seq = path.get("nodes") or []
    for n in seq:
        key = _node_key(n)
        if not key:
            continue
        cur = nodes.setdefault(key, {
            "label": n.get("display") or n.get("type") or key,
            "type": n.get("type") or n.get("object"),
            "risk": "GREEN",
        })
        # 节点取链路中的最高风险
        if _higher(level, cur["risk"]):
            cur["risk"] = level
    links = path.get("links") or []
    for lk in links:
        src = _node_key(lk.get("source") or (seq[0] if seq else {}))
        tgt = _node_key(lk.get("target") or (seq[-1] if seq else {}))
        rel = lk.get("relation") or lk.get("name") or "related_to"
        if not src or not tgt or src == tgt:
            continue
        ek = (src, rel, tgt)
        edge_weight[ek] += 1
        if _higher(level, edge_level.get(ek, "GREY")):
            edge_level[ek] = level


def _ingest_subgraph(subgraph: dict, nodes: dict, edge_weight: dict,
                     edge_level: dict, level: str) -> None:
    for n in subgraph.get("nodes") or []:
        key = _node_key(n)
        if not key:
            continue
        cur = nodes.setdefault(key, {
            "label": n.get("display") or n.get("type") or key,
            "type": n.get("type") or n.get("object"),
            "risk": "GREEN",
        })
        if _higher(level, cur["risk"]):
            cur["risk"] = level
    for e in subgraph.get("edges") or []:
        src = e.get("source")
        tgt = e.get("target")
        rel = e.get("relation") or e.get("name") or "related_to"
        if not src or not tgt or src == tgt:
            continue
        ek = (src, rel, tgt)
        edge_weight[ek] += 1
        if _higher(level, edge_level.get(ek, "GREY")):
            edge_level[ek] = level


def _higher(a: str, b: str) -> bool:
    rank = {"GREY": 0, "GREEN": 1, "YELLOW": 2, "RED": 3}
    return rank.get(a, 0) > rank.get(b, 0)
