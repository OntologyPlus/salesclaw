"""AI 范式沉淀服务（本体 Paradigm 实体，新表）。

将已闭环的有效执行（Execution）沉淀为通用解题范式 Paradigm，可跨代表复用。
由编排器 derive_paradigm 意图触发（经七步状态机，落 reasoning_chain_id + provenance），
也可经 API /decision/paradigm/derive 显式触发。
"""
import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from database import Paradigm
from core.ai_output_schema import generate_trace_id

logger = logging.getLogger("ai_paradigm_service")


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
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def list_paradigms(db: Session, tenant_id: str, domain: Optional[str] = None) -> list:
    """列出范式库（按域筛选）"""
    q = db.query(Paradigm).filter_by(tenant_id=tenant_id)
    if domain:
        q = q.filter_by(domain=domain)
    rows = q.order_by(Paradigm.effectiveness_score.desc(), Paradigm.usage_count.desc()).limit(100).all()
    return [
        {
            "id": p.id,
            "domain": p.domain,
            "problem_type": p.problem_type,
            "title": p.title,
            "effective_method": p.effective_method,
            "evidence_execution_ids": p.evidence_execution_ids or [],
            "usage_count": p.usage_count,
            "effectiveness_score": p.effectiveness_score,
            "reasoning_chain_id": getattr(p, "reasoning_chain_id", None),
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in rows
    ]


async def derive_paradigm(db: Session, tenant_id: str, execution_id: int, domain: str) -> dict:
    """从已闭环执行沉淀范式（落新 Paradigm 表）。

    主链路经 Orchestrator 七步状态机（derive_paradigm 意图），获得结构化范式 +
    推理链（ReasoningChain）与真实 provenance（model_version / run_id）。
    mock 模式下编排器同样跑七步，仅底层 LLM 返回 INTENT_RESPONSES 静态 JSON。
    编排器整体失败时降级到 followup_loop_service 的确定性抽取。
    """
    message = f"将执行 {execution_id} 在 {domain} 域的闭环经验沉淀为可复用解题范式"
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
            intent="derive_paradigm",
            user=str(execution_id),
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
                "intent": "derive_paradigm",
                "agent": result.get("agent_used"),
                "model_version": prov.get("model_version"),
                "run_id": prov.get("run_id"),
            }
            source = "ai"
            trace_id = result.get("trace_id") or trace_id
    except Exception as exc:
        logger.warning("AI 范式编排失败，降级确定性抽取: %s", exc)
        parsed = None

    # 兜底：确定性抽取（保持业务逻辑单一真相源）
    if not parsed:
        from services import followup_loop_service
        parsed = followup_loop_service.extract_paradigms(db, tenant_id, execution_id, domain) or {}

    pdata = parsed.get("paradigm") if isinstance(parsed.get("paradigm"), dict) else parsed
    paradigm_id = None
    if pdata and pdata.get("problem_type"):
        existing = (
            db.query(Paradigm)
            .filter_by(tenant_id=tenant_id, domain=domain, problem_type=pdata.get("problem_type", ""))
            .first()
        )
        if existing:
            existing.usage_count = (existing.usage_count or 0) + 1
            existing.evidence_execution_ids = (existing.evidence_execution_ids or []) + [execution_id]
            if pdata.get("effectiveness_score"):
                existing.effectiveness_score = max(
                    existing.effectiveness_score or 0, int(pdata["effectiveness_score"] * 100)
                    if isinstance(pdata["effectiveness_score"], float) else pdata["effectiveness_score"]
                )
            try:
                setattr(existing, "reasoning_chain_id", reasoning_chain_id)
            except Exception:
                pass
            db.commit()
            db.refresh(existing)
            paradigm_id = existing.id
        else:
            p = Paradigm(
                tenant_id=tenant_id,
                domain=domain,
                problem_type=pdata.get("problem_type", ""),
                title=pdata.get("title", ""),
                effective_method=pdata.get("effective_method", ""),
                evidence_execution_ids=[execution_id],
                usage_count=1,
                effectiveness_score=int(pdata.get("effectiveness_score", 0) * 100)
                if isinstance(pdata.get("effectiveness_score"), float) else pdata.get("effectiveness_score", 0),
            )
            try:
                setattr(p, "reasoning_chain_id", reasoning_chain_id)
            except Exception:
                pass
            db.add(p)
            db.commit()
            db.refresh(p)
            paradigm_id = p.id

    return {
        "paradigm_id": paradigm_id,
        "execution_id": execution_id,
        "domain": domain,
        "source": source,
        "reasoning_chain_id": reasoning_chain_id,
        "provenance": provenance,
        "trace_id": trace_id,
        "extracted": parsed,
    }
