"""销售执行 API - 请求模型"""
from typing import Optional

from pydantic import BaseModel


class CreatePlanRequest(BaseModel):
    period: str
    target_count: int = 0
    items: list = []


class UpdatePlanRequest(BaseModel):
    period: Optional[str] = None
    target_count: Optional[int] = None


class RejectRequest(BaseModel):
    reason: str


class PlanItemRequest(BaseModel):
    hospital_id: Optional[int] = None
    doctor_id: Optional[int] = None
    product_id: Optional[int] = None
    planned_date: Optional[str] = None
    priority: str = "medium"
    visit_type: str = "academic"
    remark: Optional[str] = None


class CreateRecordRequest(BaseModel):
    plan_id: Optional[int] = None
    hospital_id: Optional[int] = None
    doctor_id: Optional[int] = None
    product_id: Optional[int] = None
    visit_date: str
    visit_type: str = "academic"
    duration_minutes: int = 30
    location: Optional[str] = None
    summary: Optional[str] = None


class UpdateRecordRequest(BaseModel):
    plan_id: Optional[int] = None
    hospital_id: Optional[int] = None
    doctor_id: Optional[int] = None
    product_id: Optional[int] = None
    visit_date: Optional[str] = None
    visit_type: Optional[str] = None
    duration_minutes: Optional[int] = None
    location: Optional[str] = None
    summary: Optional[str] = None


class CreateFeedbackRequest(BaseModel):
    record_id: int
    sentiment: str = "neutral"
    interest_points: list = []
    objections: list = []
    action_items: list = []


class UpdateFeedbackRequest(BaseModel):
    sentiment: Optional[str] = None
    interest_points: Optional[list] = None
    objections: Optional[list] = None
    action_items: Optional[list] = None


class AssignCoverageRequest(BaseModel):
    user_id: int
    hospital_id: Optional[int] = None
    doctor_id: Optional[int] = None
    product_id: Optional[int] = None
    role: str = "primary"
    start_date: Optional[str] = None
