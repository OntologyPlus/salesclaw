"""图存储层

与 LightGraph 共享同一接口（add_entity / add_relation / neighbors /
subgraph / shortest_path / stats / all_nodes），由 graph_store.factory
按环境选择后端，pipeline / kg_explorer 零改动切换。

设计要点：
    - 节点用 (Entity) 幂等 MERGE（按 entity_id），关系用 (subject, predicate, obj) 幂等
    - 每次写操作封装在事务中；连接失败由 factory 降级
    - shortest_path 用 Cypher shortestPath，最大深度可配，防 OOM
    - 第 13 批：共享 driver（Neo4jConnectionManager），不在本类持有 driver 生命周期

"""
from __future__ import annotations

import logging
import threading
from typing import Any, Iterable, Optional

from config import settings
from core.neo4j_driver import Neo4jConnectionManager

logger = logging.getLogger(__name__)

# 防 OOM：图遍历/最短路径最大节点数
_MAX_NODES = 5000


class Neo4jGraphStore:
    """Neo4j 图存储实现（候选层后端）。

    与 LightGraph 接口对齐：
        add_entity(e) / add_relation(r) / neighbors(entity_id) / subgraph(ids)
        / shortest_path(src, dst) / stats() / all_nodes()

    Driver 由 Neo4jConnectionManager 统一管理；本类不再持有 driver。
    """

    _schema_initialized: bool = False  # 类级 flag：去重 _init_schema 调用

    def __init__(self, uri: Optional[str] = None,
                 user: Optional[str] = None,
                 password: Optional[str] = None,
                 database: Optional[str] = None,
                 timeout: Optional[float] = None):
        # 把连接参数透传给 manager（仅首次生效）
        Neo4jConnectionManager.acquire(
            uri=uri, user=user, password=password,
            database=database, timeout=timeout)
        self._lock = threading.Lock()
        if not Neo4jGraphStore._schema_initialized:
            self._init_schema()
            Neo4jGraphStore._schema_initialized = True

    # ── schema ──
    def _init_schema(self) -> None:
        """创建 Entity 唯一约束（幂等，IF NOT EXISTS）。"""
        with Neo4jConnectionManager.session() as s:
            s.run(
                "CREATE CONSTRAINT graph_entity_id IF NOT EXISTS "
                "FOR (n:Entity) REQUIRE n.entity_id IS UNIQUE")
            s.run(
                "CREATE INDEX graph_entity_type IF NOT EXISTS "
                "FOR (n:Entity) ON (n.entity_type)")

    def _ensure_session(self):
        if not Neo4jConnectionManager.is_connected():
            raise RuntimeError("Neo4j 未连接")
        return Neo4jConnectionManager.session()

    @property
    def is_connected(self) -> bool:
        return Neo4jConnectionManager.is_connected()

    def backend_name(self) -> str:
        return "neo4j"

    def close(self) -> None:
        """共享 driver：no-op。

        历史：曾直接关闭本 store 的 driver，会破坏其他 3 个共享 store 的连接。
        现在 driver 生命周期由 Neo4jConnectionManager.close_all() 统一管理。
        调用 close() 仅打日志便于排查误用。
        """
        logger.debug("Neo4jGraphStore.close() 无效调用（共享 driver），"
                     "如需释放连接请使用 Neo4jConnectionManager.close_all()")

    # ── 写入（幂等 MERGE）──
    def add_entity(self, e) -> None:
        """e 支持 entity_id / entity_type / mention / properties 属性（duck typing）。"""
        with self._lock:
            with self._ensure_session() as s:
                s.execute_write(self._tx_add_entity, e)

    @staticmethod
    def _tx_add_entity(tx, e) -> None:
        # Neo4j 5.x 严格：SET 不能赋空 map。空 props 时仅写核心字段。
        props = getattr(e, "properties", None) or {}
        if props:
            tx.run(
                "MERGE (n:Entity {entity_id: $eid}) "
                "SET n.entity_type = $etype, n.mention = $mention, n.props = $props",
                eid=e.entity_id, etype=e.entity_type,
                mention=getattr(e, "mention", ""), props=props)
        else:
            tx.run(
                "MERGE (n:Entity {entity_id: $eid}) "
                "SET n.entity_type = $etype, n.mention = $mention",
                eid=e.entity_id, etype=e.entity_type,
                mention=getattr(e, "mention", ""))

    def add_relation(self, r) -> None:
        with self._lock:
            with self._ensure_session() as s:
                s.execute_write(self._tx_add_relation, r)

    @staticmethod
    def _tx_add_relation(tx, r) -> None:
        # 端点自动创建（候选层允许关系先于实体）
        tx.run(
            "MERGE (s:Entity {entity_id: $subj}) "
            "MERGE (o:Entity {entity_id: $obj}) "
            "MERGE (s)-[rel:REL {relation_id: $rid}]->(o) "
            "SET rel.predicate = $pred, rel.confidence = $conf",
            subj=r.subject, obj=r.obj, rid=r.relation_id,
            pred=r.predicate, conf=getattr(r, "confidence", 1.0),
        )

    def add_entities_batch(self, entities: Iterable, batch_size: int = 500) -> int:
        n = 0
        for e in entities:
            self.add_entity(e)
            n += 1
        return n

    def add_relations_batch(self, relations: Iterable, batch_size: int = 500) -> int:
        n = 0
        for r in relations:
            self.add_relation(r)
            n += 1
        return n

    # ── 查询 ──
    def neighbors(self, entity_id: str) -> list[dict]:
        """返回 [{relation_id, predicate, subject, obj, confidence}, ...]"""
        with self._ensure_session() as s:
            rows = s.execute_read(self._tx_neighbors, entity_id)
        return rows

    @staticmethod
    def _tx_neighbors(tx, entity_id: str) -> list[dict]:
        result = tx.run(
            "MATCH (n:Entity {entity_id: $eid})-[r:REL]->(m:Entity) "
            "RETURN r.relation_id AS relation_id, r.predicate AS predicate, "
            "       n.entity_id AS subject, m.entity_id AS obj, r.confidence AS confidence",
            eid=entity_id)
        return [dict(r) for r in result]

    def subgraph(self, entity_ids: set[str]) -> dict:
        """返回 {"nodes": [...], "edges": [...]}（轻量子图快照）。"""
        if not entity_ids:
            return {"nodes": [], "edges": []}
        with self._ensure_session() as s:
            return s.execute_read(self._tx_subgraph, list(entity_ids))

    @staticmethod
    def _tx_subgraph(tx, eids: list[str]) -> dict:
        nres = tx.run(
            "MATCH (n:Entity) WHERE n.entity_id IN $eids "
            "RETURN n.entity_id AS entity_id, n.entity_type AS entity_type, "
            "       n.mention AS mention, coalesce(n.props, {}) AS props",
            eids=eids)
        nodes = [dict(r) for r in nres]
        eres = tx.run(
            "MATCH (s:Entity)-[r:REL]->(o:Entity) "
            "WHERE s.entity_id IN $eids AND o.entity_id IN $eids "
            "RETURN r.relation_id AS relation_id, r.predicate AS predicate, "
            "       s.entity_id AS subject, o.entity_id AS obj, r.confidence AS confidence",
            eids=eids)
        edges = [dict(r) for r in eres]
        if len(nodes) > _MAX_NODES:
            nodes = nodes[:_MAX_NODES]
        return {"nodes": nodes, "edges": edges}

    def shortest_path(self, source: str, target: str,
                      max_depth: int = 6) -> list[dict]:
        """Cypher shortestPath（无向：任一方向）。返回路径边序列。"""
        # Neo4j 不允许 shortestPath 的 max length 用参数；必须字面量
        if not (1 <= max_depth <= 10):
            max_depth = 6
        with self._ensure_session() as s:
            cypher = (
                "MATCH (a:Entity {entity_id: $src}), (b:Entity {entity_id: $dst}), "
                f"p = shortestPath((a)-[:REL*..{max_depth}]-(b)) "
                "UNWIND relationships(p) AS r "
                "RETURN r.relation_id AS relation_id, r.predicate AS predicate, "
                "       startNode(r).entity_id AS subject, "
                "       endNode(r).entity_id AS obj, r.confidence AS confidence"
            )
            return [dict(row) for row in s.run(cypher, src=source, dst=target)]

    def stats(self) -> dict:
        with self._ensure_session() as s:
            row = s.execute_read(self._tx_stats)
        return row

    @staticmethod
    def _tx_stats(tx) -> dict:
        r = tx.run(
            "MATCH (n:Entity) WITH count(n) AS nodes "
            "MATCH ()-[r:REL]->() WITH nodes, count(r) AS edges "
            "RETURN nodes, edges").single()
        return {"nodes": r["nodes"] if r else 0,
                "edges": r["edges"] if r else 0,
                "backend": "neo4j"}

    def all_nodes(self) -> list[dict]:
        with self._ensure_session() as s:
            return s.execute_read(self._tx_all_nodes)

    @staticmethod
    def _tx_all_nodes(tx) -> list[dict]:
        r = tx.run(
            "MATCH (n:Entity) "
            "RETURN n.entity_id AS entity_id, n.entity_type AS entity_type, "
            "       n.mention AS mention, coalesce(n.props, {}) AS props "
            "LIMIT $lim",
            lim=_MAX_NODES)
        return [dict(x) for x in r]

    # ── 清理（仅候选层/测试用）──
    def clear(self) -> None:
        with self._ensure_session() as s:
            s.execute_write(lambda tx: tx.run(
                "MATCH (n:Entity) DETACH DELETE n"))
