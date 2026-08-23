"""轻量内存知识图 —— 「节点 + 关系 + 查询」

用途：端到端切片中承接 extractor 产出的候选实体/三元组，提供基础邻接查询。
不替代 ontology/registry（运行时权威源），而是「候选层」——经审核后可回流本体/业务表。

未来可平滑替换为 graph_store 后端工厂（见蓝图 §9.3），接口保持：add_entity / add_relation / neighbors / subgraph。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GraphNode:
    entity_id: str
    entity_type: str
    mention: str
    properties: dict = field(default_factory=dict)


@dataclass
class GraphEdge:
    relation_id: str
    subject: str
    predicate: str
    obj: str
    confidence: float = 1.0


class LightGraph:
    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._adj: dict[str, list[GraphEdge]] = {}

    def add_entity(self, e) -> None:
        self._nodes[e.entity_id] = GraphNode(
            entity_id=e.entity_id, entity_type=e.entity_type,
            mention=e.mention, properties=getattr(e, "properties", {}) or {}
        )

    def add_relation(self, r) -> None:
        edge = GraphEdge(relation_id=r.relation_id, subject=r.subject,
                         predicate=r.predicate, obj=r.obj,
                         confidence=getattr(r, "confidence", 1.0))
        self._edges.append(edge)
        self._adj.setdefault(r.subject, []).append(edge)

    def add_entities_batch(self, entities) -> int:
        n = 0
        for e in entities:
            self.add_entity(e)
            n += 1
        return n

    def add_relations_batch(self, relations) -> int:
        n = 0
        for r in relations:
            self.add_relation(r)
            n += 1
        return n

    def neighbors(self, entity_id: str) -> list[GraphEdge]:
        return self._adj.get(entity_id, [])

    def subgraph(self, entity_ids: set[str]) -> "LightGraph":
        g = LightGraph()
        for nid, node in self._nodes.items():
            if nid in entity_ids:
                g._nodes[nid] = node
        for e in self._edges:
            if e.subject in entity_ids and e.obj in entity_ids:
                g._edges.append(e)
                g._adj.setdefault(e.subject, []).append(e)
        return g

    def stats(self) -> dict:
        return {"nodes": len(self._nodes), "edges": len(self._edges)}

    def all_nodes(self) -> list[GraphNode]:
        return list(self._nodes.values())
