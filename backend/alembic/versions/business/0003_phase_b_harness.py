"""Phase B harness: ai_agent_runs + action_ledgers

Revision ID: 0003_business
Revises: 0002_business
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_business"
down_revision: Union[str, None] = "0002_business"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_agent_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("is_deleted", sa.Integer(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("intent", sa.String(length=64), nullable=True),
        sa.Column("agent_name", sa.String(length=64), nullable=True),
        sa.Column("skill_name", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("cursor_round", sa.Integer(), nullable=True),
        sa.Column("max_rounds", sa.Integer(), nullable=True),
        sa.Column("messages", sa.JSON(), nullable=True),
        sa.Column("tools_used", sa.JSON(), nullable=True),
        sa.Column("last_content", sa.Text(), nullable=True),
        sa.Column("budget", sa.JSON(), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("updated_run_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index("ix_ai_agent_runs_tenant_id", "ai_agent_runs", ["tenant_id"])
    op.create_index("ix_ai_agent_runs_is_deleted", "ai_agent_runs", ["is_deleted"])
    op.create_index("ix_ai_agent_runs_run_id", "ai_agent_runs", ["run_id"])
    op.create_index("ix_ai_agent_runs_session_id", "ai_agent_runs", ["session_id"])
    op.create_index("ix_ai_agent_runs_user_id", "ai_agent_runs", ["user_id"])
    op.create_index("ix_ai_agent_runs_status", "ai_agent_runs", ["status"])
    op.create_index("ix_ai_agent_runs_trace_id", "ai_agent_runs", ["trace_id"])

    op.create_table(
        "action_ledgers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("is_deleted", sa.Integer(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("action_type", sa.String(length=128), nullable=False),
        sa.Column("target", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("proposal", sa.JSON(), nullable=True),
        sa.Column("command", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("run_id", sa.String(length=64), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_action_ledgers_tenant_id", "action_ledgers", ["tenant_id"])
    op.create_index("ix_action_ledgers_is_deleted", "action_ledgers", ["is_deleted"])
    op.create_index("ix_action_ledgers_idempotency_key", "action_ledgers", ["idempotency_key"])
    op.create_index("ix_action_ledgers_action_type", "action_ledgers", ["action_type"])
    op.create_index("ix_action_ledgers_status", "action_ledgers", ["status"])
    op.create_index("ix_action_ledgers_run_id", "action_ledgers", ["run_id"])
    op.create_index("ix_action_ledgers_trace_id", "action_ledgers", ["trace_id"])


def downgrade() -> None:
    op.drop_table("action_ledgers")
    op.drop_table("ai_agent_runs")
