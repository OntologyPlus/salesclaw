"""应用入口 - 药企医药代表统一平台

职责边界：本文件只负责「装配 FastAPI 应用」——中间件、异常处理、路由挂载、
生命周期钩子。所有启动期初始化逻辑（schema 迁移、基线数据、本体加载、
服务注册、事件总线、调度器）均已下沉到 `bootstrap` 包。

历史包袱说明：此前这里堆了 30+ 个 `_migrate_*` 手写 ALTER 补丁（约 830 行），
现已全部由 Alembic 接管（见 backend/alembic/versions/）。
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from config import settings
from core.exceptions import AppException
from core.response import error_response
from middleware.tenant import TenantMiddleware
from middleware.logging import LoggingMiddleware
from middleware.error_handler import app_exception_handler, validation_exception_handler, generic_exception_handler
from api import api_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """生命周期：startup 全部细节下沉到 bootstrap 包；shutdown 显式停止后台调度器"""
    from bootstrap import run_startup

    summary = run_startup()
    logger.info("[startup] 初始化完成：%s", summary)
    logger.info(
        "[startup] 服务就绪，API 文档：http://localhost:%s/docs", settings.APP_PORT
    )
    yield
    # shutdown：显式取消后台调度任务（幂等，失败不阻断退出）
    from services.insight_scheduler import stop_insight_scheduler
    from services.lag_scheduler import stop_lag_scheduler
    from core.neo4j_driver import Neo4jConnectionManager

    try:
        stop_insight_scheduler()
    except Exception as e:
        logger.warning("[shutdown] 停止后台调度器异常: %s", e)
    try:
        stop_lag_scheduler()
    except Exception as e:
        logger.warning("[shutdown] 停止 lag_scheduler 异常: %s", e)

    # 第 13 批：关闭共享 Neo4j driver（一次即可，4 个 store 共用）
    try:
        Neo4jConnectionManager.close_all()
    except Exception as e:
        logger.warning("[shutdown] 关闭 Neo4j 共享连接异常: %s", e)


app = FastAPI(
    title="药企医药代表统一平台",
    description="AI 原生的药企医药代表统一工作平台",
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "auth", "description": "认证"},
        {"name": "ai", "description": "AI 能力"},
        {"name": "ontology", "description": "Ontology"},
        {"name": "sales", "description": "销售执行"},
        {"name": "training", "description": "智能培训"},
        {"name": "decision", "description": "决策支持"},
        {"name": "collab", "description": "协同办公"},
        {"name": "knowledge", "description": "知识库"},
        {"name": "platform", "description": "平台管理"},
        {"name": "mdm", "description": "主数据"},
        {"name": "audit", "description": "审计"},
        {"name": "observability", "description": "可观测"},
        {"name": "crm", "description": "客户关系"},
        {"name": "cfm", "description": "会议论坛"},
        {"name": "tools", "description": "内容工具"},
        {"name": "training_effect", "description": "培训效果归因（B 路径）"},
    ],
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 自定义中间件
app.add_middleware(TenantMiddleware)
app.add_middleware(LoggingMiddleware)

# 异常处理
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# 路由
app.include_router(api_router)


@app.get("/health", tags=["health"])
async def health():
    """健康检查：附带两个库当前的 Alembic 版本与本体权威源，便于排查环境漂移

    第 13 批补：附带 neo4j.connected + 延迟探针，活跃探测 Neo4j 是否可达。
    与 /health/neo4j 的区别：本端点只关心「能否连上」，不返回 4 子系统节点数；
    后者给出 init_info / latency 详情。
    """
    from bootstrap.alembic_run import current_revisions
    from ontology.registry import registry
    from core.neo4j_driver import Neo4jConnectionManager

    probe = Neo4jConnectionManager.latency_probe()
    connected = Neo4jConnectionManager.is_connected()

    return {
        "status": "ok",
        "env": settings.APP_ENV,
        "migrations": current_revisions(),
        "ontology_source": registry.source,
        "neo4j": {
            "connected": connected,
            "latency_ms": probe["latency_ms"],
            "ok": probe["ok"],
        },
    }


@app.get("/health/neo4j", tags=["health"])
async def health_neo4j():
    """深探测：Neo4j 共享 driver 健康 + 4 子系统节点/边统计。

    用途：
        - k8s readiness probe：若 neo4j.ok=False 则停止接管流量
        - 运维体检：节点/边增量、4 个 store 是否都激活、连接池配置
        - 排障：latency_ms 异常时立刻能看到超时/网络问题

    响应字段：
        connected / init_info（首次建连时的参数）
        probe（RETURN 1 延迟，毫秒）
        counts（4 子系统节点/边/活动数）
        latency_warning_ms（>200ms 视为可疑）
    """
    from core.neo4j_driver import Neo4jConnectionManager

    # 主动触发建连（lazy acquire 失败也不会抛——latency_probe 内部已捕获）
    probe = Neo4jConnectionManager.latency_probe()
    connected = Neo4jConnectionManager.is_connected()
    counts = Neo4jConnectionManager.system_snapshot() if connected else None
    warning = None
    if not connected:
        warning = "Neo4j 未连接；4 个 store 走回退后端"
    elif probe["ok"] and probe["latency_ms"] is not None:
        if probe["latency_ms"] > 200:
            warning = (f"Neo4j 延迟偏高 ({probe['latency_ms']}ms > 200ms)，"
                       "可能存在连接池耗尽或网络抖动")
        elif probe["latency_ms"] > 100:
            warning = (f"Neo4j 延迟 {probe['latency_ms']}ms，"
                       "建议关注（warning 阈值 100ms）")

    return {
        "ok": probe["ok"] and connected,
        "connected": connected,
        "init_info": Neo4jConnectionManager.init_info(),
        "probe": probe,
        "counts": counts,
        "warning": warning,
    }


if __name__ == "__main__":
    import uvicorn

    # reload 仅用于本地开发；生产/测试环境关闭以避免资源浪费与重启竞态
    is_dev = settings.APP_ENV.lower() in ("development", "dev", "local")
    uvicorn.run(
        app,
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=is_dev,
        workers=1 if is_dev else (settings.UVICORN_WORKERS if getattr(settings, "UVICORN_WORKERS", None) else 1),
    )
