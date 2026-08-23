"""ServicePort 注册 - 跨域调用的依赖倒置装配点

各业务域之间不直接 import 对方的 service 模块，而是通过 ServicePort 接口
+ 全局 registry 解耦。本模块是唯一的「接口 → 实现」绑定处。
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def register_service_ports() -> int:
    """把各域 service 实现注册到全局 registry。

    Returns:
        成功注册的 Port 数量
    """
    from core.service_registry import registry
    from core.service_ports import (
        ProfileServicePort, CollectionServicePort, TrainingServicePort,
        DecisionServicePort, NotificationServicePort, SalesServicePort,
        DataLineageServicePort,
    )
    from services import (
        profile_service, collection_service, training_service,
        decision_service, notification_service, sales_service,
        data_lineage_service,
    )

    bindings = (
        (ProfileServicePort, profile_service),
        (CollectionServicePort, collection_service),
        (TrainingServicePort, training_service),
        (DecisionServicePort, decision_service),
        (NotificationServicePort, notification_service),
        (SalesServicePort, sales_service),
        (DataLineageServicePort, data_lineage_service),
    )
    for port, impl in bindings:
        registry.register(port, impl)

    logger.info("[bootstrap] 已注册 %d 个 ServicePort", len(bindings))
    return len(bindings)
