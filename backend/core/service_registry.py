"""服务注册表 — 运行时获取服务实现的统一入口

替代跨域直接 import（如 `from services import profile_service`），
改为 `registry.get(ProfileServicePort)`，降低编译时耦合。

启动时在 main.py startup() 中注册：
    registry.register(ProfileServicePort, profile_service)
    registry.register(CollectionServicePort, collection_service)

补齐`require()`：未注册时抛 NotFoundError（而非静默返回 None），避免
调用方误用 None 引发难以定位的 AttributeError。
"""
import logging
from typing import Any, Optional

from core.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """服务注册表（单例模式）"""

    _instances: dict = {}

    @classmethod
    def register(cls, port_class: type, implementation: Any) -> None:
        """注册服务实现

        Args:
            port_class: 服务端口类（如 ProfileServicePort）
            implementation: 服务实现（如 profile_service 模块）
        """
        cls._instances[port_class] = implementation
        logger.debug("服务注册: %s → %s", port_class.__name__, implementation)

    @classmethod
    def get(cls, port_class: type) -> Optional[Any]:
        """获取服务实现

        Args:
            port_class: 服务端口类

        Returns:
            服务实现；未注册时返回 None
        """
        impl = cls._instances.get(port_class)
        if impl is None:
            logger.warning("服务未注册: %s", getattr(port_class, '__name__', str(port_class)))
        return impl

    @classmethod
    def is_registered(cls, port_class: type) -> bool:
        """检查服务是否已注册"""
        return port_class in cls._instances

    @classmethod
    def require(cls, port_class: type) -> Any:
        """获取服务实现，未注册时显式抛错（借鉴 PluginRegistry 的解析失败报错思想）。

        调用方若确信依赖已注册（绝大多数跨域调用场景），应优先使用本方法，
        以便在启动时或首次调用时快速暴露「漏注册」问题，而非延迟到 AttributeError。
        """
        impl = cls._instances.get(port_class)
        if impl is None:
            raise NotFoundError(f"服务未注册: {getattr(port_class, '__name__', str(port_class))}")
        return impl

    @classmethod
    def clear(cls) -> None:
        """清空所有注册（用于测试）"""
        cls._instances.clear()


# 全局单例
registry = ServiceRegistry
