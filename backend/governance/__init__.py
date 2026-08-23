"""governance —— 候选审核治理子包。

候选审核库（entities / relations 候选项）原本是 SQLite 存储（batch 7），
第 11 批迁到 Neo4j，候选 ↔ 已落图 Entity 的关系化查询能力显著提升。
第 13 批：共享 Neo4jConnectionManager。
第 14 批：Neo4j 唯一主存，删除 SQLite 回退（GOVERNANCE_STORE 字段不再存在）。

导出：
    - create_candidate_store: 工厂入口（固定 Neo4j 后端，fail-fast）
    - Candidate: 候选模型
    - CandidateStore: 历史 SQLite 类（保留，仅测试/迁移参考；工厂不调度）
    - Neo4jCandidateStore: Neo4j 后端（唯一可用）
    - ActionGate: 行动门控（与 logic.executor 解耦，第 7 批）
    - reflow_approved: 把 approved 候选自动落库（第 7 批）
    - bridge: 跨 4 子系统 Cypher 桥接
"""
from .bridge import (
    activity_subgraph_extended,
    agent_audit,
    candidate_to_ontology,
    entity_story,
    system_snapshot,
)
from .gate import ActionGate
from .models import Candidate
from .neo4j_store import Neo4jCandidateStore


def create_candidate_store():
    """创建候选审核存储。

    第 14 批：固定 Neo4j 后端，返回 (store, "neo4j") 元组（形态兼容旧调用）。
    Neo4j 不可达时由 Neo4jCandidateStore 构造直接抛错（fail-fast）。
    """
    return Neo4jCandidateStore(), "neo4j"


# 兼容导出（旧测试 / 迁移参考）
try:
    from . import reflow as _reflow  # noqa: F401
    reflow_approved = _reflow.reflow_approved
except Exception:  # pragma: no cover
    reflow_approved = None


__all__ = [
    "create_candidate_store",
    "Candidate",
    "Neo4jCandidateStore",
    "ActionGate",
    "reflow_approved",
    "entity_story",
    "agent_audit",
    "candidate_to_ontology",
    "activity_subgraph_extended",
    "system_snapshot",
]
