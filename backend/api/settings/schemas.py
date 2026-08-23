"""设置 API - 请求模型"""
from pydantic import BaseModel


class UpdatePreferencesRequest(BaseModel):
    preferences: dict = {}
