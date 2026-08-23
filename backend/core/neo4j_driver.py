"""共享 Neo4j 连接管理器 —— 第十三个批次：4 个 Neo4j store 共用同一连接池。

之前每个 store 都自行 `GraphDatabase.driver(...)` 建立独立 driver：
    - graph_store.neo4j_store.Neo4jGraphStore
    - versioning.neo4j_store.Neo4jVersionStore
    - provenance.neo4j_storage.Neo4jProvenanceStorage
    - governance.neo4j_store.Neo4jCandidateStore

带来的问题：
    1. 同一进程存在 4 个 Neo4j 连接池（端口/连接数 4 倍浪费）
    2. 配置/连接参数散落 4 处，改一处忘一处
    3. 应用关闭时需调 4 次 `close()`，漏一处就泄漏连接
    4. 跨层 Cypher 桥接另起一份 driver（bridge.py 里也有独立 _get_driver），共 5 份

本模块提供 `Neo4jConnectionManager`（类方法风格单例，线程安全）：
    - acquire(...)              ：首次调用时建立共享 driver，后续直接复用
    - session(database=None)   ：从共享 driver 拿一个 session（推荐用法）
    - driver()                 ：直接拿 driver（底层 API）
    - is_connected() / database() / close_all() / reset()

设计取舍：
    - 用类属性 + 类锁而非模块级单例：类属性随进程销毁自动清理，比模块级 global
      状态更便于热重载/测试隔离（reset() 一键清空）
    - 不强制 schema 初始化由 manager 触发：每个 store 仍保留自己的 _init_schema()，
      用类级 `_schema_initialized` flag 去重。这样 schema 定义留在各 store 内（关注点分离）
    - close() 仍然在每个 store 暴露，但变成 no-op+日志，避免误调用导致共享连接关闭

"""
from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from config import settings

logger = logging.getLogger(__name__)


class Neo4jConnectionManager:
    """共享 Neo4j 连接管理器（线程安全单例）。

    使用方式：
        # 业务 store：构造时 acquire 一次
        Neo4jConnectionManager.acquire()

        # 任意位置拿会话
        with Neo4jConnectionManager.session() as s:
            s.run("...")

        # 一次性关闭（应用退出）
        Neo4jConnectionManager.close_all()
    """

    _lock = threading.Lock()
    _driver: Optional[Any] = None
    _database: Optional[str] = None
    _initialized: bool = False
    # 记录首次初始化时的连接参数，供日志/调试
    _init_uri: Optional[str] = None
    _init_user: Optional[str] = None
    _init_max_pool: Optional[int] = None
    _init_acquire_to: Optional[float] = None
    _init_timeout: Optional[float] = None

    @classmethod
    def acquire(cls, *, uri: Optional[str] = None, user: Optional[str] = None,
                password: Optional[str] = None, database: Optional[str] = None,
                timeout: Optional[float] = None,
                max_pool_size: Optional[int] = None,
                acquire_timeout: Optional[float] = None,
                force: bool = False) -> Any:
        """获取共享 driver（首次调用时建立，后续复用）。

        Args:
            uri/user/password/database/timeout/max_pool_size/acquire_timeout:
                任一 store 显式传入会被采纳，但仅在第一次（驱动未初始化时）生效。
                已初始化后忽略这些参数（保持共享）。
            force: True 时丢弃现有 driver 重建（用于 hot-reload / 重连场景）。

        Returns:
            neo4j.Driver 实例。

        Raises:
            连接失败时抛原异常（不降级），由调用方决定是否回退。
        """
        with cls._lock:
            if cls._driver is not None and cls._initialized and not force:
                # 已共享驱动；database 参数允许各 store 独立（每次 session 决定）
                return cls._driver

            from neo4j import GraphDatabase

            eff_uri = uri or settings.NEO4J_URI
            eff_user = user or settings.NEO4J_USER
            eff_pwd = password or settings.NEO4J_PASSWORD
            eff_db = database or settings.NEO4J_DATABASE
            eff_to = timeout or settings.NEO4J_TIMEOUT
            eff_pool = max_pool_size or settings.NEO4J_MAX_POOL_SIZE
            eff_acq = acquire_timeout or settings.NEO4J_ACQUIRE_TIMEOUT

            drv = GraphDatabase.driver(
                eff_uri, auth=(eff_user, eff_pwd),
                connection_timeout=eff_to,
                max_connection_pool_size=eff_pool,
                connection_acquisition_timeout=eff_acq)

            try:
                drv.verify_connectivity()
            except Exception as e:
                # 验证失败：立即关掉这个失败的 driver，不污染单例
                try:
                    drv.close()
                except Exception:
                    pass
                cls._driver = None
                cls._initialized = False
                logger.warning("Neo4jConnectionManager 连接失败: %s", e)
                raise

            cls._driver = drv
            cls._database = eff_db
            cls._initialized = True
            cls._init_uri = eff_uri
            cls._init_user = eff_user
            cls._init_max_pool = eff_pool
            cls._init_acquire_to = eff_acq
            cls._init_timeout = eff_to
            logger.info(
                "Neo4jConnectionManager: 已连接 %s db=%s pool=%s acquire_to=%ss "
                "connect_to=%ss（共享驱动）",
                eff_uri, eff_db, eff_pool, eff_acq, eff_to)
            return cls._driver

    @classmethod
    def driver(cls) -> Any:
        """直接拿底层 driver（未初始化则先 acquire）。"""
        if cls._driver is None or not cls._initialized:
            cls.acquire()
        return cls._driver  # type: ignore[return-value]

    @classmethod
    def session(cls, database: Optional[str] = None):
        """拿一个 session（最常用 API）。

        database=None 时用 acquire 时的 db（默认 settings.NEO4J_DATABASE）。
        各 store 可传入不同 database 参数（在 Neo4j Enterprise 上可跨数据库查询）。

        Returns:
            neo4j.Session 上下文管理器。
        """
        if cls._driver is None or not cls._initialized:
            cls.acquire()
        eff_db = database or cls._database or settings.NEO4J_DATABASE
        return cls._driver.session(database=eff_db)  # type: ignore[union-attr]

    @classmethod
    def is_connected(cls) -> bool:
        return cls._driver is not None and cls._initialized

    @classmethod
    def database(cls) -> str:
        return cls._database or settings.NEO4J_DATABASE

    @classmethod
    def init_info(cls) -> dict:
        """首次初始化的连接参数（用于诊断/日志）。"""
        return {
            "uri": cls._init_uri,
            "user": cls._init_user,
            "database": cls._database,
            "connected": cls._initialized,
            "max_pool_size": cls._init_max_pool,
            "acquire_timeout": cls._init_acquire_to,
            "connect_timeout": cls._init_timeout,
        }

    @classmethod
    def close_all(cls) -> None:
        """关闭共享 driver（应用退出时调用一次即可）。

        重复调用幂等。close 后下次 acquire() 会自动重建。
        """
        with cls._lock:
            if cls._driver is None:
                return
            try:
                cls._driver.close()
                logger.info("Neo4jConnectionManager: 共享 driver 已关闭")
            except Exception as e:
                logger.warning("Neo4jConnectionManager 关闭异常: %s", e)
            finally:
                cls._driver = None
                cls._database = None
                cls._initialized = False
                cls._init_uri = None
                cls._init_user = None
                cls._init_max_pool = None
                cls._init_acquire_to = None
                cls._init_timeout = None

    @classmethod
    def reset(cls) -> None:
        """测试/热重配时清空（不关闭，等下次 acquire 时重建）。"""
        with cls._lock:
            cls._driver = None
            cls._database = None
            cls._initialized = False
            cls._init_uri = None
            cls._init_user = None
            cls._init_max_pool = None
            cls._init_acquire_to = None
            cls._init_timeout = None

    @classmethod
    def latency_probe(cls) -> dict:
        """健康探测：`RETURN 1` 一次，回报耗时（毫秒）。

        Returns:
            {ok: bool, latency_ms: float|None, error: str|None}
            - 不可达时 ok=False + error，不抛异常（health check 友好）。
        """
        import time as _t
        # 主动尝试建连（lazy acquire 失败也不抛）
        if not cls.is_connected():
            try:
                cls.acquire()
            except Exception as e:
                return {"ok": False, "latency_ms": None,
                        "error": f"建连失败: {e}"}
        if not cls.is_connected():
            return {"ok": False, "latency_ms": None,
                    "error": "Neo4j 未连接"}
        start = _t.perf_counter()
        try:
            with cls.session() as s:
                row = s.run("RETURN 1 AS one").single()
                elapsed_ms = round((_t.perf_counter() - start) * 1000, 2)
                ok = row is not None and row["one"] == 1
                return {"ok": ok, "latency_ms": elapsed_ms, "error": None
                        if ok else "RETURN 1 失败"}
        except Exception as e:
            elapsed_ms = round((_t.perf_counter() - start) * 1000, 2)
            return {"ok": False, "latency_ms": elapsed_ms, "error": str(e)}

    @classmethod
    def system_snapshot(cls) -> dict:
        """Neo4j 中 4 个子系统的节点/边统计（汇集到一次性 health 响应）。

        复用 governance.bridge.system_snapshot() —— 通过 manager 共享连接取数，
        不会触发额外 driver 创建。
        """
        from governance.bridge import system_snapshot as _snapshot
        return _snapshot()
