"""bootstrap —— 启动期一次性任务（哈希链恢复、清理等）。

供 main.py lifespan startup 调用，按顺序执行：
    1. settings.ensure_dirs() — 业务/向量库目录
    2. require_neo4j() — fail-fast：连不上立刻抛错（运营要求 Neo4j 必须可用）
    3. database.init_db() — 业务库 + 本体库 schema 兜底（同引擎，同一物理库）+ 种子
    4. alembic 已升级到 head（main.py 显式调 upgrade_to_head）

主入口 `run_startup()` 与 `bootstrap_all()`，返回 summary dict（与旧 API 兼容）。
"""
from __future__ import annotations

import logging

from core.neo4j_driver import Neo4jConnectionManager

logger = logging.getLogger(__name__)


def require_neo4j() -> None:
    """启动期 Neo4j 可达性硬探测（fail-fast）。

    第 14 批：必须保证 Neo4j 可用。原「连接失败 → 回退 SQLite/内存 LightGraph」
    的语义已删除。Neo4j 不可达时抛 RuntimeError，让进程退出 / 容器重启。

    实现复用 Neo4jConnectionManager.latency_probe()，与 /health/neo4j 端点
    使用同一个探针（一致性原则）。
    """
    probe = Neo4jConnectionManager.latency_probe()
    if not probe["ok"]:
        raise RuntimeError(
            f"[bootstrap] Neo4j 不可达，第 14 批要求强制使用 Neo4j，"
            f"延迟探测失败：{probe['error']}"
        )
    logger.info(
        "[bootstrap] Neo4j 已连通（latency=%.2fms）",
        probe["latency_ms"] or 0.0,
    )


def bootstrap_all() -> dict:
    """启动期主线流程。

    抛错由 main.py 捕获并处理（一般是让 uvicorn / gunicorn 退出并由容器重启）。

    Returns:
        dict：summary，键值由 main.py 日志消费
    """
    from config import settings
    from bootstrap.alembic_run import upgrade_to_head, current_revisions

    summary: dict = {}

    # 0) 业务/向量库目录
    settings.ensure_dirs()
    summary["dirs"] = "ok"

    # 1) 硬探测 Neo4j，连不上绝不启动
    require_neo4j()
    summary["neo4j"] = Neo4jConnectionManager.init_info()

    # 2) 业务库 + 本体库 schema 兜底（共引擎），alembic 已升级到 head（主流程见下）
    from database import init_db
    init_db()
    summary["db"] = "ok"

    # 3) alembic 升级（单一 tree：business）
    summary["alembic"] = upgrade_to_head()
    summary["revisions"] = current_revisions()

    # 4) B 路径：培训效果归因滞后调度器（培训完成后 30d/180d 回填）
    try:
        from services.lag_scheduler import start_lag_scheduler
        from database import BusinessSessionLocal
        sch = start_lag_scheduler(BusinessSessionLocal)
        summary["lag_scheduler"] = "started"
    except Exception as exc:
        logger.warning("[bootstrap] lag_scheduler 启动失败（非阻塞）: %s", exc)
        summary["lag_scheduler"] = f"failed: {exc}"

    return summary


# 兼容旧入口（main.py 调用）
def run_startup() -> dict:
    """main.py lifespan 的旧入口（保持向后兼容）。"""
    return bootstrap_all()


def register_shutdown() -> None:
    """主程序退出时调用一次。

    旧 bootstrap 入口曾用此名。第 14 批：直接关闭 Neo4j 共享 driver 即可。
    """
    Neo4jConnectionManager.close_all()
