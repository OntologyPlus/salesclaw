"""AI 事件总线 + Write-Back 引擎

提供 AI 领域事件驱动能力：
- AIEventBus：医药销售场景事件的发布、订阅、重放
- WriteBackEngine：指数退避重试 + 死信队列，保证最终一致性

一致性策略：
- strong（强一致）：发布时同步执行订阅者，失败则标记事件 failed
- eventual（最终一致）：仅落库为 pending，由 process_pending 异步消费

N+4 升级：支持 causation_id（因果链）+ affected_domains（影响域）+ correlate（关联查询）

数据来源：AIEvent / DeadLetter 表。
"""
import logging
import time
from datetime import datetime
from typing import Callable, Optional

from sqlalchemy.orm import Session

from database import AIEvent, DeadLetter

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────

# 事件状态
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_DEAD_LETTER = "dead_letter"

# 一致性级别
CONSISTENCY_STRONG = "strong"
CONSISTENCY_EVENTUAL = "eventual"


# ──────────────────────────────────────────────
# 事件总线
# ──────────────────────────────────────────────

class AIEventBus:
    """AI 事件总线

    12 种医药销售领域事件，支持 strong / eventual 两种一致性模式。
    """

    # AI 领域事件（医药销售适配）
    EVENT_TYPES: dict[str, str] = {
        "visit_plan_created": "拜访计划已创建",
        "visit_record_feedback": "拜访反馈已提交",
        "course_recommended": "课程已推荐",
        "course_completed": "课程已完成",
        "decision_simulated": "决策已模拟",
        "alert_triggered": "预警已触发",
        "knowledge_suggested": "知识已推荐",
        "approval_auto_inserted": "审批已自动插入",
        "safety_valve_blocked": "安全阀已拦截",
        "hallucination_rejected": "幻觉内容已拒绝",
        "reflection_retried": "自我反思已重试",
        "decision_executed": "决策已执行",
        # 数据采集域事件
        "collection_item_submitted": "数据项已提交",
        "collection_item_approved": "数据项已批准",
        "collection_item_rejected": "数据项已驳回",
        "collection_item_published": "数据项已发布",
        # 培训活动域事件
        "activity_published": "培训活动已发布",
        "activity_off_shelf": "培训活动已下架",
        # 通知中心域事件
        "notification_sent": "通知已发送",
        "notification_failed": "通知发送失败",
        # 待办任务域事件
        "todo_submitted": "待办任务已提交",
        "todo_regenerated": "待办任务已重新生成",
        # N+2 训战升级域事件
        "persona_created": "角色画像已创建",
        "scenario_parsed": "剧本已解析为场景",
        "ppt_session_completed": "PPT 演讲会话已完成",
        "experience_earned": "经验值已累积",
        # N+3 决策穿透域事件
        "context_switched": "全局上下文已切换",
        "territory_queried": "辖区数据已查询",
        # N+4 深度融合域事件
        "insight_generated": "因果洞察已生成",
        "suggestion_action_recorded": "建议行动已记录",
        "suggestion_outcome_evaluated": "建议效果已评估",
        "skill_chain_executed": "Skill 组合链已执行",
        "ability_score_updated": "能力分已更新",
        "ability_decay_applied": "能力衰减已应用",
        "weakness_detected": "弱项已检测",
        "training_scenario_recommended": "培训场景已推荐",
        "recommendation_generated": "决策建议已生成",
        "recommendation_accepted": "建议已接受",
        "recommendation_rejected": "建议已拒绝",
        "collection_rule_violated": "采集规则违反",
        "derived_field_computed": "派生字段已计算",
        "skill_fit_recomputed": "技能匹配已重算",
        "practice_session_completed": "训战会话已完成",
        # B 路径：培训效果因果归因新增考试通过事件
        "exam_passed": "考试已通过",
        # 借鉴企业级诊断体系-批次1：审批流 SLA + 绩效边界事件
        "approval_submitted": "审批已提交",
        "approval_overdue": "审批已超期",
        "approval_escalated": "审批已升级",
        "approval_default_approved": "审批已默认同意",
        "performance_boundary_blocked": "绩效边界已阻断",
    }

    def __init__(self):
        # 事件类型 → 订阅者函数列表；延迟绑定，便于扩展
        self._subscribers: dict[str, list[Callable]] = {}

    def subscribe(self, event_type: str, handler: Optional[Callable] = None):
        """订阅事件

        支持两种用法：
          1. 直接调用：event_bus.subscribe("event_type", handler_fn)
          2. 装饰器：  @event_bus.subscribe("event_type")

        Args:
            event_type: 事件类型，必须存在于 EVENT_TYPES
            handler: 处理函数，签名 (payload: dict, tenant_id: str, db: Session) -> None
        """
        def _register(func: Callable) -> Callable:
            if event_type not in self.EVENT_TYPES:
                raise ValueError(f"unknown event_type: {event_type}")
            self._subscribers.setdefault(event_type, []).append(func)
            return func

        if handler is not None:
            return _register(handler)
        return _register

    def publish(
        self,
        event_type: str,
        payload: dict,
        tenant_id: str = "default",
        consistency: str = "eventual",
        db: Optional[Session] = None,
        causation_id: Optional[str] = None,
        affected_domains: Optional[list[str]] = None,
    ) -> dict:
        """发布事件

        1. 持久化事件到 AIEvent 表
        2. strong 模式：同步执行订阅者，失败则标记 failed
        3. eventual 模式：标记为 pending，等待异步处理

        Args:
            event_type: 事件类型
            payload: 事件载荷
            tenant_id: 租户 ID
            consistency: strong / eventual
            db: 数据库 session；为 None 时仅返回不落库
            causation_id: N+4 因果链上游事件 ID（用于串联事件链）
            affected_domains: N+4 影响域列表（如 ["profile", "training"]）

        Returns:
            {event_id, status}
        """
        # 参数校验
        if event_type not in self.EVENT_TYPES:
            return {"error": "unknown_event_type", "event_type": event_type}
        if consistency not in (CONSISTENCY_STRONG, CONSISTENCY_EVENTUAL):
            consistency = CONSISTENCY_EVENTUAL

        # N+4: 将 causation_id 和 affected_domains 注入 payload（兼容旧表结构）
        enriched_payload = dict(payload or {})
        if causation_id:
            enriched_payload["_causation_id"] = causation_id
        if affected_domains:
            enriched_payload["_affected_domains"] = affected_domains

        # 1. 持久化事件
        event_id = None
        if db is not None:
            try:
                event = AIEvent(
                    tenant_id=tenant_id,
                    event_type=event_type,
                    payload=enriched_payload,
                    consistency=consistency,
                    status=STATUS_PENDING,
                    retry_count=0,
                    error_message=None,
                    published_at=datetime.utcnow(),
                    completed_at=None,
                )
                db.add(event)
                db.commit()
                db.refresh(event)
                event_id = event.id
            except Exception as exc:
                db.rollback()
                return {"error": "persist_failed", "detail": str(exc)}

        # 2. strong 模式：同步执行订阅者
        if consistency == CONSISTENCY_STRONG and db is not None and event_id is not None:
            return self._run_strong(event_id, event_type, enriched_payload, tenant_id, db)

        # 3. eventual 模式：保持 pending，等待 process_pending
        return {"event_id": event_id, "status": STATUS_PENDING}

    def _run_strong(
        self,
        event_id: int,
        event_type: str,
        payload: dict,
        tenant_id: str,
        db: Session,
    ) -> dict:
        """同步执行订阅者（strong 一致性模式）"""
        event = db.query(AIEvent).filter(AIEvent.id == event_id).first()
        if event is None:
            return {"event_id": event_id, "status": STATUS_FAILED,
                    "error": "event_not_found_after_persist"}
        try:
            event.status = STATUS_PROCESSING
            db.commit()

            handlers = self._subscribers.get(event_type, [])
            errors: list[str] = []
            for handler in handlers:
                try:
                    handler(payload, tenant_id, db)
                except Exception as exc:
                    errors.append(f"{handler.__name__}: {exc}")

            if errors:
                event.status = STATUS_FAILED
                event.error_message = "; ".join(errors)
                db.commit()
                return {"event_id": event_id, "status": STATUS_FAILED,
                        "error": event.error_message}

            event.status = STATUS_COMPLETED
            event.completed_at = datetime.utcnow()
            db.commit()
            return {"event_id": event_id, "status": STATUS_COMPLETED}
        except Exception as exc:
            db.rollback()
            try:
                # 尝试再次标记为 failed
                ev = db.query(AIEvent).filter(AIEvent.id == event_id).first()
                if ev is not None:
                    ev.status = STATUS_FAILED
                    ev.error_message = f"strong_mode_exception: {exc}"
                    db.commit()
            except Exception:
                db.rollback()
            return {"event_id": event_id, "status": STATUS_FAILED,
                    "error": str(exc)}

    def process_pending(self, db: Session, batch_size: int = 10) -> dict:
        """处理 pending 事件（异步模式模拟）

        逐条拉取 pending 事件，调用 WriteBackEngine.execute；失败次数累计后入死信。

        Returns:
            {processed, completed, failed, dead_lettered}
        """
        # 拉取 pending 事件
        events = db.query(AIEvent).filter(
            AIEvent.status == STATUS_PENDING,
            AIEvent.is_deleted == 0,
        ).order_by(AIEvent.published_at.asc()).limit(max(1, min(batch_size, 200))).all()

        result = {"processed": 0, "completed": 0, "failed": 0, "dead_lettered": 0}
        for event in events:
            result["processed"] += 1
            # 延迟绑定 writeback_engine 避免循环引用
            wb_result = writeback_engine.execute(
                event_type=event.event_type,
                payload=event.payload or {},
                tenant_id=event.tenant_id,
                db=db,
            )
            status = wb_result.get("status")
            if status == STATUS_COMPLETED:
                # 标记事件为 completed
                event.status = STATUS_COMPLETED
                event.completed_at = datetime.utcnow()
                db.commit()
                result["completed"] += 1
            elif status == STATUS_DEAD_LETTER:
                # 入死信队列
                event.status = STATUS_DEAD_LETTER
                db.commit()
                self._create_dead_letter(
                    db=db,
                    event_id=event.id,
                    event_type=event.event_type,
                    payload=event.payload or {},
                    error_message=wb_result.get("error", "max_retry_exceeded"),
                    tenant_id=event.tenant_id,
                )
                result["dead_lettered"] += 1
            else:
                # 失败但未达上限，更新重试计数与错误信息
                event.status = STATUS_FAILED
                event.retry_count = wb_result.get("retry_count", event.retry_count)
                event.error_message = wb_result.get("error", "execution_failed")
                db.commit()
                result["failed"] += 1
        return result

    def _create_dead_letter(
        self,
        db: Session,
        event_id: int,
        event_type: str,
        payload: dict,
        error_message: str,
        tenant_id: str,
    ) -> Optional[int]:
        """创建死信记录"""
        try:
            dl = DeadLetter(
                tenant_id=tenant_id,
                event_id=event_id,
                event_type=event_type,
                payload=payload,
                error_message=error_message,
                failed_at=datetime.utcnow(),
                resolved=0,
            )
            db.add(dl)
            db.commit()
            db.refresh(dl)
            return dl.id
        except Exception as exc:
            db.rollback()
            logger.warning("[event_bus] create dead letter failed: %s", exc)
            return None

    # ──────────────────────────────────────────────
    # 查询
    # ──────────────────────────────────────────────

    def get_events(
        self,
        tenant_id: str,
        db: Session,
        event_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """获取事件列表（按发布时间倒序）"""
        q = db.query(AIEvent).filter(
            AIEvent.tenant_id == tenant_id,
            AIEvent.is_deleted == 0,
        )
        if event_type:
            q = q.filter(AIEvent.event_type == event_type)
        if status:
            q = q.filter(AIEvent.status == status)
        events = q.order_by(AIEvent.published_at.desc()).limit(
            max(1, min(limit, 200))
        ).all()
        return [self._event_to_dict(e) for e in events]

    def correlate(
        self,
        db: Session,
        event_id: Optional[int] = None,
        tenant_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """N+4: 查询因果链时间线

        向上追溯 causation_id 链，向下查询以本事件为 causation_id 的下游事件。

        Args:
            event_id: 起始事件 ID
            tenant_id: 租户 ID（可选过滤）
            limit: 最大返回数量

        Returns:
            因果链事件列表（按时间正序）
        """
        if event_id is None:
            return []

        # 获取起始事件
        start_event = db.query(AIEvent).filter(
            AIEvent.id == event_id,
            AIEvent.is_deleted == 0,
        ).first()
        if not start_event:
            return []

        result = []
        seen_ids = {event_id}

        # 1. 向上追溯 causation_id 链
        current = start_event
        upstream = []
        while current:
            payload = current.payload or {}
            causation_id = payload.get("_causation_id")
            if causation_id and causation_id not in seen_ids:
                # 查找上游事件（causation_id 可能是 event_id 的字符串形式）
                try:
                    parent_id = int(causation_id)
                    parent = db.query(AIEvent).filter(
                        AIEvent.id == parent_id,
                        AIEvent.is_deleted == 0,
                    ).first()
                    if parent and parent.id not in seen_ids:
                        upstream.insert(0, parent)
                        seen_ids.add(parent.id)
                        current = parent
                        continue
                except (ValueError, TypeError):
                    pass
            break

        # 2. 向下查询以本事件为 causation_id 的下游事件
        downstream = []
        # 查找 payload 中 _causation_id 为 event_id 的事件
        all_events = db.query(AIEvent).filter(
            AIEvent.is_deleted == 0,
        )
        if tenant_id:
            all_events = all_events.filter(AIEvent.tenant_id == tenant_id)
        all_events = all_events.order_by(AIEvent.published_at.asc()).limit(limit).all()

        for ev in all_events:
            if ev.id in seen_ids:
                continue
            payload = ev.payload or {}
            causation_id = payload.get("_causation_id")
            if causation_id and str(causation_id) == str(event_id):
                downstream.append(ev)
                seen_ids.add(ev.id)

        # 3. 合并：upstream + start_event + downstream
        chain = upstream + [start_event] + downstream
        return [self._event_to_dict(e) for e in chain]

    def get_dead_letters(self, tenant_id: str, db: Session, limit: int = 20) -> list[dict]:
        """获取死信列表（按失败时间倒序）"""
        q = db.query(DeadLetter).filter(
            DeadLetter.tenant_id == tenant_id,
            DeadLetter.is_deleted == 0,
        )
        records = q.order_by(DeadLetter.failed_at.desc()).limit(
            max(1, min(limit, 200))
        ).all()
        return [self._dead_letter_to_dict(r) for r in records]

    def resolve_dead_letter(
        self,
        dead_letter_id: int,
        tenant_id: str,
        db: Session,
        resolved_by: int,
        note: str = "",
    ) -> dict:
        """标记死信为已解决

        Args:
            dead_letter_id: 死信 ID
            resolved_by: 处理人 ID
            note: 处理说明
        """
        record = db.query(DeadLetter).filter(
            DeadLetter.id == dead_letter_id,
            DeadLetter.tenant_id == tenant_id,
            DeadLetter.is_deleted == 0,
        ).first()
        if record is None:
            return {"error": "not_found", "dead_letter_id": dead_letter_id}
        try:
            record.resolved = 1
            record.resolved_at = datetime.utcnow()
            record.resolved_by = resolved_by
            record.resolution_note = note
            db.commit()
            db.refresh(record)
        except Exception as exc:
            db.rollback()
            return {"error": "update_failed", "detail": str(exc)}
        return self._dead_letter_to_dict(record)

    def replay_event(self, event_id: int, tenant_id: str, db: Session) -> dict:
        """重放事件

        将指定事件重新交给 WriteBackEngine 执行，并重置重试计数。
        """
        event = db.query(AIEvent).filter(
            AIEvent.id == event_id,
            AIEvent.tenant_id == tenant_id,
            AIEvent.is_deleted == 0,
        ).first()
        if event is None:
            return {"error": "not_found", "event_id": event_id}

        # 调用 WriteBackEngine 重新执行
        wb_result = writeback_engine.execute(
            event_type=event.event_type,
            payload=event.payload or {},
            tenant_id=event.tenant_id,
            db=db,
        )
        status = wb_result.get("status")
        try:
            if status == STATUS_COMPLETED:
                event.status = STATUS_COMPLETED
                event.completed_at = datetime.utcnow()
                event.error_message = None
                db.commit()
            elif status == STATUS_DEAD_LETTER:
                event.status = STATUS_DEAD_LETTER
                event.error_message = wb_result.get("error", "max_retry_exceeded")
                db.commit()
                self._create_dead_letter(
                    db=db,
                    event_id=event.id,
                    event_type=event.event_type,
                    payload=event.payload or {},
                    error_message=event.error_message,
                    tenant_id=event.tenant_id,
                )
            else:
                event.status = STATUS_FAILED
                event.error_message = wb_result.get("error", "replay_failed")
                event.retry_count = wb_result.get("retry_count", event.retry_count)
                db.commit()
            db.refresh(event)
        except Exception as exc:
            db.rollback()
            return {"error": "replay_failed", "detail": str(exc)}

        result = self._event_to_dict(event)
        result["replay_result"] = wb_result
        return result

    # ──────────────────────────────────────────────
    # 序列化
    # ──────────────────────────────────────────────

    @staticmethod
    def _event_to_dict(event: AIEvent) -> dict:
        payload = event.payload or {}
        return {
            "event_id": event.id,
            "event_type": event.event_type,
            "event_type_desc": AIEventBus.EVENT_TYPES.get(event.event_type, ""),
            "payload": payload,
            "causation_id": payload.get("_causation_id"),
            "affected_domains": payload.get("_affected_domains", []),
            "consistency": event.consistency,
            "status": event.status,
            "retry_count": event.retry_count,
            "error_message": event.error_message,
            "published_at": event.published_at.isoformat() if event.published_at else None,
            "completed_at": event.completed_at.isoformat() if event.completed_at else None,
        }

    @staticmethod
    def _dead_letter_to_dict(record: DeadLetter) -> dict:
        return {
            "dead_letter_id": record.id,
            "event_id": record.event_id,
            "event_type": record.event_type,
            "event_type_desc": AIEventBus.EVENT_TYPES.get(record.event_type, ""),
            "payload": record.payload or {},
            "error_message": record.error_message,
            "failed_at": record.failed_at.isoformat() if record.failed_at else None,
            "resolved": record.resolved,
            "resolved_at": record.resolved_at.isoformat() if record.resolved_at else None,
            "resolved_by": record.resolved_by,
            "resolution_note": record.resolution_note,
        }


# ──────────────────────────────────────────────
# Write-Back 引擎
# ──────────────────────────────────────────────

class WriteBackEngine:
    """Write-Back 引擎

    指数退避重试 + 死信队列：
        - MAX_RETRY：3 次
        - 退避：1s, 2s, 4s
        - 失败入死信队列
    """

    MAX_RETRY = 3

    # 退避序列（秒）
    _BACKOFF_SECONDS = [1, 2, 4]

    def execute(
        self,
        event_type: str,
        payload: dict,
        tenant_id: str,
        db: Session,
    ) -> dict:
        """执行事件处理，含指数退避重试

        注意：本方法为同步阻塞实现（重试间含 time.sleep 退避），
        禁止直接在 asyncio 事件循环中调用；异步上下文请用
        `asyncio.to_thread(writeback_engine.execute, ...)` 包装。

        Returns:
            {status: completed/failed/dead_letter, retry_count, error?}
        """
        last_error: Optional[str] = None
        retry_count = 0

        # 第一次执行 + 最多 MAX_RETRY 次重试
        for attempt in range(self.MAX_RETRY + 1):
            retry_count = attempt
            try:
                self._dispatch(event_type, payload, tenant_id, db)
                return {"status": STATUS_COMPLETED, "retry_count": retry_count}
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                # 最后一次不再 sleep
                if attempt < self.MAX_RETRY:
                    # 指数退避
                    sleep_seconds = self._BACKOFF_SECONDS[
                        min(attempt, len(self._BACKOFF_SECONDS) - 1)
                    ]
                    time.sleep(sleep_seconds)

        # 全部失败，标记入死信
        return {
            "status": STATUS_DEAD_LETTER,
            "retry_count": retry_count,
            "error": last_error or "max_retry_exceeded",
        }

    def _dispatch(
        self,
        event_type: str,
        payload: dict,
        tenant_id: str,
        db: Session,
    ) -> None:
        """按事件类型路由到对应处理函数

        Raises:
            Exception: 处理失败时抛出，由上层 execute 捕获并重试
        """
        handler = getattr(self, f"_handle_{event_type}", None)
        if handler is None:
            # 其他事件 → 记录审计日志
            self._handle_default(event_type, payload, tenant_id, db)
            return
        handler(payload, tenant_id, db)

    # ──────────────────────────────────────────────
    # 各事件类型处理器
    # ──────────────────────────────────────────────

    def _handle_visit_plan_created(
        self, payload: dict, tenant_id: str, db: Session
    ) -> None:
        """visit_plan_created → 更新覆盖矩阵（Mock：记录日志）"""
        plan_id = payload.get("plan_id")
        user_id = payload.get("user_id")
        period = payload.get("period")
        # Mock 实现：实际场景下应刷新 coverage_matrix 表
        logger.info(
            "[writeback] visit_plan_created: tenant=%s "
            "plan_id=%s user_id=%s period=%s → 覆盖矩阵已更新（Mock）",
            tenant_id, plan_id, user_id, period,
        )

    def _handle_course_completed(
        self, payload: dict, tenant_id: str, db: Session
    ) -> None:
        """course_completed → 更新能力评分（Mock：记录日志）"""
        course_id = payload.get("course_id")
        user_id = payload.get("user_id")
        score = payload.get("score")
        # Mock 实现：实际场景下应更新用户能力评分
        logger.info(
            "[writeback] course_completed: tenant=%s "
            "course_id=%s user_id=%s score=%s → 能力评分已更新（Mock）",
            tenant_id, course_id, user_id, score,
        )

    def _handle_alert_triggered(
        self, payload: dict, tenant_id: str, db: Session
    ) -> None:
        """alert_triggered → 发送通知（Mock：记录日志）"""
        level = payload.get("level")
        title = payload.get("title")
        category = payload.get("category")
        # Mock 实现：实际场景下应调用通知服务
        logger.info(
            "[writeback] alert_triggered: tenant=%s "
            "level=%s category=%s title=%s → 通知已发送（Mock）",
            tenant_id, level, category, title,
        )

    def _handle_default(
        self, event_type: str, payload: dict, tenant_id: str, db: Session
    ) -> None:
        """其他事件 → 记录审计日志（Mock：记录日志）"""
        # Mock 实现：实际场景下应写入 AuditLog
        logger.info(
            "[writeback] audit_log: tenant=%s "
            "event_type=%s payload_keys=%s → 审计日志已记录（Mock）",
            tenant_id, event_type, list(payload.keys()) if payload else [],
        )


# ──────────────────────────────────────────────
# 全局单例
# ──────────────────────────────────────────────

event_bus = AIEventBus()
writeback_engine = WriteBackEngine()


__all__ = ["AIEventBus", "WriteBackEngine", "event_bus", "writeback_engine"]
