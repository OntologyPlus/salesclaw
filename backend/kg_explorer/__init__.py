"""kg_explorer —— 知识图谱探索子包

把现有全量 /graph 升级为结构化探索（邻域/子图/路径/统计），
可作用于 LightGraph 候选层、graph_store 后端（含 Neo4j）或 ontology 本体结构图。

导出：
    - GraphView：邻接视图 + 探索 API
    - from_lightgraph：LightGraph → GraphView 适配
    - from_graph_store：graph_store 后端 → GraphView 适配（第八批新增）
"""
from .queries import GraphView, from_lightgraph, from_graph_store

__all__ = ["GraphView", "from_lightgraph", "from_graph_store"]
