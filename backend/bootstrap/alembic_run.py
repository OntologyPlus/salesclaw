"""Alembic 迁移执行器 - 启动时把单库升级到 head

第 15 批：业务库与本体库共用同一物理库（database.business_engine =
database.ontology_engine），Alembic 仅保留单一 tree：
    business -> psp.db  (alembic/versions/business)

第 14 批前历史：
    原 ontology 树（alembic/versions/ontology/）已被迁移数据后删除；
    原 ontology DB（psp_ontology.db）已经迁入 psp.db 后归档；
    原 [ontology] alembic.ini section 已删除。
    业务/本体表的 schema 定义统一进 business tree。
"""
from __future__ import annotations

import logging
import os
from typing import Iterable

logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALEMBIC_INI = os.path.join(BACKEND_DIR, "alembic.ini")

# 第 15 批：单一库 + 单一升级目标
PRIMARY_SECTION = "business"


def _make_config(section: str):
    """构造指定配置节的 Alembic Config"""
    from alembic.config import Config

    cfg = Config(ALEMBIC_INI, ini_section=section)
    # script_location 在 ini 里是相对路径，转成绝对路径避免受 CWD 影响
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    version_locations = cfg.get_main_option("version_locations")
    if version_locations:
        cfg.set_main_option(
            "version_locations",
            os.path.join(BACKEND_DIR, version_locations),
        )
    return cfg


def upgrade_to_head(sections: Iterable[str] | None = None) -> dict:
    """将单库升级到 head。

    幂等：已应用的版本会被跳过；失败不抛出，仅记录，避免因迁移问题导致
    整个服务无法启动（与既有「跳过不影响启动」的风格保持一致）。

    第 15 批：仅升级 business tree；sections 参数保留仅为兼容旧调用，
    但仅传 'business' 时才有意义。
    """
    from alembic import command

    results: dict[str, str] = {}
    targets = set(sections) if sections else {PRIMARY_SECTION}

    if "business" in targets:
        try:
            cfg = _make_config("business")
            command.upgrade(cfg, "head")
            results["business"] = "ok"
            logger.info("[alembic] 单库（业务 + 本体）已升级至 head")
        except Exception as e:
            results["business"] = f"failed: {e}"
            logger.error("[alembic] 业务库迁移失败: %s", e, exc_info=True)

    return results


def current_revisions() -> dict:
    """读取当前迁移版本（用于健康检查/诊断）

    第 15 批：仅查询单一库的 alembic_version 行；返回 dict 仅含 'business'
    一项。旧 'ontology'/'business' 双 key 调用方请迁到单 key。
    """
    from alembic.runtime.migration import MigrationContext

    from database import business_engine

    try:
        with business_engine.connect() as conn:
            rev = MigrationContext.configure(conn).get_current_revision()
    except Exception as e:
        return {"business": f"unknown: {e}"}

    return {"business": rev}
