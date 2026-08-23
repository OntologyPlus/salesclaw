"""Ontology 注册层 - Object / Link / Action / Permission 的统一访问入口

运行时权威源是 psp_ontology.db（经 `ontology.registry` 加载到进程内缓存），
`ontology/objects.py`、`links.py`、`actions.py` 已降级为「seed 声明源」，
仅在首次初始化 / DB 不可用降级时使用。

本模块导出面保持与历史版本完全一致（OBJECTS/LINKS/ACTIONS/*_MAP + 访问函数），
消费方无需改写；其中容器类导出为实时代理对象，reload 后自动生效。
"""
from ontology.registry import (
    # 实时容器代理（热更新安全）
    OBJECTS, LINKS, ACTIONS,
    OBJECT_MAP, LINK_MAP, ACTION_MAP,
    # 访问函数
    list_objects, get_object,
    list_links, get_link,
    list_actions, get_action,
    # 注册表单例与热更新
    registry, reload_ontology,
)
from ontology.permissions import (
    ROLE_PERMISSIONS, OBJECT_PERMISSIONS, ROLE_DEFINITIONS,
    get_role_permissions, has_permission, can_access_object,
)


def get_graph(tenant_id: str | None = None) -> dict:
    """获取完整的 Ontology 图谱（Object + Link + Action 概览）"""
    objects = list_objects(tenant_id=tenant_id)
    links = list_links(tenant_id=tenant_id)
    actions = list_actions(tenant_id=tenant_id)
    return {
        "objects": len(objects),
        "links": len(links),
        "actions": len(actions),
        "domains": sorted({obj["domain"] for obj in objects}),
        "risk_levels": ["L1", "L2", "L3", "L4"],
        "action_by_risk": {
            level: len(list_actions(risk_level=level, tenant_id=tenant_id))
            for level in ["L1", "L2", "L3", "L4"]
        },
    }


__all__ = [
    # Object
    "list_objects", "get_object", "OBJECTS", "OBJECT_MAP",
    # Link
    "list_links", "get_link", "LINKS", "LINK_MAP",
    # Action
    "list_actions", "get_action", "ACTIONS", "ACTION_MAP",
    # Permission
    "ROLE_PERMISSIONS", "OBJECT_PERMISSIONS", "ROLE_DEFINITIONS",
    "get_role_permissions", "has_permission", "can_access_object",
    # Graph
    "get_graph",
    # Registry
    "registry", "reload_ontology",
]
