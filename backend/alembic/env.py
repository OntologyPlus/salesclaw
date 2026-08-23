"""Alembic 环境配置 - 单一库迁移（业务 + 本体共用）

设计要点
────────
1. **复用应用引擎**：不在 alembic.ini 里写死连接串，而是直接 import
   `database.business_engine`（= ontology_engine，第 14 批单库合并后
   ontology_engine 与 business_engine 是同一 Engine），保证迁移与运行时
   用的是同一套 DB_BACKEND/DB_PATH 配置（含 SQLite/PG 切换）。
2. **单一配置节 + 单一 metadata**：第 15 批起，仅保留 `[business]` 一个
   section，target_metadata 仅取 BusinessBase.metadata，因为：
     - psp.db 的 alembic_version 仍写 `0002_business`（历史审计）
     - ontology 10 张表已在 business 库存在，由 bootstrap/merge_ontology_to_business
       + database.run_migrations() 的 create_all 兜底维护；alembic 不主动接管
3. **SQLite 兼容**：SQLite 不支持大部分 ALTER，开启 `render_as_batch=True`
   让 Alembic 用「建新表→拷数据→改名」的 batch 模式执行变更。
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context

# 使 backend/ 根目录可被 import（database、config 等）
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import (  # noqa: E402
    BusinessBase, business_engine,
)

config = context.config

if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:
        pass

target_engine = business_engine
target_metadata = BusinessBase.metadata


def run_migrations_offline() -> None:
    """离线模式：仅生成 SQL，不连接 DB"""
    context.configure(
        url=str(target_engine.url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：复用应用已创建的 engine 执行迁移"""
    with target_engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite 无法直接 ALTER，用 batch 模式重建表
            render_as_batch=connection.dialect.name == "sqlite",
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
