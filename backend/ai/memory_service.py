"""四层记忆系统 - Working / Episodic / Semantic / Procedural

层次划分：
1. Working Memory：当前会话增量摘要（内存中，>30 条触发压缩）
2. Episodic：对话片段存储 + 语义搜索（SQLite LIKE 降级）+ 时间衰减
3. Semantic：用户画像 + 偏好演化（semantic_memories 表）
4. Procedural：策略成功率追踪（procedural_memories 表）

时间衰减：decay_score = max(0, 100 - days_elapsed * 5)

B5：在 LIKE 召回基础上叠加 TF-IDF 语义重排，提升跨会话语义匹配召回率。
"""
import re
from datetime import datetime

from database import EpisodicMemory, SemanticMemory, ProceduralMemory


class MemoryService:
    """四层记忆系统"""

    # Working Memory 压缩阈值
    WORKING_COMPRESS_THRESHOLD = 30
    # 时间衰减：每天扣 5 分
    DECAY_PER_DAY = 5
    # B5：语义重排最小候选数（少于该值跳过重排）
    RERANK_MIN_ITEMS = 5
    # 中文停用词（与 rag/__init__.py 保持一致）
    _STOP_WORDS = {
        "的", "了", "是", "在", "和", "与", "或", "及", "等", "为",
        "对", "中", "可", "以", "由", "向", "及", "其", "此", "该",
        "这", "那", "一", "个", "种", "些", "上", "下", "不", "无",
    }

    def __init__(self):
        # Working Memory：{session_key: [{"role", "content", "ts"}]}
        self._working: dict = {}
        # B5：延迟初始化 TfidfVectorizer（避免无查询时也加载 sklearn）
        self._vectorizer = None

    def _get_vectorizer(self):
        """B5：懒加载 TfidfVectorizer（与 rag 模块一致的中文分词）"""
        if self._vectorizer is None:
            from sklearn.feature_extraction.text import TfidfVectorizer
            self._vectorizer = TfidfVectorizer(
                tokenizer=self._tokenize,
                token_pattern=None,
                stop_words=None,
            )
        return self._vectorizer

    @staticmethod
    def _tokenize(text: str) -> list:
        """简易分词：英文按词、中文按字符 + bigram（与 rag 模块一致）"""
        if not text:
            return []
        cleaned = re.sub(r'[^\w\u4e00-\u9fff\s]', ' ', text)
        tokens: list = []
        for word in cleaned.split():
            wl = word.lower()
            if len(wl) > 1 and wl not in MemoryService._STOP_WORDS:
                tokens.append(wl)
            elif wl and wl not in MemoryService._STOP_WORDS:
                tokens.append(wl)
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        for ch in chinese_chars:
            if ch not in MemoryService._STOP_WORDS:
                tokens.append(ch)
        for i in range(len(chinese_chars) - 1):
            tokens.append(chinese_chars[i] + chinese_chars[i + 1])
        return tokens

    # ──────────────────────────────────────────────
    # Working Memory（内存层）
    # ──────────────────────────────────────────────
    @staticmethod
    def _working_key(user_id, tenant_id, session_id) -> str:
        return f"{tenant_id}:{user_id}:{session_id or 'default'}"

    def _append_working(self, user_id, tenant_id, session_id, content: str, role: str = "user") -> None:
        """追加 Working Memory，超过阈值触发压缩"""
        key = self._working_key(user_id, tenant_id, session_id)
        self._working.setdefault(key, []).append({
            "role": role,
            "content": content,
            "ts": datetime.utcnow(),
        })
        if len(self._working[key]) > self.WORKING_COMPRESS_THRESHOLD:
            self._compress_working(key)

    def _compress_working(self, key: str) -> str:
        """压缩 Working Memory：生成摘要并保留近期条目"""
        entries = self._working.get(key, [])
        if not entries:
            return ""
        summary_parts = [f"[{e['role']}] {e['content'][:120]}" for e in entries]
        compressed = "会话摘要：\n" + "\n".join(summary_parts[:10])
        if len(summary_parts) > 10:
            compressed += f"\n...（共 {len(summary_parts)} 条，已压缩）"
        # 保留最后 5 条作为短期上下文，并在头部插入摘要
        self._working[key] = entries[-5:]
        self._working[key].insert(0, {
            "role": "system",
            "content": compressed,
            "ts": datetime.utcnow(),
        })
        return compressed

    def get_working(self, user_id, tenant_id, session_id) -> list:
        """读取当前会话的 Working Memory"""
        key = self._working_key(user_id, tenant_id, session_id)
        return list(self._working.get(key, []))

    # ──────────────────────────────────────────────
    # 时间衰减
    # ──────────────────────────────────────────────
    @staticmethod
    def _compute_decay(occurred_at) -> int:
        """计算时间衰减分：decay_score = max(0, 100 - days_elapsed * 5)"""
        if occurred_at is None:
            return 0
        days = (datetime.utcnow() - occurred_at).days
        return max(0, 100 - days * MemoryService.DECAY_PER_DAY)

    # ──────────────────────────────────────────────
    # 存储记忆
    # ──────────────────────────────────────────────
    def store(self, user_id, tenant_id, content, memory_type="episodic",
              session_id=None, db=None, **kwargs):
        """存储记忆

        Args:
            memory_type: episodic / semantic / procedural
            kwargs: 取决于类型
                episodic: summary, importance, occurred_at
                semantic: category, key, confidence
                procedural: strategy_name, success_count, failure_count, context_pattern
        """
        # Working Memory 始终记录（无需 db）
        self._append_working(user_id, tenant_id, session_id, content,
                             kwargs.get("role", "user"))

        if db is None:
            return None

        tid = str(tenant_id)
        uid = int(user_id) if user_id is not None else None

        if memory_type == "episodic":
            mem = EpisodicMemory(
                tenant_id=tid,
                user_id=uid,
                session_id=str(session_id) if session_id is not None else None,
                content=content,
                summary=kwargs.get("summary"),
                importance=int(kwargs.get("importance", 5)),
                occurred_at=kwargs.get("occurred_at", datetime.utcnow()),
                decay_score=100,
            )
            db.add(mem)
            db.commit()
            db.refresh(mem)
            return mem

        if memory_type == "semantic":
            mem = SemanticMemory(
                tenant_id=tid,
                user_id=uid,
                category=kwargs.get("category", "profile"),
                key=kwargs.get("key", ""),
                value=content,
                confidence=int(kwargs.get("confidence", 50)),
            )
            db.add(mem)
            db.commit()
            db.refresh(mem)
            return mem

        if memory_type == "procedural":
            mem = ProceduralMemory(
                tenant_id=tid,
                user_id=uid,
                strategy_name=kwargs.get("strategy_name", ""),
                success_count=int(kwargs.get("success_count", 0)),
                failure_count=int(kwargs.get("failure_count", 0)),
                last_used_at=datetime.utcnow(),
                context_pattern=kwargs.get("context_pattern", {}),
            )
            db.add(mem)
            db.commit()
            db.refresh(mem)
            return mem

        return None

    # ──────────────────────────────────────────────
    # 综合检索
    # ──────────────────────────────────────────────
    def _semantic_rerank(self, query: str, items: list, top_k: int) -> list:
        """B5：在 LIKE 召回结果上叠加 TF-IDF 语义重排

        Args:
            query: 查询字符串
            items: 召回的记忆条目列表（每个含 content/summary 字段）
            top_k: 返回数量

        Returns:
            按语义相似度重排后的 top_k 条目，每条加 'semantic_score' 字段。
            若 items 数量 < RERANK_MIN_ITEMS，直接返回原序（性能保护）。
        """
        if not items or not query:
            return items[:top_k]
        # 性能保护：候选数过少时跳过重排
        if len(items) < self.RERANK_MIN_ITEMS:
            return items[:top_k]

        try:
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity
            vectorizer = self._get_vectorizer()
            # 构建文本集合：query + 每条记忆的 content/summary
            item_texts = [
                f"{it.get('content', '')} {it.get('summary', '') or ''}"
                for it in items
            ]
            corpus = [query] + item_texts
            tfidf_matrix = vectorizer.fit_transform(corpus)
            query_vec = tfidf_matrix[0:1]
            item_vecs = tfidf_matrix[1:]
            sims = cosine_similarity(query_vec, item_vecs).ravel()
            sims = np.nan_to_num(sims, nan=0.0)
            sims = np.clip(sims, 0.0, 1.0)
            # 融合语义分与原 score：原分 0.5 + 语义分 0.5
            for idx, it in enumerate(items):
                sem = float(sims[idx])
                orig = it.get("score", 0.0)
                it["semantic_score"] = round(sem, 4)
                it["score"] = round(orig * 0.5 + sem * 0.5, 4)
            # 按融合分排序
            items.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        except Exception:
            # 重排失败 → 保持原序（不影响功能）
            pass
        return items[:top_k]

    def retrieve(self, user_id, tenant_id, query, top_k=5, db=None) -> list:
        """综合检索（跨情景 + 语义），按相关性 + 时间衰减 + 重要性 + 语义重排排序"""
        if db is None:
            return []
        tid = str(tenant_id)
        uid = int(user_id) if user_id is not None else None
        results = []

        # 情景记忆检索（SQLite LIKE 降级 + 时间衰减）
        # B5：扩大召回量（top_k * 3），交给 _semantic_rerank 精排
        ep_q = db.query(EpisodicMemory).filter(
            EpisodicMemory.tenant_id == tid,
            EpisodicMemory.is_deleted == 0,
        )
        if uid is not None:
            ep_q = ep_q.filter(EpisodicMemory.user_id == uid)
        if query:
            like = f"%{query}%"
            ep_q = ep_q.filter(
                (EpisodicMemory.content.like(like)) |
                (EpisodicMemory.summary.like(like))
            )
        ep_items = ep_q.order_by(EpisodicMemory.occurred_at.desc()).limit(top_k * 3).all()
        ep_results = []
        for it in ep_items:
            decay = self._compute_decay(it.occurred_at)
            importance = it.importance or 5
            # 综合得分：时间衰减 0.6 + 重要性 0.4
            score = (decay / 100.0) * 0.6 + (importance / 10.0) * 0.4
            ep_results.append({
                "type": "episodic",
                "id": it.id,
                "content": it.content,
                "summary": it.summary,
                "importance": importance,
                "occurred_at": it.occurred_at.isoformat() if it.occurred_at else None,
                "decay_score": decay,
                "score": round(score, 4),
            })
        # B5：语义重排
        ep_results = self._semantic_rerank(query, ep_results, top_k)
        results.extend(ep_results)

        # 语义记忆检索
        sm_q = db.query(SemanticMemory).filter(
            SemanticMemory.tenant_id == tid,
            SemanticMemory.is_deleted == 0,
        )
        if uid is not None:
            sm_q = sm_q.filter(SemanticMemory.user_id == uid)
        if query:
            like = f"%{query}%"
            sm_q = sm_q.filter(
                (SemanticMemory.key.like(like)) |
                (SemanticMemory.value.like(like))
            )
        sm_items = sm_q.order_by(SemanticMemory.confidence.desc()).limit(top_k).all()
        sm_results = []
        for it in sm_items:
            sm_results.append({
                "type": "semantic",
                "id": it.id,
                "category": it.category,
                "key": it.key,
                "value": it.value,
                "confidence": it.confidence,
                "score": round((it.confidence or 0) / 100.0, 4),
            })
        # B5：语义记忆也走重排
        sm_results = self._semantic_rerank(query, sm_results, top_k)
        results.extend(sm_results)

        # 综合排序后截断
        results.sort(key=lambda r: r.get("score", 0.0), reverse=True)
        return results[:top_k]

    # ──────────────────────────────────────────────
    # 记忆整合
    # ──────────────────────────────────────────────
    def consolidate(self, user_id, tenant_id, db) -> dict:
        """记忆整合：去重 + 摘要，结果存为 semantic 记忆"""
        if db is None:
            return {"consolidated": 0, "summary": ""}
        tid = str(tenant_id)
        uid = int(user_id) if user_id is not None else None

        q = db.query(EpisodicMemory).filter(
            EpisodicMemory.tenant_id == tid,
            EpisodicMemory.is_deleted == 0,
        )
        if uid is not None:
            q = q.filter(EpisodicMemory.user_id == uid)
        items = q.order_by(EpisodicMemory.occurred_at.desc()).limit(50).all()

        if not items:
            return {"consolidated": 0, "summary": "无情景记忆可整合。"}

        # 去重：基于内容前缀的字符集相似度
        seen_sigs = []
        unique = []
        for it in items:
            sig = (it.content or "").strip()[:60]
            is_dup = False
            for s in seen_sigs:
                if self._similarity(sig, s) > 0.8:
                    is_dup = True
                    break
            if not is_dup:
                seen_sigs.append(sig)
                unique.append(it)

        # 生成摘要：按重要性排序取 Top5
        unique.sort(key=lambda x: x.importance or 0, reverse=True)
        top = unique[:5]
        summary_parts = []
        for it in top:
            text = it.summary or (it.content or "")[:100]
            summary_parts.append(f"- [{it.importance or 5}/10] {text}")
        summary = "记忆整合摘要：\n" + "\n".join(summary_parts)

        # 存储整合结果到 semantic_memories
        consolidation = SemanticMemory(
            tenant_id=tid,
            user_id=uid,
            category="consolidation",
            key=f"consolidation-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            value=summary,
            confidence=70,
        )
        db.add(consolidation)
        db.commit()

        return {
            "consolidated": len(unique),
            "duplicates_removed": len(items) - len(unique),
            "summary": summary,
        }

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """字符集 Jaccard 相似度（用于去重）"""
        sa, sb = set(a), set(b)
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)

    # ──────────────────────────────────────────────
    # 构建增强上下文
    # ──────────────────────────────────────────────
    def build_context(self, user_id, tenant_id, query, db=None) -> str:
        """构建增强 prompt 上下文：画像 + 相关记忆 + 策略 + 近期会话"""
        sections = []

        # 1. 语义记忆：用户画像与偏好
        profile = self._get_profile(user_id, tenant_id, db)
        if profile:
            sections.append("【用户画像】\n" + profile)

        # 2. 情景记忆检索（跨情景 + 语义）
        if query and db is not None:
            memories = self.retrieve(user_id, tenant_id, query, top_k=3, db=db)
            if memories:
                lines = []
                for m in memories:
                    if m["type"] == "episodic":
                        lines.append(f"- {m.get('summary') or m.get('content', '')[:80]}")
                    else:
                        lines.append(f"- {m.get('key', '')}: {m.get('value', '')[:80]}")
                sections.append("【相关记忆】\n" + "\n".join(lines))

        # 3. 程序记忆：策略成功率
        strategies = self._get_strategies(user_id, tenant_id, db)
        if strategies:
            sections.append("【可用策略】\n" + strategies)

        # 4. Working Memory：近期会话
        working = self.get_working(user_id, tenant_id, None)
        if working:
            lines = [f"- [{e['role']}] {e['content'][:80]}" for e in working[-3:]]
            sections.append("【近期会话】\n" + "\n".join(lines))

        if not sections:
            return ""
        return "\n\n".join(sections)

    def _get_profile(self, user_id, tenant_id, db) -> str:
        """读取用户画像与偏好（semantic_memories 表）"""
        if db is None:
            return ""
        tid = str(tenant_id)
        uid = int(user_id) if user_id is not None else None
        q = db.query(SemanticMemory).filter(
            SemanticMemory.tenant_id == tid,
            SemanticMemory.is_deleted == 0,
            SemanticMemory.category.in_(["profile", "preference"]),
        )
        if uid is not None:
            q = q.filter(SemanticMemory.user_id == uid)
        items = q.order_by(SemanticMemory.confidence.desc()).limit(10).all()
        if not items:
            return ""
        return "\n".join(
            f"- {it.key}: {it.value}"
            for it in items if it.key and it.value
        )

    def _get_strategies(self, user_id, tenant_id, db) -> str:
        """读取策略成功率（procedural_memories 表）"""
        if db is None:
            return ""
        tid = str(tenant_id)
        uid = int(user_id) if user_id is not None else None
        q = db.query(ProceduralMemory).filter(
            ProceduralMemory.tenant_id == tid,
            ProceduralMemory.is_deleted == 0,
        )
        if uid is not None:
            # 包含全局策略（user_id 为 null）
            q = q.filter((ProceduralMemory.user_id == uid) | (ProceduralMemory.user_id.is_(None)))
        items = q.order_by(ProceduralMemory.success_count.desc()).limit(5).all()
        if not items:
            return ""
        lines = []
        for it in items:
            total = (it.success_count or 0) + (it.failure_count or 0)
            rate = (it.success_count or 0) / total if total else 0.0
            lines.append(f"- {it.strategy_name}（成功率 {rate * 100:.0f}%，共 {total} 次）")
        return "\n".join(lines)

    # ──────────────────────────────────────────────
    # 程序记忆更新
    # ──────────────────────────────────────────────
    def update_procedural(self, strategy_name, success, tenant_id, db, user_id=None):
        """更新策略成功率：存在则累加，不存在则新建"""
        if db is None or not strategy_name:
            return None
        tid = str(tenant_id)
        uid = int(user_id) if user_id is not None else None
        q = db.query(ProceduralMemory).filter(
            ProceduralMemory.tenant_id == tid,
            ProceduralMemory.is_deleted == 0,
            ProceduralMemory.strategy_name == strategy_name,
        )
        if uid is not None:
            q = q.filter((ProceduralMemory.user_id == uid) | (ProceduralMemory.user_id.is_(None)))
        mem = q.first()
        now = datetime.utcnow()
        if mem is None:
            mem = ProceduralMemory(
                tenant_id=tid,
                user_id=uid,
                strategy_name=strategy_name,
                success_count=1 if success else 0,
                failure_count=0 if success else 1,
                last_used_at=now,
                context_pattern={},
            )
            db.add(mem)
        else:
            if success:
                mem.success_count = (mem.success_count or 0) + 1
            else:
                mem.failure_count = (mem.failure_count or 0) + 1
            mem.last_used_at = now
        db.commit()
        if mem.id:
            db.refresh(mem)
        return mem


# 全局单例
memory_service = MemoryService()


__all__ = ["MemoryService", "memory_service"]
