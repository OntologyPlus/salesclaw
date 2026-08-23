"""培训活动 API Schemas"""
from typing import Optional, List
from pydantic import BaseModel


class ActivityCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    domain: Optional[str] = None
    product_id: Optional[int] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    visible_scope: Optional[dict] = {}
    open_practice: Optional[int] = 1
    open_train: Optional[int] = 1
    pass_score: Optional[int] = 60


class ActivityUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    domain: Optional[str] = None
    product_id: Optional[int] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    visible_scope: Optional[dict] = None
    open_practice: Optional[int] = None
    open_train: Optional[int] = None
    pass_score: Optional[int] = None


class AddScenariosRequest(BaseModel):
    scenario_ids: List[int]
