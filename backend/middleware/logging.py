"""请求日志中间件"""
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware


class LoggingMiddleware(BaseHTTPMiddleware):
    """记录每个请求的方法、路径、状态码、耗时"""

    async def dispatch(self, request, call_next):
        request.state.trace_id = str(uuid.uuid4())
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Trace-Id"] = request.state.trace_id
        response.headers["X-Response-Time"] = f"{duration_ms}ms"

        print(
            f"[{request.state.trace_id[:8]}] "
            f"{request.method} {request.url.path} "
            f"→ {response.status_code} ({duration_ms}ms)"
        )
        return response
