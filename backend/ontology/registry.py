"""OntologyRegistry - 本体运行时权威源（DB 加载 + 进程内缓存 + 热更新）

架构背景
────────
历史实现中，本体（Object/Link/Action）是 `ontology/objects.py` 等文件里的 Python
硬编码常量，运行时直接读常量：
  - 无法热更新（改本体 = 改代码 + 重启）
  - 无法按租户/项目差异化配置
  - `object_definitions` 等 ORM 表沦为「镜像/审计落点」，不是真正的权威源

本模块把权威源翻转过来：

    ontology/*.py (seed 声明)  --sync-->  psp_ontology.db (运行时权威源)
                                              |
                                              v
                                     OntologyRegistry 进程内缓存
                                              |
                                              v
                               api / ai / services / skills 消费

关键设计
────────
1. **懒加载**：首次访问时才查 DB，避免 import 期触发 DB IO（import 顺序敏感）。
2. **兜底降级**：DB 不可用/为空时自动回退到 seed 常量，保证进程永远能启动。
   这是刻意的可用性取舍——本体是只读元数据，宁可用稍旧的 seed 也不能让服务起不来。
3. **租户覆盖**：`tenant_id IS NULL` 为全局基线，`tenant_id = X` 为该租户覆盖项，
   按 name 覆盖合并（租户项优先）。
4. **向后兼容**：通过 `_ListProxy`/`_MapProxy` 让 `OBJECTS`/`OBJECT_MAP` 这类
   模块级常量在 `from ontology import OBJECTS` 的 import-time 绑定下依然能读到
   最新缓存——因为消费方绑定的是代理对象而非快照 list/dict。
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)

# 缓存有效期（秒）。本体是低频变更的元数据，TTL 仅用于兜底自愈，
# 真正的更新走显式 reload()。
_CACHE_TTL_SECONDS = 300


class OntologyRegistry:
    """本体注册表：从 psp_ontology.db 加载 Object/Link/Action 到进程内缓存。

    线程安全：用可重入锁保护缓存读写。加载是幂等的，重复调用只会刷新缓存。
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._loaded = False
        self._from_db = False  # True=数据来自 DB；False=降级用的 seed 常量
        self._loaded_at: float = 0.0
        self._objects: list[dict] = []
        self._links: list[dict] = []
        self._actions: list[dict] = []
        self._object_map: dict[str, dict] = {}
        self._link_map: dict[str, dict] = {}
        self._action_map: dict[str, dict] = {}
        # tenant_id -> 该租户的覆盖视图（仅在存在租户级覆盖时才建）
        self._tenant_objects: dict[str, list[dict]] = {}
        self._tenant_links: dict[str, list[dict]] = {}
        self._tenant_actions: dict[str, list[dict]] = {}

    # ── seed 兜底 ────────────────────────────────────────────

    @staticmethod
    def _seed_data() -> tuple[list[dict], list[dict], list[dict]]:
        """读取 .py seed 声明（仅作为 DB 空/不可用时的兜底与 sync 输入源）"""
        from ontology.objects import OBJECTS as SEED_OBJECTS
        from ontology.links import LINKS as SEED_LINKS
        from ontology.actions import ACTIONS as SEED_ACTIONS
        return list(SEED_OBJECTS), list(SEED_LINKS), list(SEED_ACTIONS)

    # ── DB 行 → dict（保持与 seed 常量完全一致的结构）────────

    @staticmethod
    def _row_to_object(row) -> dict:
        schema = row.schema or {}
        return {
            "name": row.name,
            "display_name": row.display_name,
            "domain": row.domain or "unknown",
            "description": row.description or "",
            "fields": schema.get("fields", []),
            "actions": schema.get("actions", []),
        }

    @staticmethod
    def _row_to_link(row) -> dict:
        return {
            "name": row.name,
            "display_name": row.display_name,
            "source_object": row.source_object,
            "target_object": row.target_object,
            "cardinality": row.cardinality or "1:N",
            "description": row.description or "",
        }

    @staticmethod
    def _row_to_action(row) -> dict:
        return {
            "name": row.name,
            "display_name": row.display_name,
            "domain": row.domain or "unknown",
            "risk_level": row.risk_level or "L1",
            "permission_required": row.permission_required,
            "description": row.description or "",
            "input_schema": row.input_schema or {},
            "output_schema": row.output_schema or {},
        }

    # ── 加载 ─────────────────────────────────────────────────

    def load(self, force: bool = False) -> dict:
        """从 DB 加载本体到缓存。DB 空或异常时回退 seed 常量。

        Args:
            force: True 则忽略 TTL 强制重新加载
        Returns:
            加载统计 {objects, links, actions, source}
        """
        import time

        with self._lock:
            if self._loaded and not force:
                if time.time() - self._loaded_at < _CACHE_TTL_SECONDS:
                    return self._stats()

            objects: list[dict] = []
            links: list[dict] = []
            actions: list[dict] = []
            from_db = False

            try:
                from database import (
                    OntologySessionLocal, ObjectDefinition,
                    LinkDefinition, ActionDefinition,
                )
                with OntologySessionLocal() as db:
                    obj_rows = (
                        db.query(ObjectDefinition)
                        .filter(ObjectDefinition.is_active == 1)
                        .order_by(ObjectDefinition.sort_order, ObjectDefinition.id)
                        .all()
                    )
                    link_rows = (
                        db.query(LinkDefinition)
                        .order_by(LinkDefinition.sort_order, LinkDefinition.id)
                        .all()
                    )
                    act_rows = (
                        db.query(ActionDefinition)
                        .order_by(ActionDefinition.sort_order, ActionDefinition.id)
                        .all()
                    )

                    if obj_rows or link_rows or act_rows:
                        from_db = True
                        self._rebuild_tenant_views(obj_rows, link_rows, act_rows)
                        # 全局基线视图：tenant_id 为空的行
                        objects = [self._row_to_object(r) for r in obj_rows if not r.tenant_id]
                        links = [self._row_to_link(r) for r in link_rows if not r.tenant_id]
                        actions = [self._row_to_action(r) for r in act_rows if not r.tenant_id]
            except Exception as e:
                # DB 尚未建表 / 迁移未跑 / 文件缺失 —— 不阻断启动
                logger.warning("[ontology] 从 DB 加载本体失败，回退 seed 常量: %s", e)

            if not from_db or not objects:
                objects, links, actions = self._seed_data()
                if from_db and not objects:
                    logger.info("[ontology] DB 本体表为空，使用 seed 常量")
                from_db = False
                self._tenant_objects.clear()
                self._tenant_links.clear()
                self._tenant_actions.clear()

            self._objects = objects
            self._links = links
            self._actions = actions
            self._object_map = {o["name"]: o for o in objects}
            self._link_map = {l["name"]: l for l in links}
            self._action_map = {a["name"]: a for a in actions}
            self._loaded = True
            self._from_db = from_db
            self._loaded_at = time.time()

            logger.info(
                "[ontology] 本体加载完成 source=%s objects=%d links=%d actions=%d",
                "db" if from_db else "seed", len(objects), len(links), len(actions),
            )
            return self._stats()

    def _rebuild_tenant_views(self, obj_rows, link_rows, act_rows) -> None:
        """构建租户覆盖视图：基线 + 该租户覆盖项（按 name 覆盖）"""
        self._tenant_objects.clear()
        self._tenant_links.clear()
        self._tenant_actions.clear()

        def build(rows, converter, bucket: dict) -> None:
            tenants = {r.tenant_id for r in rows if r.tenant_id}
            if not tenants:
                return
            baseline = [r for r in rows if not r.tenant_id]
            for tid in tenants:
                merged: dict[str, dict] = {r.name: converter(r) for r in baseline}
                for r in rows:
                    if r.tenant_id == tid:
                        merged[r.name] = converter(r)
                bucket[tid] = list(merged.values())

        build(obj_rows, self._row_to_object, self._tenant_objects)
        build(link_rows, self._row_to_link, self._tenant_links)
        build(act_rows, self._row_to_action, self._tenant_actions)

    def _ensure(self) -> None:
        if not self._loaded:
            self.load()

    def _stats(self) -> dict:
        return {
            "objects": len(self._objects),
            "links": len(self._links),
            "actions": len(self._actions),
            "source": "db" if self._from_db else "seed",
            "tenant_overrides": sorted(
                set(self._tenant_objects) | set(self._tenant_links) | set(self._tenant_actions)
            ),
        }

    def reload(self) -> dict:
        """热更新：强制从 DB 重新加载缓存（供 /ontology/reload 端点调用）"""
        return self.load(force=True)

    def apply_snapshot(self, objects: list[dict], links: list[dict],
                       actions: list[dict]) -> dict:
        """将一组定义设为当前内存权威源（供 versioning.restore 回放）。

        与 reload() 的区别：不读 DB/seed，直接采用调用方提供的快照定义，
        并重置缓存时间戳，使后续访问器立即返回该版本。原 DB 内容不被覆盖，
        下次 reload() 仍可回到运行时最新定义。
        """
        with self._lock:
            self._objects = objects
            self._links = links
            self._actions = actions
            self._object_map = {o["name"]: o for o in objects}
            self._link_map = {l["name"]: l for l in links}
            self._action_map = {a["name"]: a for a in actions}
            self._loaded = True
            self._loaded_at = __import__("time").time()
            logger.info(
                "[ontology] 已应用快照定义 objects=%d links=%d actions=%d",
                len(objects), len(links), len(actions),
            )
            return self._stats()

    @property
    def source(self) -> str:
        self._ensure()
        return "db" if self._from_db else "seed"

    # ── 访问器（与原 .py 函数签名保持完全一致）──────────────

    def list_objects(self, domain: Optional[str] = None,
                     tenant_id: Optional[str] = None) -> list[dict]:
        self._ensure()
        items = self._tenant_objects.get(tenant_id) if tenant_id else None
        if items is None:
            items = self._objects
        if domain:
            return [o for o in items if o.get("domain") == domain]
        return items

    def get_object(self, name: str, tenant_id: Optional[str] = None) -> Optional[dict]:
        self._ensure()
        if tenant_id and tenant_id in self._tenant_objects:
            for o in self._tenant_objects[tenant_id]:
                if o["name"] == name:
                    return o
        return self._object_map.get(name)

    def list_links(self, tenant_id: Optional[str] = None) -> list[dict]:
        self._ensure()
        if tenant_id:
            items = self._tenant_links.get(tenant_id)
            if items is not None:
                return items
        return self._links

    def get_link(self, name: str, tenant_id: Optional[str] = None) -> Optional[dict]:
        self._ensure()
        if tenant_id and tenant_id in self._tenant_links:
            for l in self._tenant_links[tenant_id]:
                if l["name"] == name:
                    return l
        return self._link_map.get(name)

    def list_actions(self, domain: Optional[str] = None,
                     risk_level: Optional[str] = None,
                     tenant_id: Optional[str] = None) -> list[dict]:
        self._ensure()
        result = self._tenant_actions.get(tenant_id) if tenant_id else None
        if result is None:
            result = self._actions
        if domain:
            result = [a for a in result if a.get("domain") == domain]
        if risk_level:
            result = [a for a in result if a.get("risk_level") == risk_level]
        return result

    def get_action(self, name: str, tenant_id: Optional[str] = None) -> Optional[dict]:
        self._ensure()
        if tenant_id and tenant_id in self._tenant_actions:
            for a in self._tenant_actions[tenant_id]:
                if a["name"] == name:
                    return a
        return self._action_map.get(name)

    # ── 原始容器（供 Proxy 转发）────────────────────────────

    @property
    def objects(self) -> list[dict]:
        self._ensure()
        return self._objects

    @property
    def links(self) -> list[dict]:
        self._ensure()
        return self._links

    @property
    def actions(self) -> list[dict]:
        self._ensure()
        return self._actions

    @property
    def object_map(self) -> dict[str, dict]:
        self._ensure()
        return self._object_map

    @property
    def link_map(self) -> dict[str, dict]:
        self._ensure()
        return self._link_map

    @property
    def action_map(self) -> dict[str, dict]:
        self._ensure()
        return self._action_map


# 全局单例
registry = OntologyRegistry()


# ──────────────────────────────────────────────────────────
# 向后兼容代理
#
# 消费方普遍写成 `from ontology import OBJECTS` —— 这是 import-time 绑定，
# 若直接导出快照 list/dict，reload() 后消费方仍持有旧对象。
# 代理对象把所有容器协议转发到 registry 的实时缓存，从而在不改动
# 60+ 处调用点写法的前提下获得热更新能力。
# ──────────────────────────────────────────────────────────

class _ListProxy:
    """只读 list 代理：转发到 registry 的实时列表"""

    __slots__ = ("_attr",)

    def __init__(self, attr: str) -> None:
        self._attr = attr

    def _target(self) -> list[dict]:
        return getattr(registry, self._attr)

    def __iter__(self) -> Iterator[dict]:
        return iter(self._target())

    def __len__(self) -> int:
        return len(self._target())

    def __getitem__(self, item) -> Any:
        return self._target()[item]

    def __contains__(self, item) -> bool:
        return item in self._target()

    def __bool__(self) -> bool:
        return bool(self._target())

    def __eq__(self, other) -> bool:
        return self._target() == other

    def __add__(self, other):
        return self._target() + other

    def __radd__(self, other):
        return other + self._target()

    def __repr__(self) -> str:
        return repr(self._target())

    def index(self, *args) -> int:
        return self._target().index(*args)

    def count(self, item) -> int:
        return self._target().count(item)


class _MapProxy:
    """只读 dict 代理：转发到 registry 的实时映射"""

    __slots__ = ("_attr",)

    def __init__(self, attr: str) -> None:
        self._attr = attr

    def _target(self) -> dict[str, dict]:
        return getattr(registry, self._attr)

    def get(self, key, default=None):
        return self._target().get(key, default)

    def __getitem__(self, key):
        return self._target()[key]

    def __iter__(self):
        return iter(self._target())

    def __len__(self) -> int:
        return len(self._target())

    def __contains__(self, key) -> bool:
        return key in self._target()

    def __bool__(self) -> bool:
        return bool(self._target())

    def __eq__(self, other) -> bool:
        return self._target() == other

    def keys(self):
        return self._target().keys()

    def values(self):
        return self._target().values()

    def items(self):
        return self._target().items()

    def __repr__(self) -> str:
        return repr(self._target())


# 运行时权威容器（热更新安全）
OBJECTS = _ListProxy("objects")
LINKS = _ListProxy("links")
ACTIONS = _ListProxy("actions")
OBJECT_MAP = _MapProxy("object_map")
LINK_MAP = _MapProxy("link_map")
ACTION_MAP = _MapProxy("action_map")


# ── 模块级访问函数（与原 objects.py/links.py/actions.py 签名一致）──

def list_objects(domain: Optional[str] = None, tenant_id: Optional[str] = None) -> list[dict]:
    """列出所有 Object，可按域 / 租户过滤"""
    return registry.list_objects(domain, tenant_id)


def get_object(name: str, tenant_id: Optional[str] = None) -> Optional[dict]:
    """按名称获取 Object"""
    return registry.get_object(name, tenant_id)


def list_links(tenant_id: Optional[str] = None) -> list[dict]:
    """列出所有 Link"""
    return registry.list_links(tenant_id)


def get_link(name: str, tenant_id: Optional[str] = None) -> Optional[dict]:
    """按名称获取 Link"""
    return registry.get_link(name, tenant_id)


def list_actions(domain: Optional[str] = None, risk_level: Optional[str] = None,
                 tenant_id: Optional[str] = None) -> list[dict]:
    """列出所有 Action，可按域 / 风险等级 / 租户过滤"""
    return registry.list_actions(domain, risk_level, tenant_id)


def get_action(name: str, tenant_id: Optional[str] = None) -> Optional[dict]:
    """按名称获取 Action"""
    return registry.get_action(name, tenant_id)


def reload_ontology() -> dict:
    """热更新入口：重新从 DB 加载本体缓存"""
    return registry.reload()
