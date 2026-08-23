"""统一响应封装"""
import uuid


def unified_response(data=None, code: int = 0, message: str = "ok") -> dict:
    return {
        "code": code,
        "message": message,
        "data": data,
        "trace_id": str(uuid.uuid4()),
    }


def error_response(code: int, message: str, trace_id: str | None = None) -> dict:
    return {
        "code": code,
        "message": message,
        "data": None,
        "trace_id": trace_id or str(uuid.uuid4()),
    }
