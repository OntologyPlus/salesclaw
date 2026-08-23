"""主动建议引擎 - 基于数据模式生成主动建议

5 类建议：
1. 覆盖提醒（coverage_reminder）：30 天未拜访的客户
2. 培训提醒（training_reminder）：合规培训即将到期
3. 反馈跟进（feedback_followup）：有负面反馈未处理
4. KPI 预警（kpi_alert）：某项 KPI 低于阈值
5. 知识推荐（knowledge_rec）：基于近期拜访话题推荐文档

每条建议格式：
    {type, title, description, action, priority, target_id?}
    - type: coverage_reminder/training_reminder/feedback_followup/kpi_alert/knowledge_rec
    - priority: high/medium/low
    - action: navigate（带 target 路由）

N+4 升级：建议行动闭环
- record_action: 记录用户对建议的行为（accepted/ignored/dismissed）
- _schedule_evaluation: 安排 24h 延迟评估
- evaluate_outcome: 评估建议行动效果（查对应指标变化）
- effectiveness_score: 某类建议总体有效率，< 30% 时降权
- get_action_history: 用户建议行动历史
"""
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func

from database import (
    VisitRecord, VisitFeedback, CourseEnrollment, KnowledgeDocument,
    Doctor, Hospital, Product,
    SuggestionAction,
)


class ProactiveSuggestionEngine:
    """主动建议引擎 - 多源数据扫描 + 优先级排序"""

    # 阈值常量
    COVERAGE_DAYS = 30              # 覆盖提醒阈值（天）
    KPI_ACHIEVEMENT_THRESHOLD = 0.6  # 拜访达成率预警阈值
    KPI_COVERAGE_THRESHOLD = 0.5     # 覆盖率预警阈值
    MAX_SUGGESTIONS_PER_TYPE = 5    # 每类建议上限
    RECENT_VISIT_DAYS = 14          # 近期拜访窗口（天）

    def __init__(self):
        # 外部推送的建议暂存队列（按 tenant_id + user_id 分组）
        self._pushed: dict[tuple, list[dict]] = {}

    def push_suggestion(self, user_id, tenant_id, suggestion_type: str,
                        title: str, description: str = "",
                        priority: str = "medium",
                        action: dict = None) -> None:
        """外部推送一条建议到内存队列，generate() 时合并返回

        Args:
            user_id: 用户 ID；None 表示租户级广播（所有用户可见）
            tenant_id: 租户 ID
            suggestion_type: 建议类型（coverage_reminder/training_reminder/...）
            title: 标题
            description: 描述
            priority: high/medium/low
            action: 建议动作（如 {"type": "navigate", "target": "/sales/plans"}）
        """
        suggestion = {
            "type": suggestion_type,
            "title": title,
            "description": description,
            "action": action or {"type": "navigate", "target": "/"},
            "priority": priority,
            "target_id": None,
            "pushed": True,  # 标记为外部推送
        }
        # 按 (tenant_id, user_id) 分组存储；user_id=None 用 "broadcast" 占位
        key = (str(tenant_id), str(user_id) if user_id else "broadcast")
        self._pushed.setdefault(key, []).append(suggestion)

    # ──────────────────────────────────────────────
    # 主入口
    # ──────────────────────────────────────────────
    def generate(self, user_id: int, tenant_id, db) -> list[dict]:
        """生成主动建议列表

        Args:
            user_id: 当前用户 ID
            tenant_id: 租户 ID
            db: 数据库 session

        Returns:
            建议列表，按优先级排序（high > medium > low）
        """
        if db is None or user_id is None or tenant_id is None:
            return []

        suggestions: list[dict] = []

        # 合并外部推送的建议（用户专属 + 租户广播）
        for key in [(str(tenant_id), str(user_id)), (str(tenant_id), "broadcast")]:
            suggestions.extend(self._pushed.pop(key, []))

        # 依次调用 5 个生成器，异常隔离保证单点失败不影响整体
        for generator in (
            self._gen_coverage_reminders,
            self._gen_training_reminders,
            self._gen_feedback_followups,
            self._gen_kpi_alerts,
            self._gen_knowledge_recs,
        ):
            try:
                suggestions.extend(generator(user_id, tenant_id, db))
            except Exception:
                # 单个生成器异常不阻断整体流程
                continue

        # 按优先级排序
        priority_order = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(key=lambda s: priority_order.get(s.get("priority", "low"), 3))

        # N+4: 根据 effectiveness_score 对建议降权（低采纳率建议 priority 降一级）
        try:
            suggestions = self._apply_effectiveness_demotion(suggestions, db, tenant_id)
            # 降权后重新排序
            suggestions.sort(key=lambda s: priority_order.get(s.get("priority", "low"), 3))
        except Exception:
            # 降权失败不影响主流程
            pass

        return suggestions

    # ──────────────────────────────────────────────
    # 1. 覆盖提醒：30 天未拜访的客户
    # ──────────────────────────────────────────────
    def _gen_coverage_reminders(self, user_id: int, tenant_id, db) -> list[dict]:
        """查询 VisitRecord，找近 30 天无拜访记录的医生"""
        threshold_date = date.today() - timedelta(days=self.COVERAGE_DAYS)
        tid = str(tenant_id)

        # 按医生分组取最近一次拜访日期
        latest_visits = db.query(
            VisitRecord.doctor_id,
            func.max(VisitRecord.visit_date).label("last_visit"),
        ).filter(
            VisitRecord.tenant_id == tid,
            VisitRecord.user_id == int(user_id),
            VisitRecord.is_deleted == 0,
        ).group_by(VisitRecord.doctor_id).all()

        # 筛选最近拜访超过 30 天的医生 ID
        stale_doctor_ids = [
            r.doctor_id for r in latest_visits
            if r.doctor_id and r.last_visit and r.last_visit < threshold_date
        ]
        if not stale_doctor_ids:
            return []

        # 批量查询医生与所属医院信息
        doctors = db.query(Doctor, Hospital).outerjoin(
            Hospital, Doctor.hospital_id == Hospital.id,
        ).filter(
            Doctor.tenant_id == tid,
            Doctor.is_deleted == 0,
            Doctor.id.in_(stale_doctor_ids),
        ).limit(self.MAX_SUGGESTIONS_PER_TYPE).all()

        suggestions = []
        for doctor, hospital in doctors:
            # 距今天数
            last_visit_row = next(
                (r for r in latest_visits if r.doctor_id == doctor.id), None,
            )
            days_since = (
                (date.today() - last_visit_row.last_visit).days
                if last_visit_row and last_visit_row.last_visit else self.COVERAGE_DAYS
            )
            hospital_name = hospital.name if hospital else "未关联医院"
            # 距离越久优先级越高
            priority = "high" if days_since >= 45 else "medium"
            suggestions.append({
                "type": "coverage_reminder",
                "title": f"{doctor.name}（{hospital_name}）已 {days_since} 天未拜访",
                "description": (
                    f"医生 {doctor.name}，{doctor.department or ''} "
                    f"{doctor.title or ''}，最近拜访于 "
                    f"{last_visit_row.last_visit.isoformat() if last_visit_row and last_visit_row.last_visit else '无记录'}，"
                    f"建议尽快安排跟进拜访。"
                ),
                "action": {"type": "navigate", "target": f"/doctors/{doctor.id}"},
                "priority": priority,
                "target_id": doctor.id,
            })
        return suggestions

    # ──────────────────────────────────────────────
    # 2. 培训提醒：合规培训即将到期（已报名未完成）
    # ──────────────────────────────────────────────
    def _gen_training_reminders(self, user_id: int, tenant_id, db) -> list[dict]:
        """查询 CourseEnrollment，找未完成但已报名的课程"""
        tid = str(tenant_id)
        # 已报名或进行中、尚未完成的课程
        enrollments = db.query(CourseEnrollment).filter(
            CourseEnrollment.tenant_id == tid,
            CourseEnrollment.user_id == int(user_id),
            CourseEnrollment.is_deleted == 0,
            CourseEnrollment.status.in_(["enrolled", "in_progress"]),
        ).order_by(CourseEnrollment.enrolled_at.asc()).limit(
            self.MAX_SUGGESTIONS_PER_TYPE,
        ).all()

        if not enrollments:
            return []

        suggestions = []
        # 一次性查询相关课程信息
        course_ids = [e.course_id for e in enrollments if e.course_id]
        courses_map = {}
        if course_ids:
            from database import Course
            courses = db.query(Course).filter(
                Course.tenant_id == tid,
                Course.is_deleted == 0,
                Course.id.in_(course_ids),
            ).all()
            courses_map = {c.id: c for c in courses}

        for enroll in enrollments:
            course = courses_map.get(enroll.course_id)
            if not course:
                continue
            # 报名越久未完成优先级越高
            days_enrolled = (datetime.utcnow() - enroll.enrolled_at).days if enroll.enrolled_at else 0
            priority = "high" if days_enrolled >= 30 else ("medium" if days_enrolled >= 14 else "low")
            suggestions.append({
                "type": "training_reminder",
                "title": f"课程《{course.title}》学习进度 {enroll.progress}%",
                "description": (
                    f"已报名 {days_enrolled} 天，当前进度 {enroll.progress}%，"
                    f"状态：{enroll.status}。建议尽快完成学习。"
                ),
                "action": {"type": "navigate", "target": f"/training/courses/{course.id}"},
                "priority": priority,
                "target_id": course.id,
            })
        return suggestions

    # ──────────────────────────────────────────────
    # 3. 反馈跟进：有负面反馈未处理
    # ──────────────────────────────────────────────
    def _gen_feedback_followups(self, user_id: int, tenant_id, db) -> list[dict]:
        """查询 VisitFeedback，找 sentiment=negative 的记录"""
        tid = str(tenant_id)
        # 关联拜访记录获取上下文
        rows = db.query(VisitFeedback, VisitRecord).join(
            VisitRecord, VisitFeedback.record_id == VisitRecord.id,
        ).filter(
            VisitFeedback.tenant_id == tid,
            VisitFeedback.is_deleted == 0,
            VisitRecord.is_deleted == 0,
            VisitRecord.user_id == int(user_id),
            VisitFeedback.sentiment == "negative",
        ).order_by(VisitFeedback.created_at.desc()).limit(
            self.MAX_SUGGESTIONS_PER_TYPE,
        ).all()

        suggestions = []
        for feedback, record in rows:
            # 关联医生信息
            doctor = db.query(Doctor).filter(
                Doctor.id == record.doctor_id,
                Doctor.tenant_id == tid,
                Doctor.is_deleted == 0,
            ).first() if record.doctor_id else None
            doctor_name = doctor.name if doctor else "未知医生"
            objections = feedback.objections or []
            objection_text = "、".join(objections) if objections else "无明确异议"
            suggestions.append({
                "type": "feedback_followup",
                "title": f"{doctor_name} 的拜访出现负面反馈待跟进",
                "description": (
                    f"拜访日期 {record.visit_date.isoformat() if record.visit_date else '未知'}，"
                    f"异议要点：{objection_text}。建议 24 小时内安排区域经理跟进。"
                ),
                "action": {"type": "navigate", "target": f"/visits/records/{record.id}"},
                "priority": "high",
                "target_id": record.id,
            })
        return suggestions

    # ──────────────────────────────────────────────
    # 4. KPI 预警：拜访达成率与覆盖率（Mock 阈值判断）
    # ──────────────────────────────────────────────
    def _gen_kpi_alerts(self, user_id: int, tenant_id, db) -> list[dict]:
        """基于拜访达成率、覆盖率判断 KPI 是否低于阈值"""
        tid = str(tenant_id)
        today = date.today()
        month_start = today.replace(day=1)

        # 本月实际拜访次数
        visit_count = db.query(func.count(VisitRecord.id)).filter(
            VisitRecord.tenant_id == tid,
            VisitRecord.user_id == int(user_id),
            VisitRecord.is_deleted == 0,
            VisitRecord.visit_date >= month_start,
        ).scalar() or 0

        # 本月目标拜访次数（从 VisitPlan 取最新一期）
        from database import VisitPlan
        plan = db.query(VisitPlan).filter(
            VisitPlan.tenant_id == tid,
            VisitPlan.user_id == int(user_id),
            VisitPlan.is_deleted == 0,
            VisitPlan.period == today.strftime("%Y-%m"),
        ).order_by(VisitPlan.created_at.desc()).first()
        target_count = plan.target_count if plan and plan.target_count else 0

        # 覆盖医生数（本用户历史覆盖）
        covered_doctor_count = db.query(
            func.count(func.distinct(VisitRecord.doctor_id))
        ).filter(
            VisitRecord.tenant_id == tid,
            VisitRecord.user_id == int(user_id),
            VisitRecord.is_deleted == 0,
        ).scalar() or 0

        # 本月已覆盖医生数
        month_covered = db.query(
            func.count(func.distinct(VisitRecord.doctor_id))
        ).filter(
            VisitRecord.tenant_id == tid,
            VisitRecord.user_id == int(user_id),
            VisitRecord.is_deleted == 0,
            VisitRecord.visit_date >= month_start,
        ).scalar() or 0

        suggestions = []
        # 拜访达成率预警
        if target_count > 0:
            achievement_rate = visit_count / target_count
            if achievement_rate < self.KPI_ACHIEVEMENT_THRESHOLD:
                priority = "high" if achievement_rate < 0.3 else "medium"
                suggestions.append({
                    "type": "kpi_alert",
                    "title": f"本月拜访达成率 {achievement_rate:.0%} 低于阈值 {self.KPI_ACHIEVEMENT_THRESHOLD:.0%}",
                    "description": (
                        f"本月已拜访 {visit_count} 次，目标 {target_count} 次，"
                        f"达成率 {achievement_rate:.0%}。建议加快拜访节奏或调整目标。"
                    ),
                    "action": {"type": "navigate", "target": "/reports/weekly"},
                    "priority": priority,
                })

        # 覆盖率预警
        if covered_doctor_count > 0:
            coverage_rate = month_covered / covered_doctor_count
            if coverage_rate < self.KPI_COVERAGE_THRESHOLD:
                priority = "medium" if coverage_rate >= 0.3 else "high"
                suggestions.append({
                    "type": "kpi_alert",
                    "title": f"本月客户覆盖率 {coverage_rate:.0%} 低于阈值 {self.KPI_COVERAGE_THRESHOLD:.0%}",
                    "description": (
                        f"本月已覆盖 {month_covered} 位医生，累计覆盖 {covered_doctor_count} 位，"
                        f"覆盖率 {coverage_rate:.0%}。建议优先拜访长期未覆盖客户。"
                    ),
                    "action": {"type": "navigate", "target": "/coverage/matrix"},
                    "priority": priority,
                })
        return suggestions

    # ──────────────────────────────────────────────
    # 5. 知识推荐：基于近期拜访话题推荐文档
    # ──────────────────────────────────────────────
    def _gen_knowledge_recs(self, user_id: int, tenant_id, db) -> list[dict]:
        """查询近期 VisitRecord 话题，匹配 KnowledgeDocument 分类推荐"""
        tid = str(tenant_id)
        recent_date = date.today() - timedelta(days=self.RECENT_VISIT_DAYS)

        # 取近期拜访摘要
        recent_records = db.query(VisitRecord).filter(
            VisitRecord.tenant_id == tid,
            VisitRecord.user_id == int(user_id),
            VisitRecord.is_deleted == 0,
            VisitRecord.visit_date >= recent_date,
        ).order_by(VisitRecord.visit_date.desc()).limit(10).all()

        if not recent_records:
            return []

        # 从摘要中提取话题关键词（基于简单词典匹配）
        topic_categories = self._extract_topics(recent_records)
        if not topic_categories:
            return []

        suggestions = []
        # 按分类查询相关文档
        for category, weight in topic_categories.items():
            docs = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.tenant_id == tid,
                KnowledgeDocument.is_deleted == 0,
                KnowledgeDocument.is_published == 1,
                KnowledgeDocument.category == category,
            ).limit(self.MAX_SUGGESTIONS_PER_TYPE).all()
            for doc in docs:
                priority = "high" if weight >= 2 else ("medium" if weight == 1 else "low")
                suggestions.append({
                    "type": "knowledge_rec",
                    "title": f"推荐阅读：《{doc.title}》",
                    "description": (
                        f"基于您近 {self.RECENT_VISIT_DAYS} 天的拜访话题，"
                        f"推荐分类 {category} 的知识文档：{doc.summary or doc.title}"
                    ),
                    "action": {"type": "navigate", "target": f"/knowledge/documents/{doc.id}"},
                    "priority": priority,
                    "target_id": doc.id,
                })
            if len(suggestions) >= self.MAX_SUGGESTIONS_PER_TYPE:
                break
        return suggestions[: self.MAX_SUGGESTIONS_PER_TYPE]

    def _extract_topics(self, records: list) -> dict:
        """从拜访记录摘要中提取话题分类与权重

        Returns:
            {category: weight} 权重为出现次数
        """
        # 关键词到知识库分类的映射词典
        topic_map = {
            "product": ["产品", "心血通", "脑复康", "胃复安", "药品", "适应症", "剂量", "用法"],
            "clinical": ["临床", "数据", "疗效", "Meta", "RCT", "试验", "不良反应", "副作用"],
            "compliance": ["合规", "学术推广", "礼品", "接待", "备案", "贿赂"],
            "sales": ["拜访", "异议", "价格", "话术", "科室宣讲", "客户", "沟通"],
        }
        category_weights: dict[str, int] = {}
        for record in records:
            text = (record.summary or "") + " " + (record.visit_type or "")
            for category, keywords in topic_map.items():
                for kw in keywords:
                    if kw in text:
                        category_weights[category] = category_weights.get(category, 0) + 1
                        break
        # 按权重降序
        return dict(sorted(
            category_weights.items(), key=lambda x: x[1], reverse=True,
        ))

    # ──────────────────────────────────────────────
    # N+4: 建议行动闭环
    # ──────────────────────────────────────────────

    def record_action(
        self,
        suggestion_id: str,
        user_id: int,
        action_type: str,
        db,
        suggestion_type: str = None,
        tenant_id: str = "default",
    ) -> dict:
        """N+4: 记录用户对建议的行为

        Args:
            suggestion_id: 建议 ID（前端生成的稳定 key）
            user_id: 用户 ID
            action_type: accepted / ignored / dismissed
            db: 数据库 session
            suggestion_type: 建议类型（用于 effectiveness_score 统计）
            tenant_id: 租户 ID

        Returns:
            {action_id, scheduled_eval}
        """
        action = SuggestionAction(
            tenant_id=tenant_id,
            suggestion_id=str(suggestion_id),
            suggestion_type=suggestion_type,
            user_id=int(user_id),
            action_type=action_type,
            acted_at=datetime.utcnow(),
            evaluate_after=datetime.utcnow() + timedelta(hours=24),
        )
        db.add(action)
        db.commit()
        db.refresh(action)

        # 发布事件（causation 串联）
        try:
            from ai.event_bus import event_bus
            event_bus.publish(
                "suggestion_action_recorded",
                {
                    "action_id": action.id,
                    "suggestion_id": str(suggestion_id),
                    "suggestion_type": suggestion_type,
                    "user_id": int(user_id),
                    "action_type": action_type,
                },
                tenant_id=tenant_id,
                affected_domains=["ai"],
            )
        except Exception:
            pass

        return {"action_id": action.id, "scheduled_eval": True}

    def evaluate_outcome(self, action_id: int, db, tenant_id: str = "default") -> dict:
        """N+4: 评估建议行动效果

        根据建议类型查对应指标变化，写入 outcome_metric / outcome_value / evaluated_at。

        评估规则：
        - coverage_reminder: 24h 内是否完成对应医生拜访（outcome_value=1 有效 / 0 无效）
        - training_reminder: 24h 内课程进度是否提升
        - feedback_followup: 24h 内是否有新反馈记录
        - kpi_alert: 24h 内 KPI 是否改善
        - knowledge_rec: 24h 内是否阅读文档（简化为 action_type=accepted 即有效）

        Returns:
            {action_id, evaluated, outcome_metric, outcome_value, effective}
        """
        action = db.query(SuggestionAction).filter(
            SuggestionAction.id == action_id,
            SuggestionAction.is_deleted == 0,
        ).first()
        if not action:
            return {"error": "action_not_found", "action_id": action_id}

        # 已评估则跳过
        if action.evaluated_at is not None:
            return {
                "action_id": action_id,
                "evaluated": False,
                "reason": "already_evaluated",
            }

        suggestion_type = action.suggestion_type or ""
        user_id = action.user_id
        tid = str(tenant_id)
        effective = False
        outcome_metric = ""
        outcome_value = 0.0

        # 仅评估 accepted 的建议
        if action.action_type != "accepted":
            outcome_metric = "action_type"
            outcome_value = 0.0
        else:
            # 根据 suggestion_type 查对应指标
            since = action.acted_at or datetime.utcnow()
            if suggestion_type == "coverage_reminder":
                # 24h 内是否有新拜访记录
                cnt = db.query(func.count(VisitRecord.id)).filter(
                    VisitRecord.tenant_id == tid,
                    VisitRecord.user_id == user_id,
                    VisitRecord.is_deleted == 0,
                    VisitRecord.visit_date >= since.date(),
                ).scalar() or 0
                outcome_metric = "visits_after_action"
                outcome_value = float(cnt)
                effective = cnt > 0

            elif suggestion_type == "training_reminder":
                # 24h 内课程进度是否提升
                enrollments = db.query(CourseEnrollment).filter(
                    CourseEnrollment.tenant_id == tid,
                    CourseEnrollment.user_id == user_id,
                    CourseEnrollment.is_deleted == 0,
                    CourseEnrollment.updated_at >= since,
                ).all()
                progress_gain = sum(e.progress or 0 for e in enrollments)
                outcome_metric = "progress_gain_after_action"
                outcome_value = float(progress_gain)
                effective = progress_gain > 0

            elif suggestion_type == "feedback_followup":
                # 24h 内是否有新反馈
                cnt = db.query(func.count(VisitFeedback.id)).filter(
                    VisitFeedback.tenant_id == tid,
                    VisitFeedback.is_deleted == 0,
                    VisitFeedback.created_at >= since,
                ).scalar() or 0
                outcome_metric = "new_feedbacks_after_action"
                outcome_value = float(cnt)
                effective = cnt > 0

            elif suggestion_type == "kpi_alert":
                # 简化：accepted 即视为有效响应
                outcome_metric = "kpi_acknowledged"
                outcome_value = 1.0
                effective = True

            elif suggestion_type == "knowledge_rec":
                # 简化：accepted 即视为有效
                outcome_metric = "knowledge_acknowledged"
                outcome_value = 1.0
                effective = True

            else:
                outcome_metric = "generic_acknowledged"
                outcome_value = 1.0 if action.action_type == "accepted" else 0.0
                effective = action.action_type == "accepted"

        # 写入评估结果
        action.outcome_metric = outcome_metric
        action.outcome_value = outcome_value
        action.evaluated_at = datetime.utcnow()
        db.commit()

        # 发布评估完成事件
        try:
            from ai.event_bus import event_bus
            event_bus.publish(
                "suggestion_outcome_evaluated",
                {
                    "action_id": action_id,
                    "suggestion_type": suggestion_type,
                    "user_id": user_id,
                    "effective": effective,
                    "outcome_value": outcome_value,
                },
                tenant_id=tid,
                affected_domains=["ai"],
            )
        except Exception:
            pass

        return {
            "action_id": action_id,
            "evaluated": True,
            "outcome_metric": outcome_metric,
            "outcome_value": outcome_value,
            "effective": effective,
        }

    def effectiveness_score(self, suggestion_type: str, db, tenant_id: str = "default") -> float:
        """N+4: 某类建议总体有效率（采纳率 × 有效率）

        Returns:
            0.0-1.0 的有效率分数。
            < SUGGESTION_LOW_ADOPTION_THRESHOLD(0.30) 时，后续生成应降权。
        """
        from core.constants import SUGGESTION_LOW_ADOPTION_THRESHOLD

        tid = str(tenant_id)
        # 查询该类建议的所有行动记录
        actions = db.query(SuggestionAction).filter(
            SuggestionAction.tenant_id == tid,
            SuggestionAction.is_deleted == 0,
            SuggestionAction.suggestion_type == suggestion_type,
        ).all()

        if not actions:
            return 1.0  # 无历史数据时默认满分

        total = len(actions)
        accepted = sum(1 for a in actions if a.action_type == "accepted")
        if accepted == 0:
            return 0.0

        adoption_rate = accepted / total
        # 有效数：accepted 且 outcome_value > 0
        effective_count = sum(
            1 for a in actions
            if a.action_type == "accepted"
            and a.outcome_value is not None
            and a.outcome_value > 0
        )
        effective_rate = effective_count / accepted if accepted > 0 else 0.0

        return adoption_rate * effective_rate

    def get_action_history(
        self, user_id: int, days: int, db, tenant_id: str = "default",
    ) -> list[dict]:
        """N+4: 用户建议行动历史"""
        tid = str(tenant_id)
        since = datetime.utcnow() - timedelta(days=days)
        rows = db.query(SuggestionAction).filter(
            SuggestionAction.tenant_id == tid,
            SuggestionAction.user_id == int(user_id),
            SuggestionAction.is_deleted == 0,
            SuggestionAction.acted_at >= since,
        ).order_by(SuggestionAction.acted_at.desc()).all()

        return [
            {
                "id": r.id,
                "suggestion_id": r.suggestion_id,
                "suggestion_type": r.suggestion_type,
                "action_type": r.action_type,
                "acted_at": r.acted_at.isoformat() if r.acted_at else None,
                "outcome_metric": r.outcome_metric,
                "outcome_value": r.outcome_value,
                "evaluated_at": r.evaluated_at.isoformat() if r.evaluated_at else None,
            }
            for r in rows
        ]

    def process_pending_evaluations(self, db, tenant_id: str = "default", batch: int = 50) -> int:
        """N+4: 扫描并评估到期的待评估行动（evaluate_after <= now）

        Returns:
            已评估的行动数
        """
        tid = str(tenant_id)
        now = datetime.utcnow()
        rows = db.query(SuggestionAction).filter(
            SuggestionAction.tenant_id == tid,
            SuggestionAction.is_deleted == 0,
            SuggestionAction.evaluated_at.is_(None),
            SuggestionAction.evaluate_after <= now,
        ).order_by(SuggestionAction.evaluate_after.asc()).limit(batch).all()

        count = 0
        for action in rows:
            try:
                self.evaluate_outcome(action.id, db, tid)
                count += 1
            except Exception:
                continue
        return count

    # ──────────────────────────────────────────────
    # N+AI原生闭环：AI 主动建议（经编排器 suggest 意图）
    # ──────────────────────────────────────────────

    async def ai_suggest(self, user_id: int, tenant_id, db,
                         domain: Optional[str] = None) -> dict:
        """生成 AI 原生主动建议：先确定性扫描多源数据，再经编排器 suggest 意图
        做 AI 优先级排序与可解释包装，产出统一 provenance + reasoning_chain_id。

        mock 模式下编排器同样跑七步，仅底层 LLM 返回 INTENT_RESPONSES 静态 JSON。
        编排器整体失败时降级到 generate() 确定性建议（仍返回 summary）。
        """
        # 1. 确定性多源扫描（保持既有业务逻辑单一真相源）
        base = self.generate(user_id, tenant_id, db)
        base_summary = (
            f"基于覆盖/培训/反馈/KPI/知识五类信号扫描，共 {len(base)} 条建议，"
            f"其中高危 {sum(1 for s in base if s.get('priority') == 'high')} 条。"
        )

        import json
        message = (
            f"为代表 {user_id} 在 {domain or 'sales'} 域生成主动建议。"
            f"已扫描数据：{json.dumps(base, ensure_ascii=False, default=str)[:2000]}"
        )
        parsed = None
        reasoning_chain_id = None
        provenance = {"mode": "rule_fallback"}
        source = "rule_fallback"
        from core.ai_output_schema import generate_trace_id
        trace_id = generate_trace_id()

        try:
            from ai.orchestrator import Orchestrator
            orch = Orchestrator()
            result = await orch.chat(
                message=message,
                intent="suggest",
                user=str(user_id),
                tenant_id=str(tenant_id),
                db=db,
            )
            resp_text = result.get("response", "")
            parsed = self._safe_parse_json(resp_text)
            if parsed:
                reasoning_chain_id = (
                    result.get("reasoning_chain", {}) or {}
                ).get("chain_id")
                prov = result.get("provenance") or {}
                provenance = {
                    "mode": "ai_orchestrated",
                    "intent": "suggest",
                    "agent": result.get("agent_used"),
                    "model_version": prov.get("model_version"),
                    "run_id": prov.get("run_id"),
                }
                source = "ai"
                trace_id = result.get("trace_id") or trace_id
        except Exception as exc:
            logger.warning("AI 主动建议编排失败，降级确定性建议: %s", exc)
            parsed = None

        suggestions = parsed.get("suggestions") if parsed else None
        if not suggestions:
            # 降级：确定性建议（补齐 AI 字段默认值）
            suggestions = [
                {**s, "ai_explanation": base_summary} for s in base
            ]

        return {
            "user_id": user_id,
            "domain": domain,
            "source": source,
            "summary": (parsed or {}).get("summary") or base_summary,
            "suggestions": suggestions,
            "reasoning_chain_id": reasoning_chain_id,
            "provenance": provenance,
            "trace_id": trace_id,
        }

    @staticmethod
    def _safe_parse_json(content: str):
        """从 LLM/编排器输出中安全解析 JSON（兼容 ```json 围栏与尾部免责声明文本）"""
        if not content:
            return None
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start:end + 1]
        try:
            import json
            return json.loads(text)
        except Exception:
            return None

    def _apply_effectiveness_demotion(
        self, suggestions: list[dict], db, tenant_id: str,
    ) -> list[dict]:
        """N+4: 根据 effectiveness_score 对建议降权

        某类建议 effectiveness_score < 0.30 时，priority 降一级。
        """
        from core.constants import (
            SUGGESTION_LOW_ADOPTION_THRESHOLD, SUGGESTION_DEMOTE_FACTOR,
        )

        # 按类型分组计算 effectiveness
        type_scores: dict[str, float] = {}
        for s in suggestions:
            stype = s.get("type", "")
            if stype and stype not in type_scores:
                type_scores[stype] = self.effectiveness_score(stype, db, tenant_id)

        # 应用降权
        priority_demotion = {"high": "medium", "medium": "low", "low": "low"}
        for s in suggestions:
            stype = s.get("type", "")
            score = type_scores.get(stype, 1.0)
            if score < SUGGESTION_LOW_ADOPTION_THRESHOLD:
                old_priority = s.get("priority", "low")
                s["priority"] = priority_demotion.get(old_priority, "low")
                s["_demoted_by_effectiveness"] = True
                s["_effectiveness_score"] = score
        return suggestions


# 全局单例
proactive_engine = ProactiveSuggestionEngine()


__all__ = ["ProactiveSuggestionEngine", "proactive_engine"]
