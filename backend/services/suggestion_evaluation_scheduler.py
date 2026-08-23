"""N+4: 建议行动延迟评估调度器

定期扫描到期的待评估建议行动（evaluate_after <= now），
调用 proactive_engine.evaluate_outcome 评估效果。

执行策略：
  - 每 30 分钟执行一次
  - 每次最多评估 50 条
  - 单条失败不影响其他
  - 自动遍历所有活跃租户

使用 asyncio.create_task 在后台运行，无需第三方调度库。
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# 每 30 分钟执行一次
SCHEDULE_INTERVAL_SECONDS = 30 * 60

# 每次最多评估的行动数
BATCH_SIZE = 50

# 全局调度器实例
_scheduler_task: Optional[asyncio.Task] = None


async def _evaluate_all_tenants():
    """为所有活跃租户评估到期的待评估行动"""
    from database import BusinessSessionLocal, Tenant
    from ai.proactive_suggestions import proactive_engine

    db = BusinessSessionLocal()
    try:
        tenants = db.query(Tenant).filter(Tenant.is_active == 1).all()
        tenant_ids = [str(t.id) for t in tenants]
        if not tenant_ids:
            tenant_ids = ["default"]
    finally:
        db.close()

    total_evaluated = 0
    for tenant_id in tenant_ids:
        db = BusinessSessionLocal()
        try:
            count = proactive_engine.process_pending_evaluations(
                db=db, tenant_id=tenant_id, batch=BATCH_SIZE,
            )
            total_evaluated += count
        except Exception as e:
            logger.warning(
                f"[suggestion_eval_scheduler] tenant={tenant_id}: 评估失败 - {e}"
            )
        finally:
            db.close()

    if total_evaluated > 0:
        logger.info(
            f"[suggestion_eval_scheduler] 本次共评估 {total_evaluated} 条建议行动"
        )


async def _scheduler_loop():
    """定时调度循环 — 每 SCHEDULE_INTERVAL_SECONDS 秒执行一次"""
    # 首次启动后等待 60 秒再执行，避免与启动流程冲突
    await asyncio.sleep(60)

    while True:
        try:
            await _evaluate_all_tenants()
        except Exception as e:
            logger.error(f"[suggestion_eval_scheduler] 调度循环异常: {e}")
        await asyncio.sleep(SCHEDULE_INTERVAL_SECONDS)


def start_suggestion_evaluation_scheduler():
    """启动建议评估调度器

    在 main.py 的 startup 事件中调用。
    幂等：多次调用不会重复启动。
    """
    global _scheduler_task
    if _scheduler_task is not None and not _scheduler_task.done():
        logger.info("[suggestion_eval_scheduler] 调度器已在运行，跳过")
        return

    _scheduler_task = asyncio.create_task(_scheduler_loop())
    logger.info(
        f"[suggestion_eval_scheduler] 调度器已启动，"
        f"每 {SCHEDULE_INTERVAL_SECONDS // 60} 分钟执行一次"
    )


def stop_suggestion_evaluation_scheduler():
    """停止建议评估调度器"""
    global _scheduler_task
    if _scheduler_task is not None and not _scheduler_task.done():
        _scheduler_task.cancel()
        logger.info("[suggestion_eval_scheduler] 调度器已停止")


__all__ = [
    "start_suggestion_evaluation_scheduler",
    "stop_suggestion_evaluation_scheduler",
]
