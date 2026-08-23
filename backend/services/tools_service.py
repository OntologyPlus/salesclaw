"""内容工具服务层

提供工具执行、最近使用工具查询、AI 推荐工具能力。
数据来源：内存存储（工具执行历史），工具目录为静态预设。
"""
from datetime import datetime
from sqlalchemy.orm import Session


# ──────────────────────────────────────────────
# 工具目录
# ──────────────────────────────────────────────

_TOOL_CATALOG = {
    "ppt_generator": {"name": "学术PPT生成器", "description": "一键生成学术推广PPT", "category": "content"},
    "visit_summary": {"name": "拜访总结生成", "description": "AI自动生成拜访记录摘要", "category": "ai"},
    "objection_handler": {"name": "异议处理话术", "description": "生成针对性异议应对话术", "category": "ai"},
    "weekly_report": {"name": "周报生成器", "description": "自动汇总周报内容", "category": "report"},
    "product_card": {"name": "产品卡片制作", "description": "生成标准产品介绍卡片", "category": "content"},
    "clinical_search": {"name": "临床文献检索", "description": "按关键词检索相关临床文献", "category": "search"},
}

# 内存存储：{user_id: [{tool_id, name, params, executed_at}, ...]}
_RECENT_TOOLS_STORE = {}


# ──────────────────────────────────────────────
# 执行工具
# ──────────────────────────────────────────────

def execute_tool(db: Session, tenant_id: str, user_id: int, tool_id: str, params: dict) -> dict:
    """执行工具：返回执行结果，并记录到最近使用"""
    tool = _TOOL_CATALOG.get(tool_id)
    if not tool:
        return None

    # 记录使用历史
    if user_id not in _RECENT_TOOLS_STORE:
        _RECENT_TOOLS_STORE[user_id] = []
    _RECENT_TOOLS_STORE[user_id].insert(0, {
        "tool_id": tool_id,
        "name": tool["name"],
        "params": params,
        "executed_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    })
    # 保留最近 20 条
    _RECENT_TOOLS_STORE[user_id] = _RECENT_TOOLS_STORE[user_id][:20]

    return {
        "tool_id": tool_id,
        "name": tool["name"],
        "status": "completed",
        "result": f"工具「{tool['name']}」执行完成",
        "params": params,
    }


# ──────────────────────────────────────────────
# 最近使用工具
# ──────────────────────────────────────────────

def get_recent_tools(user_id: int) -> dict:
    """最近使用工具"""
    items = _RECENT_TOOLS_STORE.get(user_id, [])
    return {"items": list(items), "total": len(items)}


# ──────────────────────────────────────────────
# AI 推荐工具
# ──────────────────────────────────────────────

def recommend_tools(context: dict) -> dict:
    """AI 推荐工具：基于上下文关键词推荐"""
    context_str = str(context).lower() if context else ""
    recommendations = []

    if any(kw in context_str for kw in ["拜访", "visit", "总结", "summary"]):
        recommendations.append({"tool_id": "visit_summary", "reason": "与拜访场景相关"})
    if any(kw in context_str for kw in ["异议", "价格", "objection"]):
        recommendations.append({"tool_id": "objection_handler", "reason": "适合处理异议场景"})
    if any(kw in context_str for kw in ["周报", "report", "汇总"]):
        recommendations.append({"tool_id": "weekly_report", "reason": "适合周报场景"})
    if any(kw in context_str for kw in ["文献", "临床", "academic"]):
        recommendations.append({"tool_id": "clinical_search", "reason": "适合学术拜访准备"})
    if any(kw in context_str for kw in ["ppt", "幻灯", "presentation"]):
        recommendations.append({"tool_id": "ppt_generator", "reason": "适合学术推广场景"})

    # 默认推荐
    if not recommendations:
        recommendations = [
            {"tool_id": "visit_summary", "reason": "高频使用工具推荐"},
            {"tool_id": "weekly_report", "reason": "提升周报效率"},
        ]

    # 附加工具详情
    for rec in recommendations:
        tool = _TOOL_CATALOG.get(rec["tool_id"])
        if tool:
            rec["name"] = tool["name"]
            rec["description"] = tool["description"]
            rec["category"] = tool["category"]

    return {"recommendations": recommendations, "total": len(recommendations)}
