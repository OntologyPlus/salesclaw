"""AI 诊断编排适配层（本体论 + AI 原生改造核心）。

职责：
1. 调用 Orchestrator 七步状态机（diagnose / attribute 意图），获得结构化推理 +
   推理链（ReasoningChain）+ 真实 provenance（model_version / run_id）
2. 将输出经 ai_output_schema 解析为 Diagnosis / Signal 实体字段并落库
3. 诊断状态机流转（draft → confirmed → executing → verified → closed）
4. 编排器整体失败时降级到 decision_service 的确定性规则计算

设计要点：
- 实体创建与状态确认分离：AI 生成 Diagnosis(status=draft)，需 API 确认后流转，
  满足药企"AI 不自动执行"合规约束
- mock 与真实 LLM 均走同一编排器七步状态机（guardrails→cache→intent→slot→
  agent+reflection→hallucination→persist），仅 llm_client 内部 provider 分支不同
"""
import json
import logging
from typing import Optional, Any

from sqlalchemy.orm import Session

from database import Diagnosis, Signal
from core.ai_output_schema import (
    build_diagnosis_output,
    parse_diagnosis_to_entities,
    generate_trace_id,
)
from services import decision_service

logger = logging.getLogger("ai_diagnosis_service")


def _parse_provenance(value: Any) -> Optional[dict]:
    """落库的 provenance 为 JSON 字符串，返回前端前解析回 dict"""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _safe_parse_json(content: str) -> Optional[dict]:
    """从 LLM/编排器输出中安全解析 JSON（兼容 ```json 围栏与尾部免责声明文本）"""
    if not content:
        return None
    text = content.strip()
    # 去除 ```json ... ``` 围栏
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    # 截取首尾大括号之间的纯净 JSON（剥离尾部"仅供参考"等免责后缀）
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


async def run_diagnosis(
    db: Session,
    tenant_id: str,
    rep_id: int,
    domain: str,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    user: Optional[str] = None,
) -> dict:
    """对代表/医院/科室在某业务域运行 AI 诊断，生成 Diagnosis 草稿 + Signal 实体。

    主链路经 Orchestrator 七步状态机（diagnose 意图），获得结构化推理 +
    推理链（ReasoningChain）与真实 provenance（model_version / run_id）。
    mock 模式下编排器同样跑七步，仅底层 LLM 返回 INTENT_RESPONSES 静态 JSON。

    返回 {diagnosis_id, status, level, summary, signal_count, source,
         reasoning_chain_id, provenance, trace_id}
    """
    message = (
        f"请对代表 {rep_id} 在 {domain} 域进行诊断"
        + (f"（{target_type}:{target_id}）" if target_type else "")
    )
    parsed = None
    reasoning_chain_id = None
    provenance = {"mode": "rule_fallback"}
    trace_id = generate_trace_id()
    source = "rule_fallback"

    try:
        from ai.orchestrator import Orchestrator
        orch = Orchestrator()
        result = await orch.chat(
            message=message,
            intent="diagnose",
            user=str(rep_id),
            tenant_id=tenant_id,
            db=db,
        )
        resp_text = result.get("response", "")
        parsed = _safe_parse_json(resp_text)
        if parsed:
            reasoning_chain_id = (
                result.get("reasoning_chain", {}) or {}
            ).get("chain_id")
            prov = result.get("provenance") or {}
            provenance = {
                "mode": "ai_orchestrated",
                "intent": "diagnose",
                "agent": result.get("agent_used"),
                "model_version": prov.get("model_version"),
                "run_id": prov.get("run_id"),
            }
            source = "ai"
            trace_id = result.get("trace_id") or trace_id
    except Exception as exc:  # 编排器整体失败降级
        logger.warning("AI 诊断编排失败，降级规则计算: %s", exc)
        parsed = None

    if parsed:
        out = build_diagnosis_output(
            summary=parsed.get("summary", ""),
            level=parsed.get("level", "YELLOW"),
            confidence=float(parsed.get("confidence", 0.0)),
            domain=domain,
            signals=parsed.get("signals", []),
            evidence=parsed.get("evidence", []),
            reasoning_trace=parsed.get("reasoning_trace", []),
            provenance=provenance,
            trace_id=trace_id,
        )
    else:
        # 降级：复用 decision_service 确定性诊断
        rule = decision_service.evaluate_diagnosis(db, tenant_id, rep_id)
        out = build_diagnosis_output(
            summary=rule.get("summary", "规则诊断结论"),
            level=rule.get("light", "YELLOW"),
            confidence=0.6,
            domain=domain,
            signals=[],
            evidence=[{"source": "rule", "metric": "light", "value": rule.get("light")}],
            provenance=provenance,
            trace_id=trace_id,
        )

    # ── OAG Layer 4/5 借鉴点：注入结构化校验明细 + 置信度档位 + 可触发动作 ──
    try:
        from ai.hallucination_detector import HallucinationDetector
        from ontology.actions import recommend_actions_for_diagnosis

        detector = HallucinationDetector()
        det_resp = detector.detect(response=out["summary"], context={}, ontology_data={})
        validation_detail = det_resp.get("validation_detail") or {}
        # score 以诊断 confidence 为准（更准确），其余维度明细来自检测器
        validation_detail["score"] = out["confidence"]
        confidence_band = (
            det_resp.get("confidence_band")
            or ("GREEN" if out["confidence"] >= 0.9
                else "YELLOW" if out["confidence"] >= 0.7 else "RED")
        )
        action_suggestion = recommend_actions_for_diagnosis(out["level"], out["domain"])
        out["validation_detail"] = validation_detail
        out["confidence_band"] = confidence_band
        out["action_suggestion"] = action_suggestion
    except Exception as exc:  # 安全降级：不阻断主流程
        logger.warning("OAG 校验/动作推荐失败，跳过附加字段: %s", exc)

    # ── 误判排除闸（方案第五章 O14）：红/黄灯受结构性因素驱动时降级并标记 ──
    try:
        from ai.exclusion_gate import evaluate as exclusion_evaluate
        gate = exclusion_evaluate(out, context={
            "tenant_id": tenant_id, "rep_id": rep_id,
            "domain": domain, "target_type": target_type, "target_id": target_id,
        })
        if gate["excluded"]:
            # 高危灯降级，避免误报浪费一线精力
            out["level"] = gate["degraded_level"]
            # 置信度档位随 level 同步刷新
            out["confidence_band"] = (
                "GREEN" if gate["degraded_level"] == "GREEN"
                else "YELLOW" if gate["degraded_level"] in ("YELLOW",)
                else out.get("confidence_band", "YELLOW")
            )
        out["excluded"] = 1 if gate["excluded"] else 0
        out["excluded_reason"] = gate["excluded_reason"] or {}
    except Exception as exc:  # 安全降级：不阻断主流程
        logger.warning("误判排除闸执行失败，跳过: %s", exc)
        out["excluded"] = 0
        out["excluded_reason"] = {}


    entities = parse_diagnosis_to_entities(out, tenant_id, rep_id, target_type, target_id)

    # provenance 列是 Text，需序列化为 JSON 字符串后落库
    diag_payload = dict(entities["diagnosis"])
    try:
        diag_payload["provenance"] = json.dumps(diag_payload.get("provenance"), ensure_ascii=False)
    except Exception:
        pass

    diag = Diagnosis(**diag_payload)
    # P1: 关联编排器推理链（新增列，缺失时忽略不阻断落库）
    try:
        setattr(diag, "reasoning_chain_id", reasoning_chain_id)
    except Exception:
        pass
    db.add(diag)
    db.flush()
    for s in entities["signals"]:
        db.add(Signal(diagnosis_id=diag.id, **s))
    db.commit()
    db.refresh(diag)

    # 返回给前端的 provenance 恢复为 dict（落库已序列化为字符串）
    try:
        prov_return = json.loads(diag.provenance) if diag.provenance else provenance
    except (json.JSONDecodeError, TypeError):
        prov_return = provenance

    return {
        "diagnosis_id": diag.id,
        "status": diag.status,
        "level": diag.level,
        "summary": diag.summary,
        "confidence": diag.confidence,
        "signal_count": len(entities["signals"]),
        "trace_id": diag.trace_id,
        "source": source,
        "reasoning_chain_id": getattr(diag, "reasoning_chain_id", None),
        "provenance": prov_return,
        "excluded": getattr(diag, "excluded", 0) or 0,
        "excluded_reason": getattr(diag, "excluded_reason", None) or {},
    }


def confirm_diagnosis(db: Session, tenant_id: str, diagnosis_id: int,
                      user: Optional[str] = None) -> dict:
    """人工确认诊断草稿 → confirmed（合规闸门，AI 不自动执行）"""
    diag = db.query(Diagnosis).filter_by(id=diagnosis_id, tenant_id=tenant_id).first()
    if not diag:
        return {"ok": False, "error": "diagnosis_not_found"}
    if diag.status != "draft":
        return {"ok": False, "error": "not_draft", "status": diag.status}
    diag.status = "confirmed"
    diag.confirmed_at = __import__("datetime").datetime.utcnow()
    db.commit()
    return {"ok": True, "diagnosis_id": diag.id, "status": diag.status}


def advance_diagnosis(db: Session, tenant_id: str, diagnosis_id: int,
                      to_status: str, user: Optional[str] = None) -> dict:
    """推进诊断状态机（confirmed→executing→verified→closed），需 API 触发"""
    diag = db.query(Diagnosis).filter_by(id=diagnosis_id, tenant_id=tenant_id).first()
    if not diag:
        return {"ok": False, "error": "diagnosis_not_found"}
    allowed = {"executing", "verified", "closed"}
    if to_status not in allowed:
        return {"ok": False, "error": "invalid_status", "allowed": list(allowed)}
    diag.status = to_status
    db.commit()
    return {"ok": True, "diagnosis_id": diag.id, "status": diag.status}


def clear_signal(db: Session, tenant_id: str, signal_id: int,
                 user: Optional[str] = None) -> dict:
    """标记信号已消除（需 API 触发）"""
    sig = db.query(Signal).filter_by(id=signal_id, tenant_id=tenant_id).first()
    if not sig:
        return {"ok": False, "error": "signal_not_found"}
    sig.cleared = 1
    sig.cleared_at = __import__("datetime").datetime.utcnow()
    db.commit()
    return {"ok": True, "signal_id": sig.id, "cleared": 1}


def list_diagnoses(db: Session, tenant_id: str, rep_id: Optional[int] = None,
                   status: Optional[str] = None, domain: Optional[str] = None) -> list:
    q = db.query(Diagnosis).filter_by(tenant_id=tenant_id)
    if rep_id is not None:
        q = q.filter_by(rep_id=rep_id)
    if status:
        q = q.filter_by(status=status)
    if domain:
        q = q.filter_by(domain=domain)
    rows = q.order_by(Diagnosis.created_at.desc()).limit(100).all()
    result = []
    for d in rows:
        sigs = db.query(Signal).filter_by(diagnosis_id=d.id).all()
        result.append({
            "id": d.id, "rep_id": d.rep_id, "domain": d.domain,
            "target_type": d.target_type, "target_id": d.target_id,
            "summary": d.summary, "level": d.level, "confidence": d.confidence,
            "status": d.status, "trace_id": d.trace_id,
            "reasoning_chain_id": getattr(d, "reasoning_chain_id", None),
            "provenance": _parse_provenance(d.provenance),
            "confidence_band": getattr(d, "confidence_band", None),
            "validation_detail": getattr(d, "validation_detail", None),
            "action_suggestion": getattr(d, "action_suggestion", None) or [],
            "excluded": getattr(d, "excluded", 0) or 0,
            "excluded_reason": getattr(d, "excluded_reason", None) or {},
            "signals": [{"id": s.id, "name": s.name, "category": s.category,
                         "severity": s.severity, "cleared": s.cleared,
                         "clear_condition": s.clear_condition} for s in sigs],
            "created_at": d.created_at.isoformat() if d.created_at else None,
        })
    return result


async def run_attribution(db: Session, tenant_id: str, rep_id: int, domain: str,
                           target_type: Optional[str] = None, target_id: Optional[int] = None,
                           user: Optional[str] = None) -> dict:
    """运行 AI 归因/根因分析，返回结构化因素与根因（驱动下游 Diagnosis 信号修正）

    主链路经 Orchestrator 七步状态机（attribute 意图），mock 下同样跑七步。
    """
    message = (
        f"分析代表 {rep_id} 在 {domain} 域指标下滑的归因与根因"
        + (f"（{target_type}:{target_id}）" if target_type else "")
    )
    parsed = None
    reasoning_chain_id = None
    provenance = {"mode": "rule_fallback"}
    trace_id = generate_trace_id()

    # L2 关系链推理（确定性规则，独立于 LLM，不阻塞主归因流程）
    try:
        from ontology.chain import infer_relation_chain
        chain_result = infer_relation_chain(
            root_type="User",          # 根对象：医药代表
            root_id=rep_id,
            target_type="Diagnosis",   # 目标：诊断/指标异常
            domain=None,
            max_depth=4,
        )
    except Exception as ce:
        logger.warning("L2 关系链推理失败（已忽略）: %s", ce)
        chain_result = None

    try:
        from ai.orchestrator import Orchestrator
        orch = Orchestrator()
        result = await orch.chat(
            message=message,
            intent="attribute",
            user=str(rep_id),
            tenant_id=tenant_id,
            db=db,
        )
        resp_text = result.get("response", "")
        parsed = _safe_parse_json(resp_text)
        if parsed:
            reasoning_chain_id = (
                result.get("reasoning_chain", {}) or {}
            ).get("chain_id")
            prov = result.get("provenance") or {}
            provenance = {
                "mode": "ai_orchestrated",
                "intent": "attribute",
                "agent": result.get("agent_used"),
                "model_version": prov.get("model_version"),
                "run_id": prov.get("run_id"),
            }
            trace_id = result.get("trace_id") or trace_id
    except Exception as exc:
        logger.warning("AI 归因编排失败，降级规则计算: %s", exc)
        parsed = None

    if parsed and parsed.get("factors"):
        return {
            "source": "ai",
            "summary": parsed.get("summary", ""),
            "level": parsed.get("level", "YELLOW"),
            "confidence": float(parsed.get("confidence", 0.0)),
            "factors": parsed.get("factors", []),
            "root_cause": parsed.get("root_cause", ""),
            "evidence": parsed.get("evidence", []),
            "reasoning_chain_id": reasoning_chain_id,
            "provenance": provenance,
            "trace_id": trace_id,
            "chain": chain_result,
        }
    # 降级：确定性加权归因（无 domain 维度，按综合能力分贡献度）
    rule = decision_service.get_attribution(db, tenant_id, rep_id)
    contributions = rule.get("contributions", [])
    return {
        "source": "rule_fallback",
        "summary": rule.get("ai_summary", "规则归因结论"),
        "level": "YELLOW",
        "confidence": 0.6,
        "factors": [
            {"name": c["dimension"], "contribution": c["contribution"],
             "direction": "negative" if c["value"] < 60 else "positive",
             "evidence": c.get("category", "")}
            for c in contributions
        ],
        "root_cause": rule.get("weaknesses", [{}])[0].get("dimension", "")
        if rule.get("weaknesses") else "",
        "evidence": [{"source": "rule", "metric": "score",
                      "value": rule.get("comprehensive_score")}],
        "reasoning_chain_id": reasoning_chain_id,
        "provenance": provenance,
        "trace_id": trace_id,
        "chain": chain_result,
    }
