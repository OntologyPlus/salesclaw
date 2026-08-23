"""溯源管理器

职责：
    - 串联 storage + integrity，写入时自动维护 hash-chain
    - 提供 activity 生命周期（start/finish）与 entry 记录
    - 提供 lineage（上游/下游检索）与整链完整性校验
    - 提供非侵入式 track() 上下文管理器

第 9 批：后端切换到 Neo4j（批次 13 共享 driver）。
第 14 批：Neo4j 唯一主存，删除 SQLite 回退（PROVENANCE_STORE 字段不再存在），
Neo4j 不可达 → 启动失败（运营要求：必须保证 Neo4j 可用）。

本模块为「技术级全链路溯源」中枢，与 services/data_lineage_service.py
（业务实体级血缘）互补，不替代它。
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from .integrity import chain_hash, compute_data_hash, verify_chain
from .schemas import (
    ActivityRecord,
    AgentRecord,
    ProvenanceEntry,
    SourceReference,
)

logger = logging.getLogger(__name__)


def _create_storage():
    """工厂：固定 Neo4j 后端（fail-fast）。

    第 14 批：原 PROVENANCE_STORE=auto|neo4j|sqlite 已删除，统一 Neo4j。
    Neo4j 不可达抛 RuntimeError，调用方应承担启动失败的语义。
    """
    from .neo4j_storage import Neo4jProvenanceStorage
    storage = Neo4jProvenanceStorage()  # Neo4j 不可达时直接抛错
    return storage, "neo4j"


class ProvenanceManager:
    """溯源管理器（Neo4j 唯一后端）。

    第 14 批：构造函数去除 db_path 入参（不再有 SQLite 回退路径）。
    历史调用 `ProvenanceManager(db_path=...)` 兼容保留：仅打 warning，不使用。
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is not None:
            logger.warning(
                "ProvenanceManager(db_path=...) 第 14 批已废弃，Neo4j 为主存；"
                "db_path 参数被忽略（保持兼容）"
            )
        self._storage, self._backend = _create_storage()
        self._agents: dict[str, AgentRecord] = {}

    @property
    def backend(self) -> str:
        return self._backend

    # ── agent ──────────────────────────────────
    def register_agent(self, agent_type: str = "service", name: str = None,
                       properties: dict = None) -> AgentRecord:
        agent = AgentRecord(agent_type=agent_type, name=name,
                            properties=properties or {})
        self._storage.save_agent(agent)
        self._agents[agent.agent_id] = agent
        return agent

    def get_agent(self, agent_id: str) -> Optional[AgentRecord]:
        return self._agents.get(agent_id)

    # ── activity ───────────────────────────────
    def start_activity(self, activity_type: str, name: str = None,
                       agent_id: str = None, input_refs: list[str] = None) -> ActivityRecord:
        act = ActivityRecord(activity_type=activity_type, name=name,
                             agent_id=agent_id, input_refs=input_refs or [])
        self._storage.save_activity(act)
        return act

    def finish_activity(self, act: ActivityRecord, status: str = "completed",
                        error: str = None, output_refs: list[str] = None) -> None:
        act.finish(status=status, error=error)
        if output_refs is not None:
            act.output_refs = output_refs
        self._storage.save_activity(act)

    # ── entry（核心：自动维护 hash-chain）────────
    def record(self, *, activity_id: str = None, entity_id: str = None,
               entity_type: str = None, action: str = "generated",
               agent_id: str = None, source: SourceReference = None,
               data: Any = None, properties: dict = None) -> ProvenanceEntry:
        """记录一条溯源条目，自动接上 hash-chain。"""
        prev = self._storage.get_last_hash()
        entry = ProvenanceEntry(
            activity_id=activity_id,
            entity_id=entity_id,
            entity_type=entity_type,
            action=action,
            agent_id=agent_id,
            source=source,
            data_hash=compute_data_hash(data) if data is not None else None,
            prev_hash=prev,
            properties=properties or {},
        )
        entry.entry_hash = chain_hash(prev, entry)
        self._storage.append_entry(entry)
        return entry

    def record_activity_bound(self, act: ActivityRecord) -> None:
        """活动结束时把活动本身作为一条 entry 落链（便于整链校验）。"""
        self.record(
            activity_id=act.activity_id,
            entity_id=act.activity_id,
            entity_type="activity",
            action="completed" if act.status == "completed" else "failed",
            agent_id=act.agent_id,
            properties={"status": act.status, "error": act.error},
        )

    # ── 检索 ───────────────────────────────────
    def get(self, entry_id: str) -> Optional[ProvenanceEntry]:
        return self._storage.get_entry(entry_id)

    def lineage_of(self, entity_id: str, entity_type: str = None) -> list[ProvenanceEntry]:
        """某实体的全部溯源条目（即其血缘链）。"""
        return self._storage.get_by_entity(entity_id, entity_type)

    def entries_of_activity(self, activity_id: str) -> list[ProvenanceEntry]:
        return self._storage.get_by_activity(activity_id)

    def activity(self, activity_id: str) -> Optional[ActivityRecord]:
        return self._storage.get_activity(activity_id)

    # ── 完整性 ─────────────────────────────────
    def verify(self) -> tuple[bool, int, int]:
        """校验整条哈希链。

        Returns:
            (ok, broken_at_index, total)
        """
        entries = self._storage.iter_entries()
        ok, broken = verify_chain(entries)
        return ok, broken, len(entries)

    def close(self) -> None:
        self._storage.close()


class track:  # noqa: N801 —— 设计为上下文管理器，刻意小写以便 `with track(...) as act:`
    """非侵入式活动追踪上下文。

    用法：
        with track("extract", name="NER", agent_id=agent.agent_id) as act:
            ... 处理逻辑 ...
            act.output_refs.append(chunk_id)
        # 退出时自动 record_activity_bound + finish

    异常时自动以 failed 状态落链。
    """

    def __init__(self, activity_type: str, name: str = None, agent_id: str = None,
                 input_refs: list[str] = None, mgr: ProvenanceManager = None):
        self.mgr = mgr or _default_manager()
        self.act = self.mgr.start_activity(
            activity_type, name=name, agent_id=agent_id, input_refs=input_refs
        )

    def __enter__(self) -> ActivityRecord:
        return self.act

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is not None:
            self.mgr.finish_activity(self.act, status="failed", error=str(exc))
        else:
            self.mgr.finish_activity(self.act, status="completed")
        self.mgr.record_activity_bound(self.act)
        return False  # 不吞异常


_DEFAULT: Optional[ProvenanceManager] = None


def _default_manager() -> ProvenanceManager:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = ProvenanceManager()
    return _DEFAULT
