"""ingest —— 文档摄入子包

端到端切片：split → extract → graph，全程挂 provenance 溯源。
第八批加固后：
    - 抽取：rule / llm / llm_ner（LLM 为主 + 本地 NER/规则兜底）
    - 图存储：可选 Neo4j 后端（graph_store 工厂），无 Neo4j 时回退 LightGraph

导出：
    - IngestPipeline：编排入口（.run(text, document_id)）
    - TextSplitter / RuleExtractor / LLMExtractor / LLMWithNerFallbackExtractor
    - LightGraph / GraphStoreFactory（from graph_store）
"""
from .extractor import (
    Entity,
    ExtractionResult,
    Relation,
    RuleExtractor,
    LLMExtractor,
    LLMWithNerFallbackExtractor,
    LLMProvider,
    LangChainOpenAIProvider,
    LocalNerProvider,
    TemplateLLMProvider,
    get_extractor,
)
from .graph import GraphEdge, GraphNode, LightGraph
from .pipeline import IngestPipeline, PipelineError, PipelineResult
from .splitter import Chunk, TextSplitter

__all__ = [
    "IngestPipeline",
    "PipelineError",
    "PipelineResult",
    "TextSplitter",
    "Chunk",
    "RuleExtractor",
    "LLMExtractor",
    "LLMWithNerFallbackExtractor",
    "LLMProvider",
    "LangChainOpenAIProvider",
    "LocalNerProvider",
    "TemplateLLMProvider",
    "ExtractionResult",
    "Entity",
    "Relation",
    "get_extractor",
    "LightGraph",
    "GraphNode",
    "GraphEdge",
]
