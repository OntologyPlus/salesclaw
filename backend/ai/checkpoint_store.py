"""Phase B：AiAgentRun checkpoint 持久化与续跑加载。"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


def new_run_id() -> str:
    return str(uuid.uuid4())


def begin_run(
    db,
    *,
    tenant_id: str,
    session_id: Optional[str] = None,
    user_id: Any = None,
    intent: str = "",
    agent_name: str = "",
    skill_name: Optional[str] = None,
    max_rounds: int = 3,
    budget: Optional[dict] = None,
    trace_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Optional[str]:
    """创建 running 状态的 run，返回 run_id。db 不可用时返回 None。"""
    if db is None:
        return None
    try:
        from config import settings
        if not settings.AI_ENABLE_RUN_CHECKPOINT:
            return None
        from database import AiAgentRun

        rid = run_id or new_run_id()
        row = AiAgentRun(
            tenant_id=str(tenant_id or "default"),
            run_id=rid,
            session_id=session_id,
            user_id=int(user_id) if user_id is not None else None,
            intent=intent or None,
            agent_name=agent_name or None,
            skill_name=skill_name,
            status="running",
            cursor_round=0,
            max_rounds=max_rounds,
            messages=[],
            tools_used=[],
            budget=budget or {},
            trace_id=trace_id,
            started_at=datetime.utcnow(),
            updated_run_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        return rid
    except Exception as e:
        logger.warning("checkpoint begin_run 失败: %s", e, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        return None


def save_checkpoint(
    db,
    run_id: Optional[str],
    *,
    cursor_round: int,
    messages: list,
    tools_used: list,
    last_content: str = "",
    status: str = "running",
    error_message: Optional[str] = None,
) -> None:
    if db is None or not run_id:
        return
    try:
        from config import settings
        if not settings.AI_ENABLE_RUN_CHECKPOINT:
            return
        from database import AiAgentRun

        row = db.query(AiAgentRun).filter(
            AiAgentRun.run_id == run_id,
            AiAgentRun.is_deleted == 0,
        ).first()
        if not row:
            return
        row.cursor_round = cursor_round
        # 截断过大消息，避免 JSON 膨胀
        row.messages = _trim_messages(messages)
        row.tools_used = _trim_tools(tools_used)
        row.last_content = (last_content or "")[:4000]
        row.status = status
        if error_message:
            row.error_message = error_message[:2000]
        row.updated_run_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        logger.debug("checkpoint save 失败: %s", e, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass


def finish_run(
    db,
    run_id: Optional[str],
    *,
    status: str = "completed",
    last_content: str = "",
    error_message: Optional[str] = None,
) -> None:
    if db is None or not run_id:
        return
    try:
        from database import AiAgentRun
        row = db.query(AiAgentRun).filter(AiAgentRun.run_id == run_id).first()
        if not row:
            return
        row.status = status
        if last_content:
            row.last_content = last_content[:4000]
        if error_message:
            row.error_message = error_message[:2000]
        row.updated_run_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        logger.debug("checkpoint finish 失败: %s", e)
        try:
            db.rollback()
        except Exception:
            pass


def load_run(db, run_id: str, tenant_id: Optional[str] = None) -> Optional[dict]:
    if db is None or not run_id:
        return None
    try:
        from database import AiAgentRun
        q = db.query(AiAgentRun).filter(
            AiAgentRun.run_id == run_id,
            AiAgentRun.is_deleted == 0,
        )
        if tenant_id:
            q = q.filter(AiAgentRun.tenant_id == str(tenant_id))
        row = q.first()
        if not row:
            return None
        return {
            "run_id": row.run_id,
            "session_id": row.session_id,
            "tenant_id": row.tenant_id,
            "user_id": row.user_id,
            "intent": row.intent,
            "agent_name": row.agent_name,
            "skill_name": row.skill_name,
            "status": row.status,
            "cursor_round": row.cursor_round or 0,
            "max_rounds": row.max_rounds or 3,
            "messages": row.messages or [],
            "tools_used": row.tools_used or [],
            "last_content": row.last_content or "",
            "budget": row.budget or {},
            "trace_id": row.trace_id,
            "error_message": row.error_message,
        }
    except Exception as e:
        logger.warning("checkpoint load 失败: %s", e)
        return None


def list_runs(
    db, *, tenant_id: str, session_id: Optional[str] = None, limit: int = 20
) -> list[dict]:
    if db is None:
        return []
    try:
        from database import AiAgentRun
        q = db.query(AiAgentRun).filter(
            AiAgentRun.tenant_id == str(tenant_id),
            AiAgentRun.is_deleted == 0,
        )
        if session_id:
            q = q.filter(AiAgentRun.session_id == session_id)
        rows = q.order_by(AiAgentRun.updated_run_at.desc()).limit(limit).all()
        return [
            {
                "run_id": r.run_id,
                "session_id": r.session_id,
                "status": r.status,
                "intent": r.intent,
                "agent_name": r.agent_name,
                "cursor_round": r.cursor_round,
                "max_rounds": r.max_rounds,
                "trace_id": r.trace_id,
                "updated_run_at": r.updated_run_at.isoformat() if r.updated_run_at else None,
            }
            for r in rows
        ]
    except Exception as e:
        logger.debug("list_runs 失败: %s", e)
        return []


def _trim_messages(messages: list, max_items: int = 40, max_chars: int = 4000) -> list:
    out = []
    for m in (messages or [])[-max_items:]:
        if not isinstance(m, dict):
            continue
        content = m.get("content", "")
        if isinstance(content, str) and len(content) > max_chars:
            content = content[:max_chars] + "...(truncated)"
        item = {"role": m.get("role", "user"), "content": content}
        if m.get("tool_calls"):
            item["tool_calls"] = m["tool_calls"]
        if m.get("tool_call_id"):
            item["tool_call_id"] = m["tool_call_id"]
        out.append(item)
    return out


def _trim_tools(tools_used: list, max_items: int = 30) -> list:
    out = []
    for t in (tools_used or [])[-max_items:]:
        if not isinstance(t, dict):
            continue
        result = t.get("result")
        if isinstance(result, (dict, list)):
            import json
            s = json.dumps(result, ensure_ascii=False, default=str)
            if len(s) > 1500:
                result = {"_truncated": s[:1500]}
        out.append({
            "name": t.get("name"),
            "args": t.get("args"),
            "result": result,
            "error": t.get("error"),
        })
    return out


__all__ = [
    "new_run_id", "begin_run", "save_checkpoint", "finish_run",
    "load_run", "list_runs",
]
