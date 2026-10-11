"""Phase B：轻量 OTEL 风格 span（无硬依赖 opentelemetry）

若已安装 opentelemetry-api 则桥接；否则使用进程内 span 树，
挂到 trace_id，可供 /ai/traces/{trace_id} 查询与日志关联。
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Generator, Optional

logger = logging.getLogger(__name__)

_current_trace: ContextVar[Optional[str]] = ContextVar("otel_trace_id", default=None)
_current_span: ContextVar[Optional[str]] = ContextVar("otel_span_id", default=None)

_lock = threading.Lock()
# trace_id -> list[span dict]
_TRACE_STORE: dict[str, list[dict]] = {}
_MAX_TRACES = 200
_MAX_SPANS_PER_TRACE = 100


@dataclass
class SpanHandle:
    trace_id: str
    span_id: str
    name: str
    parent_id: Optional[str] = None
    attrs: dict = field(default_factory=dict)
    start_ms: float = 0.0
    end_ms: float = 0.0
    status: str = "ok"
    error: Optional[str] = None


def _otel_enabled() -> bool:
    try:
        from config import settings
        return bool(settings.AI_ENABLE_OTEL_SPANS)
    except Exception:
        return True


def get_trace_id() -> Optional[str]:
    return _current_trace.get()


def get_spans(trace_id: str) -> list[dict]:
    with _lock:
        return list(_TRACE_STORE.get(trace_id, []))


@contextmanager
def span(
    name: str,
    *,
    trace_id: Optional[str] = None,
    attributes: Optional[dict] = None,
) -> Generator[SpanHandle, None, None]:
    """嵌套 span 上下文。"""
    if not _otel_enabled():
        yield SpanHandle(trace_id=trace_id or "", span_id="", name=name)
        return

    tid = trace_id or _current_trace.get() or str(uuid.uuid4())[:12]
    parent = _current_span.get()
    sid = uuid.uuid4().hex[:12]
    handle = SpanHandle(
        trace_id=tid,
        span_id=sid,
        name=name,
        parent_id=parent,
        attrs=dict(attributes or {}),
        start_ms=time.time() * 1000,
    )
    tok_t = _current_trace.set(tid)
    tok_s = _current_span.set(sid)

    # 可选桥接真实 OTEL
    otel_cm = None
    try:
        from opentelemetry import trace as otel_trace  # type: ignore
        tracer = otel_trace.get_tracer("salesclaw")
        otel_cm = tracer.start_as_current_span(name)
        otel_span = otel_cm.__enter__()
        for k, v in handle.attrs.items():
            try:
                otel_span.set_attribute(k, v if isinstance(v, (str, int, float, bool)) else str(v))
            except Exception:
                pass
    except Exception:
        otel_cm = None

    try:
        yield handle
    except Exception as e:
        handle.status = "error"
        handle.error = str(e)[:500]
        raise
    finally:
        handle.end_ms = time.time() * 1000
        _record(handle)
        if otel_cm is not None:
            try:
                otel_cm.__exit__(None, None, None)
            except Exception:
                pass
        _current_span.reset(tok_s)
        _current_trace.reset(tok_t)


def _record(handle: SpanHandle) -> None:
    rec = {
        "trace_id": handle.trace_id,
        "span_id": handle.span_id,
        "parent_id": handle.parent_id,
        "name": handle.name,
        "attributes": handle.attrs,
        "start_ms": round(handle.start_ms, 3),
        "end_ms": round(handle.end_ms, 3),
        "duration_ms": round(max(0.0, handle.end_ms - handle.start_ms), 3),
        "status": handle.status,
        "error": handle.error,
    }
    with _lock:
        bucket = _TRACE_STORE.setdefault(handle.trace_id, [])
        bucket.append(rec)
        if len(bucket) > _MAX_SPANS_PER_TRACE:
            del bucket[: len(bucket) - _MAX_SPANS_PER_TRACE]
        if len(_TRACE_STORE) > _MAX_TRACES:
            # 丢掉最旧的
            for old in list(_TRACE_STORE.keys())[: len(_TRACE_STORE) - _MAX_TRACES]:
                _TRACE_STORE.pop(old, None)
    logger.debug(
        "[otel] %s trace=%s span=%s dur=%.1fms status=%s",
        handle.name, handle.trace_id, handle.span_id,
        rec["duration_ms"], handle.status,
    )


__all__ = ["span", "get_trace_id", "get_spans", "SpanHandle"]
