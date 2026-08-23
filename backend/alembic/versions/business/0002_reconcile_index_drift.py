"""reconcile index drift from legacy _migrate_* patches

历史库由 main.py 的 30+ 个 `_migrate_*` 手写补丁演进而来，其中手工创建的索引
使用了 `idx_*` 命名，而 SQLAlchemy 模型声明的索引是 `ix_<table>_<col>` 命名。
两者指向同一批列，但名字不一致会让 Alembic autogenerate 持续报 drift。

本迁移把历史库对齐到 ORM 声明：
  - 删除历史遗留的 `idx_*` 重复索引
  - 补建 ORM 声明但历史库缺失的 `ix_*` 索引
  - 重建 `idx_insight_lookup`（列集合已变更，新增 period_end）
  - 清理已从模型移除的 `users.avatar` 列

全部操作幂等：空库（baseline 已按 ORM 建好索引）执行时自动跳过。

Revision ID: 0002_business
Revises: 0001_business
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002_business'
down_revision: Union[str, None] = '0001_business'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 历史遗留索引（手写迁移产物）-> 直接删除，由 ix_* 取代
_LEGACY_INDEXES = [
    ("ai_insight_cache", "idx_ai_insight_trace_id"),
    ("audit_logs", "idx_audit_logs_is_compliance_critical"),
    ("audit_logs", "idx_audit_logs_record_hash"),
    ("courses", "idx_courses_is_compliance"),
    ("decision_executions", "idx_decision_executions_reasoning_chain_id"),
    ("tasks", "idx_tasks_dedup_key"),
    ("visit_records", "idx_visit_records_is_academic_activity"),
    ("visit_records", "idx_visit_records_meeting_protocol_no"),
]

# ORM 声明的索引：(表, 索引名, [列])
_ORM_INDEXES = [
    ("ai_insight_cache", "ix_ai_insight_cache_trace_id", ["trace_id"]),
    ("audit_logs", "ix_audit_logs_is_compliance_critical", ["is_compliance_critical"]),
    ("audit_logs", "ix_audit_logs_record_hash", ["record_hash"]),
    ("courses", "ix_courses_is_compliance", ["is_compliance"]),
    ("decision_executions", "ix_decision_executions_reasoning_chain_id", ["reasoning_chain_id"]),
    ("diagnoses", "ix_diagnoses_confidence_band", ["confidence_band"]),
    ("diagnoses", "ix_diagnoses_excluded", ["excluded"]),
    ("practice_scenarios", "ix_practice_scenarios_doctor_id", ["doctor_id"]),
    ("practice_scenarios", "ix_practice_scenarios_hospital_id", ["hospital_id"]),
    ("practice_scenarios", "ix_practice_scenarios_persona_id", ["persona_id"]),
    ("practice_sessions", "ix_practice_sessions_activity_id", ["activity_id"]),
    ("tasks", "ix_tasks_closure_state", ["closure_state"]),
    ("tasks", "ix_tasks_dedup_key", ["dedup_key"]),
    ("visit_records", "ix_visit_records_is_academic_activity", ["is_academic_activity"]),
    ("visit_records", "ix_visit_records_meeting_protocol_no", ["meeting_protocol_no"]),
]

# 列集合发生变更、需重建的复合索引
_REBUILD_INDEXES = [
    (
        "ai_insight_cache",
        "idx_insight_lookup",
        ["tenant_id", "domain", "user_id", "insight_date", "period_end"],
    ),
]


def _inspector():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    insp = _inspector()
    tables = set(insp.get_table_names())

    def indexes_of(table: str) -> dict:
        return {i["name"]: i for i in insp.get_indexes(table)}

    # 1) 删除历史遗留的 idx_* 索引
    for table, idx in _LEGACY_INDEXES:
        if table in tables and idx in indexes_of(table):
            op.drop_index(idx, table_name=table)

    # 2) 补建 ORM 声明的 ix_* 索引
    insp = _inspector()
    for table, idx, cols in _ORM_INDEXES:
        if table not in tables:
            continue
        existing = {i["name"] for i in insp.get_indexes(table)}
        if idx in existing:
            continue
        table_cols = {c["name"] for c in insp.get_columns(table)}
        if not set(cols).issubset(table_cols):
            continue  # 列不存在（更早版本的库），跳过
        op.create_index(idx, table, cols, unique=False)

    # 3) 重建列集合变更的复合索引
    insp = _inspector()
    for table, idx, cols in _REBUILD_INDEXES:
        if table not in tables:
            continue
        current = {i["name"]: i for i in insp.get_indexes(table)}
        table_cols = {c["name"] for c in insp.get_columns(table)}
        if not set(cols).issubset(table_cols):
            continue
        if idx in current:
            if list(current[idx].get("column_names") or []) == cols:
                continue  # 已是目标列集合
            op.drop_index(idx, table_name=table)
        op.create_index(idx, table, cols, unique=False)

    # 4) 清理已从 ORM 模型移除的遗留列
    insp = _inspector()
    if "users" in tables:
        if "avatar" in {c["name"] for c in insp.get_columns("users")}:
            with op.batch_alter_table("users", schema=None) as batch_op:
                batch_op.drop_column("avatar")

    # 5) 列类型对齐：diagnoses.excluded_reason 手写迁移建为 TEXT，ORM 声明为 JSON
    #    （SQLite 底层同为 TEXT 存储，此处仅为消除 autogenerate drift）
    insp = _inspector()
    if "diagnoses" in tables:
        cols = {c["name"]: c for c in insp.get_columns("diagnoses")}
        col = cols.get("excluded_reason")
        if col is not None and not isinstance(col["type"], sa.JSON):
            with op.batch_alter_table("diagnoses", schema=None) as batch_op:
                batch_op.alter_column(
                    "excluded_reason",
                    existing_type=sa.TEXT(),
                    type_=sa.JSON(),
                    existing_nullable=True,
                )


def downgrade() -> None:
    """回退：恢复 users.avatar 并还原索引命名"""
    insp = _inspector()
    tables = set(insp.get_table_names())

    if "users" in tables:
        if "avatar" not in {c["name"] for c in insp.get_columns("users")}:
            with op.batch_alter_table("users", schema=None) as batch_op:
                batch_op.add_column(sa.Column("avatar", sa.String(length=256), nullable=True))

    insp = _inspector()
    for table, idx, _cols in _ORM_INDEXES:
        if table in tables and idx in {i["name"] for i in insp.get_indexes(table)}:
            op.drop_index(idx, table_name=table)

    insp = _inspector()
    for table, idx in _LEGACY_INDEXES:
        if table not in tables:
            continue
        if idx in {i["name"] for i in insp.get_indexes(table)}:
            continue
        # 由索引名反推列名：idx_<table>_<col> / idx_<col>
        col = idx.replace(f"idx_{table}_", "").replace("idx_", "")
        if col in {c["name"] for c in insp.get_columns(table)}:
            op.create_index(idx, table, [col], unique=False)
