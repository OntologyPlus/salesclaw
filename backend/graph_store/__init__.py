"""图存储层 —— 第八批：Neo4j 后端封装
                第 14 批：Neo4j 唯一主存，删除 LightGraph 生产路径。

对外暴露：
    - Neo4jGraphStore: 真实 Cypher 后端（唯一可用）
    - LightGraph: 内存回退保留（仅供测试构造，不入工厂调度路径）
    - create_graph_store(): 工厂，固定 Neo4j，连接失败抛错（fail-fast）
    - backend_name(store): 查询后端名（兼容旧 API）

"""
from .neo4j_store import Neo4jGraphStore
from .factory import create_graph_store, reset_for_testing


def backend_name(store=None):
    """查询 store 的后端名（兼容旧 API 调用 `backend_name()`）。"""
    s = store if store is not None else create_graph_store()
    return getattr(s, "backend_name", lambda: type(s).__name__)()


# 兼容旧 API 别名：旧 import `reset_factory` 已重命名 `reset_for_testing`
def reset_factory():
    """兼容旧工厂接口别名（生产代码不要调用）。"""
    return reset_for_testing()


# LightGraph 仍从 ingest.graph 导出（保持现有引用不破坏）
from ingest.graph import LightGraph, GraphNode, GraphEdge

__all__ = [
    "Neo4jGraphStore",
    "LightGraph",
    "GraphNode",
    "GraphEdge",
    "create_graph_store",
    "backend_name",
    "reset_factory",
    "reset_for_testing",
]
