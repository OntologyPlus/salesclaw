"""摄入管线 —— 「阶段编排 + 状态机 + 失败不阻断 + provenance 每步自带」

阶段（可配置，借鉴 PipelineStep）：
    1. split   : 文本切分
    2. extract : 实体/关系抽取（规则版）
    3. graph   : 候选实体/关系落内存图

全程每一步都用 provenance.track() 包裹，自动写入溯源哈希链；
单阶段失败不影响整条管线
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from provenance import ProvenanceManager, track
from provenance.schemas import SourceReference

from .extractor import ExtractionResult, RuleExtractor, get_extractor
from .graph import LightGraph
from .splitter import Chunk, TextSplitter

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """管线阶段错误"""


@dataclass
class PipelineResult:
    document_id: str
    chunks: list[Chunk] = field(default_factory=list)
    extraction: Optional[ExtractionResult] = None
    graph: Optional[LightGraph] = None
    graph_backend: str = "light"  # "light" | "neo4j"
    activity_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class IngestPipeline:
    """文档摄入管线（split → extract → graph），全程挂 provenance。"""

    def __init__(self, provenance: ProvenanceManager = None,
                 extractor_name: str = "rule", agent_id: str = None,
                 review_store=None, graph_store=None):
        self.prov = provenance or ProvenanceManager()
        self.extractor_cls = get_extractor(extractor_name)
        self.agent_id = agent_id
        self.review_store = review_store  # 候选审核队列（可空，不阻断）
        # 图存储后端：None 时仅落 LightGraph；显式传入则双写
        # （graph_store 通常是 graph_store.create_graph_store() 返回的实例）
        self.graph_store = graph_store

    def run(self, text: str, document_id: str,
            source: SourceReference = None, max_chunk_chars: int = 800) -> PipelineResult:
        if source is None:
            source = SourceReference(source_type="text", uri=document_id, title=document_id)
        result = PipelineResult(document_id=document_id)

        # ── 阶段 1：切分 ──
        try:
            with track("split", name=f"split:{document_id}",
                       agent_id=self.agent_id, mgr=self.prov) as act:
                splitter = TextSplitter(max_chunk_chars=max_chunk_chars)
                result.chunks = splitter.split(text, source)
                act.output_refs.append(f"chunks:{len(result.chunks)}")
            result.activity_ids.append(act.activity_id)
        except Exception as e:  # 切分失败为阻断级（无输入则后续无意义）
            result.errors.append(f"split failed: {e}")
            logger.error("摄入管线切分阶段失败: %s", e)
            raise PipelineError(f"split failed: {e}")

        # ── 阶段 2：抽取（非阻断）──
        try:
            with track("extract", name=f"extract:{document_id}",
                       agent_id=self.agent_id, input_refs=[f"chunks:{len(result.chunks)}"],
                       mgr=self.prov) as act:
                extractor = self.extractor_cls()
                result.extraction = extractor.extract(result.chunks)
                act.output_refs.append(
                    f"entities:{len(result.extraction.entities)}")
                act.output_refs.append(
                    f"relations:{len(result.extraction.relations)}")
            result.activity_ids.append(act.activity_id)
        except Exception as e:
            result.errors.append(f"extract failed: {e}")
            logger.warning("摄入管线抽取阶段失败（非阻断）: %s", e)

        # ── 阶段 3：落图（非阻断）──
        if result.extraction is not None:
            try:
                with track("graph", name=f"graph:{document_id}",
                           agent_id=self.agent_id,
                           input_refs=[f"entities:{len(result.extraction.entities)}"],
                           mgr=self.prov) as act:
                    # 始终维护 LightGraph（保持下游兼容）
                    g = LightGraph()
                    for e in result.extraction.entities:
                        g.add_entity(e)
                    for r in result.extraction.relations:
                        g.add_relation(r)
                    result.graph = g
                    # 若指定 graph_store，幂等 MERGE 写入
                    if self.graph_store is not None:
                        try:
                            self.graph_store.add_entities_batch(
                                result.extraction.entities)
                            self.graph_store.add_relations_batch(
                                result.extraction.relations)
                            result.graph_backend = getattr(
                                self.graph_store, "backend_name", lambda: type(self.graph_store).__name__)()
                        except Exception as ge:
                            result.errors.append(f"graph_store write failed: {ge}")
                            logger.warning("graph_store 写入失败（非阻断）: %s", ge)
                    act.output_refs.append(f"nodes:{g.stats()['nodes']}")
                    act.output_refs.append(f"edges:{g.stats()['edges']}")
                result.activity_ids.append(act.activity_id)
            except Exception as e:
                result.errors.append(f"graph failed: {e}")
                logger.warning("摄入管线落图阶段失败（非阻断）: %s", e)

        # ── 阶段 4：候选入审核队列（非阻断，治理平面闸口）──
        if self.review_store is not None and result.extraction is not None:
            try:
                self._queue_candidates(result.extraction, document_id)
            except Exception as e:
                result.errors.append(f"review queue failed: {e}")
                logger.warning("候选入审核队列失败（非阻断）: %s", e)

        return result

    def _queue_candidates(self, extraction, document_id: str) -> int:
        """把抽取候选推入审核队列，返回入库数。"""
        n = 0
        for e in extraction.entities:
            cid = f"ent:{document_id}:{e.entity_id}"
            self.review_store.add(cid, "entity", {
                "entity_id": e.entity_id,
                "entity_type": e.entity_type,
                "mention": e.mention,
                "document_id": document_id,
            })
            n += 1
        for r in extraction.relations:
            cid = f"rel:{document_id}:{r.relation_id}"
            self.review_store.add(cid, "relation", {
                "relation_id": r.relation_id,
                "subject": r.subject,
                "predicate": r.predicate,
                "obj": r.obj,
                "confidence": r.confidence,
                "document_id": document_id,
            })
            n += 1
        return n
