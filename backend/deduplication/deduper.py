"""去重器 —— 第八批：实体/三元组合并

策略：
    - mention 相似度：TF-IDF + 余弦相似度（sklearn，已装）
    - 合并原则：
        * 同类型 + 相似度 ≥ threshold → 视为同一实体
        * 合并策略：keep_first / most_complete（properties 多的胜出）
    - 输出：合并映射 {canonical_id: [merged_ids]} 与合并后实体列表

"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein 距离（短串用 DP）。"""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(
                cur[j - 1] + 1,        # insert
                prev[j] + 1,           # delete
                prev[j - 1] + (ca != cb),  # replace
            )
        prev = cur
    return prev[-1]


class EntityDeduper:
    """实体去重器（基于 mention 相似度 + 类型匹配）。"""

    def __init__(self, *, threshold: float = 0.85,
                 strategy: str = "most_complete"):
        self._threshold = threshold
        self._strategy = strategy  # "keep_first" | "most_complete"
        self._vectorizer = None
        self._matrix: Optional[np.ndarray] = None
        self._ents: list[dict] = []

    def _build_vectors(self) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        mentions = [e.get("mention", "") or e.get("entity_id", "")
                    for e in self._ents]
        # 中文：char-level analyzer
        self._vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3))
        m = self._vectorizer.fit_transform(mentions)
        self._matrix = m.toarray() if m.shape[0] < 5000 else m  # 稀疏即可

    def _sim(self, i: int, j: int) -> float:
        if i == j:
            return 1.0
        if self._matrix is None:
            return 0.0
        from sklearn.metrics.pairwise import cosine_similarity
        v1 = self._matrix[i:i + 1]
        v2 = self._matrix[j:j + 1]
        if hasattr(v1, "toarray"):
            return float(cosine_similarity(v1, v2)[0][0])
        return float(cosine_similarity(v1, v2)[0][0])

    def dedup(self, entities: list[dict]) -> dict:
        """去重实体列表。

        输入：[{"entity_id","entity_type","mention","properties"?}, ...]
        输出：{
            "merged": [{canonical dict}],
            "groups": {canonical_id: [merged_ids]},
            "dropped": [merged_ids],
        }
        """
        self._ents = list(entities)
        if not self._ents:
            return {"merged": [], "groups": {}, "dropped": []}

        self._build_vectors()
        n = len(self._ents)

        # 同类型分桶后做相似度聚类（避免跨类型误合并）
        buckets: dict[str, list[int]] = defaultdict(list)
        for i, e in enumerate(self._ents):
            buckets[e.get("entity_type", "Unknown")].append(i)

        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for etype, idxs in buckets.items():
            for i_pos, i in enumerate(idxs):
                for j in idxs[i_pos + 1:]:
                    sim = self._sim(i, j)
                    if sim >= self._threshold:
                        union(i, j)
                    else:
                        # 短串额外用编辑距离（避免 TF-IDF 短文失真）
                        m_i = self._ents[i].get("mention", "") or self._ents[i].get("entity_id", "")
                        m_j = self._ents[j].get("mention", "") or self._ents[j].get("entity_id", "")
                        if m_i and m_j and max(len(m_i), len(m_j)) <= 6:
                            dist = _edit_distance(m_i, m_j)
                            if dist <= 1:
                                union(i, j)

        # 按 root 聚合
        groups: dict[int, list[int]] = defaultdict(list)
        for i in range(n):
            groups[find(i)].append(i)

        merged: list[dict] = []
        groups_out: dict[str, list[str]] = {}
        dropped: list[str] = []
        for root, members in groups.items():
            ids = [self._ents[m]["entity_id"] for m in members]
            canonical_id = self._ents[root]["entity_id"]
            groups_out[canonical_id] = ids
            if len(members) == 1:
                merged.append(dict(self._ents[root]))
                continue
            # 合并：按策略选 canonical
            if self._strategy == "most_complete":
                pick = max(members, key=lambda m: len(
                    (self._ents[m].get("properties") or {})))
            else:  # keep_first
                pick = members[0]
            canonical = dict(self._ents[pick])
            # 合并 properties（去重值）
            merged_props: dict = {}
            for m in members:
                p = self._ents[m].get("properties") or {}
                merged_props.update(p)
            canonical["properties"] = merged_props
            canonical["merged_from"] = ids
            merged.append(canonical)
            dropped.extend([i for i in ids if i != canonical["entity_id"]])
        return {"merged": merged, "groups": groups_out, "dropped": dropped}
