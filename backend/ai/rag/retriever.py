"""增强 RAG 检索器 - 关键词 LIKE + 向量语义（embeddings/sqlite-vec）+ TF-IDF 降级

检索策略：
1. 关键词检索（SQL LIKE）：搜索 KnowledgeDocument + FaqItem 表
2. 语义检索（主路径）：TextEmbedder + 余弦 / VectorStore(sqlite-vec) 缓存
3. 语义检索（降级）：sklearn TF-IDF + cosine_similarity
4. 融合排序：关键词匹配分 × 0.4 + 语义相似度 × 0.6
5. 语义分块：按段落 + 标题边界分块，支持 overlap

B6：TF-IDF fit 缓存 - 相同候选集（hash 命中）跳过 fit_transform。
Phase A：语义主路径切换为 embedding；TF-IDF 仅作降级。
"""
import hashlib
import logging
import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from database import KnowledgeDocument, FaqItem

logger = logging.getLogger(__name__)


class EnhancedRAGRetriever:
    """增强 RAG 检索器 - 向量语义主路径，TF-IDF 降级"""

    # 融合排序权重
    KEYWORD_WEIGHT = 0.4
    SEMANTIC_WEIGHT = 0.6
    # 分块参数
    CHUNK_MAX_CHARS = 500   # 单块最大字符数
    CHUNK_OVERLAP = 50      # 块间重叠字符数（保持上下文连贯）
    # 候选集上限
    MAX_CANDIDATES = 50
    # 中文停用词
    STOP_WORDS = {
        "的", "了", "是", "在", "和", "与", "或", "及", "等", "为",
        "对", "中", "可", "以", "由", "向", "及", "其", "此", "该",
        "这", "那", "一", "个", "种", "些", "上", "下", "不", "无",
    }

    def __init__(self):
        # TF-IDF 向量化器：使用自定义中文分词器（降级路径）
        self._vectorizer = TfidfVectorizer(
            tokenizer=self._tokenize,
            token_pattern=None,  # 禁用默认 pattern，使用自定义 tokenizer
            stop_words=None,     # 停用词已在 tokenizer 中处理
        )
        # 标记是否已 fit（避免空 fit 报错）
        self._fitted = False
        # B6：fit 缓存 - 相同候选集 hash 命中时复用 tfidf_matrix
        self._fitted_hash: str = ""
        self._cached_candidate_vecs = None  # 缓存的候选向量矩阵（query 向量需每次重算）
        self._embedder = None
        self._vector_store = None
        self._embedder_failed = False

    def _get_embedder(self):
        """延迟加载 TextEmbedder；失败后标记并走 TF-IDF。"""
        if self._embedder_failed:
            return None
        if self._embedder is not None:
            return self._embedder
        try:
            from embeddings import TextEmbedder, VectorStore
            from config import settings
            self._embedder = TextEmbedder()
            self._vector_store = VectorStore(
                db_path=settings.VEC_DB_PATH,
                dim=self._embedder.dim,
            )
            return self._embedder
        except Exception as e:
            logger.warning("RAG embedder 初始化失败，降级 TF-IDF: %s", e)
            self._embedder_failed = True
            return None

    # ──────────────────────────────────────────────
    # 主入口
    # ──────────────────────────────────────────────
    def retrieve(self, query: str, tenant_id, db, top_k: int = 5) -> list[dict]:
        """检索：返回排序后的结果列表

        Args:
            query: 查询字符串
            tenant_id: 租户 ID
            db: 数据库 session
            top_k: 返回结果数上限

        Returns:
            [{title, content, source, score, type}]，按得分降序
        """
        if not query or not query.strip() or db is None or tenant_id is None:
            return []

        tid = str(tenant_id)
        # 收集候选文档（含分块）
        candidates = self._collect_candidates(query, tid, db)
        if not candidates:
            return []

        # Phase A：优先 embedding 语义分；失败则 TF-IDF
        semantic_scores, semantic_backend = self._compute_vector_scores(query, candidates, tid)
        if semantic_scores is None:
            semantic_scores = self._compute_semantic_scores(query, candidates)
            semantic_backend = "tfidf"

        # 融合打分：关键词匹配分 × 0.4 + 语义相似度 × 0.6
        for idx, candidate in enumerate(candidates):
            kw_score = self._keyword_score(query, candidate)
            sem_score = float(semantic_scores[idx]) if idx < len(semantic_scores) else 0.0
            candidate["score"] = round(
                self.KEYWORD_WEIGHT * kw_score + self.SEMANTIC_WEIGHT * sem_score, 4,
            )
            candidate["semantic_backend"] = semantic_backend

        # 排序并取 top_k（过滤零分结果）
        scored = [c for c in candidates if c["score"] > 0]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def _item_id(self, candidate: dict, tenant_id: str) -> str:
        ctype = candidate.get("type", "doc")
        doc_id = candidate.get("doc_id", 0)
        idx = candidate.get("_idx", 0)
        return f"{tenant_id}:{ctype}:{doc_id}:{idx}"

    def _compute_vector_scores(
        self, query: str, candidates: list[dict], tenant_id: str
    ):
        """用 TextEmbedder 对 query+候选打分，并写入 VectorStore 供后续复用。

        Returns:
            (scores ndarray | None, backend_name)
        """
        embedder = self._get_embedder()
        if embedder is None or not candidates:
            return None, "none"

        try:
            texts = [
                f"{c.get('title', '')} {c.get('content', '')}".strip() or " "
                for c in candidates
            ]
            matrix = embedder.embed([query] + texts)
            q = np.asarray(matrix[0], dtype=np.float32).ravel()
            docs = np.asarray(matrix[1:], dtype=np.float32)
            qn = float(np.linalg.norm(q)) + 1e-12
            dn = np.linalg.norm(docs, axis=1) + 1e-12
            sims = (docs @ q) / (dn * qn)
            sims = np.clip(np.nan_to_num(sims, nan=0.0), 0.0, 1.0)

            # 旁路写入 sqlite-vec，便于后续索引命中（失败忽略）
            if self._vector_store is not None:
                try:
                    for i, c in enumerate(candidates):
                        self._vector_store.add(self._item_id(c, tenant_id), docs[i])
                except Exception as e:
                    logger.debug("RAG VectorStore 写入跳过: %s", e)

            return sims, f"embed:{embedder.backend}"
        except Exception as e:
            logger.warning("RAG 向量打分失败，降级 TF-IDF: %s", e)
            return None, "none"

    def search(self, query: str, tenant_id, db, top_k: int = 5) -> dict:
        """检索（带元信息）

        Returns:
            {results, total, query}
        """
        results = self.retrieve(query, tenant_id, db, top_k=top_k)
        return {
            "results": results,
            "total": len(results),
            "query": query,
        }

    # ──────────────────────────────────────────────
    # 候选收集 + 语义分块
    # ──────────────────────────────────────────────
    def _collect_candidates(self, query: str, tid: str, db) -> list[dict]:
        """从 KnowledgeDocument + FaqItem 收集候选，含语义分块"""
        candidates: list[dict] = []

        # 查询 KnowledgeDocument（先 LIKE 匹配，无结果则全量兜底）
        docs = self._query_documents(query, tid, db)
        for doc in docs:
            chunks = self._chunk_document(doc)
            for idx, chunk in enumerate(chunks):
                candidates.append({
                    "title": doc.title or "",
                    "content": chunk,
                    "source": f"/knowledge/documents/{doc.id}",
                    "type": "document",
                    "doc_id": doc.id,
                    "tags": doc.tags or "",
                    "category": doc.category or "",
                    "_idx": idx,
                })

        # 查询 FaqItem（先 LIKE 匹配，无结果则全量兜底）
        faqs = self._query_faqs(query, tid, db)
        for faq in faqs:
            content = f"问：{faq.question}\n答：{faq.answer}"
            candidates.append({
                "title": faq.question or "",
                "content": content,
                "source": f"/knowledge/faq/{faq.id}",
                "type": "faq",
                "doc_id": faq.id,
                "tags": "",
                "category": faq.category or "",
                "_idx": 0,
            })

        # 限制候选集规模，避免打分阶段耗时过长
        return candidates[: self.MAX_CANDIDATES]

    def _query_documents(self, query: str, tid: str, db) -> list:
        """查询 KnowledgeDocument：多字段 LIKE，无匹配时全量兜底"""
        like_pattern = f"%{query}%"
        docs = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.tenant_id == tid,
            KnowledgeDocument.is_deleted == 0,
            KnowledgeDocument.is_published == 1,
            KnowledgeDocument.title.like(like_pattern)
            | KnowledgeDocument.summary.like(like_pattern)
            | KnowledgeDocument.content.like(like_pattern)
            | KnowledgeDocument.tags.like(like_pattern),
        ).limit(20).all()
        # 无 LIKE 匹配时，全量返回已发布文档作为候选（供语义检索）
        if not docs:
            docs = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.tenant_id == tid,
                KnowledgeDocument.is_deleted == 0,
                KnowledgeDocument.is_published == 1,
            ).limit(30).all()
        return docs

    def _query_faqs(self, query: str, tid: str, db) -> list:
        """查询 FaqItem：question + answer 字段 LIKE，无匹配时全量兜底"""
        like_pattern = f"%{query}%"
        faqs = db.query(FaqItem).filter(
            FaqItem.tenant_id == tid,
            FaqItem.is_deleted == 0,
            FaqItem.question.like(like_pattern) | FaqItem.answer.like(like_pattern),
        ).limit(20).all()
        if not faqs:
            faqs = db.query(FaqItem).filter(
                FaqItem.tenant_id == tid,
                FaqItem.is_deleted == 0,
            ).limit(20).all()
        return faqs

    def _chunk_document(self, doc) -> list[str]:
        """语义分块：按段落 + 标题边界分割，支持 overlap

        标题边界识别：以【】或行首数字编号开头的行视为标题边界。
        """
        content = doc.content or doc.summary or ""
        if not content:
            return []
        # 按换行分割段落
        raw_paragraphs = re.split(r'\n+', content)
        paragraphs = [p.strip() for p in raw_paragraphs if p.strip()]
        if not paragraphs:
            return []

        chunks: list[str] = []
        current = ""
        for para in paragraphs:
            # 标题边界检测：遇到新标题时强制切分
            is_heading = bool(re.match(r'^【.*】|^[一二三四五六七八九十\d]+[、.．]', para))
            if is_heading and current:
                chunks.append(current)
                overlap = current[-self.CHUNK_OVERLAP:] if len(current) > self.CHUNK_OVERLAP else ""
                current = overlap + para
                continue
            # 长度超限时切分
            if current and len(current) + len(para) + 1 > self.CHUNK_MAX_CHARS:
                chunks.append(current)
                overlap = current[-self.CHUNK_OVERLAP:] if len(current) > self.CHUNK_OVERLAP else ""
                current = overlap + para
            else:
                current = f"{current}\n{para}" if current else para
        if current:
            chunks.append(current)

        # 兜底：若无有效分块，返回截断的原文
        if not chunks:
            chunks = [content[: self.CHUNK_MAX_CHARS]]
        return chunks

    # ──────────────────────────────────────────────
    # 关键词匹配得分
    # ──────────────────────────────────────────────
    def _keyword_score(self, query: str, candidate: dict) -> float:
        """计算关键词匹配得分（0-1）

        统计查询词在候选文本（标题+内容+标签+分类）中的命中率。
        """
        query_terms = self._tokenize(query)
        if not query_terms:
            return 0.0
        # 合并候选文本字段
        candidate_text = " ".join([
            candidate.get("title", ""),
            candidate.get("content", ""),
            candidate.get("tags", ""),
            candidate.get("category", ""),
        ]).lower()
        if not candidate_text:
            return 0.0

        matched = 0
        for term in query_terms:
            if term.lower() in candidate_text:
                matched += 1
        return matched / len(query_terms)

    # ──────────────────────────────────────────────
    # TF-IDF 语义相似度（sklearn 实现）
    # ──────────────────────────────────────────────
    def _corpus_hash(self, candidates: list[dict]) -> str:
        """B6：基于候选集内容计算 md5 哈希，用于检测语料是否变化

        哈希输入：每个候选的 (doc_id, title, content[:200]) 元组列表
        """
        signature = [
            (c.get('doc_id'), c.get('title', ''), (c.get('content', '') or '')[:200])
            for c in candidates
        ]
        return hashlib.md5(repr(signature).encode('utf-8')).hexdigest()

    def _compute_semantic_scores(self, query: str, candidates: list[dict]) -> np.ndarray:
        """计算查询与所有候选的 TF-IDF 余弦相似度

        B6：候选集 hash 命中缓存时，仅对 query 做 transform（不重算 IDF）；
        候选集变化时才 fit_transform 并更新缓存。

        Returns:
            长度为 len(candidates) 的 numpy 数组，元素 ∈ [0, 1]
        """
        if not candidates:
            self._fitted = False
            return np.zeros(0)

        current_hash = self._corpus_hash(candidates)

        # B6：候选集未变 → 复用缓存的候选向量矩阵，仅对 query 做 transform
        if current_hash == self._fitted_hash and self._cached_candidate_vecs is not None:
            try:
                query_vec = self._vectorizer.transform([query])
                sims = cosine_similarity(query_vec, self._cached_candidate_vecs).ravel()
                sims = np.nan_to_num(sims, nan=0.0)
                return np.clip(sims, 0.0, 1.0)
            except Exception:
                # 缓存失效（如 vectorizer 状态异常）→ 回退到 refit
                pass

        # 候选集变化 → 重新 fit
        candidate_texts = [
            f"{c.get('title', '')} {c.get('content', '')}"
            for c in candidates
        ]
        corpus = [query] + candidate_texts

        try:
            tfidf_matrix = self._vectorizer.fit_transform(corpus)
            self._fitted = True
            # 更新缓存
            self._fitted_hash = current_hash
            self._cached_candidate_vecs = tfidf_matrix[1:]
        except ValueError:
            # 全部为空文本或 tokenizer 全空时 fit_transform 抛 ValueError
            self._fitted = False
            return np.zeros(len(candidates))

        # query 向量与各候选向量的余弦相似度
        query_vec = tfidf_matrix[0:1]
        candidate_vecs = tfidf_matrix[1:]
        sims = cosine_similarity(query_vec, candidate_vecs).ravel()
        # cosine_similarity 可能因零向量返回 nan，填 0
        sims = np.nan_to_num(sims, nan=0.0)
        # 相似度范围裁剪到 [0, 1]（余弦相似度理论上 ∈ [-1, 1]，文本场景负值无意义）
        return np.clip(sims, 0.0, 1.0)

    # ──────────────────────────────────────────────
    # 分词
    # ──────────────────────────────────────────────
    def _tokenize(self, text: str) -> list[str]:
        """简易分词：英文按词、中文按字符 + bigram，去除停用词

        中文 bigram 提升短语级匹配质量（如"心血通"→"心血"+"血通"）。
        """
        if not text:
            return []
        # 去除标点与特殊符号（保留中英文与数字）
        cleaned = re.sub(r'[^\w\u4e00-\u9fff\s]', ' ', text)
        tokens: list[str] = []
        # 英文按空白分词
        for word in cleaned.split():
            word_lower = word.lower()
            if len(word_lower) > 1 and word_lower not in self.STOP_WORDS:
                tokens.append(word_lower)
            elif word_lower and word_lower not in self.STOP_WORDS:
                tokens.append(word_lower)
        # 中文按字符 + bigram
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        # 单字
        for ch in chinese_chars:
            if ch not in self.STOP_WORDS:
                tokens.append(ch)
        # bigram（相邻两字组合）
        for i in range(len(chinese_chars) - 1):
            bigram = chinese_chars[i] + chinese_chars[i + 1]
            tokens.append(bigram)
        return tokens


# 保留原类名作为别名，兼容已有调用方
RAGRetriever = EnhancedRAGRetriever


__all__ = ["EnhancedRAGRetriever", "RAGRetriever"]
