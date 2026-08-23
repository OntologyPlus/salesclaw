"""AI 洞察定时预生成服务

每天早上 6:00 为所有租户的所有领域预生成 AI 洞察，
存入 ai_insight_cache 表，/ai-insights 端点直接查询缓存。

执行策略：
  - 每天 06:00 执行一次
  - 启动时计算距离下次 06:00 的秒数，sleep 到目标时间
  - 每次为所有活跃租户的所有 13 个领域生成洞察
  - 单域生成失败不影响其他域
  - LLM 模式失败自动降级到预设

使用 asyncio.create_task 在后台运行，无需第三方调度库。
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

logger = logging.getLogger(__name__)

# 支持的领域列表（与 ai_insight_service._DOMAIN_INSIGHTS 保持一致）
SUPPORTED_DOMAINS: List[str] = [
    "sales", "training", "decision", "collab", "knowledge",
    "crm", "cfm", "mdm", "audit", "observability",
    "platform", "settings", "tools",
]

# 每天执行时间（小时:分钟）
SCHEDULE_HOUR = 6
SCHEDULE_MINUTE = 0

# F1: SLA 检查执行间隔（秒）= 1 小时
SLA_CHECK_INTERVAL_SECONDS = 3600

# F8: 月度复核触发日 = 每月 12 日（与每日 06:00 洞察生成同时间触发）
CLOSURE_REVIEW_DAY = 12

# 全局调度器实例
_scheduler_task: asyncio.Task = None
_sla_check_task: asyncio.Task = None


def _seconds_until_next_run() -> int:
    """计算距离下次 SCHEDULE_HOUR:SCHEDULE_MINUTE 的秒数

    如果今天的目标时间已过，则返回到明天同一时间的秒数。
    """
    now = datetime.now()
    target = now.replace(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, second=0, microsecond=0)
    if target <= now:
        target = target + timedelta(days=1)
    return int((target - now).total_seconds())


async def _generate_all_insights():
    """为所有租户的所有领域预生成 AI 洞察

    单域失败不影响其他域。每个域使用独立的 db session。
    自动遍历所有活跃租户。
    """
    from services.ai_insight_service import ai_insight_service
    from database import BusinessSessionLocal, Tenant

    db = BusinessSessionLocal()
    try:
        tenants = db.query(Tenant).filter(Tenant.is_active == 1).all()
        tenant_ids = [str(t.id) for t in tenants]
        if not tenant_ids:
            tenant_ids = ["default"]
    finally:
        db.close()

    logger.info(f"[insight_scheduler] 开始预生成 AI 洞察，租户数: {len(tenant_ids)}")

    total_success = 0
    total_fail = 0

    for tenant_id in tenant_ids:
        for domain in SUPPORTED_DOMAINS:
            db = BusinessSessionLocal()
            try:
                # 阻塞治理：generate_and_store_insight 内部是同步 LLM 调用，
                # 放入线程池执行，避免阻塞事件循环
                insight = await asyncio.to_thread(
                    ai_insight_service.generate_and_store_insight,
                    domain=domain,
                    tenant_id=tenant_id,
                    user_id=None,
                    db=db,
                    data=None,  # 定时任务不传上下文数据，由 LLM 自行生成
                )
                generated_by = insight.get("generated_by", "unknown")
                generation_ms = insight.get("generation_ms", 0)
                logger.info(
                    f"[insight_scheduler] tenant={tenant_id} {domain}: 成功 ({generated_by}, {generation_ms}ms)"
                )
                total_success += 1
            except Exception as e:
                logger.warning(f"[insight_scheduler] tenant={tenant_id} {domain}: 失败 - {e}")
                total_fail += 1
            finally:
                db.close()

    logger.info(
        f"[insight_scheduler] 预生成完成：成功 {total_success}，失败 {total_fail}"
    )


async def _scheduler_loop():
    """定时调度循环

    每天 SCHEDULE_HOUR:SCHEDULE_MINUTE 时刻执行（如 06:00）。
    启动时计算距离下次执行时间的秒数，先 sleep 到目标时间再执行。
    """
    while True:
        # 计算到下次执行的秒数
        sleep_seconds = _seconds_until_next_run()
        next_run = datetime.now() + timedelta(seconds=sleep_seconds)
        logger.info(
            f"[insight_scheduler] 下次执行时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}, "
            f"距离 {sleep_seconds} 秒"
        )
        await asyncio.sleep(sleep_seconds)

        try:
            await _generate_all_insights()
        except Exception as e:
            logger.error(f"[insight_scheduler] 调度循环异常: {e}")

        # F8: 每月 12 日 06:00 触发月度复核批次
        try:
            from datetime import date as _date
            if _date.today().day == CLOSURE_REVIEW_DAY:
                await _run_monthly_closure_review()
        except Exception as e:
            logger.error(f"[insight_scheduler] 月度复核触发异常: {e}")


def start_insight_scheduler():
    """启动 AI 洞察定时调度器

    在 main.py 的 startup 事件中调用。
    幂等：多次调用不会重复启动。
    """
    global _scheduler_task
    if _scheduler_task is not None and not _scheduler_task.done():
        logger.info("[insight_scheduler] 调度器已在运行，跳过")
        return

    _scheduler_task = asyncio.create_task(_scheduler_loop())
    first_run = datetime.now() + timedelta(seconds=_seconds_until_next_run())
    logger.info(
        f"[insight_scheduler] 调度器已启动，"
        f"每天 {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} 执行，"
        f"下次执行: {first_run.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    # F1: 同时启动 SLA 检查调度器（每小时一次）
    start_sla_check_scheduler()


def stop_insight_scheduler():
    """停止 AI 洞察定时调度器"""
    global _scheduler_task, _sla_check_task
    if _scheduler_task is not None and not _scheduler_task.done():
        _scheduler_task.cancel()
        logger.info("[insight_scheduler] 调度器已停止")
    if _sla_check_task is not None and not _sla_check_task.done():
        _sla_check_task.cancel()
        logger.info("[insight_scheduler] SLA 检查调度器已停止")


# ──────────────────────────────────────────────
# F1: 审批流 SLA 检查调度器（借鉴企业级诊断体系 §7.4 + §13）
# ──────────────────────────────────────────────

async def _run_sla_check():
    """执行一次 SLA 检查（所有租户）

    借鉴诊断体系 §7.4 + §13：
    - 剩余 20% 时间触发提醒
    - 超期且非高风险 → 默认同意
    - 超期且高风险 → 升级 + 通知
    """
    from database import BusinessSessionLocal, Tenant
    from services.collab_service import check_overdue_approvals

    db = BusinessSessionLocal()
    try:
        tenants = db.query(Tenant).filter(Tenant.is_active == 1).all()
        tenant_ids = [str(t.id) for t in tenants]
        if not tenant_ids:
            tenant_ids = ["default"]
    finally:
        db.close()

    logger.info(f"[sla_check] 开始 SLA 检查，租户数: {len(tenant_ids)}")

    total_reminded = 0
    total_escalated = 0
    total_auto_approved = 0

    for tenant_id in tenant_ids:
        db = BusinessSessionLocal()
        try:
            # 阻塞治理：同步重活放入线程池，避免阻塞事件循环
            result = await asyncio.to_thread(check_overdue_approvals, db, tenant_id)
            total_reminded += result.get("reminded", 0)
            total_escalated += result.get("overdue_escalated", 0)
            total_auto_approved += result.get("auto_approved", 0)
        except Exception as e:
            logger.warning(f"[sla_check] tenant={tenant_id} 失败: {e}")
        finally:
            db.close()

    logger.info(
        f"[sla_check] 完成：提醒 {total_reminded}，升级 {total_escalated}，默认同意 {total_auto_approved}"
    )


async def _sla_check_loop():
    """SLA 检查调度循环

    每 SLA_CHECK_INTERVAL_SECONDS（默认 1 小时）执行一次。
    """
    while True:
        await asyncio.sleep(SLA_CHECK_INTERVAL_SECONDS)
        try:
            await _run_sla_check()
        except Exception as e:
            logger.error(f"[sla_check] 调度循环异常: {e}")


def start_sla_check_scheduler():
    """启动 SLA 检查调度器（每小时一次）

    幂等：多次调用不会重复启动。
    """
    global _sla_check_task
    if _sla_check_task is not None and not _sla_check_task.done():
        logger.info("[sla_check] 调度器已在运行，跳过")
        return

    _sla_check_task = asyncio.create_task(_sla_check_loop())
    logger.info(
        f"[sla_check] 调度器已启动，每 {SLA_CHECK_INTERVAL_SECONDS // 3600} 小时执行一次"
    )


def trigger_sla_check_now():
    """立即触发一次 SLA 检查（用于测试或手动触发）

    返回执行结果摘要。
    """
    import asyncio as _asyncio
    try:
        loop = _asyncio.get_event_loop()
    except RuntimeError:
        loop = _asyncio.new_event_loop()
        _asyncio.set_event_loop(loop)

    if loop.is_running():
        # 已在事件循环中，创建任务异步执行
        _asyncio.create_task(_run_sla_check())
        return {"status": "scheduled", "message": "SLA 检查已异步触发"}
    else:
        # 同步执行
        loop.run_until_complete(_run_sla_check())
        return {"status": "completed", "message": "SLA 检查已完成"}


def trigger_insight_generation_now():
    """立即触发一次洞察生成（用于测试或手动触发）

    遍历所有活跃租户，为每个租户的每个领域生成洞察。
    返回执行结果摘要。
    """
    from database import BusinessSessionLocal, Tenant, AIInsightCache
    from services.ai_insight_service import ai_insight_service

    db = BusinessSessionLocal()
    try:
        tenants = db.query(Tenant).filter(Tenant.is_active == 1).all()
        tenant_ids = [str(t.id) for t in tenants]
        if not tenant_ids:
            tenant_ids = ["default"]
    finally:
        db.close()

    results = []
    for tenant_id in tenant_ids:
        for domain in SUPPORTED_DOMAINS:
            db = BusinessSessionLocal()
            try:
                insight = ai_insight_service.generate_and_store_insight(
                    domain=domain,
                    tenant_id=tenant_id,
                    user_id=None,
                    db=db,
                    data=None,
                )
                results.append({
                    "tenant_id": tenant_id,
                    "domain": domain,
                    "status": "ok",
                    "generated_by": insight.get("generated_by"),
                    "generation_ms": insight.get("generation_ms", 0),
                })
            except Exception as e:
                results.append({
                    "tenant_id": tenant_id,
                    "domain": domain,
                    "status": "fail",
                    "error": str(e),
                })
            finally:
                db.close()
    return results


# ──────────────────────────────────────────────
# F8: 月度闭环复核调度器（借鉴企业级诊断体系 §7.5、§8.4）
# ──────────────────────────────────────────────

async def _run_monthly_closure_review():
    """每月 12 日 06:00 触发月度闭环复核批次

    对应诊断体系 §7.5：
    1. 自动创建当月复核批次（cycle_month = 上月）
    2. 批量执行 run_review_batch：扫描上月及更早 status=completed 但未闭环的任务
    3. 未闭环任务 priority 升级 + 复制到下月
    """
    from database import BusinessSessionLocal, Tenant
    from services.closure_review_service import (
        create_monthly_review_cycle, run_review_batch,
    )

    db = BusinessSessionLocal()
    try:
        tenants = db.query(Tenant).filter(Tenant.is_active == 1).all()
        tenant_ids = [str(t.id) for t in tenants]
        if not tenant_ids:
            tenant_ids = ["default"]
    finally:
        db.close()

    logger.info(f"[closure_review] 开始月度复核，租户数: {len(tenant_ids)}")

    total_processed = 0
    total_closed = 0
    total_partial = 0
    total_unresolved = 0
    total_promoted = 0

    for tenant_id in tenant_ids:
        db = BusinessSessionLocal()
        try:
            # 阻塞治理：同步批量扫描放入线程池，避免阻塞事件循环
            def _run_batch(db=db, tenant_id=tenant_id):
                cycle = create_monthly_review_cycle(db, tenant_id, actor_id=0)
                return cycle, run_review_batch(db, tenant_id, cycle.id, batch_size=100)

            cycle, result = await asyncio.to_thread(_run_batch)
            total_processed += result.get("processed", 0)
            total_closed += result.get("closed", 0)
            total_partial += result.get("partial", 0)
            total_unresolved += result.get("unresolved", 0)
            total_promoted += result.get("promoted", 0)
        except Exception as e:
            logger.warning(f"[closure_review] tenant={tenant_id} 失败: {e}")
        finally:
            db.close()

    logger.info(
        f"[closure_review] 月度复核完成："
        f"processed={total_processed} closed={total_closed} "
        f"partial={total_partial} unresolved={total_unresolved} promoted={total_promoted}"
    )


def trigger_closure_review_now():
    """立即触发一次月度闭环复核（用于测试或手动触发）

    返回执行结果摘要。
    """
    import asyncio as _asyncio
    try:
        loop = _asyncio.get_event_loop()
    except RuntimeError:
        loop = _asyncio.new_event_loop()
        _asyncio.set_event_loop(loop)

    if loop.is_running():
        _asyncio.create_task(_run_monthly_closure_review())
        return {"status": "scheduled", "message": "月度闭环复核已异步触发"}
    else:
        loop.run_until_complete(_run_monthly_closure_review())
        return {"status": "completed", "message": "月度闭环复核已完成"}


__all__ = [
    "start_insight_scheduler",
    "stop_insight_scheduler",
    "trigger_insight_generation_now",
    "start_sla_check_scheduler",
    "trigger_sla_check_now",
    "trigger_closure_review_now",
    "SUPPORTED_DOMAINS",
]
