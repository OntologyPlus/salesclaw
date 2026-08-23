"""溯源完整性

设计目标：溯源记录一旦写入不可被静默篡改。
实现方式：每条 ProvenanceEntry 携带 ``prev_hash``（上一条 entry 的哈希），
        自身 ``entry_hash`` = sha256(prev_hash || 规范化内容)；
        首尾相连形成「哈希链」，verify 时重算并比对，任一节点被改都会断链。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from .schemas import ProvenanceEntry


def _canonical(entry: ProvenanceEntry) -> str:
    """把一条 entry 规范化为稳定字符串（排除自身 entry_hash，避免自引用）。"""
    payload = {
        "entry_id": entry.entry_id,
        "activity_id": entry.activity_id,
        "entity_id": entry.entity_id,
        "entity_type": entry.entity_type,
        "action": entry.action,
        "agent_id": entry.agent_id,
        "source": entry.source.to_dict() if entry.source else None,
        "data_hash": entry.data_hash,
        "occurred_at": entry.occurred_at.isoformat() if entry.occurred_at else None,
        "prev_hash": entry.prev_hash,
        "properties": entry.properties,
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)


def compute_entry_hash(entry: ProvenanceEntry) -> str:
    """计算单条 entry 的哈希（含 prev_hash）。"""
    return hashlib.sha256(_canonical(entry).encode("utf-8")).hexdigest()


def chain_hash(prev_hash: str, entry: ProvenanceEntry) -> str:
    """基于前驱哈希计算本 entry 哈希（显式传入 prev_hash，便于重算校验）。"""
    entry.prev_hash = prev_hash
    return compute_entry_hash(entry)


def compute_data_hash(data: Any) -> str:
    """对任意内容计算 sha256（用于 ProvenanceEntry.data_hash）。"""
    if isinstance(data, (dict, list)):
        data = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    elif not isinstance(data, str):
        data = str(data)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def verify_chain(entries: list[ProvenanceEntry], genesis: str = "GENESIS") -> tuple[bool, int]:
    """校验哈希链连续性。

    Args:
        entries: 按写入顺序（时间升序）排列的 entry 列表
        genesis: 链首期望的 prev_hash

    Returns:
        (ok, broken_at_index)：ok 为 False 时 broken_at_index 指出首个断点
    """
    prev = genesis
    for i, e in enumerate(entries):
        expected = chain_hash(prev, e)
        if e.entry_hash != expected:
            return False, i
        prev = e.entry_hash
    return True, -1


def verify_entry(entry: ProvenanceEntry, prev_hash: Optional[str] = None) -> bool:
    """校验单条 entry 的哈希（给定前驱哈希）。"""
    expected = chain_hash(prev_hash if prev_hash is not None else entry.prev_hash, entry)
    return entry.entry_hash == expected
