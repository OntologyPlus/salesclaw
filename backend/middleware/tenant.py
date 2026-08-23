"""租户中间件 - 从 JWT 提取 tenant_id 注入 request.state"""
import jwt
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from config import settings
from core.security import decode_token


class TenantMiddleware(BaseHTTPMiddleware):
    """HTTP 中间件：解析 JWT 并注入 tenant_id / user_id 到 request.state"""

    async def dispatch(self, request, call_next):
        request.state.tenant_id = None
        request.state.user_id = None
        request.state.role = None
        request.state.permissions = []

        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            try:
                payload = decode_token(token)
                if payload.get("type") == "access":
                    request.state.tenant_id = payload.get("tenant_id")
                    request.state.user_id = payload.get("user_id")
                    request.state.role = payload.get("role")
                    request.state.permissions = payload.get("permissions", [])
            except Exception:
                pass  # 让路由层的 get_current_user 处理错误

        response = await call_next(request)
        return response


def get_tenant_id(request: Request) -> str | None:
    return getattr(request.state, "tenant_id", None)
