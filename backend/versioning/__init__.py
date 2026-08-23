"""versioning —— 本体版本化管理子包

为 ontology 定义（OBJECTS/LINKS/ACTIONS）提供不可变版本快照 + 校验和 + 回放，
与 ontology/registry（运行时权威源 + reload）解耦，构成治理双轨（蓝图 §9.11）。

第 9 批：后端切换到 Neo4j。
第 13 批：共享 Neo4jConnectionManager。
第 14 批：Neo4j 唯一主存；删 VersionStore（SQLite 旧实现）。

导出：
    - VersionManager：capture / restore / verify / list_versions / ancestors_of / lca
    - OntologySnapshot：快照模型
    - Neo4jVersionStore：Neo4j 后端（唯一可用）
"""
from .manager import VersionManager
from .snapshot import OntologySnapshot
from .neo4j_store import Neo4jVersionStore

__all__ = [
    "VersionManager",
    "OntologySnapshot",
    "Neo4jVersionStore",
]
