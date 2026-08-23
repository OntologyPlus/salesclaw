"""Neo4j 版本存储 —— 第九批：本体快照迁 Neo4j（图数据库承载版本链）。
                      第 13 批：共享 driver（Neo4jConnectionManager）。

把 VersionStore 从 SQLite 升级到 Neo4j，享受：
    - 版本链 `(:OntSnapshot)-[:DERIVED_FROM]->(:OntSnapshot)` 天然 DAG
    - ancestor 链查询：`shortestPath((s)-[:DERIVED_FROM*]->(root))`
    - 跨分支对比：任意两个 snapshot 的 LCA
    - Neo4j Browser 可视化本体演进史

Schema：
    - 节点 `(:OntSnapshot {version_id, parent_version, content_hash, parent_hash,
                              created_at, authored_by, note})`
    - 节点 `(:OntDefinitions {snapshot_id})`：承载 objects/links/actions 列表
    - 关系 `(:OntSnapshot)-[:HAS_DEFINITIONS]->(:OntDefinitions)`
    - 关系 `(:OntSnapshot)-[:DERIVED_FROM]->(:OntSnapshot)`
    - 关系 `(:OntSnapshot)-[:NEXT_HASH]->(:OntSnapshot)`（按 content_hash 链）

与 SQLite 兼容：实现相同接口（append/get/latest/all/get_last_hash/close），
VersionManager 走工厂，Neo4j 不可用时回退 SQLite（fallback 零侵入）。
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from config import settings
from core.neo4j_driver import Neo4jConnectionManager

from .snapshot import OntologySnapshot

logger = logging.getLogger(__name__)


class Neo4jVersionStore:
    """Neo4j 版本存储（实现 VersionStore 同接口）。

    Driver 由 Neo4jConnectionManager 共享，本类不持有 driver 生命周期。
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
        if not Neo4jVersionStore._schema_initialized:
            self._init_schema()
            Neo4jVersionStore._schema_initialized = True

    # ── schema ──
    def _init_schema(self) -> None:
        """创建唯一约束 / 索引（幂等，IF NOT EXISTS）。"""
        with Neo4jConnectionManager.session() as s:
            s.run(
                "CREATE CONSTRAINT ont_snapshot_id IF NOT EXISTS "
                "FOR (n:OntSnapshot) REQUIRE n.version_id IS UNIQUE")
            s.run(
                "CREATE INDEX ont_snapshot_created IF NOT EXISTS "
                "FOR (n:OntSnapshot) ON (n.created_at)")
            s.run(
                "CREATE CONSTRAINT ont_definitions_sid IF NOT EXISTS "
                "FOR (n:OntDefinitions) REQUIRE n.snapshot_id IS UNIQUE")

    def _session(self):
        if not Neo4jConnectionManager.is_connected():
            raise RuntimeError("Neo4jVersionStore 未连接")
        return Neo4jConnectionManager.session()

    @property
    def is_connected(self) -> bool:
        return Neo4jConnectionManager.is_connected()

    def close(self) -> None:
        """共享 driver：no-op（Neo4jConnectionManager.close_all() 统一关闭）。"""
        logger.debug("Neo4jVersionStore.close() 无效调用（共享 driver），"
                     "如需释放连接请使用 Neo4jConnectionManager.close_all()")

    # ── 写入 ──
    def append(self, snap: OntologySnapshot) -> None:
        """MERGE 幂等写入：重复 version_id 不重复创建。"""
        defs_payload = {
            "objects": snap.objects,
            "links": snap.links,
            "actions": snap.actions,
        }
        with self._session() as s:
            s.execute_write(self._tx_append, snap, defs_payload)

    @staticmethod
    def _tx_append(tx, snap: OntologySnapshot, defs_payload: dict) -> None:
        # 1) MERGE snapshot 节点
        tx.run(
            """
            MERGE (n:OntSnapshot {version_id: $vid})
            SET n.parent_version = $pv,
                n.content_hash = $ch,
                n.parent_hash = $ph,
                n.created_at = datetime($ts),
                n.authored_by = $ab,
                n.note = $note
            """,
            vid=snap.version_id, pv=snap.parent_version,
            ch=snap.content_hash, ph=snap.parent_hash,
            ts=snap.created_at.isoformat() if snap.created_at else None,
            ab=snap.authored_by, note=snap.note,
        )
        # 2) MERGE definitions 子节点
        tx.run(
            """
            MATCH (n:OntSnapshot {version_id: $vid})
            MERGE (d:OntDefinitions {snapshot_id: $vid})
            SET d.objects_json = $objs,
                d.links_json = $links,
                d.actions_json = $acts
            MERGE (n)-[:HAS_DEFINITIONS]->(d)
            """,
            vid=snap.version_id,
            objs=json.dumps(defs_payload["objects"], ensure_ascii=False, default=str),
            links=json.dumps(defs_payload["links"], ensure_ascii=False, default=str),
            acts=json.dumps(defs_payload["actions"], ensure_ascii=False, default=str),
        )
        # 3) DERIVED_FROM 父链（仅当 parent_version 存在）
        if snap.parent_version:
            tx.run(
                """
                MATCH (n:OntSnapshot {version_id: $vid})
                MATCH (p:OntSnapshot {version_id: $pv})
                MERGE (n)-[:DERIVED_FROM]->(p)
                """,
                vid=snap.version_id, pv=snap.parent_version)
        # 4) NEXT_HASH 链（按 content_hash 链相邻）
        tx.run(
            """
            MATCH (n:OntSnapshot {version_id: $vid})
            MATCH (prev:OntSnapshot {content_hash: $ph})
            WHERE prev.version_id <> $vid
            MERGE (n)-[:NEXT_HASH]->(prev)
            """,
            vid=snap.version_id, ph=snap.parent_hash)

    # ── 查询 ──
    def get(self, version_id: str) -> Optional[OntologySnapshot]:
        with self._session() as s:
            return s.execute_read(self._tx_get, version_id)

    @staticmethod
    def _tx_get(tx, version_id: str) -> Optional[OntologySnapshot]:
        from datetime import datetime as _dt
        row = tx.run(
            """
            MATCH (n:OntSnapshot {version_id: $vid})
            OPTIONAL MATCH (n)-[:HAS_DEFINITIONS]->(d:OntDefinitions)
            RETURN n.version_id AS version_id, n.parent_version AS parent_version,
                   n.content_hash AS content_hash, n.parent_hash AS parent_hash,
                   n.created_at AS created_at, n.authored_by AS authored_by,
                   n.note AS note,
                   d.objects_json AS objects_json,
                   d.links_json AS links_json,
                   d.actions_json AS actions_json
            """, vid=version_id).single()
        if not row:
            return None
        return _row_to_snapshot(row)

    def latest(self) -> Optional[OntologySnapshot]:
        """返回最新（按 created_at 降序第一个）。"""
        with self._session() as s:
            return s.execute_read(self._tx_latest)

    @staticmethod
    def _tx_latest(tx) -> Optional[OntologySnapshot]:
        from datetime import datetime as _dt
        row = tx.run(
            """
            MATCH (n:OntSnapshot)
            OPTIONAL MATCH (n)-[:HAS_DEFINITIONS]->(d:OntDefinitions)
            RETURN n.version_id AS version_id, n.parent_version AS parent_version,
                   n.content_hash AS content_hash, n.parent_hash AS parent_hash,
                   n.created_at AS created_at, n.authored_by AS authored_by,
                   n.note AS note,
                   d.objects_json AS objects_json,
                   d.links_json AS links_json,
                   d.actions_json AS actions_json
            ORDER BY n.created_at DESC
            LIMIT 1
            """).single()
        if not row:
            return None
        return _row_to_snapshot(row)

    def all(self) -> list[OntologySnapshot]:
        """按时间升序返回所有 snapshot。"""
        with self._session() as s:
            return s.execute_read(self._tx_all)

    @staticmethod
    def _tx_all(tx) -> list[OntologySnapshot]:
        rows = tx.run(
            """
            MATCH (n:OntSnapshot)
            OPTIONAL MATCH (n)-[:HAS_DEFINITIONS]->(d:OntDefinitions)
            RETURN n.version_id AS version_id, n.parent_version AS parent_version,
                   n.content_hash AS content_hash, n.parent_hash AS parent_hash,
                   n.created_at AS created_at, n.authored_by AS authored_by,
                   n.note AS note,
                   d.objects_json AS objects_json,
                   d.links_json AS links_json,
                   d.actions_json AS actions_json
            ORDER BY n.created_at ASC
            """)
        return [_row_to_snapshot(r) for r in rows]

    def get_last_hash(self) -> str:
        """返回最后一个 snapshot 的 content_hash（用于新区块的 parent_hash）。"""
        latest = self.latest()
        return latest.content_hash if latest else "GENESIS"

    # ── 图查询（Neo4j 专属能力，原 SQLite 做不到）──
    def ancestors_of(self, version_id: str, max_depth: int = 32) -> list[str]:
        """从 version_id 向上找祖先链（DERIVED_FROM），返回 version_id 列表（含自己）。"""
        if not (1 <= max_depth <= 50):
            max_depth = 32
        with self._session() as s:
            rows = s.run(
                f"""
                MATCH p = (s:OntSnapshot {{version_id: $vid}})
                       -[:DERIVED_FROM*..{max_depth}]->(root:OntSnapshot)
                WITH nodes(p) AS ns
                UNWIND ns AS n
                RETURN DISTINCT n.version_id AS version_id
                ORDER BY version_id
                """, vid=version_id)
            return [r["version_id"] for r in rows]

    def lca(self, vid_a: str, vid_b: str) -> Optional[str]:
        """两个 snapshot 的最近公共祖先（LCA）version_id。"""
        with self._session() as s:
            row = s.run(
                """
                MATCH (a:OntSnapshot {version_id: $a}),
                      (b:OntSnapshot {version_id: $b})
                MATCH p1 = (a)-[:DERIVED_FROM*]->(anc:OntSnapshot)
                MATCH p2 = (b)-[:DERIVED_FROM*]->(anc)
                WITH anc, length(p1) AS d1, length(p2) AS d2
                ORDER BY d1 + d2
                LIMIT 1
                RETURN anc.version_id AS version_id
                """, a=vid_a, b=vid_b).single()
            return row["version_id"] if row else None

    def count(self) -> int:
        with self._session() as s:
            return s.run("MATCH (n:OntSnapshot) RETURN count(n) AS c").single()["c"]


def _row_to_snapshot(row) -> OntologySnapshot:
    """把 Neo4j 行（Row）反序列化为 OntologySnapshot。"""
    from datetime import datetime as _dt
    import json as _json
    from .snapshot import OntologySnapshot

    created = row["created_at"]
    if hasattr(created, "to_native"):  # neo4j.time.DateTime
        created = created.to_native()
    elif isinstance(created, str):
        try:
            created = _dt.fromisoformat(created.replace("Z", "+00:00"))
        except Exception:
            created = None

    def _load(jstr):
        if not jstr:
            return []
        try:
            return _json.loads(jstr)
        except Exception:
            return []

    return OntologySnapshot(
        version_id=row["version_id"],
        parent_version=row["parent_version"],
        objects=_load(row["objects_json"]),
        links=_load(row["links_json"]),
        actions=_load(row["actions_json"]),
        authored_by=row["authored_by"],
        note=row["note"],
        created_at=created,
        content_hash=row["content_hash"] or "",
        parent_hash=row["parent_hash"] or "GENESIS",
    )
