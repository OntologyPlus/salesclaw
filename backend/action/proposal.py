"""ActionProposal — Agent 提议的受控写意图（尚未落库）。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class ActionProposal:
    action_type: str
    args: dict
    tenant_id: str = "default"
    user_id: Optional[int] = None
    target: str = ""
    risk_level: str = "L2"
    run_id: Optional[str] = None
    trace_id: Optional[str] = None
    session_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)
