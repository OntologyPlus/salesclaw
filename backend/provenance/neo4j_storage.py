"""Neo4j 溯源存储 —— 第九批：Provenance 迁 Neo4j（图数据库承载血缘 + 哈希链）。
                      第 13 批：共享 driver（Neo4jConnectionManager）。

把 SQLiteStorage 升级到 Neo4j，享受：
    - 跨 entity 血缘链：`MATCH (e:Entity)-[:DERIVED_FROM*]->(root)`
    - 跨 activity 实体产出树：`MATCH (a:Activity)-[:GENERATED]->(e:Entity)`
    - 哈希链可视化：`(:Entry)-[:NEXT]->(:Entry)`
    - Neo4j Browser 直接看整链 + 反向追溯

Schema（PROV-O 风格）：
    - 节点 `(:ProvAgent {agent_id, agent_type, name, properties_json})`
    - 节点 `(:ProvActivity {activity_id, activity_type, name, started_at, ended_at,
                              status, input_refs_json, output_refs_json, agent_id,
                              error, properties_json})`
    - 节点 `(:ProvEntry {entry_id, activity_id, entity_id, entity_type, action,
                          agent_id, source_json, data_hash, occurred_at, prev_hash,
                          entry_hash, properties_json})`
    - 关系 `(:ProvEntry)-[:WAS_GENERATED_BY]->(:ProvActivity)`
    - 关系 `(:ProvActivity)-[:WAS_ASSOCIATED_WITH]->(:ProvAgent)`
    - 关系 `(:ProvEntry)-[:NEXT]->(:ProvEntry)`（hash 链）
    - 关系 `(:ProvEntry)-[:WAS_DERIVED_FROM]->(:ProvEntry)`（同 entity 上一条）
    - 关系 `(:ProvActivity)-[:USED]->(:ProvEntry)`（输入引用）
    - 关系 `(:ProvActivity)-[:GENERATED]->(:ProvEntry)`（输出引用）

与 SQLiteStorage 兼容：实现相同接口（append_entry/get_entry/get_last_hash/
iter_entries/get_by_entity/get_by_activity/save_activity/get_activity/
save_agent/close），ProvenanceManager 走工厂，Neo4j 不可用时回退 SQLite。

"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from config import settings
from core.neo4j_driver import Neo4jConnectionManager

from .schemas import ActivityRecord, AgentRecord, ProvenanceEntry, SourceReference

logger = logging.getLogger(__name__)


class Neo4jProvenanceStorage:
    """Neo4j 溯源存储（实现与 SQLiteStorage 相同接口）。

    Driver 由 Neo4jConnectionManager 共享。
    """

    _schema_initialized: bool = False

    def __init__(self, uri: Optional[str] = None,
                 user: Optional[str] = None,
                 password: Optional[str] = None,
                 database: Optional[str] = None,
                 timeout: Optional[float] = None):
        Neo4jConnectionManager.acquire(
            uri=uri, user=user, password=password,
            database=database, timeout=timeout)
        if not Neo4jProvenanceStorage._schema_initialized:
            self._init_schema()
            Neo4jProvenanceStorage._schema_initialized = True

    # ── schema ──
    def _init_schema(self) -> None:
        """创建唯一约束 / 索引（幂等）。"""
        with Neo4jConnectionManager.session() as s:
            for label, prop in [
                ("ProvAgent", "agent_id"),
                ("ProvActivity", "activity_id"),
                ("ProvEntry", "entry_id"),
            ]:
                s.run(
                    f"CREATE CONSTRAINT {label.lower()}_{prop} IF NOT EXISTS "
                    f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE")
            s.run(
                "CREATE INDEX prov_entry_entity IF NOT EXISTS "
                "FOR (n:ProvEntry) ON (n.entity_id, n.entity_type)")
            s.run(
                "CREATE INDEX prov_entry_hash IF NOT EXISTS "
                "FOR (n:ProvEntry) ON (n.entry_hash)")
            s.run(
                "CREATE INDEX prov_activity_type IF NOT EXISTS "
                "FOR (n:ProvActivity) ON (n.activity_type)")

    def _session(self):
        if not Neo4jConnectionManager.is_connected():
            raise RuntimeError("Neo4jProvenanceStorage 未连接")
        return Neo4jConnectionManager.session()

    @property
    def is_connected(self) -> bool:
        return Neo4jConnectionManager.is_connected()

    def close(self) -> None:
        """共享 driver：no-op。"""
        logger.debug("Neo4jProvenanceStorage.close() 无效调用（共享 driver），"
                     "如需释放连接请使用 Neo4jConnectionManager.close_all()")

    # ── entry（核心：自动维护 hash-chain + 派生关系）──
    def append_entry(self, entry: ProvenanceEntry) -> None:
        src_json = json.dumps(entry.source.to_dict(),
                              ensure_ascii=False) if entry.source else None
        props_json = json.dumps(entry.properties,
                                ensure_ascii=False, default=str)
        with self._session() as s:
            s.execute_write(self._tx_append_entry, entry, src_json, props_json)

    @staticmethod
    def _tx_append_entry(tx, entry: ProvenanceEntry,
                          src_json: Optional[str], props_json: str) -> None:
        # 1) MERGE entry 节点
        tx.run(
            """
            MERGE (e:ProvEntry {entry_id: $eid})
            SET e.activity_id = $aid, e.entity_id = $entid, e.entity_type = $etype,
                e.action = $action, e.agent_id = $agid,
                e.source_json = $src, e.data_hash = $dh,
                e.occurred_at = datetime($occ),
                e.prev_hash = $ph, e.entry_hash = $eh,
                e.properties_json = $props
            """,
            eid=entry.entry_id, aid=entry.activity_id,
            entid=entry.entity_id, etype=entry.entity_type,
            action=entry.action, agid=entry.agent_id,
            src=src_json, dh=entry.data_hash,
            occ=entry.occurred_at.isoformat() if entry.occurred_at else None,
            ph=entry.prev_hash, eh=entry.entry_hash, props=props_json,
        )
        # 2) WAS_GENERATED_BY 关系
        if entry.activity_id:
            tx.run(
                """
                MATCH (e:ProvEntry {entry_id: $eid})
                MERGE (a:ProvActivity {activity_id: $aid})
                MERGE (e)-[:WAS_GENERATED_BY]->(a)
                """,
                eid=entry.entry_id, aid=entry.activity_id)
        # 3) WAS_ASSOCIATED_WITH 关系
        if entry.agent_id:
            tx.run(
                """
                MATCH (e:ProvEntry {entry_id: $eid})
                MERGE (ag:ProvAgent {agent_id: $agid})
                MERGE (e)-[:WAS_ASSOCIATED_WITH]->(ag)
                """,
                eid=entry.entry_id, agid=entry.agent_id)
        # 4) NEXT 关系（hash 链：当前 entry 指向 prev_hash 指向的 entry）
        if entry.prev_hash and entry.prev_hash != "GENESIS":
            tx.run(
                """
                MATCH (cur:ProvEntry {entry_id: $eid})
                MATCH (prev:ProvEntry {entry_hash: $ph})
                MERGE (cur)-[:NEXT]->(prev)
                """,
                eid=entry.entry_id, ph=entry.prev_hash)
        # 5) WAS_DERIVED_FROM 关系（同 entity 上一条）
        if entry.entity_id:
            tx.run(
                """
                MATCH (cur:ProvEntry {entry_id: $eid, entity_id: $entid})
                MATCH (prev:ProvEntry {entity_id: $entid})
                WHERE prev.entry_id <> $eid
                  AND prev.occurred_at < cur.occurred_at
                WITH prev ORDER BY prev.occurred_at DESC LIMIT 1
                MERGE (cur)-[:WAS_DERIVED_FROM]->(prev)
                """,
                eid=entry.entry_id, entid=entry.entity_id)

    def get_last_hash(self) -> str:
        with self._session() as s:
            row = s.run(
                "MATCH (e:ProvEntry) "
                "RETURN e.entry_hash AS eh "
                "ORDER BY e.occurred_at DESC LIMIT 1").single()
            return row["eh"] if row else "GENESIS"

    def iter_entries(self, limit: int = 100_000) -> list[ProvenanceEntry]:
        with self._session() as s:
            rows = s.run(
                "MATCH (e:ProvEntry) "
                "RETURN e.entry_id AS entry_id, e.activity_id AS activity_id, "
                "       e.entity_id AS entity_id, e.entity_type AS entity_type, "
                "       e.action AS action, e.agent_id AS agent_id, "
                "       e.source_json AS source_json, e.data_hash AS data_hash, "
                "       e.occurred_at AS occurred_at, e.prev_hash AS prev_hash, "
                "       e.entry_hash AS entry_hash, e.properties_json AS properties_json "
                "ORDER BY e.occurred_at ASC LIMIT $lim",
                lim=limit)
            return [_row_to_entry(r) for r in rows]

    def get_entry(self, entry_id: str) -> Optional[ProvenanceEntry]:
        with self._session() as s:
            row = s.run(
                "MATCH (e:ProvEntry {entry_id: $eid}) "
                "RETURN e.entry_id AS entry_id, e.activity_id AS activity_id, "
                "       e.entity_id AS entity_id, e.entity_type AS entity_type, "
                "       e.action AS action, e.agent_id AS agent_id, "
                "       e.source_json AS source_json, e.data_hash AS data_hash, "
                "       e.occurred_at AS occurred_at, e.prev_hash AS prev_hash, "
                "       e.entry_hash AS entry_hash, e.properties_json AS properties_json",
                eid=entry_id).single()
            return _row_to_entry(row) if row else None

    def get_by_entity(self, entity_id: str,
                      entity_type: Optional[str] = None) -> list[ProvenanceEntry]:
        cypher = (
            "MATCH (e:ProvEntry {entity_id: $eid}) "
            "RETURN e.entry_id AS entry_id, e.activity_id AS activity_id, "
            "       e.entity_id AS entity_id, e.entity_type AS entity_type, "
            "       e.action AS action, e.agent_id AS agent_id, "
            "       e.source_json AS source_json, e.data_hash AS data_hash, "
            "       e.occurred_at AS occurred_at, e.prev_hash AS prev_hash, "
            "       e.entry_hash AS entry_hash, e.properties_json AS properties_json "
            "ORDER BY e.occurred_at ASC"
        )
        params = {"eid": entity_id}
        if entity_type:
            cypher = cypher.replace(
                "{entity_id: $eid}",
                "{entity_id: $eid, entity_type: $etype}")
            params["etype"] = entity_type
        with self._session() as s:
            return [_row_to_entry(r) for r in s.run(cypher, **params)]

    def get_by_activity(self, activity_id: str) -> list[ProvenanceEntry]:
        with self._session() as s:
            rows = s.run(
                "MATCH (e:ProvEntry {activity_id: $aid}) "
                "RETURN e.entry_id AS entry_id, e.activity_id AS activity_id, "
                "       e.entity_id AS entity_id, e.entity_type AS entity_type, "
                "       e.action AS action, e.agent_id AS agent_id, "
                "       e.source_json AS source_json, e.data_hash AS data_hash, "
                "       e.occurred_at AS occurred_at, e.prev_hash AS prev_hash, "
                "       e.entry_hash AS entry_hash, e.properties_json AS properties_json "
                "ORDER BY e.occurred_at ASC",
                aid=activity_id)
            return [_row_to_entry(r) for r in rows]

    # ── activity ───────────────────────────────
    def save_activity(self, act: ActivityRecord) -> None:
        with self._session() as s:
            s.execute_write(self._tx_save_activity, act)

    @staticmethod
    def _tx_save_activity(tx, act: ActivityRecord) -> None:
        tx.run(
            """
            MERGE (a:ProvActivity {activity_id: $aid})
            SET a.activity_type = $atype, a.name = $name,
                a.started_at = datetime($sa), a.ended_at = datetime($ea),
                a.status = $status,
                a.input_refs_json = $inp, a.output_refs_json = $outp,
                a.agent_id = $agid, a.error = $err,
                a.properties_json = $props
            """,
            aid=act.activity_id, atype=act.activity_type, name=act.name,
            sa=act.started_at.isoformat() if act.started_at else None,
            ea=act.ended_at.isoformat() if act.ended_at else None,
            status=act.status,
            inp=json.dumps(act.input_refs), outp=json.dumps(act.output_refs),
            agid=act.agent_id, err=act.error,
            props=json.dumps(act.properties, ensure_ascii=False, default=str),
        )
        if act.agent_id:
            tx.run(
                """
                MATCH (a:ProvActivity {activity_id: $aid})
                MERGE (ag:ProvAgent {agent_id: $agid})
                MERGE (a)-[:WAS_ASSOCIATED_WITH]->(ag)
                """,
                aid=act.activity_id, agid=act.agent_id)

    def get_activity(self, activity_id: str) -> Optional[ActivityRecord]:
        with self._session() as s:
            row = s.run(
                "MATCH (a:ProvActivity {activity_id: $aid}) "
                "RETURN a.activity_id AS activity_id, a.activity_type AS activity_type, "
                "       a.name AS name, a.started_at AS started_at, "
                "       a.ended_at AS ended_at, a.status AS status, "
                "       a.input_refs_json AS input_refs_json, "
                "       a.output_refs_json AS output_refs_json, "
                "       a.agent_id AS agent_id, a.error AS error, "
                "       a.properties_json AS properties_json",
                aid=activity_id).single()
            if not row:
                return None
            return _row_to_activity(row)

    # ── agent ──────────────────────────────────
    def save_agent(self, agent: AgentRecord) -> None:
        with self._session() as s:
            s.execute_write(self._tx_save_agent, agent)

    @staticmethod
    def _tx_save_agent(tx, agent: AgentRecord) -> None:
        tx.run(
            """
            MERGE (ag:ProvAgent {agent_id: $agid})
            SET ag.agent_type = $atype, ag.name = $name,
                ag.properties_json = $props
            """,
            agid=agent.agent_id, atype=agent.agent_type, name=agent.name,
            props=json.dumps(agent.properties, ensure_ascii=False, default=str))

    # ── 图查询（Neo4j 专属）──
    def lineage_chain(self, entity_id: str, max_depth: int = 50) -> list[dict]:
        """某 entity 的完整 WAS_DERIVED_FROM 链（沿时间向过去追溯）。"""
        if not (1 <= max_depth <= 100):
            max_depth = 50
        with self._session() as s:
            rows = s.run(
                f"""
                MATCH p = (start:ProvEntry {{entity_id: $eid}})
                       -[:WAS_DERIVED_FROM*..{max_depth}]->(root:ProvEntry)
                WITH nodes(p) AS ns
                UNWIND ns AS n
                RETURN DISTINCT n.entry_id AS entry_id,
                       n.entity_id AS entity_id, n.action AS action,
                       n.occurred_at AS occurred_at, n.entry_hash AS entry_hash
                ORDER BY occurred_at ASC
                """, eid=entity_id)
            return [dict(r) for r in rows]

    def activity_subgraph(self, activity_id: str) -> dict:
        """某 activity 的输入/输出/agent 子图（可视化根）。"""
        with self._session() as s:
            row = s.run(
                """
                MATCH (a:ProvActivity {activity_id: $aid})
                OPTIONAL MATCH (a)-[:WAS_ASSOCIATED_WITH]->(ag:ProvAgent)
                OPTIONAL MATCH (e:ProvEntry)-[:WAS_GENERATED_BY]->(a)
                WITH a, ag, collect(DISTINCT {id:e.entry_id, entity:e.entity_id,
                                              action:e.action, occurred_at:e.occurred_at}) AS outputs
                OPTIONAL MATCH (a)-[:USED]->(in_e:ProvEntry)
                WITH a, ag, outputs,
                     collect(DISTINCT {id:in_e.entry_id, entity:in_e.entity_id,
                                       action:in_e.action, occurred_at:in_e.occurred_at}) AS inputs
                RETURN a {.*} AS activity,
                       ag {.*} AS agent,
                       outputs, inputs
                """, aid=activity_id).single()
            return dict(row) if row else {}

    def count(self) -> int:
        with self._session() as s:
            return s.run("MATCH (e:ProvEntry) RETURN count(e) AS c").single()["c"]


def _row_to_entry(row) -> ProvenanceEntry:
    src = json.loads(row["source_json"]) if row["source_json"] else None
    occurred = row["occurred_at"]
    if hasattr(occurred, "to_native"):
        occurred = occurred.to_native()
    elif isinstance(occurred, str):
        try:
            occurred = datetime.fromisoformat(occurred.replace("Z", "+00:00"))
        except Exception:
            occurred = None
    return ProvenanceEntry(
        entry_id=row["entry_id"],
        activity_id=row["activity_id"],
        entity_id=row["entity_id"],
        entity_type=row["entity_type"],
        action=row["action"],
        agent_id=row["agent_id"],
        source=SourceReference(**src) if src else None,
        data_hash=row["data_hash"],
        occurred_at=occurred,
        prev_hash=row["prev_hash"],
        entry_hash=row["entry_hash"],
        properties=json.loads(row["properties_json"] or "{}"),
    )


def _row_to_activity(row) -> ActivityRecord:
    def _parse(v):
        if hasattr(v, "to_native"):
            return v.to_native()
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except Exception:
                return None
        return v
    return ActivityRecord(
        activity_id=row["activity_id"],
        activity_type=row["activity_type"],
        name=row["name"],
        started_at=_parse(row["started_at"]),
        ended_at=_parse(row["ended_at"]),
        status=row["status"],
        input_refs=json.loads(row["input_refs_json"] or "[]"),
        output_refs=json.loads(row["output_refs_json"] or "[]"),
        agent_id=row["agent_id"],
        error=row["error"],
        properties=json.loads(row["properties_json"] or "{}"),
    )
