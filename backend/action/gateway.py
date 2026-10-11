"""Action Gateway — 写工具唯一受控入口（幂等 + 账本）。

读工具直通；写工具（create_/update_/delete_/sync_* 等）经 Proposal→Command→Ledger。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Optional

from action.command import ActionCommand
from action.proposal import ActionProposal

logger = logging.getLogger(__name__)

# 写工具启发式：名称前缀 / 显式名单
_WRITE_PREFIXES = (
    "create_", "update_", "delete_", "remove_", "upsert_",
    "sync_", "merge_", "submit_", "publish_", "archive_",
    "cancel_", "approve_", "reject_", "dispatch_",
)

# 明确视为写的工具（即使不匹配前缀）
_WRITE_EXPLICIT = frozenset({
    "create_visit_record",
    "create_visit_plan",
    "create_visit_plan_record",
    "create_scene_record",
    "create_exam_record",
    "create_alert_disposition_record",
    "create_kol_record",
    "create_meeting_record",
    "create_report_record",
    "create_onboarding_record",
    "sync_visit_draft",
    "merge_visit_draft",
})

# 草稿类写操作风险较低
_DRAFT_TOOLS = frozenset({"sync_visit_draft", "merge_visit_draft"})


def is_write_tool(name: str) -> bool:
    if not name:
        return False
    if name in _WRITE_EXPLICIT:
        return True
    return any(name.startswith(p) for p in _WRITE_PREFIXES)


def _risk_for(name: str) -> str:
    if name in _DRAFT_TOOLS:
        return "L1"
    if name.startswith("create_") or name.startswith("delete_"):
        return "L3"
    return "L2"


class ActionGateway:
    """受控写入口。"""

    def dispatch_tool(
        self,
        name: str,
        args: dict,
        ctx: dict,
        tool_fn: Callable,
    ) -> Any:
        """执行工具：读直通；写走 Gateway。"""
        try:
            from config import settings
            gateway_on = bool(settings.AI_ENABLE_ACTION_GATEWAY)
        except Exception:
            gateway_on = True

        if not gateway_on or not is_write_tool(name):
            return tool_fn(args, ctx)

        db = ctx.get("db")
        tenant_id = str(ctx.get("tenant_id") or "default")
        user_id = ctx.get("user_id")
        try:
            user_id_int = int(user_id) if user_id is not None else None
        except Exception:
            user_id_int = None

        target = str(
            args.get("id")
            or args.get("plan_id")
            or args.get("record_id")
            or args.get("scenario_id")
            or ""
        )
        proposal = ActionProposal(
            action_type=name,
            args=args or {},
            tenant_id=tenant_id,
            user_id=user_id_int,
            target=target,
            risk_level=_risk_for(name),
            run_id=ctx.get("run_id"),
            trace_id=ctx.get("trace_id"),
            session_id=ctx.get("session_id"),
        )
        command = ActionCommand.from_proposal(proposal)
        return self.execute(command, tool_fn, ctx)

    def execute(
        self,
        command: ActionCommand,
        tool_fn: Callable,
        ctx: dict,
    ) -> Any:
        """查账本 → 命中则返回；否则执行并落账。"""
        from ai.otel_spans import span

        db = ctx.get("db")
        with span(
            "action.gateway",
            trace_id=command.trace_id,
            attributes={
                "action_type": command.action_type,
                "idempotency_key": command.idempotency_key[:16],
                "risk_level": command.risk_level,
            },
        ):
            cached = self._lookup_ledger(db, command.idempotency_key, command.tenant_id)
            if cached is not None:
                logger.info(
                    "[gateway] idempotent hit action=%s key=%s",
                    command.action_type, command.idempotency_key[:12],
                )
                result = cached.get("result")
                if isinstance(result, dict):
                    result = {**result, "idempotent_replay": True}
                return result

            ledger_id = self._insert_pending(db, command)
            try:
                result = tool_fn(command.args, ctx)
                self._complete(db, command, result, ledger_id)
                if isinstance(result, dict):
                    result = {**result, "gateway": True, "idempotency_key": command.idempotency_key}
                return result
            except Exception as e:
                self._fail(db, command, str(e), ledger_id)
                raise

    def _lookup_ledger(self, db, key: str, tenant_id: str) -> Optional[dict]:
        if db is None:
            return None
        try:
            from database import ActionLedger
            row = db.query(ActionLedger).filter(
                ActionLedger.idempotency_key == key,
                ActionLedger.tenant_id == str(tenant_id),
                ActionLedger.is_deleted == 0,
                ActionLedger.status == "completed",
            ).first()
            if not row:
                return None
            return {"result": row.result or {}, "status": row.status}
        except Exception as e:
            logger.debug("ledger lookup 失败: %s", e)
            return None

    def _insert_pending(self, db, command: ActionCommand) -> Optional[int]:
        if db is None:
            return None
        try:
            from database import ActionLedger
            # 并发下可能已有 pending/completed
            existing = db.query(ActionLedger).filter(
                ActionLedger.idempotency_key == command.idempotency_key,
            ).first()
            if existing:
                if existing.status == "completed":
                    return existing.id
                return existing.id
            row = ActionLedger(
                tenant_id=command.tenant_id,
                idempotency_key=command.idempotency_key,
                action_type=command.action_type,
                target=command.target or None,
                status="pending",
                proposal=command.proposal or {},
                command=command.to_dict(),
                result={},
                run_id=command.run_id,
                trace_id=command.trace_id,
                user_id=command.user_id,
            )
            db.add(row)
            db.commit()
            return row.id
        except Exception as e:
            logger.debug("ledger insert 失败: %s", e)
            try:
                db.rollback()
            except Exception:
                pass
            return None

    def _complete(self, db, command: ActionCommand, result: Any, ledger_id: Optional[int]) -> None:
        if db is None:
            return
        try:
            from database import ActionLedger
            row = None
            if ledger_id:
                row = db.query(ActionLedger).filter(ActionLedger.id == ledger_id).first()
            if not row:
                row = db.query(ActionLedger).filter(
                    ActionLedger.idempotency_key == command.idempotency_key,
                ).first()
            if not row:
                return
            # 序列化结果
            if not isinstance(result, dict):
                result = {"value": result}
            row.status = "completed"
            row.result = result
            row.executed_at = datetime.utcnow()
            db.commit()
        except Exception as e:
            logger.debug("ledger complete 失败: %s", e)
            try:
                db.rollback()
            except Exception:
                pass

    def _fail(self, db, command: ActionCommand, error: str, ledger_id: Optional[int]) -> None:
        if db is None:
            return
        try:
            from database import ActionLedger
            row = None
            if ledger_id:
                row = db.query(ActionLedger).filter(ActionLedger.id == ledger_id).first()
            if not row:
                row = db.query(ActionLedger).filter(
                    ActionLedger.idempotency_key == command.idempotency_key,
                ).first()
            if not row:
                return
            row.status = "failed"
            row.error_message = error[:2000]
            row.executed_at = datetime.utcnow()
            db.commit()
        except Exception as e:
            logger.debug("ledger fail 失败: %s", e)
            try:
                db.rollback()
            except Exception:
                pass


action_gateway = ActionGateway()

__all__ = ["ActionGateway", "action_gateway", "is_write_tool"]
