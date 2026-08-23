"""知识库 API - 请求模型"""
from typing import Optional

from pydantic import BaseModel, Field


class DocumentCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    category: str = Field("other")
    content: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[str] = None
    is_published: int = Field(1)
