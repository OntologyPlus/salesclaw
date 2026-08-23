"""AI API - 请求模型"""
from pydantic import BaseModel


class ChatSendRequest(BaseModel):
    message: str
    agent: str | None = None
    session_id: str | None = None
    stream: bool = False


class ReasoningFeedbackRequest(BaseModel):
    rating: int  # 1-5
    feedback_text: str | None = None


class DeadLetterResolveRequest(BaseModel):
    note: str = ""


class CollaborateRequest(BaseModel):
    """多 Agent 协作请求"""
    message: str
    mode: str = "auto"  # auto / delegate / orchestrate / aggregate
    agents: list[str] | None = None  # 参与的 Agent 名称（auto 模式下自动判定）
    strategy: str = "merge"  # aggregate 模式的合并策略：merge / vote / best
    context: dict | None = None  # 额外上下文
