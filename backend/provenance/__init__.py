"""provenance —— 技术级全链路溯源子包

与 services/data_lineage_service.py（业务实体级血缘）互补：
    - data_lineage：业务实体间流动（collection → ability_profile）
    - provenance ：处理步骤的因果与完整性（doc → chunk → triplet → insight）

第 9 批：后端切换到 Neo4j。
第 13 批：共享 Neo4jConnectionManager。
第 14 批：Neo4j 唯一主存；删 SQLiteStorage（SQLite 旧实现）。
"""
from .integrity import (
    chain_hash,
    compute_data_hash,
    verify_chain,
    verify_entry,
)
from .manager import ProvenanceManager, track
from .schemas import (
    ActivityRecord,
    AgentRecord,
    ProvenanceEntry,
    SourceReference,
)
from .neo4j_storage import Neo4jProvenanceStorage

__all__ = [
    "ProvenanceManager",
    "track",
    "ActivityRecord",
    "AgentRecord",
    "ProvenanceEntry",
    "SourceReference",
    "Neo4jProvenanceStorage",
    "chain_hash",
    "compute_data_hash",
    "verify_chain",
    "verify_entry",
]
