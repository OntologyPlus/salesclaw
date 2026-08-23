"""跨会话交接 - 会话摘要与待办传承

save_handoff：从当前会话高重要性情景记忆 + 推理结论生成摘要，存入 SemanticMemory
load_handoff：从 SemanticMemory 读取最近一次交接信息，供新会话继承
"""
import json
from datetime import datetime

from database import EpisodicMemory, SemanticMemory


# 可选导入 ReasoningChain（存在则使用，不存在则降级）
try:
    from database import ReasoningChain
    _HAS_REASONING = True
except ImportError:
    ReasoningChain = None
    _HAS_REASONING = False


class SessionHandoff:
    """跨会话交接"""

    HANDOFF_CATEGORY = "handoff"
    IMPORTANCE_THRESHOLD = 7

    # ──────────────────────────────────────────────
    # 保存交接
    # ──────────────────────────────────────────────
    def save_handoff(self, user_id, tenant_id, session_id, db) -> dict:
        """保存会话交接信息

        - 取当前会话 importance>=7 的情景记忆
        - 取最近推理结论（ReasoningChain 可导入时）
        - 生成摘要并存储到 SemanticMemory（category="handoff"）
        """
        if db is None:
            return {"summary": "", "key_decisions": [], "pending_todos": []}

        tid = str(tenant_id)
        uid = int(user_id) if user_id is not None else None

        # 1. 取当前会话高重要性情景记忆
        ep_q = db.query(EpisodicMemory).filter(
            EpisodicMemory.tenant_id == tid,
            EpisodicMemory.is_deleted == 0,
            EpisodicMemory.importance >= self.IMPORTANCE_THRESHOLD,
        )
        if uid is not None:
            ep_q = ep_q.filter(EpisodicMemory.user_id == uid)
        if session_id is not None:
            ep_q = ep_q.filter(EpisodicMemory.session_id == str(session_id))
        ep_items = ep_q.order_by(EpisodicMemory.occurred_at.desc()).limit(20).all()

        # 2. 取最近推理结论（如可导入）
        reasoning_items = []
        if _HAS_REASONING and ReasoningChain is not None:
            rc_q = db.query(ReasoningChain).filter(
                ReasoningChain.tenant_id == tid,
                ReasoningChain.is_deleted == 0,
            )
            if uid is not None:
                rc_q = rc_q.filter(ReasoningChain.user_id == uid)
            if session_id is not None:
                rc_q = rc_q.filter(ReasoningChain.session_id == str(session_id))
            reasoning_items = rc_q.order_by(ReasoningChain.ts.desc()).limit(10).all()

        # 3. 生成会话摘要
        summary_parts = []
        for it in ep_items:
            text = it.summary or (it.content or "")[:120]
            summary_parts.append(f"- [{it.importance}/10] {text}")
        for rc in reasoning_items:
            if rc.conclusion:
                summary_parts.append(f"- 推理结论：{rc.conclusion[:120]}")
        if not summary_parts:
            summary_parts.append("- 本会话无可提取的关键信息。")
        summary = "会话交接摘要：\n" + "\n".join(summary_parts)

        # 4. 抽取关键决策（来自推理结论 + 高重要性情景记忆）
        key_decisions = []
        for rc in reasoning_items:
            if rc.conclusion:
                key_decisions.append(rc.conclusion)
        for it in ep_items:
            if (it.importance or 0) >= 8:
                key_decisions.append(it.summary or (it.content or "")[:80])

        # 5. 抽取待办（从情景记忆内容中匹配待办类关键词）
        pending_todos = []
        todo_keywords = ["待办", "todo", "任务", "跟进", "下周", "明天", "计划"]
        for it in ep_items:
            content = it.content or ""
            for kw in todo_keywords:
                if kw in content:
                    idx = content.find(kw)
                    snippet = content[max(0, idx - 10): idx + 80].strip()
                    pending_todos.append(snippet)
                    break

        # 6. 存储到 SemanticMemory（category="handoff"），value 为 JSON
        payload = {
            "summary": summary,
            "key_decisions": key_decisions,
            "pending_todos": pending_todos,
            "last_session_id": str(session_id) if session_id is not None else None,
            "saved_at": datetime.utcnow().isoformat(),
            "episodic_count": len(ep_items),
            "reasoning_count": len(reasoning_items),
        }
        handoff_mem = SemanticMemory(
            tenant_id=tid,
            user_id=uid,
            category=self.HANDOFF_CATEGORY,
            key=f"handoff-{session_id or datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            value=json.dumps(payload, ensure_ascii=False),
            confidence=80,
        )
        db.add(handoff_mem)
        db.commit()
        db.refresh(handoff_mem)

        return {
            "summary": summary,
            "key_decisions": key_decisions,
            "pending_todos": pending_todos,
        }

    # ──────────────────────────────────────────────
    # 加载交接
    # ──────────────────────────────────────────────
    def load_handoff(self, user_id, tenant_id, db) -> dict:
        """加载最近一次会话交接信息"""
        empty = {
            "summary": "",
            "key_decisions": [],
            "pending_todos": [],
            "last_session_id": None,
        }
        if db is None:
            return empty

        tid = str(tenant_id)
        uid = int(user_id) if user_id is not None else None
        q = db.query(SemanticMemory).filter(
            SemanticMemory.tenant_id == tid,
            SemanticMemory.is_deleted == 0,
            SemanticMemory.category == self.HANDOFF_CATEGORY,
        )
        if uid is not None:
            q = q.filter(SemanticMemory.user_id == uid)
        latest = q.order_by(SemanticMemory.created_at.desc()).first()
        if latest is None:
            return empty

        # 解析 value（JSON）
        try:
            payload = json.loads(latest.value)
        except (json.JSONDecodeError, TypeError):
            return {
                "summary": latest.value or "",
                "key_decisions": [],
                "pending_todos": [],
                "last_session_id": None,
            }

        return {
            "summary": payload.get("summary", ""),
            "key_decisions": payload.get("key_decisions", []),
            "pending_todos": payload.get("pending_todos", []),
            "last_session_id": payload.get("last_session_id"),
        }


# 全局单例
session_handoff = SessionHandoff()


__all__ = ["SessionHandoff", "session_handoff"]
