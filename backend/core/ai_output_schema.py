"""F2: AI 输出结构化 Schema（借鉴企业级诊断体系 §4.1、§11.4）

统一 AI 输出结构，支持：
- 结论 (summary)
- 事实证据 (evidence)
- 规则引用 (rule_reference)
- 推测 (rationale)
- 建议 (recommendations)
- 置信度 (confidence)
- 需人审项 (needs_human_review)
- 血缘 (provenance: diagnostic_run_id / data_cutoff / model_version / rule_versions / org_snapshot_id)
- 追踪 ID (trace_id)

借鉴来源：
- §4.1 Agent 输出结构化
- §11.4 API 响应证据结构（result + evidence + provenance + humanReviewRequired + traceId）
"""
import json
import uuid
from datetime import datetime, date
from typing import Any, Optional


def generate_trace_id() -> str:
    """生成追踪 ID（UUID v4）"""
    return str(uuid.uuid4())


def build_provenance(
    model_version: str,
    rule_versions: Optional[dict] = None,
    data_cutoff: Optional[str] = None,
    run_id: Optional[str] = None,
    org_snapshot_id: Optional[str] = None,
) -> dict:
    """构建血缘信息

    Args:
        model_version: LLM 模型版本（如 nvidia/nemotron-3-ultra-550b-a55b）
        rule_versions: 规则版本字典（如 {"compliance": "v1.2", "audit": "v1.0"}）
        data_cutoff: 数据截止时间（ISO 字符串）
        run_id: 诊断运行 ID（可对应 reasoning_chain_id）
        org_snapshot_id: 组织快照 ID（暂留空，后续支持）
    """
    if data_cutoff is None:
        data_cutoff = datetime.utcnow().isoformat() + "Z"
    if rule_versions is None:
        rule_versions = {"compliance": "v2.2"}
    return {
        "diagnostic_run_id": run_id,
        "data_cutoff": data_cutoff,
        "model_version": model_version,
        "rule_versions": rule_versions,
        "org_snapshot_id": org_snapshot_id,
    }


def build_insight_output(
    summary: str,
    insights: list,
    recommendations: list,
    risk_alerts: list,
    provenance: dict,
    trace_id: Optional[str] = None,
    source: str = "preset",
    evidence: Optional[list] = None,
    confidence: float = 0.0,
    human_review_required: bool = False,
    generated_at: Optional[str] = None,
) -> dict:
    """统一构建 AI 洞察输出

    Args:
        summary: 结论文本
        insights: 洞察列表（每项含 type/level/message/evidence/rule_reference/confidence/needs_human_review）
        recommendations: 建议列表（每项含 action/priority/rationale/confidence/needs_human_review）
        risk_alerts: 风险告警列表
        provenance: 血缘信息（由 build_provenance 构建）
        trace_id: 追踪 ID（若 None 则自动生成）
        source: 来源 preset/llm/cache
        evidence: 全局证据列表（可选，与每条 insight 内的证据互补）
        confidence: 整体置信度 0-1
        human_review_required: 是否需人审
        generated_at: 生成时间（若 None 则自动填充）
    """
    if trace_id is None:
        trace_id = generate_trace_id()
    if generated_at is None:
        generated_at = datetime.utcnow().isoformat() + "Z"
    if evidence is None:
        evidence = []

    # 为每条 insight 补充默认字段（若缺失）
    normalized_insights = []
    for ins in insights:
        if isinstance(ins, str):
            ins = {"type": "info", "level": "info", "message": ins}
        normalized_insights.append({
            "type": ins.get("type", "info"),
            "level": ins.get("level", "info"),
            "message": ins.get("message", ""),
            "evidence": ins.get("evidence", []),
            "rule_reference": ins.get("rule_reference"),
            "confidence": ins.get("confidence", confidence),
            "needs_human_review": ins.get("needs_human_review", False),
        })

    # 为每条 recommendation 补充默认字段
    normalized_recs = []
    for rec in recommendations:
        if isinstance(rec, str):
            rec = {"action": rec, "priority": "medium"}
        normalized_recs.append({
            "action": rec.get("action", ""),
            "priority": rec.get("priority", "medium"),
            "rationale": rec.get("rationale"),
            "confidence": rec.get("confidence", confidence),
            "needs_human_review": rec.get("needs_human_review", False),
        })

    return {
        "summary": summary,
        "insights": normalized_insights,
        "recommendations": normalized_recs,
        "risk_alerts": risk_alerts,
        "evidence": evidence,
        "provenance": provenance,
        "trace_id": trace_id,
        "confidence": confidence,
        "needs_human_review": human_review_required,
        "generated_at": generated_at,
        "source": source,
    }


def serialize_for_db(output: dict) -> dict:
    """将输出结构序列化为数据库存储格式（拆分 JSON 字段）

    用于将 build_insight_output 的结果映射到 AIInsightCache 表的各字段。
    """
    return {
        "summary": output.get("summary", ""),
        "insights_json": json.dumps(output.get("insights", []), ensure_ascii=False),
        "recommendations_json": json.dumps(output.get("recommendations", []), ensure_ascii=False),
        "risk_alerts_json": json.dumps(output.get("risk_alerts", []), ensure_ascii=False),
        "evidence_json": json.dumps(output.get("evidence", []), ensure_ascii=False),
        "provenance_json": json.dumps(output.get("provenance", {}), ensure_ascii=False),
        "trace_id": output.get("trace_id"),
        "confidence": output.get("confidence", 0.0),
        "human_review_required": 1 if output.get("needs_human_review") else 0,
    }


def deserialize_from_db(record: Any) -> dict:
    """从数据库记录反序列化为输出结构

    将 AIInsightCache 记录还原为 build_insight_output 的输出格式。
    """
    return {
        "summary": record.summary or "",
        "insights": json.loads(record.insights_json) if record.insights_json else [],
        "recommendations": json.loads(record.recommendations_json) if record.recommendations_json else [],
        "risk_alerts": json.loads(record.risk_alerts_json) if record.risk_alerts_json else [],
        "evidence": json.loads(record.evidence_json) if getattr(record, "evidence_json", None) else [],
        "provenance": json.loads(record.provenance_json) if getattr(record, "provenance_json", None) else {},
        "trace_id": getattr(record, "trace_id", None),
        "confidence": getattr(record, "confidence", 0.0),
        "needs_human_review": bool(getattr(record, "human_review_required", 0)),
        "generated_at": record.insight_date.isoformat() if record.insight_date else None,
        "generated_by": record.generated_by or "preset",
        "source": "cache",
    }


def build_diagnosis_output(
    summary: str,
    level: str,
    confidence: float,
    domain: str,
    signals: Optional[list] = None,
    evidence: Optional[list] = None,
    reasoning_trace: Optional[list] = None,
    provenance: Optional[dict] = None,
    trace_id: Optional[str] = None,
    needs_human_review: bool = True,
    validation_detail: Optional[dict] = None,
    confidence_band: Optional[str] = None,
    action_suggestion: Optional[list] = None,
) -> dict:
    """构建 AI 诊断的结构化输出（驱动 Diagnosis / Signal 实体落库）

    与 build_insight_output 同构但面向"诊断"语义：核心差异在于
    - 顶层带 level（GREEN/YELLOW/RED/BLACK）与 signals 信号列表
    - signals 中每项可解析为独立 Signal 实体

    Args:
        summary: 诊断结论
        level: 诊断级别 GREEN/YELLOW/RED/BLACK
        confidence: 置信度 0-1
        domain: 业务域 coverage/visit/adoption/...
        signals: 信号列表 [{name, category, severity, description, clear_condition}]
        evidence: 证据列表 [{source, metric, value, ref}]
        reasoning_trace: 推理链 [{step, thought, tool, observation}]
        provenance: 血缘信息
        trace_id: 追踪 ID
        needs_human_review: 诊断草稿默认需人工确认（合规闸门）
        validation_detail: OAG Layer 4 结构化校验明细（五维校验结论，来自 hallucination_detector）
        confidence_band: 置信度档位 GREEN/YELLOW/RED（🟢/🟡/🔴 对齐方案，由综合评分派生）
        action_suggestion: 可触发动作建议列表（来自 ontology/actions.recommend_actions_for_diagnosis）
    """
    if trace_id is None:
        trace_id = generate_trace_id()
    if signals is None:
        signals = []
    if evidence is None:
        evidence = []
    if reasoning_trace is None:
        reasoning_trace = []
    if provenance is None:
        provenance = build_provenance(model_version="structured-mock-v1")
    # confidence_band 未显式传入时按 confidence 派生（兜底）
    if confidence_band is None:
        confidence_band = ("GREEN" if confidence >= 0.9
                           else "YELLOW" if confidence >= 0.7 else "RED")

    normalized_signals = []
    for s in signals:
        if isinstance(s, str):
            s = {"name": s, "category": "general", "severity": "medium"}
        normalized_signals.append({
            "name": s.get("name", ""),
            "category": s.get("category", "general"),
            "severity": s.get("severity", "medium"),
            "description": s.get("description", ""),
            "clear_condition": s.get("clear_condition", ""),
        })

    return {
        "summary": summary,
        "level": level,
        "confidence": confidence,
        "domain": domain,
        "signals": normalized_signals,
        "evidence": evidence,
        "reasoning_trace": reasoning_trace,
        "provenance": provenance,
        "trace_id": trace_id,
        "needs_human_review": needs_human_review,
        "validation_detail": validation_detail,
        "confidence_band": confidence_band,
        "action_suggestion": action_suggestion or [],
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def parse_diagnosis_to_entities(output: dict, tenant_id: str, rep_id: int,
                                target_type: Optional[str] = None,
                                target_id: Optional[int] = None) -> dict:
    """将 build_diagnosis_output 的结果解析为 Diagnosis + Signal 实体字段映射

    返回的 dict 含:
    - diagnosis: {tenant_id, rep_id, domain, target_type, target_id, summary,
                  level, confidence, status, evidence, reasoning_trace, provenance,
                  trace_id, confidence_band, validation_detail, action_suggestion}
    - signals:   [{tenant_id, name, category, severity, description, clear_condition}]

    由 ai_diagnosis_service 调用并落库。status 默认 "draft"（待人工确认）。
    """
    diagnosis = {
        "tenant_id": tenant_id,
        "rep_id": rep_id,
        "domain": output.get("domain", "general"),
        "target_type": target_type,
        "target_id": target_id,
        "summary": output.get("summary", ""),
        "level": output.get("level", "YELLOW"),
        "confidence": output.get("confidence", 0.0),
        "status": "draft",
        "evidence": output.get("evidence", []),
        "reasoning_trace": output.get("reasoning_trace", []),
        "provenance": output.get("provenance"),
        "trace_id": output.get("trace_id"),
        "confidence_band": output.get("confidence_band"),
        "validation_detail": output.get("validation_detail"),
        "action_suggestion": output.get("action_suggestion", []),
        "excluded": output.get("excluded", 0),
        "excluded_reason": output.get("excluded_reason", {}),
    }
    signals = []
    for s in output.get("signals", []):
        signals.append({
            "tenant_id": tenant_id,
            "name": s.get("name", ""),
            "category": s.get("category", "general"),
            "severity": s.get("severity", "medium"),
            "description": s.get("description", ""),
            "clear_condition": s.get("clear_condition", ""),
        })
    return {"diagnosis": diagnosis, "signals": signals}


__all__ = [
    "generate_trace_id",
    "build_provenance",
    "build_insight_output",
    "serialize_for_db",
    "deserialize_from_db",
    "build_diagnosis_output",
    "parse_diagnosis_to_entities",
]
