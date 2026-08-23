"""本体语义推理层 —— 第八批：rdflib OWL 推理

职责：
    - 把 ontology.registry 里的 OBJECTS / LINKS 序列化为 RDF/OWL 图
    - 用 rdflib 的 RDFS 推理 + 手动声明的传递闭包，发现"可走"但 BFS 不易枚举的隐式关系
    - 补充 ontology.chain 的显式 BFS：rdflib 给出"类型层"可推导的关系模板

与 ontology.chain 关系：
    - chain.infer_relation_chain: 沿注册表做加权多跳 BFS（实例级归因，权重有业务语义）
    - reasoning.OntologyReasoner: 类型/模式级 OWL 推理（判断"哪类对象能到哪类对象"）
    - 两者并行不互斥，由调用方按场景选择
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# rdflib 命名空间
from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal, URIRef
from rdflib.namespace import XSD


_EX = Namespace("http://salesclaw.example/ontology#")


class OntologyReasoner:
    """把本体注册表（OBJECTS/LINKS）转为 RDF/OWL 图并做语义推理。"""

    def __init__(self, registry: Optional[object] = None):
        from ontology.registry import OBJECTS, LINKS
        self._registry = registry
        self._g = Graph()
        self._g.bind("ex", _EX)
        self._g.bind("owl", OWL)
        self._g.bind("rdfs", RDFS)
        self._obj_by_name: dict[str, dict] = {o["name"]: o for o in OBJECTS}
        self._link_by_name: dict[str, dict] = {l["name"]: l for l in LINKS}
        self._build()

    # ── 构造 RDF 图 ──
    def _build(self) -> None:
        # Object types → owl:Class
        for name, obj in self._obj_by_name.items():
            uri = _EX[name]
            self._g.add((uri, RDF.type, OWL.Class))
            if obj.get("display_name"):
                self._g.add((uri, RDFS.label, Literal(obj["display_name"], lang="zh")))
            if obj.get("domain"):
                self._g.add((uri, _EX.domain, Literal(obj["domain"])))

        # Link types → owl:ObjectProperty + domain/range
        for name, link in self._link_by_name.items():
            uri = _EX[name]
            self._g.add((uri, RDF.type, OWL.ObjectProperty))
            src = link.get("source_object")
            tgt = link.get("target_object")
            if src in self._obj_by_name:
                self._g.add((uri, RDFS.domain, _EX[src]))
            if tgt in self._obj_by_name:
                self._g.add((uri, RDFS.range, _EX[tgt]))
            if link.get("display_name"):
                self._g.add((uri, RDFS.label, Literal(link["display_name"], lang="zh")))
            if link.get("cardinality"):
                self._g.add((uri, _EX.cardinality, Literal(link["cardinality"])))

        # 关键业务规则：links 视为"可传递复合闭包"——但 OWL 不会自动
        # 推断任意多跳，需要在类型层用 SPARQL/手动 BFS 计算。
        # 这里补一个 SHACL-lite 规则：covers 视为可传递（业务定义）
        # 用 rdf:type owl:TransitiveProperty 显式标记 "covers"
        if "covers" in self._link_by_name:
            self._g.add((_EX["covers"], RDF.type, OWL.TransitiveProperty))
        if "located_in" in self._link_by_name:
            self._g.add((_EX["located_in"], RDF.type, OWL.TransitiveProperty))
        if "belongs_to" in self._link_by_name:
            self._g.add((_EX["belongs_to"], RDF.type, OWL.TransitiveProperty))

    # ── 查询 ──
    def reachable_types(self, source_type: str, max_depth: int = 4) -> list[dict]:
        """类型层可达性：从 source_type 出发，深度 ≤ max_depth 能到达的 object 类型。

        走两层：
            1) 直接 link（domain/range）
            2) 传递闭包：transitive properties 在多次 use 后可达的类型

        返回 [{type, via_link, depth, transitive}, ...]
        """
        if source_type not in self._obj_by_name:
            return []
        from collections import deque
        seen = {source_type}
        out: list[dict] = []
        q = deque([(source_type, 0, None, False)])
        while q:
            cur, d, via, transitive = q.popleft()
            if d >= max_depth:
                continue
            for link_name, link in self._link_by_name.items():
                src = link.get("source_object")
                tgt = link.get("target_object")
                is_trans = (_EX[link_name], RDF.type, OWL.TransitiveProperty) in self._g
                # 正向
                if cur == src and tgt and tgt not in seen:
                    seen.add(tgt)
                    out.append({"type": tgt, "via_link": link_name,
                                "depth": d + 1, "transitive": is_trans})
                    q.append((tgt, d + 1, link_name, is_trans))
                # 反向（当作可达，因为图探索是无向语义）
                if cur == tgt and src and src not in seen:
                    seen.add(src)
                    out.append({"type": src, "via_link": link_name,
                                "depth": d + 1, "transitive": is_trans})
                    q.append((src, d + 1, link_name, is_trans))
        return out

    def explain_link(self, source_type: str, target_type: str) -> dict:
        """解释：从 source_type 到 target_type 是否能直达（不限制跳数）。

        返回 {"direct": bool, "path": [...], "reason": ...}
        """
        if source_type not in self._obj_by_name or target_type not in self._obj_by_name:
            return {"direct": False, "path": [], "reason": "unknown type"}

        # BFS 找最短路径（仅类型层）
        from collections import deque
        prev: dict[str, tuple[str, str]] = {}  # node -> (prev_node, via_link)
        seen = {source_type}
        q = deque([source_type])
        while q:
            cur = q.popleft()
            if cur == target_type:
                # 重建路径
                path = []
                node = target_type
                while node != source_type:
                    p, link = prev[node]
                    path.append({"from": p, "to": node, "link": link})
                    node = p
                path.reverse()
                return {"direct": len(path) == 1, "path": path,
                        "reason": "rdflib 类型层 BFS 推理"}
            for link_name, link in self._link_by_name.items():
                src = link.get("source_object")
                tgt = link.get("target_object")
                if cur == src and tgt and tgt not in seen:
                    seen.add(tgt)
                    prev[tgt] = (cur, link_name)
                    q.append(tgt)
                if cur == tgt and src and src not in seen:
                    seen.add(src)
                    prev[src] = (cur, link_name)
                    q.append(src)
        return {"direct": False, "path": [], "reason": "类型层不可达"}

    def triples_count(self) -> int:
        return len(self._g)

    def to_rdf_graph(self) -> Graph:
        return self._g

    def export_turtle(self) -> str:
        return self._g.serialize(format="turtle")
