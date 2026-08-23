"""平台管理 API - 请求模型"""
from typing import Any

from pydantic import BaseModel


class UpdateConfigRequest(BaseModel):
    value: Any = None
