"""混合意图分类器 - 规则 + LLM 双轨分类

四层处理：
1. 规则匹配（复用 INTENT_KEYWORDS，加权匹配）
2. LLM 分类（低置信度时调用，Mock 模式语义兜底）
3. 冲突仲裁（规则 0.4 / LLM 0.6）
4. 反馈校准（基于 IntentFeedback 历史纠正）
"""
import json
import logging
import re
from datetime import datetime
from typing import Optional

from ai.llm_client import llm_client
from ai.orchestrator import INTENT_KEYWORDS, DOMAIN_AGENT_MAP
from database import IntentFeedback

logger = logging.getLogger(__name__)


class HybridIntentClassifier:
    """混合意图分类器（规则 + LLM 双轨）"""

    # 关键词匹配权重
    WEIGHT_EXACT = 1.0       # 精确匹配
    WEIGHT_CONTAINS = 0.7    # 包含匹配
    WEIGHT_FUZZY = 0.4       # 模糊匹配
    # 冲突仲裁权重
    RULE_WEIGHT = 0.4
    LLM_WEIGHT = 0.6
    # 规则直返阈值
    RULE_THRESHOLD = 0.7
    # 模糊匹配 Jaccard 阈值
    FUZZY_THRESHOLD = 0.5

    def __init__(self):
        # 意图列表：(关键词列表, 意图名, domain)
        self.intents = [(list(kws), name, domain) for kws, name, domain in INTENT_KEYWORDS]
        # 意图名 -> domain 映射
        self.intent_domain_map = {name: domain for _, name, domain in INTENT_KEYWORDS}

    def _domain_to_agent(self, domain: Optional[str]) -> str:
        """domain → Agent name 转换"""
        return DOMAIN_AGENT_MAP.get(domain or "", "Supervisor")

    # ──────────────────────────────────────────────
    # Level 1: 规则匹配（加权）
    # ──────────────────────────────────────────────
    def _rule_classify(self, message: str) -> dict:
        """规则匹配：为每个意图计算加权得分，返回最高分意图"""
        message_lower = (message or "").lower().strip()
        # N+5：优先识别 scenario-create 工作流意图（避免被 visit 的"拜访"关键词抢占）
        import re
        if re.search(r"(创建|新建|设计|生成|做一个|建一个|想做).{0,15}场景", message) or "场景创建" in message or "创建培训场景" in message:
            return {
                "intent": "scenario-create",
                "domain": "training",
                "agent": self._domain_to_agent("training"),
                "score": self.WEIGHT_EXACT,  # 1.0 直接达到 RULE_THRESHOLD，规则直返
                "matched_keywords": ["scenario-create-pattern"],
            }
        results = []
        for keywords, intent_name, domain in self.intents:
            best_weight = 0.0
            matched = []
            for kw in keywords:
                kw_lower = kw.lower()
                if not kw_lower:
                    continue
                weight, hit = self._match_keyword(message_lower, kw_lower)
                if hit:
                    matched.append(kw)
                    if weight > best_weight:
                        best_weight = weight
            if best_weight > 0:
                results.append({
                    "intent": intent_name,
                    "domain": domain,
                    "agent": self._domain_to_agent(domain),
                    "score": best_weight,
                    "matched_keywords": matched,
                })
        if not results:
            return {"intent": None, "domain": None, "agent": None, "score": 0.0, "matched_keywords": []}
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[0]

    def _match_keyword(self, message: str, keyword: str) -> tuple:
        """单关键词匹配，返回 (权重, 是否命中)"""
        # 精确匹配
        if message == keyword:
            return self.WEIGHT_EXACT, True
        # 包含匹配
        if keyword in message:
            return self.WEIGHT_CONTAINS, True
        # 模糊匹配：字符级 Jaccard 相似度
        sim = self._char_jaccard(message, keyword)
        if sim >= self.FUZZY_THRESHOLD:
            return self.WEIGHT_FUZZY, True
        return 0.0, False

    @staticmethod
    def _char_jaccard(a: str, b: str) -> float:
        """字符级 Jaccard 相似度"""
        sa, sb = set(a), set(b)
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)

    # ──────────────────────────────────────────────
    # Level 2: LLM 分类
    # ──────────────────────────────────────────────
    def _llm_classify(self, message: str, rule_result: dict) -> dict:
        """LLM 分类：真实模式调用 LLM，Mock 模式使用语义相似度兜底"""
        # Mock 模式：使用简单语义相似度兜底
        if getattr(llm_client, "provider", "mock") == "mock":
            return self._semantic_fallback(message, rule_result)

        # 真实 LLM 调用，要求结构化 JSON 输出
        intent_list = [name for _, name, _ in self.intents]
        prompt = (
            "你是一个意图分类器。根据用户消息，从以下意图中选择最匹配的一个。\n"
            f"可选意图：{', '.join(intent_list)}\n"
            f"用户消息：{message}\n"
            "请以 JSON 格式返回："
            '{"intent": "意图名", "confidence": 0.0-1.0, "reason": "简短原因"}'
        )
        messages = [
            {"role": "system", "content": "你是意图分类助手，只输出 JSON。"},
            {"role": "user", "content": prompt},
        ]
        try:
            result = llm_client.chat(messages, intent="", temperature=0.1, max_tokens=256)
            content = result.get("content", "")
            parsed = self._parse_llm_json(content)
            if parsed:
                intent = parsed.get("intent")
                if intent and intent in self.intent_domain_map:
                    confidence = float(parsed.get("confidence", 0.5))
                    domain = self.intent_domain_map.get(intent)
                    return {
                        "intent": intent,
                        "domain": domain,
                        "agent": self._domain_to_agent(domain),
                        "confidence": confidence,
                    }
        except Exception as e:
            logger.warning("LLM 意图分类失败: %s", e, exc_info=True)
        # 解析失败或异常：降级到语义兜底
        return self._semantic_fallback(message, rule_result)

    def _semantic_fallback(self, message: str, rule_result: dict) -> dict:
        """Mock 模式语义兜底：基于字符集与关键词重合度的简单相似度"""
        message_lower = (message or "").lower()
        best = None
        best_score = 0.0
        for keywords, intent_name, domain in self.intents:
            for kw in keywords:
                kw_lower = kw.lower()
                sim = self._char_jaccard(message_lower, kw_lower)
                # 长度加成：关键词越长匹配越可信
                len_bonus = min(0.2, len(kw_lower) / 50.0)
                score = sim + len_bonus
                if score > best_score:
                    best_score = score
                    best = {
                        "intent": intent_name,
                        "domain": domain,
                        "agent": self._domain_to_agent(domain),
                        # 兜底置信度限制在阈值以下，避免覆盖高置信规则
                        "confidence": min(0.69, score),
                    }
        if best is None:
            return {"intent": None, "domain": None, "agent": None, "confidence": 0.0}
        return best

    @staticmethod
    def _parse_llm_json(content: str) -> Optional[dict]:
        """解析 LLM 返回的 JSON（兼容裸 JSON 与带说明文本）"""
        try:
            return json.loads(content)
        except Exception as e:
            logger.warning("LLM JSON 解析失败: %s", e, exc_info=True)
        # 提取首个 {...} 片段
        match = re.search(r"\{[^{}]*\}", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception as e:
                logger.warning("LLM JSON 片段解析失败: %s", e, exc_info=True)
        return None

    # ──────────────────────────────────────────────
    # Level 3: 冲突仲裁
    # ──────────────────────────────────────────────
    def _arbitrate(self, rule_result: dict, llm_result: dict) -> dict:
        """规则与 LLM 冲突仲裁：规则权重 0.4 / LLM 权重 0.6"""
        rule_intent = rule_result.get("intent")
        rule_score = rule_result.get("score", 0.0)
        llm_intent = llm_result.get("intent")
        llm_conf = llm_result.get("confidence", 0.0)
        matched_keywords = rule_result.get("matched_keywords", [])

        # 无 LLM 结果：采用规则
        if not llm_intent:
            return {
                "intent": rule_intent or "default",
                "domain": rule_result.get("domain"),
                "agent": rule_result.get("agent") or "Supervisor",
                "confidence": rule_score,
                "method": "rule",
                "matched_keywords": matched_keywords,
            }
        # 无规则结果：采用 LLM
        if not rule_intent:
            return {
                "intent": llm_intent,
                "domain": llm_result.get("domain"),
                "agent": llm_result.get("agent", "Supervisor"),
                "confidence": llm_conf,
                "method": "llm",
                "matched_keywords": [],
            }
        # 一致：取较高置信度
        if rule_intent == llm_intent:
            return {
                "intent": rule_intent,
                "domain": rule_result.get("domain") or llm_result.get("domain"),
                "agent": rule_result.get("agent") or llm_result.get("agent"),
                "confidence": max(rule_score, llm_conf),
                "method": "rule" if rule_score >= self.RULE_THRESHOLD else "llm",
                "matched_keywords": matched_keywords,
            }
        # 冲突：加权仲裁
        rule_combined = rule_score * self.RULE_WEIGHT
        llm_combined = llm_conf * self.LLM_WEIGHT
        if rule_combined >= llm_combined:
            return {
                "intent": rule_intent,
                "domain": rule_result.get("domain"),
                "agent": rule_result.get("agent"),
                "confidence": rule_combined,
                "method": "rule",
                "matched_keywords": matched_keywords,
            }
        return {
            "intent": llm_intent,
            "domain": llm_result.get("domain"),
            "agent": llm_result.get("agent", "Supervisor"),
            "confidence": llm_combined,
            "method": "llm",
            "matched_keywords": [],
        }

    # ──────────────────────────────────────────────
    # Level 4: 反馈校准
    # ──────────────────────────────────────────────
    def record_feedback(self, user_id, query, predicted, corrected, tenant_id, db) -> None:
        """记录用户对意图分类的纠正到 IntentFeedback 表"""
        if db is None or user_id is None or tenant_id is None:
            return
        fb = IntentFeedback(
            tenant_id=str(tenant_id),
            user_id=int(user_id),
            query=query,
            predicted_intent=predicted,
            corrected_intent=corrected,
            ts=datetime.utcnow(),
        )
        db.add(fb)
        db.commit()

    def _lookup_feedback(self, user_id, query, tenant_id, db) -> Optional[dict]:
        """查询历史反馈，相同查询自动应用纠正结果"""
        if db is None or user_id is None or tenant_id is None:
            return None
        fb = db.query(IntentFeedback).filter(
            IntentFeedback.tenant_id == str(tenant_id),
            IntentFeedback.user_id == int(user_id),
            IntentFeedback.query == query,
        ).order_by(IntentFeedback.ts.desc()).first()
        if fb:
            corrected = fb.corrected_intent
            domain = self.intent_domain_map.get(corrected)
            return {"intent": corrected, "domain": domain, "agent": self._domain_to_agent(domain), "confidence": 1.0}
        return None

    # ──────────────────────────────────────────────
    # 主入口
    # ──────────────────────────────────────────────
    def classify(self, message, db=None, user_id=None, tenant_id=None) -> dict:
        """意图分类主入口

        Returns:
            {intent, agent, confidence, method: "rule"|"llm"|"feedback", matched_keywords: []}
        """
        if not message or not message.strip():
            return {
                "intent": "default",
                "domain": "global",
                "agent": "Supervisor",
                "confidence": 0.0,
                "method": "rule",
                "matched_keywords": [],
            }

        query = message.strip()

        # Level 4 优先：反馈校准（相同查询直接应用历史纠正）
        if db is not None and user_id is not None and tenant_id is not None:
            fb = self._lookup_feedback(user_id, query, tenant_id, db)
            if fb:
                return {
                    "intent": fb["intent"],
                    "domain": fb.get("domain"),
                    "agent": fb["agent"],
                    "confidence": fb["confidence"],
                    "method": "feedback",
                    "matched_keywords": [],
                }

        # Level 1：规则匹配
        rule_result = self._rule_classify(query)
        if rule_result["score"] >= self.RULE_THRESHOLD:
            return {
                "intent": rule_result["intent"],
                "domain": rule_result.get("domain"),
                "agent": rule_result["agent"],
                "confidence": rule_result["score"],
                "method": "rule",
                "matched_keywords": rule_result["matched_keywords"],
            }

        # Level 2：LLM 分类（低置信度时调用）
        llm_result = self._llm_classify(query, rule_result)

        # Level 3：冲突仲裁
        return self._arbitrate(rule_result, llm_result)


# 全局单例
intent_classifier = HybridIntentClassifier()


__all__ = ["HybridIntentClassifier", "intent_classifier"]
