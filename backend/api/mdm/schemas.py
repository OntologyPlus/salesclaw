"""主数据 API - 请求模型"""
from typing import Optional

from pydantic import BaseModel


class CreateRuleRequest(BaseModel):
    name: str
    domain: str = "general"
    field: Optional[str] = None
    rule_type: str = "not_null"
    severity: str = "medium"
    is_active: int = 1
