"""智能培训 API - 请求模型"""
from typing import Optional

from pydantic import BaseModel


class CreateCourseRequest(BaseModel):
    title: str
    description: Optional[str] = None
    course_type: str = "video"
    category: Optional[str] = None
    difficulty: str = "beginner"
    duration_minutes: int = 0
    cover_image: Optional[str] = None
    content_url: Optional[str] = None
    tags: list = []
    is_published: int = 0


class UpdateCourseRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    course_type: Optional[str] = None
    category: Optional[str] = None
    difficulty: Optional[str] = None
    duration_minutes: Optional[int] = None
    cover_image: Optional[str] = None
    content_url: Optional[str] = None
    tags: Optional[list] = None
    is_published: Optional[int] = None


class UpdateProgressRequest(BaseModel):
    progress: int
    last_position: int = 0


class CreateQuestionRequest(BaseModel):
    question_type: str
    content: str
    options: list = []
    answer: list = []
    explanation: Optional[str] = None
    difficulty: str = "medium"
    category: Optional[str] = None
    points: int = 5


class CreateExamRequest(BaseModel):
    title: str
    description: Optional[str] = None
    duration_minutes: int = 60
    pass_score: int = 60
    question_ids: list = []
    status: str = "draft"
    start_at: Optional[str] = None
    end_at: Optional[str] = None
    max_attempts: int = 1


class SubmitExamRequest(BaseModel):
    answers: list  # [{"question_id": 1, "answer": ["A"]}]


class CreatePathRequest(BaseModel):
    title: str
    description: Optional[str] = None
    target_role: Optional[str] = None
    stages: list = []
    total_credits: int = 0
    is_published: int = 0


class StartPracticeRequest(BaseModel):
    scenario_id: int


class PracticeMessageRequest(BaseModel):
    session_id: int
    message: str


class EndPracticeRequest(BaseModel):
    session_id: int
