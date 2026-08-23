"""本体初始化 - seed 基线落库 + 加载运行时缓存 + OBAC 覆盖校验

本体已 DB 化：`psp_ontology.db` 是运行时权威源，`ontology/*.py` 降级为 seed 声明。
启动流程：
    1. sync_ontology_to_orm()  把 seed 基线 upsert 进 DB（仅 tenant_id IS NULL 的行）
    2. registry.reload()       从 DB 加载到进程内缓存（sync 内部已触发，此处兜底）
    3. 覆盖校验                检查本体实体是否都在 OBAC 权限矩阵中声明
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def sync_ontology_baseline() -> dict:
    """把 ontology/*.py 的 seed 声明同步进本体表，并刷新运行时缓存"""
    from database import sync_ontology_to_orm

    stats = sync_ontology_to_orm()
    logger.info("[ontology] seed→DB 同步完成：%s", stats)
    return stats


def load_registry() -> dict:
    """确保本体注册表已从 DB 加载（兜底：sync 失败时也要有可用缓存）"""
    from ontology.registry import registry

    stats = registry.load(force=True)
    if stats.get("source") != "db":
        logger.warning(
            "[ontology] 运行时权威源降级为 seed 常量（DB 未就绪或为空）：%s", stats
        )
    return stats


def sync_permissions_baseline() -> dict:
    """把内置权限矩阵 seed 进 DB，并加载权限注册表缓存"""
    from ontology.permission_registry import seed_permissions_to_db

    stats = seed_permissions_to_db()
    logger.info("[permissions] seed→DB 同步完成：%s", stats)
    return stats


def check_obac_coverage() -> dict:
    """校验本体实体与 OBAC 权限矩阵的覆盖一致性"""
    from ontology import list_objects
    from ontology.permissions import check_object_permission_coverage

    cov = check_object_permission_coverage([o["name"] for o in list_objects()])
    missing = cov.get("missing_in_obac") or []
    if missing:
        logger.warning(
            "[ontology] %d 个实体未在 OBAC 权限矩阵声明：%s", len(missing), missing
        )
    else:
        logger.info(
            "[ontology] OBAC 覆盖对齐：%s/%s 实体已声明",
            cov.get("covered"), cov.get("total"),
        )
    return cov


def init_ontology() -> dict:
    """本体初始化编排。任一步失败都不阻断启动（本体是只读元数据）。"""
    result: dict[str, object] = {}
    for key, fn in (
        ("sync", sync_ontology_baseline),
        ("registry", load_registry),
        ("permissions", sync_permissions_baseline),
        ("obac_coverage", check_obac_coverage),
    ):
        try:
            result[key] = fn()
        except Exception as e:
            result[key] = f"failed: {e}"
            logger.warning("[ontology] %s 步骤跳过（不影响启动）：%s", key, e)
    return result
