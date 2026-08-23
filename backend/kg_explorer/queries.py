"""知识图谱探索查询 —— 「邻域/子图/路径/统计」

把现有全量 /graph（一次性返回整图）升级为结构化探索能力，可直接服务于
OntologyPage 的子图浏览体验（蓝图 §4、§9.8）。

设计要点：
    - 查询对象抽象为「邻接视图」：任何提供 nodes/edges 的图都可被探索
      （LightGraph 候选层 或 ontology.get_graph() 结果皆可）
    - 不直连数据库，纯内存遍历，O(节点+边)；设 _MAX_NODES 扫描上限防 OOM
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

_MAX_NODES = 5000


@dataclass
class GraphView:
    """邻接视图：从 nodes / edges 构建的轻量可遍历结构。"""

    nodes: list[dict] = field(default_factory=list)
    edges: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._adj: dict[str, list[dict]] = {}
        self._node_map: dict[str, dict] = {}
        for n in self.nodes:
            nid = n.get("id") or n.get("name") or n.get("entity_id")
            if nid is None:
                continue
            self._node_map[nid] = n
            self._adj.setdefault(nid, [])
        for e in self.edges:
            s = e.get("subject") or e.get("source")
            o = e.get("obj") or e.get("target") or e.get("object")
            if s is None or o is None:
                continue
            self._adj.setdefault(s, []).append(e)
            self._adj.setdefault(o, []).append(e)

    # ── 探索 API ──
    def neighbors(self, node_id: str, max_nodes: int = _MAX_NODES) -> dict:
        if len(self._node_map) > max_nodes:
            raise ValueError(f"图规模 {len(self._node_map)} 超过扫描上限 {max_nodes}")
        incident = self._adj.get(node_id, [])
        return {
            "node": self._node_map.get(node_id),
            "degree": len(incident),
            "edges": incident,
            "neighbor_ids": sorted({e.get("subject") or e.get("source") for e in incident}
                                  | {e.get("obj") or e.get("target") or e.get("object") for e in incident}
                                  - {node_id}),
        }

    def subgraph(self, node_ids: set[str]) -> "GraphView":
        kept_nodes = [n for n in self.nodes if (n.get("id") or n.get("name") or n.get("entity_id")) in node_ids]
        kept_edges = [
            e for e in self.edges
            if (e.get("subject") or e.get("source")) in node_ids
            and (e.get("obj") or e.get("target") or e.get("object")) in node_ids
        ]
        return GraphView(nodes=kept_nodes, edges=kept_edges)

    def shortest_path(self, source: str, target: str,
                      max_depth: int = 6, max_nodes: int = _MAX_NODES) -> Optional[list[str]]:
        if len(self._node_map) > max_nodes:
            raise ValueError(f"图规模 {len(self._node_map)} 超过扫描上限 {max_nodes}")
        if source not in self._node_map or target not in self._node_map:
            return None
        from collections import deque
        q = deque([source])
        prev: dict[str, Optional[str]] = {source: None}
        depth = {source: 0}
        while q:
            cur = q.popleft()
            if cur == target:
                break
            if depth[cur] >= max_depth:
                continue
            for e in self._adj.get(cur, []):
                nxt = (e.get("obj") or e.get("target") or e.get("object"))
                if nxt not in prev:
                    prev[nxt] = cur
                    depth[nxt] = depth[cur] + 1
                    q.append(nxt)
        if target not in prev:
            return None
        path: list[str] = []
        cur: Optional[str] = target
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        return path[::-1]

    def stats(self) -> dict:
        type_counts: dict[str, int] = {}
        for n in self.nodes:
            t = n.get("type") or n.get("entity_type") or "unknown"
            type_counts[t] = type_counts.get(t, 0) + 1
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "node_types": type_counts,
        }


def from_lightgraph(g) -> GraphView:
    """把 ingest.LightGraph 转换为 GraphView（对齐字段命名）。"""
    nodes = [
        {"id": n.entity_id, "name": n.mention, "type": n.entity_type}
        for n in g.all_nodes()
    ]
    edges = [
        {"subject": e.subject, "predicate": e.predicate, "obj": e.obj}
        for e in g._edges
    ]
    return GraphView(nodes=nodes, edges=edges)


def from_graph_store(store) -> GraphView:
    """把 graph_store 后端（Neo4jGraphStore 或 LightGraph）转换为 GraphView。

    通过 duck-typing 调用 .all_nodes() / .stats()（Neo4jGraphStore 与 LightGraph 都满足）。
    """
    raw_nodes = store.all_nodes()
    nodes: list[dict] = []
    for n in raw_nodes:
        if isinstance(n, dict):
            nodes.append({
                "id": n.get("entity_id") or n.get("id"),
                "name": n.get("mention") or n.get("name"),
                "type": n.get("entity_type") or n.get("type"),
            })
        else:  # GraphNode dataclass
            nodes.append({"id": n.entity_id, "name": n.mention, "type": n.entity_type})

    edges: list[dict] = []
    # Neo4jGraphStore 没有 all_edges()，但对每个 node 取 neighbors 即可覆盖所有边
    # （候选层图规模小，O(节点) 次 neighbors 仍可控；超大规模应改用 Cypher all_edges）
    for nd in nodes:
        nid = nd["id"]
        try:
            for e in store.neighbors(nid):
                # 边的方向：neighbor 返回 [subject -> obj] 的出边；
                # 我们统一存为 (subject, obj)
                if isinstance(e, dict):
                    edges.append({
                        "subject": e.get("subject") or nid,
                        "predicate": e.get("predicate") or "related_to",
                        "obj": e.get("obj") or e.get("object"),
                    })
                else:  # GraphEdge dataclass
                    edges.append({"subject": e.subject, "predicate": e.predicate, "obj": e.obj})
        except Exception:
            # 容错：单点查询失败不影响整体
            continue

    # 去重（无向边可能双计）
    seen = set()
    dedup: list[dict] = []
    for e in edges:
        key = (e.get("subject"), e.get("predicate"), e.get("obj"))
        if key not in seen and all(key):
            seen.add(key)
            dedup.append(e)
    return GraphView(nodes=nodes, edges=dedup)
