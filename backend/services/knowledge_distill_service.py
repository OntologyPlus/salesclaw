"""F7: 知识蒸馏 + 人审发布（借鉴诊断体系 §8.1-8.3）

蒸馏流程：
1. extract_closure_cases — 从 F8 闭环 task 抽取案例
2. distill_with_llm — LLM 蒸馏候选知识项
3. deduplicate — TF-IDF 相似度去重（>0.85 合并）
4. bind_evidence — 绑定源案例 task_id
5. submit_for_review — 写入 KnowledgeItem(status=candidate)
6. review_item — 人审决策（approve/reject/request_revision）
7. publish_item — 发布为正式知识

权限过滤策略：
- admin: 全部 knowledge_space + 全部 sensitivity_level
- compliance_officer: enterprise + compliance，全部 sensitivity_level
- regional_manager: enterprise + domain + org，normal + sensitive
- sales_rep / pharma_rep: enterprise + domain + position，normal
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import (
    Task,
    KnowledgeItem,
    KnowledgeReview,
    BusinessSessionLocal,
)
from core.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 权限过滤
# ──────────────────────────────────────────────

_ROLE_PERMISSIONS = {
    "admin": {
        "spaces": None,  # None = 全部
        "sensitivities": None,
    },
    "compliance_officer": {
        "spaces": {"enterprise", "compliance"},
        "sensitivities": None,
    },
    "regional_manager": {
        "spaces": {"enterprise", "domain", "org"},
        "sensitivities": {"normal", "sensitive"},
    },
    "sales_rep": {
        "spaces": {"enterprise", "domain", "position"},
        "sensitivities": {"normal"},
    },
    "pharma_rep": {
        "spaces": {"enterprise", "domain", "position"},
        "sensitivities": {"normal"},
    },
}


def _get_role_filter(role: str) -> dict:
    """获取角色权限过滤配置"""
    return _ROLE_PERMISSIONS.get(role, _ROLE_PERMISSIONS["sales_rep"])


def _apply_permission_filter(q, role: str):
    """对 KnowledgeItem 查询应用权限过滤"""
    perm = _get_role_filter(role)
    if perm["spaces"] is not None:
        q = q.filter(KnowledgeItem.knowledge_space.in_(perm["spaces"]))
    if perm["sensitivities"] is not None:
        q = q.filter(KnowledgeItem.sensitivity_level.in_(perm["sensitivities"]))
    return q


# ──────────────────────────────────────────────
# 1. 提取闭环案例
# ──────────────────────────────────────────────

def extract_closure_cases(db: Session, tenant_id: str, limit: int = 20) -> List[dict]:
    """提取已闭环的 task 案例

    查询条件：status=completed AND closure_state=closed
    """
    tasks = db.query(Task).filter(
        Task.tenant_id == tenant_id,
        Task.is_deleted == 0,
        Task.status == "completed",
        Task.closure_state == "closed",
    ).order_by(Task.completed_at.desc()).limit(limit).all()

    cases = []
    for t in tasks:
        cases.append({
            "task_id": t.id,
            "title": t.title,
            "description": t.description,
            "target_metrics": t.target_metric_json or [],
            "achieved_metrics": t.achieved_metric_json or [],
            "source_project": t.source_project,
            "related_type": t.related_type,
            "related_id": t.related_id,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "action_items": [],  # 可扩展：从 AuditLog 提取动作序列
        })
    return cases


# ──────────────────────────────────────────────
# 2. LLM 蒸馏候选
# ──────────────────────────────────────────────

def distill_with_llm(cases: List[dict], llm_client=None) -> List[dict]:
    """调用 LLM 从案例中蒸馏候选知识项

    返回候选列表（不带 id，待写入数据库）。
    LLM 不可用时降级为模板化蒸馏。
    """
    if not cases:
        return []

    # 优先尝试 LLM 蒸馏
    if llm_client is not None:
        try:
            return _distill_via_llm(cases, llm_client)
        except Exception as e:
            logger.warning("[distill] LLM 蒸馏失败，降级为模板化: %s", e)

    # 降级：按 source_project 分组，每组生成一个候选
    return _distill_via_template(cases)


def _distill_via_llm(cases: List[dict], llm_client) -> List[dict]:
    """通过 LLM 蒸馏"""
    import json
    cases_text = "\n".join([
        f"- 案例 #{c['task_id']}：{c['title']}（领域={c.get('source_project', 'unknown')}）"
        for c in cases
    ])
    prompt = f"""请从以下闭环案例中蒸馏共性知识，输出 JSON 数组（不要 markdown 代码块）：
{cases_text}

每个候选知识项需包含：
- title: 标题（≤80字）
- category: rule/case/experience/discussion/trend
- applicable_scene: 适用场景描述
- root_cause_tags: 根因标签数组
- action_steps: 执行步骤数组
- target_metrics: 目标指标数组
- source_task_ids: 来源案例 task_id 数组

输出格式：[{{"title": "...", "category": "...", ...}}]"""
    resp = llm_client.chat([
        {"role": "system", "content": "你是知识蒸馏专家，输出必须是合法 JSON 数组。"},
        {"role": "user", "content": prompt},
    ])
    content = resp.get("content", "") if isinstance(resp, dict) else str(resp)
    # 尝试解析 JSON
    try:
        candidates = json.loads(content)
        if not isinstance(candidates, list):
            return []
        return candidates
    except Exception:
        # 尝试提取 [...]
        start = content.find("[")
        end = content.rfind("]")
        if start >= 0 and end > start:
            try:
                return json.loads(content[start:end + 1])
            except Exception:
                pass
        return []


def _distill_via_template(cases: List[dict]) -> List[dict]:
    """模板化蒸馏（降级方案）"""
    # 按 source_project 分组
    groups: Dict[str, List[dict]] = {}
    for c in cases:
        key = c.get("source_project") or "general"
        groups.setdefault(key, []).append(c)

    candidates = []
    for domain, group_cases in groups.items():
        titles = [c["title"] for c in group_cases]
        candidate = {
            "title": f"{domain} 域闭环经验总结（{len(group_cases)} 个案例）",
            "category": "experience",
            "applicable_scene": f"适用于 {domain} 领域的同类业务场景",
            "root_cause_tags": [domain, "闭环案例"],
            "action_steps": [f"参考案例 {t}" for t in titles[:5]],
            "target_metrics": [],
            "source_task_ids": [c["task_id"] for c in group_cases],
            "knowledge_space": "domain",
        }
        candidates.append(candidate)
    return candidates


# ──────────────────────────────────────────────
# 3. 去重
# ──────────────────────────────────────────────

def deduplicate(db: Session, tenant_id: str, candidates: List[dict]) -> List[dict]:
    """对候选去重

    计算每个候选与已发布 KnowledgeItem 的 title+applicable_scene TF-IDF 相似度。
    > 0.85 合并到现有 item 的 evidence_json；<= 0.85 保留为新候选。
    """
    if not candidates:
        return []

    existing_items = db.query(KnowledgeItem).filter(
        KnowledgeItem.tenant_id == tenant_id,
        KnowledgeItem.is_deleted == 0,
        KnowledgeItem.status.in_(["published", "approved", "candidate"]),
    ).all()

    # 计算已有项的文本
    existing_texts = []
    for it in existing_items:
        text = (it.title or "") + " " + (it.applicable_scene or "")
        existing_texts.append((it, text))

    # 使用 sklearn TF-IDF 计算相似度
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        has_tfidf = True
    except ImportError:
        has_tfidf = False

    # Jaccard 兜底
    def _jaccard(a: str, b: str) -> float:
        sa = set(a.lower().split())
        sb = set(b.lower().split())
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)

    unique_candidates = []
    for cand in candidates:
        cand_text = (cand.get("title", "") + " " + cand.get("applicable_scene", "")).strip()
        best_sim = 0.0
        best_item = None

        if has_tfidf and existing_texts:
            try:
                corpus = [t for _, t in existing_texts] + [cand_text]
                vectorizer = TfidfVectorizer()
                matrix = vectorizer.fit_transform(corpus)
                sims = cosine_similarity(matrix[-1], matrix[:-1])[0]
                idx = int(sims.argmax())
                best_sim = float(sims[idx])
                best_item = existing_texts[idx][0]
            except Exception:
                has_tfidf = False

        if not has_tfidf:
            for it, text in existing_texts:
                sim = _jaccard(cand_text, text)
                if sim > best_sim:
                    best_sim = sim
                    best_item = it

        if best_sim > 0.85 and best_item is not None:
            # 合并到已有 item：追加 source_task_ids
            existing_sources = set(best_item.source_cases_json or [])
            for tid in cand.get("source_task_ids", []):
                existing_sources.add(tid)
            best_item.source_cases_json = list(existing_sources)
            logger.info("[distill] 候选合并到已存在 item_id=%s (sim=%.2f)",
                        best_item.id, best_sim)
        else:
            unique_candidates.append(cand)

    return unique_candidates


# ──────────────────────────────────────────────
# 4. 提交人审
# ──────────────────────────────────────────────

def submit_for_review(
    db: Session, tenant_id: str, candidate: dict,
    distilled_by: str = "ai",
) -> KnowledgeItem:
    """写入 KnowledgeItem(status=candidate) 并发布事件"""
    if not candidate.get("title"):
        raise ValidationError("候选知识项缺少 title")

    item = KnowledgeItem(
        tenant_id=tenant_id,
        title=candidate["title"],
        category=candidate.get("category", "experience"),
        knowledge_space=candidate.get("knowledge_space", "domain"),
        applicable_scene=candidate.get("applicable_scene"),
        preconditions=candidate.get("preconditions", []),
        root_cause_tags=candidate.get("root_cause_tags", []),
        action_steps=candidate.get("action_steps", []),
        target_metrics=candidate.get("target_metrics", []),
        observation_period_days=candidate.get("observation_period_days", 30),
        evidence_json=candidate.get("evidence", []),
        status="candidate",
        source_cases_json=candidate.get("source_task_ids", []),
        distilled_by=distilled_by,
        distilled_at=datetime.utcnow(),
        sensitivity_level=candidate.get("sensitivity_level", "normal"),
    )
    db.add(item)
    db.flush()

    # 触发事件
    try:
        from ai.event_bus import publish
        publish("knowledge_candidate_submitted", {
            "item_id": item.id, "title": item.title, "tenant_id": tenant_id,
        })
    except Exception as e:
        logger.debug("[distill] 事件发布失败: %s", e)

    db.commit()
    db.refresh(item)
    logger.info("[distill] 候选知识项已提交 item_id=%s title=%s", item.id, item.title)
    return item


# ──────────────────────────────────────────────
# 5. 人审决策
# ──────────────────────────────────────────────

def review_item(
    db: Session, tenant_id: str, item_id: int,
    reviewer_id: int, decision: str, comment: str = "",
) -> KnowledgeItem:
    """人审决策

    decision: approve / reject / request_revision
    """
    item = db.query(KnowledgeItem).filter(
        KnowledgeItem.tenant_id == tenant_id,
        KnowledgeItem.is_deleted == 0,
        KnowledgeItem.id == item_id,
    ).first()
    if not item:
        raise NotFoundError(f"知识项 {item_id} 不存在")
    if item.status != "candidate":
        raise ValidationError(f"知识项状态 {item.status} 不可人审")

    valid_decisions = {"approve", "reject", "request_revision"}
    if decision not in valid_decisions:
        raise ValidationError(f"decision 必须是 {valid_decisions} 之一")

    # 更新状态
    if decision == "approve":
        item.status = "approved"
    elif decision == "reject":
        item.status = "rejected"
    else:  # request_revision
        item.status = "candidate"  # 退回，保持 candidate
    item.reviewed_by = reviewer_id
    item.reviewed_at = datetime.utcnow()
    item.review_note = comment

    # 写入 KnowledgeReview
    review = KnowledgeReview(
        tenant_id=tenant_id,
        item_id=item.id,
        reviewer_id=reviewer_id,
        decision=decision,
        comment=comment,
        reviewed_at=datetime.utcnow(),
    )
    db.add(review)

    # 触发事件
    try:
        from ai.event_bus import publish
        event_name = {
            "approve": "knowledge_reviewed",
            "reject": "knowledge_rejected",
            "request_revision": "knowledge_reviewed",
        }[decision]
        publish(event_name, {
            "item_id": item.id, "decision": decision,
            "reviewer_id": reviewer_id, "tenant_id": tenant_id,
        })
    except Exception as e:
        logger.debug("[distill] 事件发布失败: %s", e)

    db.commit()
    db.refresh(item)
    logger.info("[distill] 知识项 %s 已人审：decision=%s", item_id, decision)
    return item


# ──────────────────────────────────────────────
# 6. 发布
# ──────────────────────────────────────────────

def publish_item(
    db: Session, tenant_id: str, item_id: int, publisher_id: int,
) -> KnowledgeItem:
    """发布知识项（仅 approved 状态可发布）"""
    item = db.query(KnowledgeItem).filter(
        KnowledgeItem.tenant_id == tenant_id,
        KnowledgeItem.is_deleted == 0,
        KnowledgeItem.id == item_id,
    ).first()
    if not item:
        raise NotFoundError(f"知识项 {item_id} 不存在")
    if item.status != "approved":
        raise ValidationError(f"知识项状态 {item.status} 不可发布（需 approved）")

    item.status = "published"
    item.published_at = datetime.utcnow()

    # 写入 KnowledgeReview
    review = KnowledgeReview(
        tenant_id=tenant_id,
        item_id=item.id,
        reviewer_id=publisher_id,
        decision="publish",
        comment="发布为正式知识",
        reviewed_at=datetime.utcnow(),
    )
    db.add(review)

    # 触发事件
    try:
        from ai.event_bus import publish
        publish("knowledge_published", {
            "item_id": item.id, "title": item.title, "tenant_id": tenant_id,
        })
    except Exception as e:
        logger.debug("[distill] 事件发布失败: %s", e)

    db.commit()
    db.refresh(item)
    logger.info("[distill] 知识项 %s 已发布", item_id)
    return item


# ──────────────────────────────────────────────
# 7. 查询与检索
# ──────────────────────────────────────────────

def list_candidates(db: Session, tenant_id: str, role: str = "admin",
                    limit: int = 50) -> List[dict]:
    """列出待审核候选"""
    q = db.query(KnowledgeItem).filter(
        KnowledgeItem.tenant_id == tenant_id,
        KnowledgeItem.is_deleted == 0,
        KnowledgeItem.status == "candidate",
    )
    q = _apply_permission_filter(q, role)
    items = q.order_by(KnowledgeItem.distilled_at.desc()).limit(limit).all()
    return [_serialize_item(i) for i in items]


def list_items(db: Session, tenant_id: str, role: str = "admin",
                category: Optional[str] = None, limit: int = 50) -> List[dict]:
    """列出已发布知识项"""
    q = db.query(KnowledgeItem).filter(
        KnowledgeItem.tenant_id == tenant_id,
        KnowledgeItem.is_deleted == 0,
        KnowledgeItem.status == "published",
    )
    if category:
        q = q.filter(KnowledgeItem.category == category)
    q = _apply_permission_filter(q, role)
    items = q.order_by(KnowledgeItem.published_at.desc()).limit(limit).all()
    return [_serialize_item(i) for i in items]


def get_item(db: Session, tenant_id: str, item_id: int, role: str = "admin") -> dict:
    """查询单条知识项"""
    q = db.query(KnowledgeItem).filter(
        KnowledgeItem.tenant_id == tenant_id,
        KnowledgeItem.is_deleted == 0,
        KnowledgeItem.id == item_id,
    )
    q = _apply_permission_filter(q, role)
    item = q.first()
    if not item:
        raise NotFoundError(f"知识项 {item_id} 不存在或无权限访问")
    return _serialize_item(item)


def search_items(
    db: Session, tenant_id: str, query: str,
    role: str = "admin", category: Optional[str] = None, limit: int = 10,
) -> List[dict]:
    """TF-IDF 语义检索（带权限过滤）"""
    q = db.query(KnowledgeItem).filter(
        KnowledgeItem.tenant_id == tenant_id,
        KnowledgeItem.is_deleted == 0,
        KnowledgeItem.status == "published",
    )
    if category:
        q = q.filter(KnowledgeItem.category == category)
    q = _apply_permission_filter(q, role)
    items = q.limit(200).all()  # 取 Top 200 候选再排序

    if not items or not query.strip():
        return [_serialize_item(i) for i in items[:limit]]

    # 构建 corpus：title + applicable_scene + root_cause_tags
    def _text(it: KnowledgeItem) -> str:
        tags = " ".join(it.root_cause_tags or [])
        return f"{it.title or ''} {it.applicable_scene or ''} {tags}"

    corpus = [_text(it) for it in items] + [query]

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        vectorizer = TfidfVectorizer()
        matrix = vectorizer.fit_transform(corpus)
        sims = cosine_similarity(matrix[-1], matrix[:-1])[0]
        ranked = sorted(zip(items, sims), key=lambda x: x[1], reverse=True)[:limit]
        return [_serialize_item(it) for it, _ in ranked]
    except ImportError:
        # Jaccard 兜底
        def _jaccard(a: str, b: str) -> float:
            sa, sb = set(a.lower().split()), set(b.lower().split())
            if not sa or not sb:
                return 0.0
            return len(sa & sb) / len(sa | sb)
        ranked = sorted(items, key=lambda it: _jaccard(_text(it), query), reverse=True)
        return [_serialize_item(it) for it in ranked[:limit]]


# ──────────────────────────────────────────────
# 8. 蒸馏编排（端到端）
# ──────────────────────────────────────────────

def run_distill_pipeline(
    db: Session, tenant_id: str, llm_client=None, case_limit: int = 20,
) -> dict:
    """端到端执行蒸馏流程：提取案例 → LLM 蒸馏 → 去重 → 提交人审

    Returns:
        {extracted_cases, distilled_candidates, unique_candidates, submitted_items}
    """
    # 1. 提取案例
    cases = extract_closure_cases(db, tenant_id, limit=case_limit)
    if not cases:
        return {
            "extracted_cases": 0,
            "distilled_candidates": 0,
            "unique_candidates": 0,
            "submitted_items": [],
            "message": "无已闭环案例可供蒸馏",
        }

    # 2. LLM 蒸馏
    candidates = distill_with_llm(cases, llm_client)

    # 3. 去重
    unique = deduplicate(db, tenant_id, candidates)

    # 4. 提交人审
    submitted = []
    for cand in unique:
        try:
            item = submit_for_review(db, tenant_id, cand, distilled_by="ai")
            submitted.append(item.id)
        except Exception as e:
            logger.warning("[distill] 候选提交失败: %s", e)

    return {
        "extracted_cases": len(cases),
        "distilled_candidates": len(candidates),
        "unique_candidates": len(unique),
        "submitted_items": submitted,
        "message": f"已提交 {len(submitted)} 个候选知识项待人审",
    }


# ──────────────────────────────────────────────
# 序列化
# ──────────────────────────────────────────────

def _serialize_item(it: KnowledgeItem) -> dict:
    return {
        "id": it.id,
        "title": it.title,
        "category": it.category,
        "knowledge_space": it.knowledge_space,
        "applicable_scene": it.applicable_scene,
        "preconditions": it.preconditions or [],
        "root_cause_tags": it.root_cause_tags or [],
        "action_steps": it.action_steps or [],
        "target_metrics": it.target_metrics or [],
        "observation_period_days": it.observation_period_days,
        "evidence": it.evidence_json or [],
        "status": it.status,
        "reviewed_by": it.reviewed_by,
        "reviewed_at": it.reviewed_at.isoformat() if it.reviewed_at else None,
        "review_note": it.review_note,
        "published_at": it.published_at.isoformat() if it.published_at else None,
        "validity_score": it.validity_score,
        "success_samples": it.success_samples,
        "failure_samples": it.failure_samples,
        "source_cases": it.source_cases_json or [],
        "distilled_by": it.distilled_by,
        "distilled_at": it.distilled_at.isoformat() if it.distilled_at else None,
        "sensitivity_level": it.sensitivity_level,
    }


__all__ = [
    "extract_closure_cases",
    "distill_with_llm",
    "deduplicate",
    "submit_for_review",
    "review_item",
    "publish_item",
    "list_candidates",
    "list_items",
    "get_item",
    "search_items",
    "run_distill_pipeline",
]
