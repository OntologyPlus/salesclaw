"""内容工具 API - 请求模型"""
from typing import Optional

from pydantic import BaseModel


class ExecuteToolRequest(BaseModel):
    params: dict = {}


class AiRecommendRequest(BaseModel):
    context: Optional[dict] = None
