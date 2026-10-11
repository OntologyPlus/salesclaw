"""会话级运行控制 —— 协作取消（abort）

Phase A：在 chat / stream / ToolLoop 轮次之间做协作式取消。
使用 threading.Event，以便 asyncio.to_thread 内的同步 ToolLoop 也能感知。
"""
from __future__ import annotations

import threading
from typing import Optional


class RunAborted(Exception):
    """当前会话已被用户/系统取消。"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"run aborted: {session_id}")


class RunRegistry:
    """session_id → cancel Event 注册表。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._flags: dict[str, threading.Event] = {}

    def begin(self, session_id: str) -> None:
        """标记一次运行开始。若已有未消费的 abort 信号则保留。"""
        if not session_id:
            return
        with self._lock:
            existing = self._flags.get(session_id)
            if existing is not None and existing.is_set():
                return
            self._flags[session_id] = threading.Event()

    def abort(self, session_id: str) -> bool:
        """请求取消。会话尚未 begin 时也会挂起 abort 标志，供后续 begin 继承。"""
        if not session_id:
            return False
        with self._lock:
            ev = self._flags.get(session_id)
            if ev is None:
                ev = threading.Event()
                self._flags[session_id] = ev
            ev.set()
            return True

    def is_aborted(self, session_id: Optional[str]) -> bool:
        if not session_id:
            return False
        with self._lock:
            ev = self._flags.get(session_id)
            return bool(ev and ev.is_set())

    def check(self, session_id: Optional[str]) -> None:
        """若已取消则抛 RunAborted。"""
        if self.is_aborted(session_id):
            raise RunAborted(session_id or "")

    def end(self, session_id: Optional[str]) -> None:
        if not session_id:
            return
        with self._lock:
            self._flags.pop(session_id, None)

    def cancel_callback(self, session_id: Optional[str]):
        """供 ToolLoop should_cancel 使用的无参回调。"""
        sid = session_id

        def _cb() -> bool:
            return self.is_aborted(sid)

        return _cb


run_registry = RunRegistry()

__all__ = ["RunAborted", "RunRegistry", "run_registry"]
