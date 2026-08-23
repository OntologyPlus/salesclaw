"""AI 事件总线订阅者 - 注册关键事件处理逻辑

由 main.py startup() 调用 register_subscribers()，将业务变更逻辑绑定到事件类型。
订阅者签名：(payload: dict, tenant_id: str, db: Session) -> None

N+4 改造：跨域调用通过 ServicePort + registry，不再直接 import 跨域 service。
"""
import logging

from ai.event_bus import event_bus
from core.service_registry import registry
from core.service_ports import (
    ProfileServicePort, CollectionServicePort, TrainingServicePort,
    DecisionServicePort,
)

logger = logging.getLogger(__name__)


def register_subscribers():
    """注册事件订阅者（main.py 启动时调用一次）"""

    @event_bus.subscribe("visit_record_feedback")
    def on_visit_feedback(payload, tenant_id, db):
        """拜访反馈提交 → 学习需求重算 + 高频异议检测"""
        from database import VisitFeedback, VisitRecord
        from datetime import datetime, timedelta

        user_id = payload.get("user_id")
        profile = registry.get(ProfileServicePort)
        if user_id and profile:
            try:
                profile.get_learning_needs(db, tenant_id, user_id)
            except Exception as e:
                logger.warning("学习需求重算失败: %s", e, exc_info=True)

        # 高频异议检测（近 30 天 ≥3 次 → 推送课程改进建议）
        try:
            month_ago = datetime.utcnow() - timedelta(days=30)
            feedbacks = db.query(VisitFeedback).join(
                VisitRecord, VisitRecord.id == VisitFeedback.record_id
            ).filter(
                VisitFeedback.tenant_id == tenant_id,
                VisitFeedback.is_deleted == 0,
                VisitRecord.visit_date >= month_ago.date(),
            ).all()

            objection_count: dict[str, int] = {}
            for fb in feedbacks:
                for obj in (fb.objections or []):
                    objection_count[obj] = objection_count.get(obj, 0) + 1

            for obj, count in objection_count.items():
                if count >= 3:
                    from ai.proactive_suggestions import proactive_engine
                    proactive_engine.push_suggestion(
                        None, tenant_id, "feedback_followup",
                        title=f"高频异议「{obj}」出现 {count} 次，建议更新课程内容",
                        description=f"近 30 天多位代表遇到客户对「{obj}」的异议，建议培训经理更新相关课程",
                        priority="high",
                        action={"type": "navigate", "target": "/training/courses"},
                    )
        except Exception as e:
            logger.warning("高频异议检测失败: %s", e, exc_info=True)

    @event_bus.subscribe("course_completed")
    def on_course_completed(payload, tenant_id, db):
        """课程完成 → 能力分重算 + 推荐相关医生拜访"""
        from database import Course, Product, CoverageAssignment

        user_id = payload.get("user_id")
        course_id = payload.get("course_id")
        if not user_id:
            return

        # 1. 能力分重算
        profile = registry.get(ProfileServicePort)
        if profile:
            try:
                profile.recalculate_ability_score(db, tenant_id, user_id)
            except Exception as e:
                logger.warning("能力分重算失败: %s", e, exc_info=True)

        # 2. 查询课程关联产品分类，推荐相关医生拜访
        if not course_id:
            return
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course or not course.category:
            return

        try:
            coverages = db.query(CoverageAssignment).filter(
                CoverageAssignment.tenant_id == tenant_id,
                CoverageAssignment.is_deleted == 0,
                CoverageAssignment.user_id == user_id,
            ).all()

            related_count = 0
            for cov in coverages:
                if not cov.product_id:
                    continue
                product = db.query(Product).filter(Product.id == cov.product_id).first()
                if product and product.category == course.category:
                    related_count += 1

            if related_count > 0:
                from ai.proactive_suggestions import proactive_engine
                proactive_engine.push_suggestion(
                    user_id, tenant_id, "training_reminder",
                    title=f"课程《{course.title}》已完成，建议拜访 {related_count} 位相关医生",
                    priority="medium",
                    action={"type": "navigate", "target": "/sales/plans"},
                )
        except Exception as e:
            logger.debug("课程关联医生推荐失败: %s", e, exc_info=True)

    @event_bus.subscribe("course_recommended")
    def on_exam_failed(payload, tenant_id, db):
        """考试低分 → 重新计算学习需求"""
        user_id = payload.get("user_id")
        if user_id and payload.get("reason") == "exam_failed":
            profile = registry.get(ProfileServicePort)
            if profile:
                try:
                    profile.get_learning_needs(db, tenant_id, user_id)
                except Exception as e:
                    logger.warning("学习需求重算失败: %s", e, exc_info=True)

    @event_bus.subscribe("safety_valve_blocked")
    def on_safety_blocked(payload, tenant_id, db):
        """安全阀拦截 → 记录审计日志"""
        from database import AuditLog
        try:
            log = AuditLog(
                tenant_id=tenant_id,
                actor_id=payload.get("user_id"),
                action="safety_valve_blocked",
                target="ai",
                detail=payload,
            )
            db.add(log)
            db.commit()
        except Exception:
            db.rollback()

    @event_bus.subscribe("hallucination_rejected")
    def on_hallucination(payload, tenant_id, db):
        """幻觉内容被拒 → 记录审计日志"""
        from database import AuditLog
        try:
            log = AuditLog(
                tenant_id=tenant_id,
                actor_id=payload.get("user_id"),
                action="hallucination_rejected",
                target="ai",
                detail=payload,
            )
            db.add(log)
            db.commit()
        except Exception:
            db.rollback()

    # ──────────────────────────────────────────────
    # N+4 Batch 3.1：采集→画像→培训 闭环
    # ──────────────────────────────────────────────
    @event_bus.subscribe("collection_item_published")
    def on_collection_published(payload, tenant_id, db):
        """采集发布 → 画像更新 → 弱项检测 → 培训推荐 → 推送建议

        affected_domains: ["profile", "training"]
        """
        from ai.proactive_suggestions import proactive_engine

        item_id = payload.get("item_id")
        user_id = payload.get("user_id")
        if not item_id or not user_id:
            return

        collection = registry.get(CollectionServicePort)
        profile = registry.get(ProfileServicePort)
        training = registry.get(TrainingServicePort)

        # 1. 采集→画像（apply_ability_impact 内部已发布 ability_score_updated）
        if collection:
            try:
                collection.apply_ability_impact(db, tenant_id, item_id)
            except Exception as e:
                logger.warning("采集回写画像失败: %s", e, exc_info=True)

        # 2. 画像→弱项检测
        weak_dims = []
        if profile:
            try:
                weak_dims = profile.detect_weakness(db, user_id, threshold=70.0)
            except Exception as e:
                logger.warning("弱项检测失败: %s", e, exc_info=True)

        # 3. 弱项→培训推荐 → 4. 推送建议
        if training and weak_dims:
            for dim in weak_dims:
                try:
                    dim_key = dim.get("dimension") if isinstance(dim, dict) else dim
                    scenarios = training.recommend_scenarios(
                        db, user_id, context={"dimension": dim_key}
                    )
                    for sc in (scenarios or [])[:2]:  # 每个弱项最多推 2 个场景
                        proactive_engine.push_suggestion(
                            user_id, tenant_id, "training_reminder",
                            title=f"检测到「{dim_key}」能力偏弱，推荐训战《{sc.get('title', '场景')}》",
                            description=sc.get("description", ""),
                            priority="high",
                            action={
                                "type": "navigate",
                                "target": f"/training/practice/{sc.get('id', '')}",
                            },
                        )
                except Exception as e:
                    logger.warning("培训推荐生成失败 dim=%s: %s", dim_key, e, exc_info=True)

    # ──────────────────────────────────────────────
    # N+4 Batch 3.2：培训→拜访能力传导
    # ──────────────────────────────────────────────
    @event_bus.subscribe("practice_session_completed")
    def on_practice_session_completed(payload, tenant_id, db):
        """训练完成 → 画像能力更新 → 推送进阶拜访建议

        affected_domains: ["profile", "sales"]
        注：training_service.apply_session_to_ability 已在事件发布前完成画像回写，
        本订阅者不再重复调用，仅基于已更新的画像触发销售域建议。
        """
        from ai.proactive_suggestions import proactive_engine

        user_id = payload.get("user_id")
        dimension = payload.get("dimension")  # 本次提升的维度
        delta = payload.get("delta", 0)
        if not user_id:
            return

        profile = registry.get(ProfileServicePort)

        # 画像→摘要 → 若该维度突破 80 阈值 → 推送进阶拜访建议
        if profile and delta > 0 and dimension:
            try:
                summary = profile.get_ability_summary(db, user_id)
                dim_score = next(
                    (d.get("score") for d in summary.get("dimensions", [])
                     if d.get("dimension") == dimension),
                    None
                )
                if dim_score is not None and dim_score >= 80:
                    proactive_engine.push_suggestion(
                        user_id, tenant_id, "coverage_reminder",
                        title=f"「{dimension}」能力已达 {dim_score:.0f} 分，建议挑战进阶客户拜访",
                        description="能力提升已突破阈值，可申请辖区内的重点医生进阶拜访",
                        priority="medium",
                        action={
                            "type": "navigate",
                            "target": "/sales/plans",
                        },
                    )
            except Exception as e:
                logger.warning("培训→拜访传导失败: %s", e, exc_info=True)

    # ──────────────────────────────────────────────
    # N+4 Batch 3.3：决策→行动→洞察 回环
    # ──────────────────────────────────────────────
    @event_bus.subscribe("insight_generated")
    def on_insight_generated(payload, tenant_id, db):
        """洞察生成 → 决策建议派单 → 推送通知

        affected_domains: ["decision", "notification"]
        """
        from ai.proactive_suggestions import proactive_engine

        insight_id = payload.get("insight_id")
        user_id = payload.get("user_id")
        domain = payload.get("domain")
        if not insight_id:
            return

        decision = registry.get(DecisionServicePort)
        if not decision:
            return

        # 1. 洞察 → 决策建议（每层因果链生成 1 条 DecisionRecommendation）
        try:
            recs = decision.derive_recommendations(db, insight_id, tenant_id)
        except Exception as e:
            logger.warning("洞察派单失败 insight_id=%s: %s", insight_id, e, exc_info=True)
            return

        # 2. 推送通知给目标用户
        for rec in recs:
            try:
                proactive_engine.push_suggestion(
                    user_id, tenant_id, "kpi_alert",
                    title=rec.get("title", "AI 洞察已生成"),
                    description=f"领域：{domain or rec.get('domain', '-')}，优先级：{rec.get('priority', 'medium')}",
                    priority=rec.get("priority", "medium"),
                    action={
                        "type": "navigate",
                        "target": (rec.get("action_params") or {}).get("url", "/decision"),
                    },
                )
            except Exception as e:
                logger.warning("决策建议推送失败 rec_id=%s: %s", rec.get("id"), e, exc_info=True)

    @event_bus.subscribe("recommendation_accepted")
    def on_recommendation_accepted(payload, tenant_id, db):
        """建议接受 → 行动记录 → 24h 评估 → AI 学习反馈

        affected_domains: ["ai", "sales"]
        注：record_action 内部已设置 evaluate_after=now+24h，
        由 suggestion_evaluation_scheduler 定时扫描调用 evaluate_outcome。
        """
        from ai.proactive_suggestions import proactive_engine

        rec_id = payload.get("rec_id")
        user_id = payload.get("user_id")
        domain = payload.get("domain")
        if not rec_id or not user_id:
            return

        # 1. 记录行动
        try:
            proactive_engine.record_action(
                suggestion_id=f"rec_{rec_id}",
                user_id=user_id,
                action_type="accepted",
                db=db,
                suggestion_type="kpi_alert",  # 用于 effectiveness_score 统计
                tenant_id=tenant_id,
            )
        except Exception as e:
            logger.warning("建议行动记录失败 rec_id=%s: %s", rec_id, e, exc_info=True)

        # 2. 同步触发一次 AI 学习反馈（基于历史 effectiveness_score 调整洞察权重）
        if domain:
            try:
                from services.ai_insight_service import ai_insight_service
                ai_insight_service.apply_feedback(
                    db=db,
                    suggestion_type="kpi_alert",
                    domain=domain,
                    tenant_id=tenant_id,
                )
            except Exception as e:
                logger.warning("AI 学习反馈失败 domain=%s: %s", domain, e, exc_info=True)

    # ──────────────────────────────────────────────
    # F1 审批流 SLA 事件订阅（借鉴企业级诊断体系 §7.4 + §13）
    # ──────────────────────────────────────────────
    @event_bus.subscribe("approval_submitted")
    def on_approval_submitted(payload, tenant_id, db):
        """审批已提交 → 记录审计日志"""
        from database import AuditLog
        try:
            log = AuditLog(
                tenant_id=tenant_id,
                actor_id=payload.get("applicant_id"),
                action="approval_submitted",
                target="approval",
                target_id=payload.get("approval_id"),
                detail=payload,
            )
            db.add(log)
            db.commit()
        except Exception:
            db.rollback()

    @event_bus.subscribe("approval_overdue")
    def on_approval_overdue(payload, tenant_id, db):
        """审批已超期 → 推送提醒 + 通知审批人"""
        from ai.proactive_suggestions import proactive_engine
        try:
            proactive_engine.push_suggestion(
                payload.get("applicant_id"),
                tenant_id,
                "kpi_alert",
                title=f"审批 #{payload.get('approval_id')} 已超期（{payload.get('elapsed_hours', 0)}h）",
                description=(
                    f"审批类型：{payload.get('approval_type', '-')}，"
                    f"SLA：{payload.get('sla_hours', 0)}h，"
                    f"升级层级：{payload.get('escalation_level', 0)}"
                ),
                priority="high",
                action={
                    "type": "navigate",
                    "target": "/collab/approvals",
                },
            )
        except Exception as e:
            logger.warning("审批超期推送失败: %s", e, exc_info=True)

    @event_bus.subscribe("approval_escalated")
    def on_approval_escalated(payload, tenant_id, db):
        """审批已升级 → 通知上级经理"""
        from ai.proactive_suggestions import proactive_engine
        try:
            proactive_engine.push_suggestion(
                payload.get("applicant_id"),
                tenant_id,
                "kpi_alert",
                title=f"审批 #{payload.get('approval_id')} 已升级到 L{payload.get('escalation_level', 0)}",
                description=(
                    f"原因：{payload.get('reason', '-')}，"
                    f"审批类型：{payload.get('approval_type', '-')}"
                ),
                priority="high",
                action={
                    "type": "navigate",
                    "target": "/collab/approvals",
                },
            )
        except Exception as e:
            logger.warning("审批升级推送失败: %s", e, exc_info=True)

    @event_bus.subscribe("approval_default_approved")
    def on_approval_default_approved(payload, tenant_id, db):
        """审批已默认同意 → 通知申请人"""
        from ai.proactive_suggestions import proactive_engine
        try:
            proactive_engine.push_suggestion(
                payload.get("applicant_id"),
                tenant_id,
                "feedback_followup",
                title=f"审批 #{payload.get('approval_id')} 已默认同意",
                description=(
                    f"SLA 超期 {payload.get('elapsed_hours', 0)}h，"
                    f"审批类型：{payload.get('approval_type', '-')}，已自动批准"
                ),
                priority="medium",
                action={
                    "type": "navigate",
                    "target": "/collab/approvals",
                },
            )
        except Exception as e:
            logger.warning("默认同意推送失败: %s", e, exc_info=True)

    @event_bus.subscribe("performance_boundary_blocked")
    def on_performance_blocked(payload, tenant_id, db):
        """绩效边界已阻断 → 记录审计日志"""
        from database import AuditLog
        try:
            log = AuditLog(
                tenant_id=tenant_id,
                action="performance_boundary_blocked",
                target="performance",
                detail=payload,
            )
            db.add(log)
            db.commit()
        except Exception:
            db.rollback()

    @event_bus.subscribe("course_completed")
    @event_bus.subscribe("practice_session_completed")
    @event_bus.subscribe("exam_passed")
    def on_training_effect_create(payload, tenant_id, db):
        """B 路径 §9.1：培训完成三事件 → 自动开 DecisionExecution(decision_type='training')

        同事件绑定三个事件源，单订阅者复用：
        - course_completed       课程学完
        - practice_session_completed 演练完成（已在画像+事件总线完成画像回写）
        - exam_passed            考试通过
        """
        # 显式延时导入避免循环
        from services.training_effect_service import handle_training_completed

        user_id = payload.get("user_id")
        if not user_id:
            return
        try:
            handle_training_completed(
                event_type=payload.get("__event_type__") or _infer_event_type(payload),
                payload=payload,
                tenant_id=tenant_id,
                db=db,
            )
        except Exception as exc:
            # 不允许阻塞主流程；记录到审计日志供排查
            logger.warning(
                "培训效果归因建 execution 失败（event=%s）: %s",
                payload.get("__event_type__"), exc, exc_info=True,
            )
            try:
                from database import AuditLog
                db.add(AuditLog(
                    tenant_id=tenant_id,
                    actor_id=user_id,
                    action="training_effect_create_failed",
                    target="training_effect",
                    detail={"error": str(exc), "payload_keys": list(payload.keys())},
                ))
                db.commit()
            except Exception:
                db.rollback()


def _infer_event_type(payload: dict) -> str:
    """从不标准化的 payload 反推事件源（兜底，仅用于审计日志）"""
    if "exam_id" in payload:
        return "exam_passed"
    if "session_id" in payload:
        return "practice_session_completed"
    if "course_id" in payload:
        return "course_completed"
    return "unknown"


__all__ = ["register_subscribers"]
