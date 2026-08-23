"""可观测 API - 请求模型"""
from typing import Optional

from pydantic import BaseModel


class AlertConfigRequest(BaseModel):
    enable_db_alert: Optional[bool] = True
    enable_ai_alert: Optional[bool] = True
    enable_api_alert: Optional[bool] = True
    threshold_latency_ms: Optional[int] = 500
    threshold_storage_pct: Optional[int] = 80
