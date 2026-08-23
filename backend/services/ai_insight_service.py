"""通用 AI 洞察服务

被各模块的 /ai-insights 端点复用，提供领域特定的 AI 洞察生成能力。
- mock 模式：返回预设洞察模板
- LLM 模式：调用 llm_client 生成洞察

架构：
  - /ai-insights 端点 → get_cached_insight() 查表（< 50ms）
  - 定时任务（每天）→ generate_and_store_insight() 预生成
  - 未命中缓存 → 降级到 _DOMAIN_INSIGHTS 预设
"""
import json
import logging
import time
from datetime import date, datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 领域洞察预设模板（mock 模式使用）
# ──────────────────────────────────────────────

_DOMAIN_INSIGHTS = {
    "audit": {
        "summary": "审计分析：近 7 天操作平稳，高风险操作占比 2.3%，无异常行为模式。",
        "insights": [
            {"type": "anomaly", "level": "info", "message": "高频操作集中在拜访记录创建（42%）和课程报名（18%）"},
            {"type": "risk", "level": "warning", "message": "检测到 3 次批量删除操作，建议复核"},
            {"type": "pattern", "level": "info", "message": "非工作时间操作占比 8%，处于正常范围"},
        ],
        "recommendations": [
            "建议对批量删除操作增加二次确认",
            "非工作时间操作日志保留 90 天",
        ],
        "risk_alerts": [],
    },
    "cfm": {
        "summary": "会议论坛分析：本月 3 场会议已完成，话题活跃度环比上升 15%。",
        "insights": [
            {"type": "engagement", "level": "info", "message": "「Q3 产品策略」话题讨论最活跃（23 条回复）"},
            {"type": "trend", "level": "info", "message": "学术类话题热度上升，合规类话题热度下降"},
            {"type": "risk", "level": "warning", "message": "1 场会议参会率低于 60%，建议加强提醒"},
        ],
        "recommendations": [
            "为低参会率会议设置自动提醒",
            "引导更多学术话题讨论",
        ],
        "risk_alerts": [],
    },
    "crm": {
        "summary": "客户关系分析：32 位活跃客户中，5 位存在流失风险，2 位为高价值 KOL。",
        "insights": [
            {"type": "churn_risk", "level": "warning", "message": "王教授近 45 天无拜访记录，流失风险高"},
            {"type": "opportunity", "level": "info", "message": "李主任近期互动积极，适合推荐新产品"},
            {"type": "kol", "level": "info", "message": "张院长为核心 KOL，影响力覆盖 3 家三甲医院"},
        ],
        "recommendations": [
            "优先跟进 5 位流失风险客户，安排本周拜访",
            "为 2 位 KOL 定制专属学术合作方案",
            "李主任适合作为新产品首批推荐对象",
        ],
        "risk_alerts": [
            {"customer": "王教授", "risk": "high", "reason": "45 天未拜访"},
        ],
    },
    "mdm": {
        "summary": "数据治理分析：主数据整体质量评分 87/100，2 项规则触发告警。",
        "insights": [
            {"type": "quality", "level": "info", "message": "医生数据完整度 92%，医院数据完整度 88%"},
            {"type": "consistency", "level": "warning", "message": "3 条医生记录的科室字段与标准不符"},
            {"type": "duplicate", "level": "info", "message": "检测到 1 组疑似重复医院记录"},
        ],
        "recommendations": [
            "修正 3 条医生科室字段",
            "合并疑似重复医院记录",
            "建立数据质量月度巡检机制",
        ],
        "risk_alerts": [],
    },
    "observability": {
        "summary": "系统健康分析：整体可用性 99.8%，AI 响应延迟 P95=320ms，状态正常。",
        "insights": [
            {"type": "performance", "level": "info", "message": "API 平均延迟 85ms，P95=210ms"},
            {"type": "ai_metrics", "level": "info", "message": "AI 命中率 73%，幻觉拦截率 2.1%，缓存命中率 41%"},
            {"type": "capacity", "level": "warning", "message": "数据库存储使用率 78%，建议扩容"},
        ],
        "recommendations": [
            "数据库存储将在 30 天内达到 90%，建议提前扩容",
            "AI 缓存命中率可优化至 50%+，建议调整 TTL",
        ],
        "risk_alerts": [],
    },
    "platform": {
        "summary": "平台运营分析：10 个租户活跃，资源利用率均衡，无瓶颈。",
        "insights": [
            {"type": "usage", "level": "info", "message": "日活用户 156，环比上升 8%"},
            {"type": "resource", "level": "info", "message": "CPU 均值 23%，内存均值 45%"},
            {"type": "bottleneck", "level": "info", "message": "无性能瓶颈，各模块响应时间正常"},
        ],
        "recommendations": [
            "用户增长趋势良好，建议扩容 AI 并发配额",
            "优化高频接口的缓存策略",
        ],
        "risk_alerts": [],
    },
    "settings": {
        "summary": "个性化分析：基于您的使用习惯，推荐 3 项配置优化。",
        "insights": [
            {"type": "preference", "level": "info", "message": "您最常使用销售模块（42%），建议设为默认首页"},
            {"type": "notification", "level": "info", "message": "当前通知频率适中，无打扰风险"},
            {"type": "ai_tuning", "level": "info", "message": "AI 主动建议频率可调至「积极」模式"},
        ],
        "recommendations": [
            "将销售总览设为默认首页",
            "启用 AI 积极建议模式获取更多主动洞察",
            "设置每日 9:00 接收 KPI 摘要推送",
        ],
        "risk_alerts": [],
    },
    "tools": {
        "summary": "工具使用分析：最常使用「拜访总结生成」和「周报生成器」。",
        "insights": [
            {"type": "usage", "level": "info", "message": "拜访总结生成器使用 23 次（本周）"},
            {"type": "recommendation", "level": "info", "message": "「异议处理话术」工具适合您的客户反馈模式"},
            {"type": "trend", "level": "info", "message": "AI 类工具使用占比 65%，呈上升趋势"},
        ],
        "recommendations": [
            "尝试使用「异议处理话术」工具处理近期价格异议",
            "「临床文献检索」可辅助您准备学术拜访",
        ],
        "risk_alerts": [],
    },
    "sales": {
        "summary": "销售执行分析：本月拜访达成率 92%，覆盖率 71%，ROI 1:3.2，整体表现良好。",
        "insights": [
            {"type": "visit", "level": "info", "message": "本月已完成拜访 23 次，达成率 92%，超目标 2%"},
            {"type": "coverage", "level": "warning", "message": "覆盖率 71% 低于目标 80%，存在 13 家空白医院"},
            {"type": "roi", "level": "info", "message": "线下拜访 ROI 4.1 为最优渠道，会议 ROI 1.8 待优化"},
            {"type": "feedback", "level": "info", "message": "正面反馈占比 62%（上升 8%），1 位医生提出不良反应疑问"},
        ],
        "recommendations": [
            "优先覆盖 5 家潜力三甲空白医院，预计提升覆盖率至 80%",
            "减少低 ROI 会议投入，增加线下拜访频次",
            "跟进不良反应疑问，建议医学部介入",
        ],
        "risk_alerts": [
            {"type": "coverage_gap", "level": "warning", "message": "区域 B 覆盖率仅 65%，低于阈值"},
        ],
    },
    "training": {
        "summary": "智能培训分析：学习路径进度 65%，能力评分 78/100，2 门课程待完成。",
        "insights": [
            {"type": "progress", "level": "info", "message": "当前学习路径进度 65%，预计 2 周内可完成"},
            {"type": "ability", "level": "info", "message": "产品知识 82 分（优秀），拜访技巧 71 分（待提升）"},
            {"type": "course", "level": "warning", "message": "《高效拜访技巧》课程逾期 3 天未完成"},
            {"type": "exam", "level": "info", "message": "最近考试平均分 85，通过率 100%"},
        ],
        "recommendations": [
            "优先完成逾期的《高效拜访技巧》课程",
            "针对拜访技巧短板，推荐 3 门进阶课程",
            "参加本周直播课《Q3 产品策略解读》获取学分",
        ],
        "risk_alerts": [
            {"type": "overdue", "level": "warning", "message": "1 门课程逾期未完成，影响学分获取"},
        ],
    },
    "decision": {
        "summary": "决策支持分析：综合评分 52/100，拜访达成率 33%，存在 2 条预警。",
        "insights": [
            {"type": "kpi", "level": "warning", "message": "拜访达成率 33% 严重低于目标 90%，需紧急关注"},
            {"type": "attribution", "level": "info", "message": "拜访频次贡献度 38%，客户画像匹配度 27%"},
            {"type": "simulation", "level": "info", "message": "模拟显示拜访频次 +20% 可提升 KPI +8.5%"},
            {"type": "alert", "level": "warning", "message": "2 条高优先级预警：覆盖率低于阈值、客户反馈异常"},
        ],
        "recommendations": [
            "立即提升拜访频次，预期 KPI 提升 8.5%",
            "处理 2 条高优先级预警，避免影响季度考核",
            "关注客户画像匹配度，优化目标客户选择",
        ],
        "risk_alerts": [
            {"type": "kpi_gap", "level": "error", "message": "拜访达成率 33%，与目标差距 57%"},
            {"type": "feedback_anomaly", "level": "warning", "message": "客户 C 反馈异常，需跟进"},
        ],
    },
    "collab": {
        "summary": "协同办公分析：5 项待办，2 项待审批，公告触达率 85%。",
        "insights": [
            {"type": "task", "level": "info", "message": "5 项待办中 2 项今日截止，建议优先处理"},
            {"type": "approval", "level": "info", "message": "2 项待审批事项平均等待 1.5 天，效率正常"},
            {"type": "announcement", "level": "info", "message": "最新公告触达率 85%，3 人未读"},
            {"type": "meeting", "level": "info", "message": "本周 1 场会议待参加，参会确认率 70%"},
        ],
        "recommendations": [
            "优先处理今日截止的 2 项待办",
            "跟进 3 位未读公告的同事",
            "确认参加本周会议，提升参会率",
        ],
        "risk_alerts": [],
    },
    "knowledge": {
        "summary": "知识库分析：文档 45 篇，FAQ 23 条，知识覆盖率 78%。",
        "insights": [
            {"type": "coverage", "level": "info", "message": "产品类文档覆盖 92%，合规类文档覆盖 65%"},
            {"type": "faq", "level": "info", "message": "FAQ 命中率 73%，常见问题集中在外发链接和课程报名"},
            {"type": "gap", "level": "warning", "message": "竞品对比类文档缺口较大，仅有 3 篇"},
            {"type": "search", "level": "info", "message": "热门搜索词：「不良反应」「适应症」「报销政策」"},
        ],
        "recommendations": [
            "补充竞品对比文档，至少新增 5 篇",
            "将高频搜索词「不良反应」相关文档置顶",
            "优化 FAQ 分类，提升命中率至 80%+",
        ],
        "risk_alerts": [
            {"type": "gap", "level": "warning", "message": "竞品对比文档不足，影响销售实战"},
        ],
    },
}


# ──────────────────────────────────────────────
# AI 洞察服务
# ──────────────────────────────────────────────

class AIInsightService:
    """通用 AI 洞察服务

    被各模块的 /ai-insights 端点调用，生成领域特定的 AI 洞察。
    """

    def __init__(self):
        from ai.llm_client import llm_client
        self.llm = llm_client

    # ──────────────────────────────────────────────
    # 端点查询入口：优先查缓存表，未命中降级到预设
    # ──────────────────────────────────────────────

    def get_cached_insight(
        self,
        domain: str,
        tenant_id: str = "default",
        user_id: Optional[int] = None,
        db: Any = None,
    ) -> dict:
        """查询预生成的 AI 洞察（端点调用入口）

        查询顺序：
        1. 查 ai_insight_cache 表（今天的记录）
        2. 未命中 → 查最近一条历史记录（7 天内）
        3. 仍未命中 → 降级到 _DOMAIN_INSIGHTS 预设

        Returns:
            {summary, insights, recommendations, risk_alerts, generated_at, source}
        """
        # 无 db 或不支持 domain → 直接返回预设
        preset = _DOMAIN_INSIGHTS.get(domain)
        if db is None or not preset:
            return preset or {
                "summary": f"暂不支持 {domain} 领域的 AI 洞察",
                "insights": [],
                "recommendations": [],
                "risk_alerts": [],
                "source": "none",
            }

        try:
            from database import AIInsightCache

            today = date.today()
            # 1. 查今天的记录
            record = db.query(AIInsightCache).filter(
                AIInsightCache.tenant_id == str(tenant_id),
                AIInsightCache.domain == domain,
                AIInsightCache.insight_date == today,
                AIInsightCache.is_deleted == 0,
            ).first()

            # 2. 未命中 → 查最近 7 天内的记录
            if record is None:
                from datetime import timedelta
                week_ago = today - timedelta(days=7)
                record = db.query(AIInsightCache).filter(
                    AIInsightCache.tenant_id == str(tenant_id),
                    AIInsightCache.domain == domain,
                    AIInsightCache.insight_date >= week_ago,
                    AIInsightCache.is_deleted == 0,
                ).order_by(AIInsightCache.insight_date.desc()).first()

            # 3. 命中缓存 → 返回（F2: 使用 deserialize_from_db 还原结构化 Schema）
            if record:
                from core.ai_output_schema import deserialize_from_db
                result = deserialize_from_db(record)
                return result
        except Exception as e:
            logger.warning(f"查询 AI 洞察缓存失败，降级到预设: {e}")

        # 4. 降级到预设（F2: 包装为结构化 Schema 输出）
        from core.ai_output_schema import build_insight_output, build_provenance, generate_trace_id
        from config import settings
        provenance = build_provenance(
            model_version=settings.LLM_MODEL or "mock",
            rule_versions={"compliance": "v2.2"},
        )
        result = build_insight_output(
            summary=preset.get("summary", ""),
            insights=preset.get("insights", []),
            recommendations=preset.get("recommendations", []),
            risk_alerts=preset.get("risk_alerts", []),
            provenance=provenance,
            trace_id=generate_trace_id(),
            source="preset",
            confidence=0.7,
            human_review_required=False,
        )
        return result

    # ──────────────────────────────────────────────
    # 定时任务入口：预生成并存储洞察
    # ──────────────────────────────────────────────

    def generate_and_store_insight(
        self,
        domain: str,
        tenant_id: str = "default",
        user_id: Optional[int] = None,
        db: Any = None,
        data: Optional[dict] = None,
    ) -> dict:
        """预生成 AI 洞察并存入缓存表（定时任务调用）

        F2 增强（借鉴企业级诊断体系 §4.1、§11.4）：
        - 使用 build_insight_output 构建包含 evidence/provenance/trace_id/confidence 的统一输出
        - 使用 serialize_for_db 序列化存储字段

        流程：
        1. 调用 LLM 或降级到预设生成洞察
        2. 包装为结构化 Schema 输出
        3. upsert 到 ai_insight_cache 表
        4. 返回生成的洞察

        Returns:
            {summary, insights, recommendations, risk_alerts, evidence, provenance,
             trace_id, confidence, needs_human_review, generated_by, generation_ms, source}
        """
        start = time.monotonic()
        today = date.today()

        # F6: 数据质量门禁（借鉴 §5.5）
        gate_decision = "pass"
        gate_info: dict = {}
        if db is not None:
            try:
                from core.data_quality import check_quality_gate
                gate_info = check_quality_gate(db, str(tenant_id), domain)
                gate_decision = gate_info.get("decision", "pass")
                logger.info("[ai_insight] F6 门禁 domain=%s decision=%s completeness=%.4f",
                            domain, gate_decision, gate_info.get("completeness", 1.0))
            except Exception as e:
                logger.warning("[ai_insight] F6 门禁校验异常（降级放行）: %s", e)
                gate_decision = "pass"

        if gate_decision == "cancel":
            # 完全取消：返回低置信预设洞察 + 标记数据断点
            logger.warning("[ai_insight] %s 域数据断点，跳过 LLM 生成，返回低置信预设",
                          domain)
            return self._build_data_blocked_output(domain, gate_info, tenant_id)

        # 生成洞察（LLM 模式尝试真实生成，失败降级到预设）
        insight = self._generate_insight_internal(domain, data or {}, tenant_id)
        generation_ms = int((time.monotonic() - start) * 1000)
        generated_by = "llm" if self.llm.provider == "openai" else "preset"

        # F6: 三档降级标记
        if gate_decision == "delay":
            generated_by = "delayed"  # 标记为延期发布
        elif gate_decision == "partial_cancel":
            generated_by = "partial"  # 标记为部分取消

        # F2: 包装为结构化 Schema 输出
        from core.ai_output_schema import build_insight_output, build_provenance, generate_trace_id
        from config import settings
        provenance = build_provenance(
            model_version=settings.LLM_MODEL or "mock",
            rule_versions={"compliance": "v2.2"},
            run_id=None,  # 由 orchestrator 在 persist 步骤填充
        )
        # confidence 与 needs_human_review 由 LLM 输出决定；Mock 模式默认 0.7 / False
        confidence = insight.get("confidence", 0.7 if generated_by == "preset" else 0.85)
        needs_human_review = insight.get("needs_human_review", False)
        # Mock 模式 evidence 为空数组（计划 §6.2 决策）
        evidence = insight.get("evidence", [])

        # F6: partial_cancel 时降低 confidence 到 0.3
        if gate_decision == "partial_cancel":
            confidence = min(confidence, 0.3)
            needs_human_review = True  # 部分取消的洞察必须人审

        structured_output = build_insight_output(
            summary=insight.get("summary", ""),
            insights=insight.get("insights", []),
            recommendations=insight.get("recommendations", []),
            risk_alerts=insight.get("risk_alerts", []),
            provenance=provenance,
            trace_id=generate_trace_id(),
            source=generated_by,
            evidence=evidence,
            confidence=confidence,
            human_review_required=needs_human_review,
        )

        # 存入缓存表
        if db is not None:
            try:
                from database import AIInsightCache
                from core.ai_output_schema import serialize_for_db
                # 删除今天同 domain 的旧记录
                db.query(AIInsightCache).filter(
                    AIInsightCache.tenant_id == str(tenant_id),
                    AIInsightCache.domain == domain,
                    AIInsightCache.insight_date == today,
                ).delete(synchronize_session=False)

                # 序列化字段
                fields = serialize_for_db(structured_output)
                record = AIInsightCache(
                    tenant_id=str(tenant_id),
                    domain=domain,
                    user_id=user_id,
                    insight_date=today,
                    summary=fields["summary"],
                    insights_json=fields["insights_json"],
                    recommendations_json=fields["recommendations_json"],
                    risk_alerts_json=fields["risk_alerts_json"],
                    generated_by=generated_by,
                    generation_ms=generation_ms,
                    evidence_json=fields["evidence_json"],
                    provenance_json=fields["provenance_json"],
                    trace_id=fields["trace_id"],
                    confidence=fields["confidence"],
                    human_review_required=fields["human_review_required"],
                )
                db.add(record)
                db.commit()
            except Exception as e:
                logger.warning(f"存储 AI 洞察缓存失败: {e}")
                db.rollback()

        structured_output["generated_by"] = generated_by
        structured_output["generation_ms"] = generation_ms
        return structured_output

    def _build_data_blocked_output(self, domain: str, gate_info: dict, tenant_id: str) -> dict:
        """F6: 数据断点时的低置信预设输出

        借鉴诊断体系 §5.5：完整度 < 阈值时停止正式判定，返回低置信洞察 + 标记数据断点。
        """
        from core.ai_output_schema import build_insight_output, build_provenance, generate_trace_id
        from config import settings

        completeness = gate_info.get("completeness", 0.0)
        threshold = gate_info.get("threshold", 0.6)
        repair_task_id = gate_info.get("repair_task_id")

        summary = f"[数据断点] {domain} 域完整度 {completeness:.2%} < 阈值 {threshold:.2%}，无法生成正式 AI 洞察"
        insights = [{
            "type": "data_quality",
            "level": "critical",
            "message": f"{domain} 域数据完整度仅 {completeness:.2%}，已派发补数工单（task_id={repair_task_id}）",
            "evidence": [],
            "rule_reference": "F6-§5.5-data-quality-gate",
            "confidence": 1.0,
            "needs_human_review": True,
        }]
        recommendations = [{
            "action": "等待数据补齐后重新触发洞察生成",
            "priority": "high",
            "rationale": "数据断点期间生成的洞察置信度过低，不可作为决策依据",
            "confidence": 1.0,
            "needs_human_review": True,
        }]
        risk_alerts = [{
            "target": domain,
            "risk": "high",
            "reason": f"数据完整度 {completeness:.2%} < 阈值 {threshold:.2%}",
        }]

        provenance = build_provenance(
            model_version=settings.LLM_MODEL or "mock",
            rule_versions={"compliance": "v2.2", "data_quality": "v1.0"},
            run_id=None,
        )

        structured_output = build_insight_output(
            summary=summary,
            insights=insights,
            recommendations=recommendations,
            risk_alerts=risk_alerts,
            provenance=provenance,
            trace_id=generate_trace_id(),
            source="data_blocked",
            evidence=[],
            confidence=0.1,
            human_review_required=True,
        )
        structured_output["generated_by"] = "data_blocked"
        structured_output["generation_ms"] = 0
        structured_output["gate_info"] = gate_info
        return structured_output

    def _generate_insight_internal(
        self, domain: str, data: dict, tenant_id: str
    ) -> dict:
        """内部生成方法：LLM 优先，失败降级到预设"""
        preset = _DOMAIN_INSIGHTS.get(domain)
        if not preset:
            return {
                "summary": f"暂不支持 {domain} 领域的 AI 洞察",
                "insights": [],
                "recommendations": [],
                "risk_alerts": [],
            }

        if self.llm.provider == "openai":
            try:
                enhanced = self._generate_llm_insight(domain, data, tenant_id)
                if enhanced:
                    return enhanced
            except Exception as e:
                logger.warning(f"LLM 洞察生成失败，降级到预设: {e}")

        return dict(preset)

    # ──────────────────────────────────────────────
    # 向后兼容：保留 generate_insight 方法（直接调用 LLM，不缓存）
    # 新代码应使用 get_cached_insight 或 generate_and_store_insight
    # ──────────────────────────────────────────────

    def generate_insight(
        self,
        domain: str,
        data: Optional[dict] = None,
        tenant_id: str = "default",
        db: Any = None,
        user: Any = None,
    ) -> dict:
        """生成 AI 洞察（向后兼容，实时调用 LLM）

        注意：此方法会实时调用 LLM，可能导致延迟。
        推荐使用 get_cached_insight() 查询预生成缓存。
        """
        preset = _DOMAIN_INSIGHTS.get(domain)
        if not preset:
            return {
                "summary": f"暂不支持 {domain} 领域的 AI 洞察",
                "insights": [],
                "recommendations": [],
                "risk_alerts": [],
            }

        if self.llm.provider == "openai":
            try:
                enhanced = self._generate_llm_insight(domain, data or {}, tenant_id)
                if enhanced:
                    return enhanced
            except Exception as e:
                logger.warning(f"LLM 洞察生成失败，降级到预设: {e}")

        return preset

    async def ai_generate_insight(
        self, domain: str, data: Optional[dict] = None, user_id: Optional[int] = None
    ) -> dict:
        """生成 AI 原生洞察：经 Orchestrator 七步状态机（insight 意图），
        产出结构化洞察 + 统一 provenance + reasoning_chain_id。

        主链路走编排器；编排器整体失败时降级到既有确定性/LLM 洞察逻辑。
        """
        from core.ai_output_schema import generate_trace_id
        trace_id = generate_trace_id()
        tenant_id = getattr(self, "tenant_id", None)
        if data is None:
            data = self._aggregate_data(domain) if hasattr(self, "_aggregate_data") else {}
        import json
        message = (
            f"在 {domain} 域生成智能洞察，输入数据摘要："
            f"{json.dumps(data, ensure_ascii=False, default=str)[:2000]}"
        )
        parsed = None
        reasoning_chain_id = None
        provenance = {"mode": "rule_fallback"}
        source = "rule_fallback"

        try:
            from ai.orchestrator import Orchestrator
            orch = Orchestrator()
            result = await orch.chat(
                message=message,
                intent="insight",
                user=str(user_id) if user_id else domain,
                tenant_id=str(tenant_id) if tenant_id else None,
                db=None,
            )
            resp_text = result.get("response", "")
            parsed = self._safe_parse_json(resp_text)
            if parsed:
                reasoning_chain_id = (
                    result.get("reasoning_chain", {}) or {}
                ).get("chain_id")
                prov = result.get("provenance") or {}
                provenance = {
                    "mode": "ai_orchestrated",
                    "intent": "insight",
                    "agent": result.get("agent_used"),
                    "model_version": prov.get("model_version"),
                    "run_id": prov.get("run_id"),
                }
                source = "ai"
                trace_id = result.get("trace_id") or trace_id
        except Exception as exc:
            logger.warning("AI 洞察编排失败，降级既有逻辑: %s", exc)
            parsed = None

        if not parsed:
            # 降级：既有确定性/LLM 洞察
            fallback = self._generate_insight_internal(domain, data, tenant_id=tenant_id)
            parsed = {
                "summary": fallback.get("summary", ""),
                "insights": fallback.get("insights", []),
                "recommendations": fallback.get("recommendations", []),
                "risk_alerts": fallback.get("risk_alerts", []),
            }

        return {
            "domain": domain,
            "source": source,
            "summary": parsed.get("summary", ""),
            "insights": parsed.get("insights", []),
            "recommendations": parsed.get("recommendations", []),
            "risk_alerts": parsed.get("risk_alerts", []),
            "reasoning_chain_id": reasoning_chain_id,
            "provenance": provenance,
            "trace_id": trace_id,
        }

    @staticmethod
    def _safe_parse_json(content: str):
        """从 LLM/编排器输出中安全解析 JSON（兼容 ```json 围栏与尾部免责声明文本）"""
        if not content:
            return None
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start:end + 1]
        try:
            import json
            return json.loads(text)
        except Exception as e:
            logger.debug("AI 洞察 JSON 解析失败，降级为空: %s", e)
            return None

    def _generate_llm_insight(
        self, domain: str, data: dict, tenant_id: str
    ) -> Optional[dict]:
        domain_names = {
            "audit": "审计日志",
            "cfm": "会议论坛",
            "crm": "客户关系",
            "mdm": "主数据管理",
            "observability": "系统可观测",
            "platform": "平台运营",
            "settings": "个性化设置",
            "tools": "内容工具",
            "sales": "销售执行",
            "training": "智能培训",
            "decision": "决策支持",
            "collab": "协同办公",
            "knowledge": "知识库",
        }
        domain_cn = domain_names.get(domain, domain)

        system_prompt = (
            f"你是 {domain_cn} 领域的 AI 分析助手。基于以下数据生成结构化洞察。\n"
            "输出 JSON 格式：\n"
            '{"summary": "一句话摘要", "insights": [{"type": "...", "level": "info/warning", "message": "..."}], '
            '"recommendations": ["建议1", "建议2"], "risk_alerts": [{"...": "..."}]}\n'
            "只输出 JSON，不要其他文字。"
        )
        user_prompt = f"领域: {domain_cn}\n数据: {json.dumps(data, ensure_ascii=False, default=str)[:2000]}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        result = self.llm.chat(messages=messages, intent=domain, tenant_id=tenant_id)
        content = result.get("content", "")
        if not content:
            return None

        # 尝试解析 JSON
        try:
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
        except (json.JSONDecodeError, AttributeError):
            pass

        return None

    # ──────────────────────────────────────────────
    # N+4 Batch 1.2: 因果洞察 — 基于 data_lineage 构建因果链
    # ──────────────────────────────────────────────

    def generate_causal_insight(self, db, domain: str, tenant_id: str,
                                scope: dict = None) -> dict:
        """生成因果洞察（N+4 新增）

        流程：
        1. 查询近 7 天 data_lineage（该 domain 作为 target）
        2. 构建 3 层因果链（根因 → 中间因素 → 表象）
        3. 写入 InsightChain 表
        4. 反向记录 lineage（insight ← domain data）

        Returns:
            {insight_id, chain, conclusion, confidence, source}
            无 lineage 证据时降级返回 source='fallback'
        """
        from database import InsightChain, DataLineage
        from services.data_lineage_service import record_lineage

        # 1. 收集近 7 天该 domain 的 lineage
        since = datetime.utcnow() - timedelta(days=7)
        lineages = db.query(DataLineage).filter(
            DataLineage.tenant_id == str(tenant_id),
            DataLineage.target_type == domain,
            DataLineage.occurred_at >= since,
            DataLineage.is_deleted == 0,
        ).order_by(DataLineage.occurred_at.desc()).limit(50).all()

        if not lineages:
            return {
                "insight_id": None,
                "chain": [],
                "conclusion": "数据不足，无法生成因果洞察",
                "confidence": 0.0,
                "source": "fallback",
            }

        # 2. 构建 3 层因果链
        chain = self._build_causal_chain(lineages, domain)

        # 3. 写入 InsightChain
        record = InsightChain(
            tenant_id=str(tenant_id),
            domain=domain,
            root_event_type=chain[0].get("source_type", "unknown") if chain else "unknown",
            chain_json=chain,
            conclusion=self._natural_language_conclusion(chain, domain),
            evidence_ids=[r.id for r in lineages[:10]],
            confidence=min(1.0, len(lineages) / 10.0),
            period_start=date.today() - timedelta(days=7),
            period_end=date.today(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        # 4. 反向记录 lineage（insight ← domain data）
        try:
            record_lineage(
                db,
                source={"type": domain, "id": None},
                target={"type": "insight", "id": record.id},
                transformation="insight_generated_from",
                tenant_id=tenant_id,
            )
        except Exception as e:
            logger.warning(f"记录 insight lineage 失败: {e}")

        # 5. 发布 insight_generated 事件（N+4 Batch 3.3 监听）
        try:
            from ai.event_bus import event_bus
            event_bus.publish(
                "insight_generated",
                {"insight_id": record.id, "domain": domain, "tenant_id": tenant_id},
                tenant_id=tenant_id,
                consistency="eventual",
                affected_domains=["decision"],
            )
        except Exception as e:
            logger.debug(f"发布 insight_generated 事件失败: {e}")

        return {
            "insight_id": record.id,
            "chain": chain,
            "conclusion": record.conclusion,
            "confidence": record.confidence,
            "source": "causal",
        }

    def explain_anomaly(self, db, anomaly_id: int) -> dict:
        """自然语言解释异常 — 追溯 anomaly 的上游 lineage

        Args:
            anomaly_id: 异常记录 ID

        Returns:
            {explanation, evidence}
        """
        from services.data_lineage_service import trace_upstream
        upstream = trace_upstream(db, "anomaly", anomaly_id)
        if not upstream:
            return {"explanation": "无可用上游数据", "evidence": []}
        explanation = "异常由以下因素引发：" + "；".join(
            f"{u['source_type']}#{u['source_id']}（{u['transformation']}）"
            for u in upstream[:3]
        )
        return {"explanation": explanation, "evidence": upstream}

    def trace_to_root_cause(self, db, metric: str, scope: dict) -> list[dict]:
        """追溯指标变化的根因（最多 3 层）

        Args:
            metric: 指标名称（如 'sales' / 'visit_count'）
            scope: 范围参数（保留参数）

        Returns:
            因果链列表 [{layer, source_type, source_id, transformation}]
        """
        from core.constants import MAX_CAUSAL_CHAIN_DEPTH
        from services.data_lineage_service import trace_upstream

        chain = []
        current_type = "metric"
        current_id = 0
        # 通过 payload.field 匹配 metric 的 lineage
        # 简化：首次查询 target_type='metric' 的所有记录，取第一条作为入口
        from database import DataLineage
        first_row = db.query(DataLineage).filter(
            DataLineage.target_type == "metric",
            DataLineage.is_deleted == 0,
        ).order_by(DataLineage.occurred_at.desc()).first()

        if first_row:
            current_type = first_row.source_type
            current_id = first_row.source_id
            chain.append({
                "layer": 1,
                "source_type": first_row.source_type,
                "source_id": first_row.source_id,
                "transformation": first_row.transformation,
            })

        # 向上追溯
        for depth in range(1, MAX_CAUSAL_CHAIN_DEPTH):
            upstream = trace_upstream(db, current_type, current_id)
            if not upstream:
                break
            root = upstream[0]
            chain.append({
                "layer": depth + 1,
                "source_type": root["source_type"],
                "source_id": root["source_id"],
                "transformation": root["transformation"],
            })
            current_type = root["source_type"]
            current_id = root["source_id"] or 0

        return chain

    def _build_causal_chain(self, lineages: list, domain: str) -> list[dict]:
        """构建 3 层因果链（根因 → 中间因素 → 表象）

        Args:
            lineages: DataLineage ORM 实例列表（已按时间倒序）
            domain: 阈域名称

        Returns:
            因果链列表 [{layer, type, source_type, transformation, weight}]
        """
        if not lineages:
            return []
        root = lineages[-1]  # 最早的是根因
        middle = lineages[len(lineages) // 2] if len(lineages) > 1 else None
        surface = lineages[0]  # 最新的是表象

        chain = [{
            "layer": 1,
            "type": "root_cause",
            "source_type": root.source_type,
            "transformation": root.transformation,
            "weight": 0.5,
        }]
        if middle:
            chain.append({
                "layer": 2,
                "type": "intermediate",
                "source_type": middle.source_type,
                "transformation": middle.transformation,
                "weight": 0.3,
            })
        chain.append({
            "layer": 3,
            "type": "surface",
            "source_type": surface.source_type,
            "transformation": surface.transformation,
            "weight": 0.2,
        })
        return chain

    def _natural_language_conclusion(self, chain: list, domain: str) -> str:
        """将因果链转为自然语言结论"""
        if not chain:
            return f"{domain} 领域无足够数据生成结论"
        root = chain[0]
        surface = chain[-1]
        return (
            f"{domain} 阈域表象为 {surface.get('source_type')}（权重 {surface.get('weight')}），"
            f"根因可追溯到 {root.get('source_type')}（权重 {root.get('weight')}）"
        )

    def apply_feedback(self, db, suggestion_type: str, domain: str,
                       tenant_id: str = "default") -> dict:
        """N+4 Batch 3.3: AI 学习反馈

        根据某类建议的历史有效率（effectiveness_score），调整对应领域洞察生成的权重。
        - effectiveness_score < 0.3：该 domain 洞察权重 -0.2（最低 0.3）
        - effectiveness_score > 0.7：该 domain 洞察权重 +0.1（最高 1.5）
        - 其他区间：不变

        Args:
            suggestion_type: 建议类型（如 kpi_alert）
            domain: 业务领域（sales/training/collection）
            tenant_id: 租户 ID

        Returns:
            {domain, effectiveness, new_weight, adjusted}
        """
        from ai.proactive_suggestions import proactive_engine

        # 1. 查询该类型建议的历史有效率
        try:
            effectiveness = proactive_engine.effectiveness_score(
                suggestion_type, db, tenant_id=tenant_id
            )
        except Exception as e:
            logger.debug("计算 suggestion 有效性失败，降级为 0.5: %s", e)
            effectiveness = 0.5

        # 2. 读取当前权重（持久化到 Tenant.settings.insight_weights，未配置默认 1.0）
        from database import Tenant
        tenant = db.query(Tenant).filter(Tenant.code == tenant_id).first()
        if not tenant:
            # 兼容 tenant_id 可能是数字 ID 的情况
            try:
                tid = int(tenant_id)
                tenant = db.query(Tenant).filter(Tenant.id == tid).first()
            except (ValueError, TypeError):
                tenant = None
        if not tenant:
            return {"domain": domain, "effectiveness": effectiveness,
                    "new_weight": 1.0, "adjusted": False}

        weights = (tenant.settings or {}).get("insight_weights", {})
        current_weight = weights.get(domain, 1.0)

        # 3. 根据有效率调整权重
        if effectiveness < 0.3:
            new_weight = max(0.3, current_weight - 0.2)
        elif effectiveness > 0.7:
            new_weight = min(1.5, current_weight + 0.1)
        else:
            new_weight = current_weight

        adjusted = abs(new_weight - current_weight) > 1e-6

        # 4. 写回 Tenant.settings
        if adjusted:
            new_settings = dict(tenant.settings or {})
            new_weights = dict(weights)
            new_weights[domain] = new_weight
            new_settings["insight_weights"] = new_weights
            tenant.settings = new_settings
            db.commit()

            # 发布 AI 学习反馈事件
            try:
                from ai.event_bus import event_bus
                event_bus.publish(
                    "suggestion_outcome_evaluated",
                    {
                        "domain": domain,
                        "suggestion_type": suggestion_type,
                        "effectiveness": effectiveness,
                        "old_weight": current_weight,
                        "new_weight": new_weight,
                    },
                    tenant_id=tenant_id,
                    affected_domains=["ai"],
                )
            except Exception as e:
                logger.debug("发布 insight_weight_adapted 事件失败（不影响主流程）: %s", e)

        return {
            "domain": domain,
            "effectiveness": effectiveness,
            "new_weight": new_weight,
            "adjusted": adjusted,
        }


# 全局单例
ai_insight_service = AIInsightService()
