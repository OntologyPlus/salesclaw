"""PPT 演讲 Schema"""
from typing import Any, List, Optional
from pydantic import BaseModel


class PPTScenarioRequest(BaseModel):
    title: str
    description: Optional[str] = None
    product_id: Optional[int] = None
    difficulty: Optional[str] = "medium"
    ppt_url: Optional[str] = None
    ppt_pages: Optional[List[Any]] = []
    coach_prompts: Optional[List[Any]] = []
    reference_audio_url: Optional[str] = None
    pass_score: Optional[int] = 60
    scoring_dimensions: Optional[List[Any]] = []


class PPTScenarioUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    ppt_url: Optional[str] = None
    ppt_pages: Optional[List[Any]] = None
    coach_prompts: Optional[List[Any]] = None
    reference_audio_url: Optional[str] = None
    pass_score: Optional[int] = None
    scoring_dimensions: Optional[List[Any]] = None
    difficulty: Optional[str] = None


class StartSessionRequest(BaseModel):
    scenario_id: int
    mode: Optional[str] = "practice"
    activity_id: Optional[int] = None


class SubmitPageRequest(BaseModel):
    page_no: int
    recording: dict


class SubmitQARequest(BaseModel):
    question_id: int
    answer: dict
