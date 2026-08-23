"""培训效果因果归因 API - 请求/响应模型

设计文档：SalesClaw_培训效果因果归因_B路径_规划.md §10
"""
from typing import Optional

from pydantic import BaseModel


class EvaluationRequest(BaseModel):
    """触发 AI 归因评估请求"""
    execution_id: int
    force: bool = False  # 强制重跑（已有 reasoning_chain_id 时仍重新调 ai_evaluate）
