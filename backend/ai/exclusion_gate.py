"""误判排除闸（方案第五章 O14 / 第九章示例4）。

诊断产出的红/黄灯，往往并非代表"躺平"，而是受客观结构性因素驱动：
  1. NEW_PRODUCT     新品导入期：产品刚上市，销量/覆盖低属正常爬坡
  2. ACCESS_STAGE     准入阶段：医院尚在准入流程未开发，覆盖低非代表不力
  3. SEASONAL         季节性波动：指标受季节周期影响，YoY 波动属正常
  4. POLICY_SHOCK    政策冲击：VBP 集采中标 / DRG 支付改革致收入骤降
  5. RESTRUCTURE      业务结构调整：产品线剥离 / 团队重组等组织因素

本模块在诊断落库前对 Diagnosis 输出做一次"排除闸"裁定：
- 命中排除信号 → 标记 excluded=True，填充 excluded_reason（类型+说明+证据），
  并将 level 降级为非高危（RED→YELLOW），避免误报浪费一线精力。
- 未命中 → 维持原诊断，excluded=False。

设计要点：
- 纯函数、证据驱动，不依赖 LLM，降级链路安全（异常时视为不命中，绝不误排）。
- 与 AI 编排 / 规则降级共用同一入口，保证 mock 与真实 LLM 行为一致。
"""
import logging
import re

logger = logging.getLogger("exclusion_gate")

# 5 类排除信号的元数据（供前端渲染角标与文案）
EXCLUSION_TYPES = {
    "NEW_PRODUCT": {
        "label": "新品导入期",
        "desc": "产品刚上市处于爬坡期，销量/覆盖偏低属正常，非代表不力",
    },
    "ACCESS_STAGE": {
        "label": "准入阶段",
        "desc": "目标医院尚在准入流程未开发，覆盖低为结构性原因",
    },
    "SEASONAL": {
        "label": "季节性波动",
        "desc": "指标受季节周期影响，同比波动在合理区间",
    },
    "POLICY_SHOCK": {
        "label": "政策冲击",
        "desc": "VBP 集采中标 / DRG 支付改革等政策导致收入骤降，非代表可左右",
    },
    "RESTRUCTURE": {
        "label": "业务结构调整",
        "desc": "产品线剥离 / 团队重组等组织因素造成的指标变化",
    },
}

# 命中后 level 降级目标（避免误报为高危红灯）
_DEGRADE_TO = {"RED": "YELLOW", "BLACK": "YELLOW"}


def _match(text: str) -> str | None:
    """对一段文本做关键词/模式匹配，返回命中的排除类型；不命中返回 None。

    优先级：政策冲击 > 新品导入 > 准入阶段 > 业务结构 > 季节性。
    """
    t = (text or "").lower()

    # 政策冲击：VBP / 集采 / DRG / 中标 / 带量采购 / 医保谈判
    if re.search(r"(vbp|集采|带量采购|drg|dip|医保谈判|中标|医保控费|支付改革)", t):
        return "POLICY_SHOCK"

    # 新品导入：上市 / 新上市 / 新品 / 刚上市 / 上市不足 / 导入期
    if re.search(r"(新品|新上市|刚上市|上市不足|导入期|上市初期|新产品上市|首年)", t):
        return "NEW_PRODUCT"

    # 准入阶段：准入 / 进院 / 未准入 / 招投标 / 挂网 / 开户
    if re.search(r"(准入|进院|未准入|招投标|挂网|开户|进院流程|待准入|在准入)", t):
        return "ACCESS_STAGE"

    # 业务结构调整：剥离 / 重组 / 合并 / 调整 / 裁撤 / 转岗 / 整合
    if re.search(r"(剥离|重组|合并|调整|裁撤|转岗|整合|产品线调整|组织调整|架构调整)", t):
        return "RESTRUCTURE"

    # 季节性：季节 / 淡季 / 旺季 / 节假日 / 季度性 / 周期性
    if re.search(r"(季节性|季节波动|淡季|旺季|节假日|季度性|周期性|寒暑假|春节后)", t):
        return "SEASONAL"

    return None


def _extract_evidence_text(out: dict) -> str:
    """从诊断输出里拼出用于匹配的证据文本（摘要 + 证据 + 推理链）"""
    parts = [str(out.get("summary") or "")]
    for ev in out.get("evidence") or []:
        if isinstance(ev, dict):
            parts.append(str(ev.get("value", "")))
            parts.append(str(ev.get("metric", "")))
        else:
            parts.append(str(ev))
    for step in out.get("reasoning_trace") or []:
        if isinstance(step, dict):
            parts.append(str(step.get("content") or step.get("text") or ""))
        else:
            parts.append(str(step))
    return "\n".join(parts)


def evaluate(out: dict, context: dict | None = None) -> dict:
    """对诊断输出做误判排除裁定。

    参数：
        out: build_diagnosis_output 的产物（含 summary/level/evidence/...）
        context: 可选，携带结构化上下文（如 target_type/target_id/source）。
    返回：
        { excluded: bool, excluded_type, excluded_reason, degraded_level }
        - excluded: 是否命中排除闸
        - excluded_type: 排除类型 code（EXCLUSION_TYPES 的 key）
        - excluded_reason: 人类可读说明 + 触发证据
        - degraded_level: 若降级，返回的 level；否则为原 level
    """
    try:
        text = _extract_evidence_text(out)
        etype = _match(text)
        original_level = out.get("level", "YELLOW")

        if not etype:
            return {
                "excluded": False,
                "excluded_type": None,
                "excluded_reason": None,
                "degraded_level": original_level,
            }

        meta = EXCLUSION_TYPES[etype]
        # 仅当原 level 为高危（RED/BLACK）才降级，避免把无问题的 GREEN 误改动
        degraded_level = _DEGRADE_TO.get(original_level, original_level)
        reason = {
            "type": etype,
            "label": meta["label"],
            "desc": meta["desc"],
            "original_level": original_level,
            "evidence": text[:300],  # 截取触发证据片段
        }
        return {
            "excluded": True,
            "excluded_type": etype,
            "excluded_reason": reason,
            "degraded_level": degraded_level,
        }
    except Exception as exc:  # 安全降级：绝不因排除闸异常而阻断主流程
        logger.warning("误判排除闸异常，按不命中处理: %s", exc)
        return {
            "excluded": False,
            "excluded_type": None,
            "excluded_reason": None,
            "degraded_level": out.get("level", "YELLOW"),
        }
