"""Neo4j 候选审核存储 —— 第十一批：Governance 候选与已落图 entity 关系化。
                       第 13 批：共享 driver（Neo4jConnectionManager）。

第 11 批：旧 SQLite CandidateStore 已退役，本模块是唯一的候选审核后端：
    - 候选节点与已落图 entity 关系化：`(:ReviewCandidate)-[:REPRESENTS]->(:Entity)`
    - 跨管线追溯：哪个 candidate 经哪次 review 被 approve → 由哪个 reflow 落库
    - Neo4j Browser 整图查看（候选 / 已落图 / 拒绝原因）

Schema：
    - 节点 `(:ReviewCandidate {candidate_id, kind, payload_json, status,
                                  decided_by, decided_at, note, created_at})`
    - 关系 `(:ReviewCandidate)-[:REPRESENTS]->(:Entity)`（由 candidate_id/relation_id
      指向 entity_id；relation 候选在两端各建一条 REPRESENTS）
    - 状态变化用属性 `status` 字段（pending/approved/rejected）

接口（add / decide / list_pending / list_approved / close）。

"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from config import settings
from core.neo4j_driver import Neo4jConnectionManager

from .models import Candidate, now_iso

# 重命名以保持本文件内原有调用点（_now()）兼容
_now = now_iso

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Neo4jCandidateStore:
    """Neo4j 候选审核存储（第 11 批迁 Neo4j 后唯一主存后端）。

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
        if not Neo4jCandidateStore._schema_initialized:
            self._init_schema()
            Neo4jCandidateStore._schema_initialized = True

    # ── schema ──
    def _init_schema(self) -> None:
        with Neo4jConnectionManager.session() as s:
            s.run(
                "CREATE CONSTRAINT review_candidate_id IF NOT EXISTS "
                "FOR (n:ReviewCandidate) REQUIRE n.candidate_id IS UNIQUE")
            s.run(
                "CREATE INDEX review_candidate_status IF NOT EXISTS "
                "FOR (n:ReviewCandidate) ON (n.status)")

    def _session(self):
        if not Neo4jConnectionManager.is_connected():
            raise RuntimeError("Neo4jCandidateStore 未连接")
        return Neo4jConnectionManager.session()

    @property
    def is_connected(self) -> bool:
        return Neo4jConnectionManager.is_connected()

    def close(self) -> None:
        """共享 driver：no-op。"""
        logger.debug("Neo4jCandidateStore.close() 无效调用（共享 driver），"
                     "如需释放连接请使用 Neo4jConnectionManager.close_all()")

    # ── 收候选 ──
    def add(self, candidate_id: str, kind: str, payload: dict) -> Candidate:
        """插入候选 + 与已落图 Entity 建 REPRESENTS 边（幂等）。"""
        payload_json = json.dumps(payload, ensure_ascii=False)
        with self._session() as s:
            s.execute_write(self._tx_add, candidate_id, kind,
                            payload_json, payload)
        return Candidate(candidate_id=candidate_id, kind=kind, payload=payload)

    @staticmethod
    def _tx_add(tx, candidate_id: str, kind: str,
                payload_json: str, payload: dict) -> None:
        # 1) MERGE candidate 节点
        tx.run(
            """
            MERGE (c:ReviewCandidate {candidate_id: $cid})
            SET c.kind = $kind, c.payload_json = $payload,
                c.status = 'pending', c.created_at = datetime($ts)
            """,
            cid=candidate_id, kind=kind, payload=payload_json, ts=_now())
        # 2) REPRESENTS 边（指向已落图 Entity；端点不存在也 MERGE 占位）
        if kind == "entity":
            ent_id = payload.get("entity_id")
            if ent_id:
                tx.run(
                    """
                    MATCH (c:ReviewCandidate {candidate_id: $cid})
                    MERGE (e:Entity {entity_id: $eid})
                    MERGE (c)-[:REPRESENTS]->(e)
                    """,
                    cid=candidate_id, eid=ent_id)
        elif kind == "relation":
            # relation 候选在两端各建一条 REPRESENTS 边
            for eid_key in ("subject", "obj"):
                ent_id = payload.get(eid_key)
                if ent_id:
                    tx.run(
                        """
                        MATCH (c:ReviewCandidate {candidate_id: $cid})
                        MERGE (e:Entity {entity_id: $eid})
                        MERGE (c)-[:REPRESENTS]->(e)
                        """,
                        cid=candidate_id, eid=ent_id)

    # ── 决策 ──
    def decide(self, candidate_id: str, decision: str,
               decided_by: str, note: Optional[str] = None) -> bool:
        """decision ∈ {approved, rejected}。返回是否生效。"""
        if decision not in ("approved", "rejected"):
            raise ValueError("decision 必须为 approved/rejected")
        with self._session() as s:
            result = s.execute_write(self._tx_decide,
                                      candidate_id, decision,
                                      decided_by, note, _now())
            return bool(result)

    @staticmethod
    def _tx_decide(tx, candidate_id: str, decision: str,
                    decided_by: str, note: Optional[str], ts: str) -> bool:
        # MERGE + SET：candidate 不存在则创建（保持接口语义），存在则改状态
        result = tx.run(
            """
            MERGE (c:ReviewCandidate {candidate_id: $cid})
            SET c.status = $st, c.decided_by = $by, c.decided_at = $ts,
                c.note = $note
            RETURN c.candidate_id AS cid
            """,
            cid=candidate_id, st=decision, by=decided_by,
            ts=ts, note=note)
        return result.single() is not None

    # ── 查询 ──
    def list_pending(self, kind: Optional[str] = None,
                     limit: int = 200) -> list[Candidate]:
        return self._query("pending", kind, limit)

    def list_approved(self, kind: Optional[str] = None,
                      limit: int = 200) -> list[Candidate]:
        return self._query("approved", kind, limit)

    def list_rejected(self, kind: Optional[str] = None,
                      limit: int = 200) -> list[Candidate]:
        return self._query("rejected", kind, limit)

    def _query(self, status: str, kind: Optional[str], limit: int) -> list[Candidate]:
        cypher = (
            "MATCH (c:ReviewCandidate {status: $st}) "
            "RETURN c.candidate_id AS candidate_id, c.kind AS kind, "
            "       c.payload_json AS payload_json, c.status AS status, "
            "       c.decided_by AS decided_by, c.decided_at AS decided_at, "
            "       c.note AS note, c.created_at AS created_at "
            "ORDER BY c.created_at ASC LIMIT $lim"
        )
        params = {"st": status, "lim": limit}
        if kind:
            cypher = cypher.replace(
                "{status: $st}", "{status: $st, kind: $kind}")
            params["kind"] = kind
        with self._session() as s:
            rows = s.run(cypher, **params)
            return [_row_to_candidate(r) for r in rows]

    # ── 图查询（Neo4j 专属）──
    def candidates_representing(self, entity_id: str) -> list[Candidate]:
        """查询代表某 entity 的所有候选（关系化查询）。"""
        with self._session() as s:
            rows = s.run(
                """
                MATCH (c:ReviewCandidate)-[:REPRESENTS]->(e:Entity {entity_id: $eid})
                RETURN c.candidate_id AS candidate_id, c.kind AS kind,
                       c.payload_json AS payload_json, c.status AS status,
                       c.decided_by AS decided_by, c.decided_at AS decided_at,
                       c.note AS note, c.created_at AS created_at
                ORDER BY c.created_at ASC
                """, eid=entity_id)
            return [_row_to_candidate(r) for r in rows]

    def count(self, status: Optional[str] = None) -> int:
        cypher = "MATCH (c:ReviewCandidate) RETURN count(c) AS c"
        params: dict = {}
        if status:
            cypher = cypher.replace(
                ") RETURN", " {status: $st}) RETURN")
            params["st"] = status
        with self._session() as s:
            return s.run(cypher, **params).single()["c"]


def _row_to_candidate(row) -> Candidate:
    payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
    return Candidate(
        candidate_id=row["candidate_id"],
        kind=row["kind"],
        payload=payload,
        status=row["status"],
        decided_by=row["decided_by"],
        decided_at=row["decided_at"],
        note=row["note"],
    )
