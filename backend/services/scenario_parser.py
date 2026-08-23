"""训练场景剧本解析服务（N+2 Step2）

用户粘贴对话/纪要/顾虑 → AI 解析为完整结构化 JSON → 自动匹配画像。
三步创建：(1) 基本信息 (2) AI 角色设定 (3) 标签+知识关联
"""
import json
import logging
import asyncio
from sqlalchemy.orm import Session

from core.exceptions import ValidationError
from database import PracticeScenario
from services import persona_service
from ai.llm_client import llm_client

logger = logging.getLogger(__name__)


# 默认五维评分模板（开场/洞察/专业/风控/推进）
DEFAULT_SCORING_RULES = [
    {"dimension": "开场", "weight": 20, "standard": "破冰自然，表明来意与价值"},
    {"dimension": "洞察", "weight": 20, "standard": "准确识别客户需求与顾虑"},
    {"dimension": "专业", "weight": 25, "standard": "产品知识准确，临床数据支撑"},
    {"dimension": "风控", "weight": 15, "standard": "合规表达，不夸大疗效"},
    {"dimension": "推进", "weight": 20, "standard": "明确下一步行动与承诺"},
]

# 剧本解析提示词
PARSE_PROMPT = """你是医药销售场景解析专家。请将用户粘贴的对话/纪要/顾虑文本，解析为结构化 JSON。

要求：
1. 仅输出一个 JSON 对象，不要 Markdown 代码块标记
2. 字段说明：
   - basic_info: {title, scenario_type, difficulty}  scenario_type 取值 visit/negotiation/objection/dialogue/ppt_speech
   - scenario_background: 背景描述（医院/科室/场合）
   - scenario_description: 场景描述（客户状态、本次目标）
   - ai_roles: [{role_name, persona_brief, objectives[], concerns[]}]  AI 扮演的角色设定
   - generation_notes: 生成备注（给用户的提示）
   - product_knowledge_needs: [产品知识点关键词]

用户文本：
{raw_text}

输出 JSON："""


# ──────────────────────────────────────────────
# 标准话术拆条
# ──────────────────────────────────────────────

def split_standard_scripts(text: str) -> list:
    """按借鉴文档 §5.3 拆条规则拆分标准话术

    - 有 ### 小节标题 → 按小节整块拆条
    - 无 ### → 按 - 行拆条
    - 第一个 ### 之前正文作为独立一条
    """
    if not text or not text.strip():
        return []
    lines = text.strip().split("\n")
    # 是否含 ### 小节
    has_section = any(line.strip().startswith("###") for line in lines)
    if not has_section:
        # 按 - 行拆条
        items = []
        for line in lines:
            s = line.strip()
            if s.startswith("-"):
                items.append(s.lstrip("-").strip())
            elif s:
                items.append(s)
        return items
    # 有 ###：按小节整块拆
    sections = []
    current_title = None
    current_body = []
    preamble = []
    in_preamble = True
    for line in lines:
        s = line.strip()
        if s.startswith("###"):
            # 收尾上一节
            if current_title is not None:
                sections.append({"title": current_title, "content": "\n".join(current_body).strip()})
            else:
                if current_body:
                    preamble = current_body[:]
            in_preamble = False
            current_title = s.lstrip("#").strip()
            current_body = []
        else:
            current_body.append(line)
    # 收尾最后一节
    if current_title is not None:
        sections.append({"title": current_title, "content": "\n".join(current_body).strip()})
    # 第一个 ### 之前正文作为独立一条
    result = []
    if preamble:
        result.append({"title": "前言", "content": "\n".join(preamble).strip()})
    result.extend(sections)
    return result


# ──────────────────────────────────────────────
# 剧本解析（LLM）
# ──────────────────────────────────────────────

async def parse_scenario(db: Session, tenant_id: str, raw_text: str) -> dict:
    """解析原始文本为结构化场景 JSON

    流程：
    1. LLM 解析为结构化 JSON
    2. 自动匹配画像（persona_service.match_persona）
    3. 填充默认评分规则
    4. 返回完整结构供前端三步创建使用
    """
    if not raw_text or not raw_text.strip():
        raise ValidationError("raw_text 不能为空")

    messages = [
        {"role": "system", "content": "你是医药销售场景解析专家，只输出 JSON。"},
        {"role": "user", "content": PARSE_PROMPT.format(raw_text=raw_text[:4000])},
    ]
    result = await llm_client.async_chat(
        messages=messages, intent="scene", temperature=0.2, max_tokens=1500, tenant_id=tenant_id,
    )
    content = result.get("content", "")
    parsed = _safe_parse_json(content)

    # LLM 解析失败时降级为模板
    if not parsed:
        parsed = _fallback_parse(raw_text)

    # 自动匹配画像
    persona = persona_service.match_persona(db, tenant_id, raw_text)
    if persona:
        parsed["matched_persona"] = persona
        # 注入到 ai_roles 第一项
        roles = parsed.get("ai_roles") or []
        if roles:
            roles[0]["persona_id"] = persona.get("id")
            roles[0]["persona_name"] = persona.get("name")
            if not roles[0].get("persona_brief"):
                roles[0]["persona_brief"] = persona.get("default_brief")
        parsed["ai_roles"] = roles

    # 填充默认评分规则
    parsed["scoring_rules"] = DEFAULT_SCORING_RULES
    parsed["generated_by"] = result.get("provider", "mock")
    return parsed


def _safe_parse_json(content: str) -> dict:
    """容错解析 LLM 输出的 JSON"""
    if not content:
        return {}
    # 去除可能的 Markdown 代码块标记
    s = content.strip()
    if s.startswith("```"):
        # 去掉首行 ```json 或 ```
        lines = s.split("\n")
        s = "\n".join(lines[1:])
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # 尝试提取第一个 { ... } 块
        start = s.find("{")
        end = s.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(s[start:end + 1])
            except json.JSONDecodeError:
                pass
    return {}


def _fallback_parse(raw_text: str) -> dict:
    """LLM 解析失败时的降级模板"""
    return {
        "basic_info": {
            "title": "新场景（待编辑）",
            "scenario_type": "visit",
            "difficulty": "medium",
        },
        "scenario_background": "请补充背景信息",
        "scenario_description": raw_text[:200],
        "ai_roles": [
            {"role_name": "客户", "persona_brief": "待设定", "objectives": [], "concerns": []},
        ],
        "generation_notes": "LLM 解析失败，已降级为模板，请手工编辑",
        "product_knowledge_needs": [],
    }


# ──────────────────────────────────────────────
# 三步创建：保存解析结果为 PracticeScenario
# ──────────────────────────────────────────────

def save_parsed_scenario(db: Session, tenant_id: str, user_id: int, data: dict) -> dict:
    """将解析结果保存为 PracticeScenario 草稿

    data 字段：
    - title, scenario_type, difficulty
    - customer_profile（背景+描述合并）
    - persona_id
    - ai_role_config（ai_roles 结构化）
    - scoring_rules
    - standard_scripts（拆条后）
    - knowledge_needs
    - product_id（可选）
    """
    basic = data.get("basic_info") or {}
    title = data.get("title") or basic.get("title") or "新场景"
    scenario_type = data.get("scenario_type") or basic.get("scenario_type") or "visit"
    difficulty = data.get("difficulty") or basic.get("difficulty") or "medium"

    background = data.get("scenario_background") or ""
    description = data.get("scenario_description") or ""
    customer_profile = f"{background}\n\n{description}".strip() if (background or description) else None

    ai_roles = data.get("ai_roles") or []
    ai_role_config = ai_roles[0] if ai_roles else {}

    scripts_raw = data.get("standard_scripts_text") or ""
    standard_scripts = split_standard_scripts(scripts_raw) if scripts_raw else []

    sc = PracticeScenario(
        tenant_id=tenant_id,
        title=title,
        scenario_type=scenario_type,
        difficulty=difficulty,
        customer_profile=customer_profile,
        product_id=data.get("product_id"),
        persona_id=data.get("persona_id"),
        ai_role_config=ai_role_config,
        scoring_rules=data.get("scoring_rules") or DEFAULT_SCORING_RULES,
        standard_scripts=standard_scripts,
        knowledge_needs=data.get("knowledge_needs") or [],
        is_published=0,
    )
    db.add(sc)
    db.commit()
    db.refresh(sc)
    return _serialize_scenario(sc)


def _serialize_scenario(sc: PracticeScenario) -> dict:
    return {
        "id": sc.id,
        "title": sc.title,
        "scenario_type": sc.scenario_type,
        "difficulty": sc.difficulty,
        "description": sc.description,
        "customer_profile": sc.customer_profile,
        "product_id": sc.product_id,
        "persona_id": sc.persona_id,
        "ai_role_config": sc.ai_role_config or {},
        "scoring_rules": sc.scoring_rules or [],
        "standard_scripts": sc.standard_scripts or [],
        "knowledge_needs": sc.knowledge_needs or [],
        "ppt_url": sc.ppt_url,
        "ppt_pages": sc.ppt_pages or [],
        "pass_score": sc.pass_score,
        "scoring_dimensions": sc.scoring_dimensions or [],
        "is_published": sc.is_published,
        "created_at": sc.created_at.strftime("%Y-%m-%d %H:%M:%S") if sc.created_at else None,
    }
