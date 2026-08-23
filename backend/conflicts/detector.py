"""冲突检测器 —— 第八批：本体/三元组矛盾检测

检测三类常见冲突：
    1) 方向冲突：同一 (subject, object) 对存在多个 predicate 方向相反
       （如 covers 与 belongs_to 同时出现，方向可能矛盾）
    2) 类型冲突：关系的 subject/obj 类型不在本体允许的 domain/range
    3) 重复冲突：同一 (subject, predicate, object) 多次出现且 confidence 差异过大
    4) 业务自反：subject == object 的退化三元组

输入：候选三元组列表 [{subject, predicate, obj, confidence, ...}, ...]
      可选 ontology LINKS 用于类型校验
输出：[{kind, severity, message, triples, suggestion}, ...]
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)


# 业务定义的"反向对"（业务语义中视为方向冲突）
_INVERSE_PAIRS = {
    frozenset({"covers", "belongs_to"}),
    frozenset({"covers", "located_in"}),
    frozenset({"located_in", "belongs_to"}),
}


class ConflictDetector:
    """冲突检测器（无状态，可复用）。"""

    def __init__(self, *, confidence_gap: float = 0.5):
        self._gap = confidence_gap

    def detect(self, triples: list[dict],
               ontology_links: Optional[list[dict]] = None) -> list[dict]:
        """返回冲突列表，每条形如
        {kind, severity, message, triples, suggestion}。
        """
        out: list[dict] = []

        # 1) 业务自反
        for t in triples:
            if t.get("subject") and t.get("subject") == t.get("obj"):
                out.append({
                    "kind": "self_loop",
                    "severity": "low",
                    "message": f"自反三元组：{t.get('subject')}→{t.get('obj')}",
                    "triples": [t],
                    "suggestion": "丢弃（subject==obj，无信息量）",
                })

        # 2) 重复冲突（多源同三元组差异过大）
        bucket: dict[tuple, list[dict]] = defaultdict(list)
        for t in triples:
            key = (t.get("subject"), t.get("predicate"), t.get("obj"))
            if all(key):
                bucket[key].append(t)
        for key, group in bucket.items():
            if len(group) >= 2:
                confs = [g.get("confidence", 1.0) for g in group]
                if max(confs) - min(confs) > self._gap:
                    out.append({
                        "kind": "confidence_divergence",
                        "severity": "medium",
                        "message": f"三元组 {key} 出现 {len(group)} 次，confidence 差异 {max(confs)-min(confs):.2f}",
                        "triples": group,
                        "suggestion": "保留 confidence 最高，丢弃其它（或人工审核）",
                    })

        # 3) 方向冲突（同一对端存在反向谓词）
        pair_predicates: dict[tuple, set[str]] = defaultdict(set)
        for t in triples:
            s, o = t.get("subject"), t.get("obj")
            p = t.get("predicate")
            if s and o and p:
                # 视为无向对
                key = tuple(sorted([s, o]))
                pair_predicates[key].add(p)
        for (s, o), preds in pair_predicates.items():
            if len(preds) >= 2:
                # 是否构成业务定义的"反向对"
                bad = [pair for pair in [frozenset({p1, p2})
                       for p1 in preds for p2 in preds if p1 != p2]
                       if pair in _INVERSE_PAIRS]
                if bad:
                    out.append({
                        "kind": "direction_conflict",
                        "severity": "high",
                        "message": f"({s},{o}) 出现反向谓词：{sorted(preds)}",
                        "triples": [t for t in triples
                                    if t.get("subject") in (s, o) and t.get("obj") in (s, o)],
                        "suggestion": "由领域专家审核：保留主导方向，丢弃反向",
                    })

        # 4) 类型冲突（relation 两端类型不在本体 domain/range）
        if ontology_links:
            link_by_name = {l["name"]: l for l in ontology_links}
            for t in triples:
                link = link_by_name.get(t.get("predicate", ""))
                if not link:
                    continue
                src_type = (t.get("subject_type") or "").strip()
                tgt_type = (t.get("object_type") or "").strip()
                if not src_type or not tgt_type:
                    continue  # 类型信息不足，跳过
                if link.get("source_object") and link["source_object"] != src_type:
                    out.append({
                        "kind": "type_mismatch",
                        "severity": "medium",
                        "message": f"关系 {t.get('predicate')} 端类型 {src_type} 不匹配本体 domain {link['source_object']}",
                        "triples": [t],
                        "suggestion": "修正抽取（subject_type 应为本体 source_object）",
                    })
                if link.get("target_object") and link["target_object"] != tgt_type:
                    out.append({
                        "kind": "type_mismatch",
                        "severity": "medium",
                        "message": f"关系 {t.get('predicate')} 端类型 {tgt_type} 不匹配本体 range {link['target_object']}",
                        "triples": [t],
                        "suggestion": "修正抽取（object_type 应为本体 target_object）",
                    })

        return out
