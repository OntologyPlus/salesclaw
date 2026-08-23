"""角色画像库 Schema"""
from typing import Any, List, Optional
from pydantic import BaseModel


class PersonaRequest(BaseModel):
    name: str
    priority: Optional[int] = 0
    keywords: Optional[List[str]] = []
    exclusion_keywords: Optional[List[str]] = []
    default_brief: Optional[str] = None
    persona_text: Optional[str] = None
    persona_type: Optional[str] = "customer"
    is_active: Optional[int] = 1


class PersonaUpdateRequest(BaseModel):
    name: Optional[str] = None
    priority: Optional[int] = None
    keywords: Optional[List[str]] = None
    exclusion_keywords: Optional[List[str]] = None
    default_brief: Optional[str] = None
    persona_text: Optional[str] = None
    persona_type: Optional[str] = None
    is_active: Optional[int] = None


class MatchRequest(BaseModel):
    raw_text: str
