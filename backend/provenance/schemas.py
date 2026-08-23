"""溯源数据模型

本模块定义一套与业务无关的「技术级全链路溯源」模型，记录一次处理
（文档摄入、文本切分、实体抽取、推理、导出……）中：

    - 谁（Agent）：人 / 服务 / LLM provider
    - 做了什么（Activity）：带起止时间的处理步骤
    - 产生了什么（Entity）：输入 / 输出 / 中间产物
    - 来源关系（wasGeneratedBy / wasDerivedFrom / wasAttributedTo）

与 services/data_lineage_service.py 的区别：
    data_lineage 记录「业务实体间流动」（collection→ability_profile），
    本模块记录「处理步骤的因果与完整性」（doc→chunk→triplet→insight），
    两者互补，不重复。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class AgentRecord:
    """溯源主体（PROV: Agent）——执行活动的实体。"""

    agent_id: str = field(default_factory=lambda: f"agent:{uuid4().hex[:8]}")
    agent_type: str = "service"           # service | user | llm | system
    name: Optional[str] = None
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "name": self.name,
            "properties": self.properties,
        }


@dataclass
class ActivityRecord:
    """溯源活动（PROV: Activity）——一次处理步骤。"""

    activity_id: str = field(default_factory=lambda: f"act:{uuid4().hex[:8]}")
    activity_type: str = "process"        # ingest | split | extract | reason | export
    name: Optional[str] = None
    started_at: datetime = field(default_factory=_now)
    ended_at: Optional[datetime] = None
    status: str = "running"               # running | completed | failed
    input_refs: list[str] = field(default_factory=list)
    output_refs: list[str] = field(default_factory=list)
    agent_id: Optional[str] = None
    error: Optional[str] = None
    properties: dict[str, Any] = field(default_factory=dict)

    def finish(self, status: str = "completed", error: Optional[str] = None) -> None:
        self.ended_at = _now()
        self.status = status
        self.error = error

    def to_dict(self) -> dict:
        return {
            "activity_id": self.activity_id,
            "activity_type": self.activity_type,
            "name": self.name,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "status": self.status,
            "input_refs": self.input_refs,
            "output_refs": self.output_refs,
            "agent_id": self.agent_id,
            "error": self.error,
            "properties": self.properties,
        }


@dataclass
class SourceReference:
    """来源引用——一个实体源自哪份原始输入。"""

    source_type: str                      # file | url | db | api | llm_prompt
    uri: str
    title: Optional[str] = None
    mime_type: Optional[str] = None
    version: Optional[str] = None
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source_type": self.source_type,
            "uri": self.uri,
            "title": self.title,
            "mime_type": self.mime_type,
            "version": self.version,
            "properties": self.properties,
        }


@dataclass
class ProvenanceEntry:
    """一条溯源条目（PROV: Entity 的载体）——一次写入的不可变记录。

    每条 entry 携带``prev_hash`` 与自身 ``entry_hash``，形成防篡改链。
    """

    entry_id: str = field(default_factory=lambda: f"prov:{uuid4().hex}")
    activity_id: Optional[str] = None
    entity_id: Optional[str] = None       # 被记录的产物 ID（chunk/triplet/insight...）
    entity_type: Optional[str] = None
    action: str = "generated"             # generated | derived | attributed | invalidated
    agent_id: Optional[str] = None
    source: Optional[SourceReference] = None
    data_hash: Optional[str] = None       # 被记录产物的内容哈希（sha256）
    occurred_at: datetime = field(default_factory=_now)
    prev_hash: str = "GENESIS"
    entry_hash: str = ""
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "activity_id": self.activity_id,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "action": self.action,
            "agent_id": self.agent_id,
            "source": self.source.to_dict() if self.source else None,
            "data_hash": self.data_hash,
            "occurred_at": self.occurred_at.isoformat(),
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash,
            "properties": self.properties,
        }
