"""PermissionRegistry - OBAC/RBAC 权限矩阵的 DB 读取层（带内置默认兜底）

背景
────
`ontology/permissions.py` 的 ROLE_PERMISSIONS / OBJECT_PERMISSIONS / ROLE_DEFINITIONS
原本是纯 Python 硬编码，与本体常量同源问题：改权限 = 改代码 + 重启，无法按租户差异化。

本模块把权威源迁到 `psp_ontology.db`，同时保持**鉴权路径绝对安全**：

  1. **fail-safe 而非 fail-open**：DB 不可用 / 表为空时，回退到 `permissions.py`
     的内置默认矩阵，绝不返回「空权限」（会导致全员被拒）或「全权限」（会越权）。
  2. **行为等价**：`has_permission` / `can_access_object` 的语义、通配符 `*` 处理、
     `admin` 短路逻辑全部与原实现一致。
  3. **租户覆盖**：某租户一旦在 DB 中声明了某角色的权限，即完全替换该角色的基线权限
     （替换而非合并——避免「删不掉继承来的权限」这类越权隐患）。
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 300


class PermissionRegistry:
    """权限矩阵注册表：DB 为权威源，内置常量为兜底"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._loaded = False
        self._from_db = False
        self._loaded_at = 0.0
        # 全局基线
        self._role_perms: dict[str, list[str]] = {}
        self._object_perms: dict[str, dict[str, list[str]]] = {}
        self._role_defs: list[dict] = []
        # 租户覆盖：tenant_id -> {role: [perm]}
        self._tenant_role_perms: dict[str, dict[str, list[str]]] = {}
        self._tenant_object_perms: dict[str, dict[str, dict[str, list[str]]]] = {}

    # ── 内置默认（兜底源）────────────────────────────────

    @staticmethod
    def _builtin():
        from ontology.permissions import (
            ROLE_PERMISSIONS, OBJECT_PERMISSIONS, ROLE_DEFINITIONS,
        )
        return ROLE_PERMISSIONS, OBJECT_PERMISSIONS, ROLE_DEFINITIONS

    # ── 加载 ────────────────────────────────────────────

    def load(self, force: bool = False) -> dict:
        with self._lock:
            if self._loaded and not force:
                if time.time() - self._loaded_at < _CACHE_TTL_SECONDS:
                    return self.stats()

            role_perms: dict[str, list[str]] = {}
            object_perms: dict[str, dict[str, list[str]]] = {}
            role_defs: list[dict] = []
            tenant_role: dict[str, dict[str, list[str]]] = {}
            tenant_object: dict[str, dict[str, dict[str, list[str]]]] = {}
            from_db = False

            try:
                from database import (
                    OntologySessionLocal, RolePermissionDefinition,
                    ObjectPermissionDefinition, RoleDefinition,
                )
                with OntologySessionLocal() as db:
                    rp_rows = db.query(RolePermissionDefinition).all()
                    op_rows = db.query(ObjectPermissionDefinition).all()
                    rd_rows = (
                        db.query(RoleDefinition)
                        .order_by(RoleDefinition.sort_order, RoleDefinition.id)
                        .all()
                    )

                    if rp_rows:
                        from_db = True
                        for r in rp_rows:
                            if r.tenant_id:
                                tenant_role.setdefault(r.tenant_id, {}).setdefault(
                                    r.role, []).append(r.permission)
                            else:
                                role_perms.setdefault(r.role, []).append(r.permission)
                        for r in op_rows:
                            if r.tenant_id:
                                (tenant_object.setdefault(r.tenant_id, {})
                                 .setdefault(r.object_name, {})
                                 .setdefault(r.access, []).append(r.role))
                            else:
                                (object_perms.setdefault(r.object_name, {})
                                 .setdefault(r.access, []).append(r.role))
                        role_defs = [
                            {
                                "code": r.code,
                                "display_name": r.display_name,
                                "description": r.description or "",
                            }
                            for r in rd_rows if not r.tenant_id
                        ]
            except Exception as e:
                logger.warning("[permissions] 从 DB 加载权限矩阵失败，回退内置默认: %s", e)

            if not from_db:
                b_role, b_obj, b_defs = self._builtin()
                role_perms = {k: list(v) for k, v in b_role.items()}
                object_perms = {
                    o: {a: list(rs) for a, rs in m.items()} for o, m in b_obj.items()
                }
                role_defs = list(b_defs)
                tenant_role, tenant_object = {}, {}

            self._role_perms = role_perms
            self._object_perms = object_perms
            self._role_defs = role_defs
            self._tenant_role_perms = tenant_role
            self._tenant_object_perms = tenant_object
            self._loaded = True
            self._from_db = from_db
            self._loaded_at = time.time()

            logger.info(
                "[permissions] 权限矩阵加载完成 source=%s roles=%d objects=%d",
                "db" if from_db else "builtin", len(role_perms), len(object_perms),
            )
            return self.stats()

    def reload(self) -> dict:
        return self.load(force=True)

    def _ensure(self) -> None:
        if not self._loaded:
            self.load()

    def stats(self) -> dict:
        return {
            "source": "db" if self._from_db else "builtin",
            "roles": len(self._role_perms),
            "objects": len(self._object_perms),
            "role_definitions": len(self._role_defs),
            "tenant_overrides": sorted(
                set(self._tenant_role_perms) | set(self._tenant_object_perms)
            ),
        }

    @property
    def source(self) -> str:
        self._ensure()
        return "db" if self._from_db else "builtin"

    # ── 查询接口 ────────────────────────────────────────

    def get_role_permissions(self, role: str,
                             tenant_id: Optional[str] = None) -> list[str]:
        """获取角色权限列表。租户声明存在时**整体替换**基线（不合并）。"""
        self._ensure()
        if tenant_id:
            overrides = self._tenant_role_perms.get(tenant_id)
            if overrides and role in overrides:
                return overrides[role]
        return self._role_perms.get(role, [])

    def has_permission(self, role: str, permission: str,
                       tenant_id: Optional[str] = None) -> bool:
        """检查角色是否拥有指定权限（行为与原 permissions.has_permission 等价）"""
        perms = self.get_role_permissions(role, tenant_id)
        return "*" in perms or permission in perms

    def can_access_object(self, role: str, object_name: str, access: str = "read",
                          tenant_id: Optional[str] = None) -> bool:
        """OBAC：检查角色能否以指定方式访问某 Object。

        行为与原实现严格等价（fail-safe）：
          - admin 直接放行
          - 未声明的 Object 返回 False（默认拒绝，不是放行）
        """
        if role == "admin":
            return True
        self._ensure()
        obj_perms = None
        if tenant_id:
            t = self._tenant_object_perms.get(tenant_id)
            if t and object_name in t:
                obj_perms = t[object_name]
        if obj_perms is None:
            obj_perms = self._object_perms.get(object_name, {})
        return role in obj_perms.get(access, [])

    def list_role_definitions(self) -> list[dict]:
        self._ensure()
        return self._role_defs

    @property
    def role_permissions(self) -> dict[str, list[str]]:
        self._ensure()
        return self._role_perms

    @property
    def object_permissions(self) -> dict[str, dict[str, list[str]]]:
        self._ensure()
        return self._object_perms


registry = PermissionRegistry()


def seed_permissions_to_db() -> dict:
    """把内置默认权限矩阵 upsert 进 DB（仅写全局基线行，不动租户覆盖）"""
    from database import (
        OntologySessionLocal, RolePermissionDefinition,
        ObjectPermissionDefinition, RoleDefinition,
    )
    from ontology.permissions import (
        ROLE_PERMISSIONS, OBJECT_PERMISSIONS, ROLE_DEFINITIONS,
    )

    stats = {"role_permissions": 0, "object_permissions": 0, "role_definitions": 0}
    with OntologySessionLocal() as db:
        existing_rp = {
            (r.role, r.permission)
            for r in db.query(RolePermissionDefinition)
            .filter(RolePermissionDefinition.tenant_id.is_(None)).all()
        }
        for role, perms in ROLE_PERMISSIONS.items():
            for perm in perms:
                if (role, perm) in existing_rp:
                    continue
                db.add(RolePermissionDefinition(role=role, permission=perm))
                stats["role_permissions"] += 1

        existing_op = {
            (r.object_name, r.access, r.role)
            for r in db.query(ObjectPermissionDefinition)
            .filter(ObjectPermissionDefinition.tenant_id.is_(None)).all()
        }
        for obj_name, access_map in OBJECT_PERMISSIONS.items():
            for access, roles in (access_map or {}).items():
                for role in roles:
                    if (obj_name, access, role) in existing_op:
                        continue
                    db.add(ObjectPermissionDefinition(
                        object_name=obj_name, access=access, role=role))
                    stats["object_permissions"] += 1

        existing_rd = {
            r.code for r in db.query(RoleDefinition)
            .filter(RoleDefinition.tenant_id.is_(None)).all()
        }
        for idx, rd in enumerate(ROLE_DEFINITIONS):
            code = rd.get("code")
            if not code or code in existing_rd:
                continue
            db.add(RoleDefinition(
                code=code,
                display_name=rd.get("display_name", code),
                description=rd.get("description", ""),
                sort_order=idx,
            ))
            stats["role_definitions"] += 1

        db.commit()

    stats["cache"] = registry.reload()
    return stats
