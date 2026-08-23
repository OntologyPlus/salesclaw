"""协同办公 API - 请求模型"""
from typing import Optional

from pydantic import BaseModel, Field


class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    description: Optional[str] = None
    task_type: str = Field("general")
    priority: str = Field("medium")
    assignee_id: Optional[int] = None
    due_date: Optional[str] = None
    related_type: Optional[str] = None
    related_id: Optional[int] = None


class TaskStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(pending|in_progress|completed|cancelled)$")


class ApprovalCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    approval_type: str = Field("general")
    description: Optional[str] = None
    related_type: Optional[str] = None
    related_id: Optional[int] = None


class ReviewRequest(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$")
    comment: Optional[str] = None
