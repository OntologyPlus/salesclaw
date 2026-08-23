"""客户关系 API - 请求模型"""
from typing import Optional

from pydantic import BaseModel


class CreateInteractionRequest(BaseModel):
    doctor_id: Optional[int] = None
    hospital_id: Optional[int] = None
    product_id: Optional[int] = None
    visit_date: str
    visit_type: str = "academic"
    duration_minutes: int = 30
    location: Optional[str] = None
    summary: Optional[str] = None
    status: str = "completed"
