"""通知催促调度器

每 60 秒扫描 enabled=1 且 deadline > now 的规则，
在 D-N 窗口的指定时间点发送通知。
"""
import asyncio
import logging
from datetime import datetime
from sqlalchemy import func

logger = logging.getLogger(__name__)
_scheduler_task: asyncio.Task = None


async def _process_notification_rules():
    """每 60 秒扫描规则并发送通知"""
    from database import (
        BusinessSessionLocal, NotificationRule, NotificationBatch,
        NotificationRecipient, User, PracticeSession,
    )
    from services.notification_service import InAppChannel

    while True:
        db = None
        try:
            db = BusinessSessionLocal()
            now = datetime.now()

            rules = db.query(NotificationRule).filter(
                NotificationRule.is_deleted == 0,
                NotificationRule.enabled == 1,
                NotificationRule.deadline.isnot(None),
                NotificationRule.deadline > now,
            ).all()

            channel = InAppChannel()

            for rule in rules:
                days_to_deadline = (rule.deadline - now).days

                # 检查当前是否在某个 D-N 窗口
                current_window = None
                for w in (rule.windows or []):
                    try:
                        n = int(w.replace("D-", "").replace("D", ""))
                        if days_to_deadline == n:
                            current_window = w
                            break
                    except ValueError:
                        continue

                if not current_window:
                    continue

                # 检查当前时间是否匹配 send_times
                current_time = now.strftime("%H:%M")
                if current_time not in (rule.send_times or []):
                    continue

                # 检查是否已发送过（同 rule + 同 window + 同日期）
                existing = db.query(NotificationBatch).filter(
                    NotificationBatch.is_deleted == 0,
                    NotificationBatch.rule_id == rule.id,
                    NotificationBatch.window == current_window,
                    func.date(NotificationBatch.trigger_at) == now.date(),
                ).first()
                if existing:
                    continue

                # 查询目标学员
                users = db.query(User).filter(
                    User.tenant_id == rule.tenant_id,
                    User.is_deleted == 0,
                    User.is_active == 1,
                ).all()

                if rule.target_user_type == "not_completed" and rule.scenario_id:
                    completed_ids = set(
                        ps.user_id for ps in db.query(PracticeSession).filter(
                            PracticeSession.scenario_id == rule.scenario_id,
                            PracticeSession.status == "completed",
                            PracticeSession.score >= 60,
                        ).all()
                    )
                    users = [u for u in users if u.id not in completed_ids]

                if not users:
                    continue

                title = f"【催促通知】{current_window} - 截止时间 {rule.deadline.strftime('%Y-%m-%d %H:%M')}"
                body = f"您有未完成的任务，请在 {rule.deadline.strftime('%Y-%m-%d %H:%M')} 前完成。"

                batch = NotificationBatch(
                    tenant_id=rule.tenant_id,
                    rule_id=rule.id,
                    trigger_at=now,
                    window=current_window,
                    target_count=len(users),
                    success_count=0,
                    failed_count=0,
                    message_title=title,
                    message_body=body,
                )
                db.add(batch)
                db.flush()

                success = 0
                failed = 0
                for user in users:
                    recipient = NotificationRecipient(
                        tenant_id=rule.tenant_id,
                        batch_id=batch.id,
                        learner_id=user.id,
                        status="pending",
                    )
                    db.add(recipient)
                    db.flush()

                    ok, err = await channel.send(db, rule.tenant_id, user.id, title, body)
                    if ok:
                        recipient.status = "sent"
                        recipient.sent_at = datetime.utcnow()
                        success += 1
                    else:
                        recipient.status = "failed"
                        recipient.reason = err
                        failed += 1

                batch.success_count = success
                batch.failed_count = failed
                db.commit()
                logger.info(f"[notification] rule={rule.id} window={current_window} sent={success} failed={failed}")

            db.close()
        except Exception as e:
            logger.error(f"[notification_scheduler] error: {e}")
        finally:
            if db is not None:
                db.close()

        await asyncio.sleep(60)


def start_notification_scheduler():
    """启动通知催促调度器"""
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_process_notification_rules())
        logger.info("[notification_scheduler] 已启动")


def stop_notification_scheduler():
    """停止通知催促调度器"""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        logger.info("[notification_scheduler] 已停止")
