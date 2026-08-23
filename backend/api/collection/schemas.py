"""数据采集 API - 请求模型"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    project_type: str = Field("plan")
    period_type: str = Field("monthly")
    status: str = Field("draft")
    zone_ids: list[int] = Field(default_factory=list)
    template_id: Optional[int] = None
    related_project_id: Optional[int] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None


class ProjectUpdateRequest(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    project_type: Optional[str] = None
    period_type: Optional[str] = None
    status: Optional[str] = None
    zone_ids: Optional[list[int]] = None
    template_id: Optional[int] = None
    related_project_id: Optional[int] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None


class ItemSubmitRequest(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class TemplateCreateRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    fields: list[dict] = Field(default_factory=list)
    version: int = Field(1)
    is_active: int = Field(1)


class TodoBatchDeleteRequest(BaseModel):
    todo_ids: list[int] = Field(..., min_length=1)
