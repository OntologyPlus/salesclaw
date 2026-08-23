"""统一错误处理"""
import logging
import traceback
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from core.exceptions import AppException
from core.response import error_response

logger = logging.getLogger(__name__)


async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(exc.code, exc.message),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    msg = "参数错误"
    if errors:
        first = errors[0]
        loc = ".".join(str(l) for l in first.get("loc", []) if l != "body")
        msg = f"参数错误: {loc} {first.get('msg', '')}"
    return JSONResponse(
        status_code=422,
        content=error_response(10001, msg),
    )


async def generic_exception_handler(request: Request, exc: Exception):
    trace_id = str(uuid.uuid4())
    logger.error(
        "未捕获异常 trace_id=%s path=%s: %s",
        trace_id, request.url.path, traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content=error_response(90001, "内部错误，请凭 trace_id 联系管理员排查", trace_id),
    )
