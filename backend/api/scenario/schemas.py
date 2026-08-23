"""场景剧本解析 Schema"""
from typing import Any, List, Optional
from pydantic import BaseModel


class ParseRequest(BaseModel):
    raw_text: str


class SaveScenarioRequest(BaseModel):
    title: Optional[str] = None
    scenario_type: Optional[str] = None
    difficulty: Optional[str] = None
    scenario_background: Optional[str] = None
    scenario_description: Optional[str] = None
    persona_id: Optional[int] = None
    ai_roles: Optional[List[Any]] = []
    scoring_rules: Optional[List[Any]] = []
    standard_scripts_text: Optional[str] = None
    knowledge_needs: Optional[List[Any]] = []
    product_id: Optional[int] = None
    basic_info: Optional[dict] = None
