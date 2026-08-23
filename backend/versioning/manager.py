"""本体版本管理器

职责：
    - capture()：对当前 ontology 定义做不可变快照（content_hash + 版本链 parent_hash）
    - restore()：把某版本定义喂回 ontology.registry（经 reload 钩子），实现「回放」
    - verify()：校验版本链完整性（任一版本内容被改都会断链）
    - list_versions()：时间线浏览（治理审计）
    - ancestors_of() / lca()：图查询（Neo4j 专属）

与 provenance 的区别：provenance 记录「处理步骤因果」，versioning 记录
「本体定义本身的版本演化」。两者互补，构成治理双轨（蓝图 §9.11）。

第 9 批：后端切换到 Neo4j（批次 13 共享 driver）。
第 14 批：Neo4j 是唯一主存。Neo4j 不可达 → 启动失败（fail-fast），
不再降级 SQLite（运营要求：必须保证 Neo4j 可用）。
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional

from config import settings

from .snapshot import OntologySnapshot

logger = logging.getLogger(__name__)


def _hash_definitions(objects: list, links: list, actions: list) -> str:
    """整组定义的内容哈希（规范化为稳定字符串）。"""
    payload = {
        "objects": objects,
        "links": links,
        "actions": actions,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _create_store():
    """工厂：固定 Neo4j 后端（fail-fast）。

    第 14 批：原 VERSIONING_STORE=auto|neo4j|sqlite 已删除，统一 Neo4j。
    Neo4j 不可达抛 RuntimeError，调用方应承担启动失败的语义。

    返回 (store, "neo4j") 元组（保留 tuple 形态以兼容旧 API 解析）。
    """
    from .neo4j_store import Neo4jVersionStore
    store = Neo4jVersionStore()  # Neo4j 不可达时直接抛错
    return store, "neo4j"


class VersionManager:
    """本体版本管理器（Neo4j 唯一后端）。"""

    def __init__(self):
        self._store, self._backend = _create_store()
        logger.info("VersionManager backend: %s", self._backend)

    @property
    def backend(self) -> str:
        return self._backend

    # ── 捕获 ──
    def capture(self, objects: list, links: list, actions: list,
                authored_by: str = None, note: str = None) -> OntologySnapshot:
        """对当前定义集做不可变快照，接入版本链。"""
        parent = self._store.latest() if hasattr(self._store, "latest") else None
        content_hash = _hash_definitions(objects, links, actions)
        snap = OntologySnapshot(
            parent_version=parent.version_id if parent else None,
            objects=objects, links=links, actions=actions,
            authored_by=authored_by, note=note,
            content_hash=content_hash,
            parent_hash=self._store.get_last_hash(),
        )
        self._store.append(snap)
        return snap

    # ── 恢复（回放）──
    def restore(self, version_id: str, apply_to_registry: bool = True) -> OntologySnapshot:
        """恢复某版本：返回快照，并可选喂回 ontology.registry 成为当前定义。"""
        snap = self._store.get(version_id)
        if snap is None:
            raise KeyError(f"版本不存在: {version_id}")
        if apply_to_registry:
            from ontology.registry import registry
            registry.apply_snapshot(snap.objects, snap.links, snap.actions)
        return snap

    # ── 校验 ──
    def verify(self) -> tuple[bool, int, int]:
        """校验版本链完整性（content_hash 应与存储内容一致 + parent 链连续）。"""
        versions = self._store.all()
        prev_hash = "GENESIS"
        for i, v in enumerate(versions):
            expected = _hash_definitions(v.objects, v.links, v.actions)
            if v.content_hash != expected:
                return False, i, len(versions)   # 内容被篡改
            if v.parent_hash != prev_hash:
                return False, i, len(versions)   # 版本链断裂
            prev_hash = v.content_hash
        return True, -1, len(versions)

    def get(self, version_id: str) -> Optional[OntologySnapshot]:
        return self._store.get(version_id)

    def latest(self) -> Optional[OntologySnapshot]:
        return self._store.latest()

    def list_versions(self) -> list[OntologySnapshot]:
        return self._store.all()

    # ── 图查询（Neo4j 专属，SQLite 降级为单链遍历）──
    def ancestors_of(self, version_id: str) -> list[str]:
        """返回从 version_id 沿 DERIVED_FROM 链向上的祖先 version_id 列表。"""
        if hasattr(self._store, "ancestors_of"):
            return self._store.ancestors_of(version_id)
        # SQLite fallback：按时间倒序查 + parent_version 字段
        result = [version_id]
        versions = {v.version_id: v for v in self._store.all()}
        cur = versions.get(version_id)
        while cur and cur.parent_version and cur.parent_version in versions:
            result.append(cur.parent_version)
            cur = versions[cur.parent_version]
        return result

    def lca(self, vid_a: str, vid_b: str) -> Optional[str]:
        """最近公共祖先。"""
        if hasattr(self._store, "lca"):
            return self._store.lca(vid_a, vid_b)
        # SQLite fallback：求两链交集的第一个
        a_chain = set(self.ancestors_of(vid_a))
        for v in self.ancestors_of(vid_b):
            if v in a_chain:
                return v
        return None

    def count(self) -> int:
        if hasattr(self._store, "count"):
            return self._store.count()
        return len(self._store.all())

    def close(self) -> None:
        if hasattr(self._store, "close"):
            self._store.close()
