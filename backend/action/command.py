"""ActionCommand — 带幂等键的可执行命令。"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional

from action.proposal import ActionProposal


@dataclass
class ActionCommand:
    action_type: str
    args: dict
    idempotency_key: str
    tenant_id: str = "default"
    user_id: Optional[int] = None
    target: str = ""
    risk_level: str = "L2"
    run_id: Optional[str] = None
    trace_id: Optional[str] = None
    proposal: Optional[dict] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_proposal(cls, proposal: ActionProposal) -> "ActionCommand":
        key = compute_idempotency_key(
            action_type=proposal.action_type,
            target=proposal.target or "",
            args=proposal.args,
            tenant_id=proposal.tenant_id,
            user_id=proposal.user_id,
        )
        return cls(
            action_type=proposal.action_type,
            args=proposal.args,
            idempotency_key=key,
            tenant_id=proposal.tenant_id,
            user_id=proposal.user_id,
            target=proposal.target,
            risk_level=proposal.risk_level,
            run_id=proposal.run_id,
            trace_id=proposal.trace_id,
            proposal=proposal.to_dict(),
        )


def compute_idempotency_key(
    *,
    action_type: str,
    target: str,
    args: dict,
    tenant_id: str,
    user_id: Optional[int],
) -> str:
    """sha256(action_type, target, tenant, user, canonical args)。"""
    try:
        payload = json.dumps(args or {}, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        payload = str(args)
    raw = f"{tenant_id}|{user_id}|{action_type}|{target}|{payload}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
