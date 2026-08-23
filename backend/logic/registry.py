"""Action 执行钩子注册表 — Logic 平面的一部分。

借鉴 core/service_registry 的 port 模式：把「动作名 → 真实执行函数」解耦，
消费方只声明要执行的 action name，由 handler 注册表决定落到哪个实现。

默认所有 action 为「占位 handler」（仅记录意图、不写业务库），
真实业务实现可在 main.py startup 中按 name 注册覆盖。
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# handler 签名： (action: dict, payload: dict, ctx: dict) -> dict
ActionHandler = Callable[[dict, dict, dict], dict]


class ActionHandlerRegistry:
    """动作处理器注册表（单例）。"""

    _handlers: dict[str, ActionHandler] = {}

    @classmethod
    def register(cls, action_name: str, handler: ActionHandler) -> None:
        cls._handlers[action_name] = handler
        logger.debug("动作处理器注册: %s → %s", action_name, handler)

    @classmethod
    def get(cls, action_name: str) -> Optional[ActionHandler]:
        return cls._handlers.get(action_name)

    @classmethod
    def is_registered(cls, action_name: str) -> bool:
        return action_name in cls._handlers

    @classmethod
    def clear(cls) -> None:
        cls._handlers.clear()


# 全局单例（供直接 import 调用）
registry = ActionHandlerRegistry()


def _placeholder_handler(action: dict, payload: dict, ctx: dict) -> dict:
    """默认占位执行器：不落业务库，仅回显意图，供架构验证。

    生产环境由 main.startup 注册真实 handler 覆盖。
    """
    return {
        "executed": False,
        "mode": "placeholder",
        "action": action.get("name"),
        "message": "占位执行：未注册真实 handler（架构验证用）",
        "received_payload": payload,
    }


def dispatch(action: dict, payload: dict, ctx: dict) -> dict:
    """派发一个动作到其 handler。

    - 已注册 handler → 调用之；
    - 未注册 → 走占位 handler（不阻断链）。
    """
    name = action.get("name")
    handler = registry.get(name) if name else None
    if handler is None:
        return _placeholder_handler(action, payload, ctx)
    return handler(action, payload, ctx)
