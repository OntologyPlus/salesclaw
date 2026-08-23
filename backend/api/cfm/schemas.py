"""会议论坛 API - 请求模型"""
from typing import Optional

from pydantic import BaseModel


class CreateMeetingRequest(BaseModel):
    title: str
    meeting_type: str = "academic"
    status: str = "planned"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    organizer_id: Optional[int] = None
    attendees_count: int = 0
    description: Optional[str] = None
    product_id: Optional[int] = None
    hospital_id: Optional[int] = None


class UpdateMeetingRequest(BaseModel):
    title: Optional[str] = None
    meeting_type: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    organizer_id: Optional[int] = None
    attendees_count: Optional[int] = None
    description: Optional[str] = None
    product_id: Optional[int] = None
    hospital_id: Optional[int] = None


class CreateTopicRequest(BaseModel):
    title: str
    content: Optional[str] = None
    category: str = "general"
    author_name: Optional[str] = None
