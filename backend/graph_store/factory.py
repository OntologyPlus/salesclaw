"""图存储工厂 —— 第 14 批：Neo4j 唯一主存。

第 8 批历史：原 factory 依据 NEO4J_ENABLED 自动选择 Neo4jGraphStore 或
内存 LightGraph（语义图快速迭代 + 零依赖跑 demo）。
第 13 批：4 store 共享 Neo4jConnectionManager 单 driver。
第 14 批：运营要求 Neo4j 必须可用，删除 LightGraph 生产路径。
        保留 LightGraph 类仅用于本地单测（in-memory 图断言）。

设计：
    - 生产路径：create_graph_store() 直接返回 Neo4jGraphStore 单例
    - 测试路径：测试代码可显式 from .light_graph import LightGraph 自构造
"""
from __future__ import annotations

import logging
import threading

from config import settings

logger = logging.getLogger(__name__)

# 第 13 批：进程内共享 Neo4jGraphStore 单例，避免每次新建触发 acquire + _init_schema
_lock = threading.Lock()
_graph_store_singleton = None


def create_graph_store():
    """创建图存储（Neo4j 单例）。

    第 14 批：删除原 LightGraph 内存回退。Neo4j 不可达时由 Neo4jGraphStore 构造
    直接抛 RuntimeError，启动期应 fail-fast（参见 bootstrap/__init__.py）。

    Returns:
        Neo4jGraphStore 单例。
    """
    global _graph_store_singleton
    with _lock:
        if _graph_store_singleton is None:
            from .neo4j_store import Neo4jGraphStore
            _graph_store_singleton = Neo4jGraphStore()
            logger.info("graph_store: Neo4j 单例已建立")
        return _graph_store_singleton


def reset_for_testing():
    """测试用：清空单例（单元测试 in-memory 重新构造时调用）。"""
    global _graph_store_singleton
    with _lock:
        _graph_store_singleton = None
