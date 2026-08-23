"""事件总线装配 - 订阅者注册 + pending 事件后台消费任务"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

# pending 事件轮询间隔（秒）
_POLL_INTERVAL_SECONDS = 30
# 单批处理条数
_BATCH_SIZE = 10


def register_event_subscribers() -> None:
    """注册 AI 事件总线的订阅者"""
    from ai.event_subscribers import register_subscribers

    register_subscribers()
    logger.info("[bootstrap] AI 事件订阅者已注册")


async def process_pending_events() -> None:
    """后台任务：周期性消费 pending 事件

    `event_bus.publish(consistency="eventual")` 发布的事件先落库为 pending，
    由本任务定期拉取并交给 WriteBackEngine 执行（含指数退避重试 + 死信队列）。

    注意：`process_pending` 是同步方法，内部用 `time.sleep` 做指数退避，
    必须放到线程池执行，否则会阻塞 asyncio 事件循环。
    """
    from ai.event_bus import event_bus
    from database import BusinessSessionLocal

    while True:
        try:
            with BusinessSessionLocal() as db:
                result = await asyncio.to_thread(
                    event_bus.process_pending, db, _BATCH_SIZE
                )
            if result["processed"] > 0:
                logger.info(
                    "[event_bus] 处理 %d 条事件：完成 %d，失败 %d，死信 %d",
                    result["processed"], result["completed"],
                    result["failed"], result["dead_lettered"],
                )
        except asyncio.CancelledError:
            logger.info("[event_bus] 后台任务已取消")
            raise
        except Exception as e:
            logger.warning("[event_bus] 后台处理异常: %s", e)
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)


def start_event_worker() -> asyncio.Task:
    """启动 pending 事件后台消费任务"""
    task = asyncio.create_task(process_pending_events())
    logger.info("[bootstrap] 事件消费后台任务已启动")
    return task
