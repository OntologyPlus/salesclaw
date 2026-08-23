"""通知中心 API Schemas"""
from typing import Optional, List
from pydantic import BaseModel


class RuleCreateRequest(BaseModel):
    activity_id: Optional[int] = None
    scenario_id: Optional[int] = None
    rule_name: str
    deadline: str
    windows: Optional[List[str]] = ["D-3", "D-2", "D-1"]
    frequency: Optional[str] = "daily"
    send_times: Optional[List[str]] = ["10:00", "16:00"]
    channel: Optional[str] = "in_app"
    target_user_type: Optional[str] = "all"


class RuleStatusRequest(BaseModel):
    enabled: int
