"""推理链构建与持久化

提供 AI 推理过程的可视化与可追溯能力：
- ReasoningStep：单个推理步骤（演绎 / 归纳 / 溯因）
- ReasoningChainBuilder：构建推理链并持久化到 reasoning_chains 表

数据来源：查询文本、意图、上下文与响应。
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from database import ReasoningChain


# ──────────────────────────────────────────────
# 推理步骤
# ──────────────────────────────────────────────

@dataclass
class ReasoningStep:
    """推理步骤

    Attributes:
        step_id: 步骤序号（从 1 开始）
        type: 推理类型，deduction（演绎）/ induction（归纳）/ abduction（溯因）
        premise: 前提
        conclusion: 结论
        confidence: 置信度，0-1
        evidence: 证据列表
    """
    step_id: int
    type: str
    premise: str
    conclusion: str
    confidence: float
    evidence: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ──────────────────────────────────────────────
# 推理链构建器
# ──────────────────────────────────────────────

class ReasoningChainBuilder:
    """推理链构建器

    负责把一次 AI 推理过程拆解为 deduction → induction → abduction 三步，
    并持久化到 ReasoningChain 表，支持后续查询、反馈与幻觉打分。
    """

    # 推理类型常量
    TYPE_DEDUCTION = "deduction"
    TYPE_INDUCTION = "induction"
    TYPE_ABDUCTION = "abduction"

    def build(
        self,
        query: str,
        intent: str,
        agent: str,
        context: dict,
        response: str,
        user_id: Optional[int] = None,
        tenant_id: str = "default",
        session_id: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> dict:
        """构建推理链并持久化到 reasoning_chains 表

        Args:
            query: 用户查询文本
            intent: 意图标签
            agent: 处理该查询的 Agent 名称
            context: 上下文（业务数据、记忆等）
            response: AI 响应文本
            user_id: 用户 ID
            tenant_id: 租户 ID
            session_id: 会话 ID
            db: 数据库 session；为 None 时不持久化

        Returns:
            推理链 JSON：{chain_id, query, intent, agent, steps, conclusion, confidence}
        """
        # 1. 记录查询与意图（构造步骤时使用）
        steps: list[ReasoningStep] = []

        # 2. 构建推理步骤：演绎 → 归纳 → 溯因
        # 演绎：从意图和规则推导需要的数据/动作
        deduction = self._build_deduction_step(query=query, intent=intent, agent=agent, context=context)
        steps.append(deduction)

        # 归纳：从上下文数据归纳出事实性结论
        induction = self._build_induction_step(intent=intent, context=context)
        steps.append(induction)

        # 溯因：基于响应与上下文给出最佳解释
        abduction = self._build_abduction_step(
            intent=intent, context=context, response=response, induction=induction
        )
        steps.append(abduction)

        # 3. 记录结论与置信度
        conclusion = abduction.conclusion or induction.conclusion or deduction.conclusion
        # 综合置信度：三步加权（归纳权重最高，因基于真实数据）
        confidence = self._aggregate_confidence([deduction.confidence, induction.confidence, abduction.confidence])

        # 持久化前构造返回结构
        chain_payload = {
            "query": query,
            "intent": intent,
            "agent": agent,
            "steps": [s.to_dict() for s in steps],
            "conclusion": conclusion,
            "confidence": confidence,
        }

        # 4. 持久化到 ReasoningChain 表
        chain_id = None
        if db is not None:
            chain_id = self._persist(
                db=db,
                user_id=user_id,
                tenant_id=tenant_id,
                session_id=session_id,
                query=query,
                intent=intent,
                agent=agent,
                steps=chain_payload["steps"],
                conclusion=conclusion,
                confidence=confidence,
            )
        chain_payload["chain_id"] = chain_id
        # 把 chain_id 放到返回结构最前面，便于消费方读取
        ordered = {"chain_id": chain_id}
        ordered.update(chain_payload)
        return ordered

    # ──────────────────────────────────────────────
    # 步骤构建
    # ──────────────────────────────────────────────

    def _build_deduction_step(
        self, query: str, intent: str, agent: str, context: dict
    ) -> ReasoningStep:
        """演绎步骤：从意图和规则推导需要查询的数据或动作"""
        # 基于意图推断需要查询的数据类型
        intent_to_data = {
            "visit": "拜访记录与计划数据",
            "coverage": "覆盖矩阵与分管数据",
            "feedback": "拜访反馈数据",
            "course": "课程与学习路径数据",
            "kpi": "KPI 指标数据",
            "alert": "预警与异常数据",
            "knowledge": "知识库与文档数据",
        }
        required_data = intent_to_data.get(intent, "相关业务数据")
        premise = f"用户意图为「{intent}」，由 Agent「{agent}」处理"
        conclusion = f"需要查询{required_data}以回答用户查询"
        evidence = [
            f"query={query[:80]}",
            f"intent={intent}",
            f"agent={agent}",
        ]
        # 演绎置信度：意图明确时较高
        confidence = 0.85 if intent and intent != "default" else 0.6
        return ReasoningStep(
            step_id=1,
            type=self.TYPE_DEDUCTION,
            premise=premise,
            conclusion=conclusion,
            confidence=confidence,
            evidence=evidence,
        )

    def _build_induction_step(self, intent: str, context: dict) -> ReasoningStep:
        """归纳步骤：从上下文数据归纳事实性结论"""
        # 从 context 中提取关键数据点作为证据
        evidence: list[str] = []
        facts: list[str] = []

        if not context:
            premise = "无可用上下文数据"
            conclusion = "基于空上下文，无法形成数据归纳"
            return ReasoningStep(
                step_id=2,
                type=self.TYPE_INDUCTION,
                premise=premise,
                conclusion=conclusion,
                confidence=0.4,
                evidence=evidence,
            )

        # 提取常见业务字段作为证据
        candidate_keys = [
            "visit_count", "coverage_rate", "positive_rate", "total_points",
            "course_completion", "avg_exam", "comprehensive_score", "completion",
        ]
        for key in candidate_keys:
            if key in context and isinstance(context[key], (int, float)):
                evidence.append(f"{key}={context[key]}")

        # 针对 visit 意图，提取拜访次数类数据
        if intent == "visit":
            visit_count = context.get("visit_count") or context.get("actual_visits") or 0
            target = context.get("target_total") or context.get("target_count") or 0
            if target > 0:
                rate = round(visit_count / target * 100, 1)
                facts.append(f"近 30 天拜访 {visit_count} 次，达成率 {rate}%")
                evidence.append(f"achievement_rate={rate}")
            elif visit_count > 0:
                facts.append(f"近 30 天拜访 {visit_count} 次")

        # 针对 coverage 意图
        if intent == "coverage":
            cov = context.get("coverage_rate")
            if cov is not None:
                facts.append(f"当前覆盖率 {cov}%")
                if cov >= 80:
                    facts.append("覆盖良好")
                elif cov >= 50:
                    facts.append("覆盖中等")
                else:
                    facts.append("覆盖不足")

        # 针对 feedback 意图
        if intent == "feedback":
            pos = context.get("positive_rate")
            if pos is not None:
                facts.append(f"反馈正面率 {pos}%")
                if pos >= 70:
                    facts.append("反馈偏正面")
                elif pos >= 40:
                    facts.append("反馈中性")
                else:
                    facts.append("反馈偏负面")

        # 针对 course / training 意图
        if intent in ("course", "training"):
            cc = context.get("course_completion")
            if cc is not None:
                facts.append(f"课程完成率 {cc}%")

        # 通用：综合能力分
        score = context.get("comprehensive_score")
        if score is not None:
            facts.append(f"综合能力分 {score}")

        premise = "基于上下文中的业务数据"
        if facts:
            conclusion = "；".join(facts)
            # 归纳置信度：取决于证据数量
            confidence = min(0.9, 0.55 + 0.08 * len(evidence))
        else:
            conclusion = "上下文未提供足够的量化数据，归纳结论较弱"
            confidence = 0.45

        return ReasoningStep(
            step_id=2,
            type=self.TYPE_INDUCTION,
            premise=premise,
            conclusion=conclusion,
            confidence=confidence,
            evidence=evidence,
        )

    def _build_abduction_step(
        self, intent: str, context: dict, response: str, induction: ReasoningStep
    ) -> ReasoningStep:
        """溯因步骤：基于响应与上下文给出最佳解释"""
        evidence: list[str] = []
        # 取归纳步骤结论作为基础
        induction_conclusion = induction.conclusion or ""

        # 根据上下文判断策略有效性
        if "偏正面" in induction_conclusion or "良好" in induction_conclusion or "达成" in induction_conclusion:
            conclusion = "当前策略有效，建议维持并优化"
            evidence.append("归纳结论偏正面")
            confidence = 0.8
        elif "偏负面" in induction_conclusion or "不足" in induction_conclusion:
            conclusion = "当前策略效果不佳，建议调整拜访节奏与覆盖策略"
            evidence.append("归纳结论偏负面")
            confidence = 0.7
        elif "中性" in induction_conclusion:
            conclusion = "策略效果一般，存在改进空间，建议加强学术拜访与培训"
            evidence.append("归纳结论为中性")
            confidence = 0.65
        else:
            # 兜底：根据响应内容推断
            if response and len(response) > 20:
                conclusion = "AI 响应基于有限上下文生成，建议结合实际数据进一步验证"
                evidence.append("响应已生成但上下文有限")
                confidence = 0.55
            else:
                conclusion = "推理证据不足，建议补充数据后重新分析"
                confidence = 0.4

        # 上下文中若有 score 类指标，进一步提升置信度
        if context.get("comprehensive_score") is not None:
            evidence.append(f"comprehensive_score={context['comprehensive_score']}")
            confidence = min(0.95, confidence + 0.05)

        premise = "基于归纳结论与 AI 响应，推测最佳解释"
        return ReasoningStep(
            step_id=3,
            type=self.TYPE_ABDUCTION,
            premise=premise,
            conclusion=conclusion,
            confidence=confidence,
            evidence=evidence,
        )

    def _aggregate_confidence(self, confidences: list[float]) -> int:
        """综合三步置信度，加权平均后转为 0-100 整数"""
        if not confidences:
            return 50
        # 权重：演绎 0.2 / 归纳 0.5 / 溯因 0.3
        weights = [0.2, 0.5, 0.3]
        if len(confidences) != len(weights):
            # 兜底：等权平均
            avg = sum(confidences) / len(confidences)
        else:
            avg = sum(c * w for c, w in zip(confidences, weights))
        # 限制到 0-1 后转 0-100
        score = int(round(max(0.0, min(1.0, avg)) * 100))
        return score

    # ──────────────────────────────────────────────
    # 持久化与查询
    # ──────────────────────────────────────────────

    def _persist(
        self,
        db: Session,
        user_id: Optional[int],
        tenant_id: str,
        session_id: Optional[str],
        query: str,
        intent: str,
        agent: str,
        steps: list,
        conclusion: str,
        confidence: int,
    ) -> Optional[int]:
        """写入 ReasoningChain 表"""
        try:
            record = ReasoningChain(
                tenant_id=tenant_id,
                user_id=user_id or 0,
                session_id=session_id,
                query=query,
                intent=intent,
                agent_used=agent,
                steps=steps,
                conclusion=conclusion,
                confidence=confidence,
                reflection_count=0,
                ts=datetime.utcnow(),
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return record.id
        except Exception as exc:
            db.rollback()
            # 持久化失败不影响推理链返回
            print(f"[reasoning_chain] persist failed: {exc}")
            return None

    def get_chains(self, user_id: int, tenant_id: str, db: Session, limit: int = 20) -> list[dict]:
        """获取用户的推理链列表（按时间倒序）"""
        q = db.query(ReasoningChain).filter(
            ReasoningChain.tenant_id == tenant_id,
            ReasoningChain.is_deleted == 0,
            ReasoningChain.user_id == user_id,
        )
        records = q.order_by(ReasoningChain.ts.desc()).limit(max(1, min(limit, 200))).all()
        return [self._to_dict(r) for r in records]

    def get_chain(self, chain_id: int, tenant_id: str, db: Session) -> dict:
        """获取推理链详情"""
        record = db.query(ReasoningChain).filter(
            ReasoningChain.id == chain_id,
            ReasoningChain.tenant_id == tenant_id,
            ReasoningChain.is_deleted == 0,
        ).first()
        if not record:
            return {"error": "not_found", "chain_id": chain_id}
        return self._to_dict(record)

    def add_feedback(
        self,
        chain_id: int,
        tenant_id: str,
        db: Session,
        rating: int,
        feedback_text: Optional[str] = None,
    ) -> dict:
        """添加用户反馈

        Args:
            chain_id: 推理链 ID
            rating: 1-5 分
            feedback_text: 反馈文本
        """
        # 限制 rating 范围
        rating = max(1, min(5, int(rating)))
        record = db.query(ReasoningChain).filter(
            ReasoningChain.id == chain_id,
            ReasoningChain.tenant_id == tenant_id,
            ReasoningChain.is_deleted == 0,
        ).first()
        if not record:
            return {"error": "not_found", "chain_id": chain_id}
        try:
            record.feedback_rating = rating
            if feedback_text is not None:
                record.feedback_text = feedback_text
            db.commit()
            db.refresh(record)
        except Exception as exc:
            db.rollback()
            return {"error": "update_failed", "detail": str(exc)}
        return self._to_dict(record)

    def update_hallucination_score(
        self, chain_id: int, tenant_id: str, db: Session, score: int
    ) -> dict:
        """更新幻觉检测分数

        Args:
            score: 0-100，越高表示幻觉风险越大
        """
        score = max(0, min(100, int(score)))
        record = db.query(ReasoningChain).filter(
            ReasoningChain.id == chain_id,
            ReasoningChain.tenant_id == tenant_id,
            ReasoningChain.is_deleted == 0,
        ).first()
        if not record:
            return {"error": "not_found", "chain_id": chain_id}
        try:
            record.hallucination_score = score
            db.commit()
            db.refresh(record)
        except Exception as exc:
            db.rollback()
            return {"error": "update_failed", "detail": str(exc)}
        return self._to_dict(record)

    # ──────────────────────────────────────────────
    # 序列化
    # ──────────────────────────────────────────────

    @staticmethod
    def _to_dict(record: ReasoningChain) -> dict:
        """将 ReasoningChain ORM 对象序列化为字典"""
        return {
            "chain_id": record.id,
            "user_id": record.user_id,
            "session_id": record.session_id,
            "query": record.query,
            "intent": record.intent,
            "agent_used": record.agent_used,
            "steps": record.steps or [],
            "conclusion": record.conclusion,
            "confidence": record.confidence,
            "feedback_rating": record.feedback_rating,
            "feedback_text": record.feedback_text,
            "hallucination_score": record.hallucination_score,
            "reflection_count": record.reflection_count,
            "ts": record.ts.isoformat() if record.ts else None,
        }


# ──────────────────────────────────────────────
# 全局单例
# ──────────────────────────────────────────────

reasoning_chain_builder = ReasoningChainBuilder()


__all__ = ["ReasoningStep", "ReasoningChainBuilder", "reasoning_chain_builder"]
