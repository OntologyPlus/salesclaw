"""governance 子包数据模型。

第 16 批：原 review.py 同时承载 SQLite CandidateStore 与 Candidate 数据类；
合并库（含 Neo4j 唯一主存）后，仅 Candidate 数据类仍被 Neo4j 路径消费，
CandidateStore 类已无任何调用方，故将模型与实现彻底分家：

    models.py    ←── Candidate（活，单点）
    neo4j_store.py    ←── Neo4jCandidateStore + _row_to_candidate（活）
    reflow.py         ←── reflow_approved（活）
    bridge.py / gate.py        ←── 活

"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Candidate:
    """候选审核模型（与 Neo4j ReviewCandidate 节点字段 1:1 对应）。"""
    candidate_id: str
    kind: str            # "entity" | "relation"
    payload: dict
    status: str = "pending"
    decided_by: Optional[str] = None
    decided_at: Optional[str] = None
    note: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "kind": self.kind,
            "payload": self.payload,
            "status": self.status,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at,
            "note": self.note,
        }


__all__ = ["Candidate", "now_iso"]
