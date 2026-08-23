"""本体版本快照模型 —— 「版本化 + checksum 审计」

本模块为 ontology 定义（OBJECTS/LINKS/ACTIONS）提供不可变版本快照，
与 ontology/registry.py 的「运行时权威源 + reload()」解耦：
    - registry.reload() 从 DB/seed 热加载当前定义
    - versioning 记录「哪一组定义对应哪个版本号」，支持回放与完整性校验
    - restore(version_id) 把该版本的定义喂回 registry（经 reload 钩子）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class OntologySnapshot:
    """一次本体定义的不可变快照。"""

    version_id: str = field(default_factory=lambda: f"v{uuid4().hex[:8]}")
    parent_version: Optional[str] = None
    objects: list[dict] = field(default_factory=list)
    links: list[dict] = field(default_factory=list)
    actions: list[dict] = field(default_factory=list)
    authored_by: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime = field(default_factory=_now)
    content_hash: str = ""            # 整组定义的 sha256（防篡改）
    parent_hash: str = "GENESIS"       # 版本链前驱（类似 provenance 的 hash-chain）

    def to_dict(self) -> dict:
        return {
            "version_id": self.version_id,
            "parent_version": self.parent_version,
            "objects": self.objects,
            "links": self.links,
            "actions": self.actions,
            "authored_by": self.authored_by,
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "content_hash": self.content_hash,
            "parent_hash": self.parent_hash,
        }
