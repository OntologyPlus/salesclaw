"""AI Prompt 模板存储 - Mock 预设模板"""

# 预设 Prompt 模板
PROMPT_TEMPLATES = {
    "visit_plan_recommend": (
        "你是一位资深医药销售经理，请根据以下信息推荐拜访计划：\n"
        "- 代表：{user_name}\n"
        "- 区域：{zone}\n"
        "- 周期：{period}\n"
        "- 历史拜访：{history}\n"
        "请输出结构化的拜访建议，包含目标医院、医生、拜访优先级。"
    ),
    "feedback_extraction": (
        "请从以下拜访记录中抽取关键信息：\n"
        "- 拜访记录：{record}\n"
        "请抽取：客户反馈要点、情感倾向（正面/中性/负面）、后续行动建议。"
    ),
    "kpi_analysis": (
        "请分析以下 KPI 数据并给出洞察：\n"
        "- KPI 名称：{kpi_name}\n"
        "- 当前值：{value}\n"
        "- 目标值：{target}\n"
        "- 历史趋势：{trend}\n"
        "请输出：达成率、差距分析、改进建议。"
    ),
    "course_recommend": (
        "你是培训课程顾问，请根据以下用户画像推荐课程：\n"
        "- 角色：{role}\n"
        "- 岗位：{position}\n"
        "- 学习历史：{history}\n"
        "请输出 3-5 门推荐课程及理由。"
    ),
    "coverage_analysis": (
        "你是覆盖分析专家，请分析以下覆盖数据：\n"
        "- 代表：{user_name}\n"
        "- 区域：{zone}\n"
        "- 覆盖矩阵：{matrix}\n"
        "请输出：覆盖空白点、潜力评估、优化建议。"
    ),
    "exam_generation": (
        "你是考试命题专家，请根据以下要求生成试卷：\n"
        "- 题库：{bank}\n"
        "- 题目数量：{count}\n"
        "- 难度：{difficulty}\n"
        "请输出：题目列表、答案、评分标准。"
    ),
    "report_generation": (
        "请根据以下数据生成业务报告：\n"
        "- 周期：{period}\n"
        "- 数据摘要：{summary}\n"
        "请输出：执行摘要、关键指标、问题分析、下一步建议。"
    ),
    "drill_scene": (
        "你是演练场景设计师，请设计一个演练场景：\n"
        "- 角色：{role}\n"
        "- 难度：{difficulty}\n"
        "- 业务背景：{context}\n"
        "请输出：场景描述、角色设定、对话脚本、评分标准。"
    ),
    "default": "你是一个智能助手，请回答用户的问题。",
}


def get_prompt(name: str) -> str:
    """按名称获取 Prompt 模板，未找到则返回默认模板"""
    return PROMPT_TEMPLATES.get(name, PROMPT_TEMPLATES["default"])


def list_prompts() -> list[str]:
    """列出所有可用的 Prompt 模板名称"""
    return list(PROMPT_TEMPLATES.keys())


__all__ = ["PROMPT_TEMPLATES", "get_prompt", "list_prompts"]
