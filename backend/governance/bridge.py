"""跨系统 Cypher 桥接 —— 第十一批补：把 Neo4j 4 大子系统（candidate / provenance /
versioning / graph）联成一张大图，单次 Cypher 返回 entity 全故事。

按现有 4 类后端可在 Neo4j Browser 一并打开：
    - (:Entity) — graph_store 候选层
    - (:ReviewCandidate)-[:REPRESENTS]->(:Entity) — governance
    - (:ProvEntry)-[:WAS_GENERATED_BY]->(:ProvActivity) — provenance
    - (:OntSnapshot)-[:DERIVED_FROM]->(:OntSnapshot) — versioning

本模块用 Cypher 跨节点查询，把以上 4 类节点的关联抽出来。

第 13 批：driver 改走 Neo4jConnectionManager 共享连接，不再单独缓存。
"""
from __future__ import annotations

import json
import logging
from typing import Any

from core.neo4j_driver import Neo4jConnectionManager

logger = logging.getLogger(__name__)


def _run(cypher: str, **params) -> list[dict]:
    """执行 Cypher 并返回 dict 列表。Neo4j 不可用时返回空（不抛错）。"""
    try:
        with Neo4jConnectionManager.session() as s:
            return [dict(r) for r in s.run(cypher, **params)]
    except Exception as e:
        logger.warning("桥接查询失败: %s", e)
        return []


def _count(cypher: str) -> int:
    rows = _run(cypher)
    if rows and "c" in rows[0]:
        return int(rows[0]["c"])
    return 0


# ─────────────────────────────────────────────────────
# 桥接 1：entity 全故事（核心查询）
# ─────────────────────────────────────────────────────
def entity_story(entity_id: str, *, max_depth: int = 8) -> dict:
    """某 entity 的完整生命周期：候选审核 → 落图 → 涉及活动。

    跨 3 个 Neo4j 子系统（candidate / graph_store / provenance）：
        1. 候选（governance）：哪些候选代表这 entity
        2. 落图（graph_store）：当前图中节点信息
        3. 涉及活动（provenance）：以这 entity_id 为输入/输出引用的活动
        4. 派生链（provenance.WAS_DERIVED_FROM）：同 entity_id 上一条

    返回 dict：{
        entity_id, graph_node, candidates, related_activities,
        derived_from, summary
    }
    """
    # 1) 候选（governance）
    cands = _run(
        """
        MATCH (c:ReviewCandidate)-[:REPRESENTS]->(e:Entity {entity_id: $eid})
        RETURN c.candidate_id AS id, c.kind AS kind, c.status AS status,
               c.decided_by AS decided_by, c.decided_at AS decided_at,
               c.note AS note, c.created_at AS created_at
        ORDER BY c.created_at ASC
        """, eid=entity_id)

    # 2) 落图节点
    graph_node_row = _run(
        """
        MATCH (n:Entity {entity_id: $eid})
        RETURN n.entity_id AS entity_id, n.entity_type AS entity_type,
               n.mention AS mention, coalesce(n.props, {}) AS props
        """, eid=entity_id)

    # 3) 涉及活动（通过 output_refs/input_refs 文本匹配 entity_id）
    #   output_refs_json 形如 ["entities:4", "relations:1"] 或 "chunks:3"
    #   更精准：找 entry.entity_id 包含此 entity_id 的（自动 + 手动 record 两种）
    related_activities = _run(
        """
        MATCH (pe:ProvEntry)
        WHERE pe.entity_id = $eid OR
              pe.entity_id CONTAINS $eid OR
              pe.properties_json CONTAINS $eid
        OPTIONAL MATCH (pe)-[:WAS_GENERATED_BY]->(pa:ProvActivity)
        OPTIONAL MATCH (pe)-[:WAS_ASSOCIATED_WITH]->(ag:ProvAgent)
        RETURN DISTINCT pe.entry_id AS entry_id, pe.action AS action,
               pa.activity_id AS activity_id, pa.activity_type AS activity_type,
               pa.name AS activity_name, pa.started_at AS started_at,
               ag.agent_id AS agent_id, ag.name AS agent_name,
               pe.occurred_at AS occurred_at
        ORDER BY pe.occurred_at ASC
        """, eid=entity_id)

    # 4) 派生链（provenance.WAS_DERIVED_FROM）
    if not (1 <= max_depth <= 30):
        max_depth = 8
    derived = _run(
        f"""
        MATCH p = (start:ProvEntry {{entity_id: $eid}})
              -[:WAS_DERIVED_FROM*..{max_depth}]->(root:ProvEntry)
        WITH nodes(p) AS ns
        UNWIND ns AS n
        RETURN DISTINCT n.entry_id AS entry_id, n.entity_id AS entity_id,
               n.action AS action, n.occurred_at AS occurred_at,
               n.entry_hash AS entry_hash
        ORDER BY occurred_at ASC
        """, eid=entity_id)

    return {
        "entity_id": entity_id,
        "graph_node": graph_node_row[0] if graph_node_row else None,
        "candidates": cands,
        "related_activities": related_activities,
        "derived_from": derived,
        "summary": {
            "candidate_count": len(cands),
            "activity_count": len(related_activities),
            "derived_count": len(derived),
            "has_graph_node": bool(graph_node_row),
        },
    }


# ─────────────────────────────────────────────────────
# 桥接 2：agent 审计
# ─────────────────────────────────────────────────────
def agent_audit(agent_id: str, *, max_activities: int = 100) -> dict:
    """某 agent 发起的所有活动 + 涉及的 entity + 产生的版本快照。"""
    activities = _run(
        """
        MATCH (pa:ProvActivity)-[:WAS_ASSOCIATED_WITH]->(ag:ProvAgent {agent_id: $agid})
        OPTIONAL MATCH (pe:ProvEntry)-[:WAS_GENERATED_BY]->(pa)
        WITH pa, collect(DISTINCT {
            id: pe.entry_id, entity_id: pe.entity_id, action: pe.action,
            occurred_at: pe.occurred_at
        }) AS entries
        RETURN pa.activity_id AS activity_id, pa.activity_type AS activity_type,
               pa.name AS name, pa.status AS status, pa.started_at AS started_at,
               pa.ended_at AS ended_at, pa.error AS error, entries
        ORDER BY pa.started_at DESC LIMIT $lim
        """, agid=agent_id, lim=max_activities)

    snapshots = _run(
        """
        MATCH (s:OntSnapshot {authored_by: $agid})
        RETURN s.version_id AS version_id, s.created_at AS created_at,
               s.note AS note, s.content_hash AS content_hash
        ORDER BY s.created_at DESC LIMIT 20
        """, agid=agent_id)

    return {
        "agent_id": agent_id,
        "activities": activities,
        "snapshots": snapshots,
        "summary": {
            "activity_count": len(activities),
            "snapshot_count": len(snapshots),
        },
    }


# ─────────────────────────────────────────────────────
# 桥接 3：candidate 命运追踪
# ─────────────────────────────────────────────────────
def candidate_to_ontology(candidate_id: str) -> dict:
    """某 candidate 的完整命运：入队 → 审核 → 落本体库 → 触发版本快照。"""
    cand = _run(
        """
        MATCH (c:ReviewCandidate {candidate_id: $cid})
        OPTIONAL MATCH (c)-[:REPRESENTS]->(e:Entity)
        WITH c, collect(DISTINCT e.entity_id) AS entities
        RETURN c.candidate_id AS candidate_id, c.kind AS kind,
               c.status AS status, c.decided_by AS decided_by,
               c.decided_at AS decided_at, c.note AS note,
               c.payload_json AS payload_json, c.created_at AS created_at,
               entities
        """, cid=candidate_id)
    if not cand:
        return {"candidate_id": candidate_id, "found": False}
    c = cand[0]
    payload = json.loads(c["payload_json"]) if c["payload_json"] else {}
    entity_id = payload.get("entity_id") or payload.get("subject")
    related_snapshots: list[dict] = []
    if entity_id:
        related_snapshots = _run(
            """
            MATCH (s:OntSnapshot)
            WHERE s.note CONTAINS 'reflow' OR s.note CONTAINS $eid
            RETURN s.version_id AS version_id, s.created_at AS created_at,
                   s.note AS note, s.content_hash AS content_hash
            ORDER BY s.created_at DESC LIMIT 5
            """, eid=entity_id)

    return {
        "candidate_id": candidate_id,
        "found": True,
        "kind": c["kind"],
        "status": c["status"],
        "decided_by": c["decided_by"],
        "decided_at": str(c["decided_at"]) if c["decided_at"] else None,
        "note": c["note"],
        "represented_entities": c["entities"],
        "payload": payload,
        "related_snapshots": related_snapshots,
    }


# ─────────────────────────────────────────────────────
# 桥接 4：activity 扩展子图（跨 provenance + graph）
# ─────────────────────────────────────────────────────
def activity_subgraph_extended(activity_id: str) -> dict:
    """provenance activity 子图 + 落图层（Entity 节点 + 邻域）。"""
    activity = _run(
        """
        MATCH (pa:ProvActivity {activity_id: $aid})
        OPTIONAL MATCH (pa)-[:WAS_ASSOCIATED_WITH]->(ag:ProvAgent)
        OPTIONAL MATCH (pe:ProvEntry)-[:WAS_GENERATED_BY]->(pa)
        WITH pa, ag, pe
        RETURN pa {.*} AS activity, ag {.*} AS agent,
               collect(DISTINCT pe {
                   entry_id: pe.entry_id, entity_id: pe.entity_id,
                   action: pe.action, occurred_at: pe.occurred_at
               }) AS entries
        """, aid=activity_id)
    if not activity:
        return {"activity_id": activity_id, "found": False}
    a = activity[0]
    act = dict(a["activity"] or {})

    def _coerce(v):
        if hasattr(v, "to_native"):
            return v.to_native()
        return v

    for k in ("started_at", "ended_at"):
        if act.get(k):
            act[k] = _coerce(act[k])
    for jk, jk_label in [("input_refs_json", "input_refs"),
                          ("output_refs_json", "output_refs"),
                          ("properties_json", "properties")]:
        if act.get(jk):
            try:
                act[jk_label] = json.loads(act[jk])
            except Exception:
                pass
            act.pop(jk, None)
    for e in (a["entries"] or []):
        if e.get("occurred_at"):
            e["occurred_at"] = _coerce(e["occurred_at"])

    eids = [e.get("entity_id") for e in (a["entries"] or []) if e.get("entity_id")]
    graph_nodes: list[dict] = []
    if eids:
        graph_nodes = _run(
            """
            MATCH (n:Entity) WHERE n.entity_id IN $eids
            OPTIONAL MATCH (n)-[r:REL]->(m:Entity)
            WITH n, collect(DISTINCT {relation_id: r.relation_id,
                                     predicate: r.predicate, to: m.entity_id}) AS neighbors
            RETURN n.entity_id AS entity_id, n.entity_type AS entity_type,
                   n.mention AS mention, neighbors
            """, eids=eids)

    return {
        "activity_id": activity_id,
        "found": True,
        "activity": act,
        "agent": dict(a["agent"]) if a["agent"] else None,
        "entries": a["entries"],
        "graph_nodes": graph_nodes,
    }


# ─────────────────────────────────────────────────────
# 桥接 5：整系统 health snapshot
# ─────────────────────────────────────────────────────
def system_snapshot() -> dict:
    """Neo4j 中各子系统节点/边数量总览（运维监控）。"""
    return {
        "entities": _count("MATCH (n:Entity) RETURN count(n) AS c"),
        "relations": _count("MATCH ()-[r:REL]->() RETURN count(r) AS c"),
        "candidates": {
            "total": _count("MATCH (c:ReviewCandidate) RETURN count(c) AS c"),
            "pending": _count("MATCH (c:ReviewCandidate {status:'pending'}) RETURN count(c) AS c"),
            "approved": _count("MATCH (c:ReviewCandidate {status:'approved'}) RETURN count(c) AS c"),
            "rejected": _count("MATCH (c:ReviewCandidate {status:'rejected'}) RETURN count(c) AS c"),
        },
        "provenance": {
            "agents": _count("MATCH (ag:ProvAgent) RETURN count(ag) AS c"),
            "activities": _count("MATCH (a:ProvActivity) RETURN count(a) AS c"),
            "entries": _count("MATCH (e:ProvEntry) RETURN count(e) AS c"),
        },
        "versioning": {
            "snapshots": _count("MATCH (s:OntSnapshot) RETURN count(s) AS c"),
            "derivations": _count("MATCH ()-[r:DERIVED_FROM]->() RETURN count(r) AS c"),
            "hash_chains": _count("MATCH ()-[r:NEXT_HASH]->() RETURN count(r) AS c"),
        },
    }
