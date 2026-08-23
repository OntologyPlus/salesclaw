"""决策效果追踪服务

记录决策执行的完整生命周期（planned → executing → completed/failed），
并对比 baseline / target / actual 三组指标，自动计算效果得分与达成率，
为后续策略迭代与归因分析提供闭环数据。

数据来源：DecisionExecution 表。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from database import DecisionExecution
from core.ai_output_schema import generate_trace_id


# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────

STATUS_PLANNED = "planned"
STATUS_EXECUTING = "executing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

_VALID_STATUS = {STATUS_PLANNED, STATUS_EXECUTING, STATUS_COMPLETED, STATUS_FAILED}


class EffectTrackingService:
    """决策效果追踪服务

    负责 DecisionExecution 记录的创建、状态流转、指标更新与效果计算。
    所有方法均接收 tenant_id 做行级隔离，db 由调用方传入并管理生命周期。
    """

    # ──────────────────────────────────────────────
    # 创建与状态流转
    # ──────────────────────────────────────────────

    def create_execution(
        self,
        user_id: int,
        tenant_id: str,
        db: Session,
        decision_type: str,
        title: str,
        description: str = "",
        baseline: Optional[dict] = None,
        target: Optional[dict] = None,
    ) -> dict:
        """创建决策执行记录，初始状态为 planned

        Args:
            user_id: 关联用户 ID
            tenant_id: 租户 ID
            decision_type: 决策类型，如 visit_plan / training / coverage
            title: 决策标题
            description: 决策描述
            baseline: 决策前指标快照，如 {"visit_count": 5, "coverage_rate": 60}
            target: 目标指标，如 {"visit_count": 12, "coverage_rate": 80}

        Returns:
            创建后的执行记录字典
        """
        record = DecisionExecution(
            tenant_id=tenant_id,
            user_id=user_id,
            decision_type=decision_type,
            title=title,
            description=description or "",
            baseline_metrics=baseline or {},
            target_metrics=target or {},
            actual_metrics={},
            status=STATUS_PLANNED,
            started_at=None,
            completed_at=None,
            effectiveness_score=None,
        )
        try:
            db.add(record)
            db.commit()
            db.refresh(record)
        except Exception as exc:
            db.rollback()
            return {"error": "create_failed", "detail": str(exc)}
        return self._to_dict(record)

    def start_execution(self, execution_id: int, tenant_id: str, db: Session) -> dict:
        """将执行记录标记为 executing，并记录开始时间"""
        record = self._get_record(execution_id, tenant_id, db)
        if record is None:
            return {"error": "not_found", "execution_id": execution_id}
        if record.status not in (STATUS_PLANNED, STATUS_EXECUTING):
            return {"error": "invalid_status", "status": record.status,
                    "message": f"仅当状态为 {STATUS_PLANNED} 时可启动"}
        try:
            record.status = STATUS_EXECUTING
            if record.started_at is None:
                record.started_at = datetime.utcnow()
            db.commit()
            db.refresh(record)
        except Exception as exc:
            db.rollback()
            return {"error": "update_failed", "detail": str(exc)}
        return self._to_dict(record)

    def update_progress(
        self, execution_id: int, tenant_id: str, db: Session, actual_metrics: dict
    ) -> dict:
        """更新执行中的实际指标（增量合并）

        Args:
            actual_metrics: 实际指标快照，将与已有 actual_metrics 合并
        """
        record = self._get_record(execution_id, tenant_id, db)
        if record is None:
            return {"error": "not_found", "execution_id": execution_id}
        if record.status not in (STATUS_PLANNED, STATUS_EXECUTING):
            return {"error": "invalid_status", "status": record.status,
                    "message": "仅 planned / executing 状态可更新进度"}
        try:
            # 合并已有 actual_metrics 与新传入的指标
            current = dict(record.actual_metrics or {})
            current.update(actual_metrics or {})
            record.actual_metrics = current
            # 自动从 planned 过渡到 executing
            if record.status == STATUS_PLANNED:
                record.status = STATUS_EXECUTING
                if record.started_at is None:
                    record.started_at = datetime.utcnow()
            db.commit()
            db.refresh(record)
        except Exception as exc:
            db.rollback()
            return {"error": "update_failed", "detail": str(exc)}
        return self._to_dict(record)

    def complete_execution(
        self, execution_id: int, tenant_id: str, db: Session, actual_metrics: Optional[dict] = None
    ) -> dict:
        """完成执行，并自动计算效果得分

        Args:
            actual_metrics: 最终实际指标（可选，将与已有数据合并）
        """
        record = self._get_record(execution_id, tenant_id, db)
        if record is None:
            return {"error": "not_found", "execution_id": execution_id}
        if record.status in (STATUS_COMPLETED, STATUS_FAILED):
            return {"error": "invalid_status", "status": record.status,
                    "message": "已完成或失败的记录不可再次完成"}
        try:
            # 合并最终指标
            if actual_metrics:
                current = dict(record.actual_metrics or {})
                current.update(actual_metrics)
                record.actual_metrics = current
            # 状态流转
            record.status = STATUS_COMPLETED
            now = datetime.utcnow()
            if record.started_at is None:
                record.started_at = now
            record.completed_at = now
            # 计算效果得分
            score_result = self._compute_score(
                baseline=record.baseline_metrics or {},
                target=record.target_metrics or {},
                actual=record.actual_metrics or {},
            )
            record.effectiveness_score = score_result["score"]
            db.commit()
            db.refresh(record)
        except Exception as exc:
            db.rollback()
            return {"error": "update_failed", "detail": str(exc)}
        return self._to_dict(record)

    # ──────────────────────────────────────────────
    # 效果计算
    # ──────────────────────────────────────────────

    def compute_effectiveness(self, execution_id: int, tenant_id: str, db: Session) -> dict:
        """对比 baseline vs actual，按维度计算达成率

        Returns:
            {score(0-100), dimensions: {metric_name: {baseline, actual, achievement_rate}}, insights: []}
        """
        record = self._get_record(execution_id, tenant_id, db)
        if record is None:
            return {"error": "not_found", "execution_id": execution_id}

        result = self._compute_score(
            baseline=record.baseline_metrics or {},
            target=record.target_metrics or {},
            actual=record.actual_metrics or {},
        )
        # 附加执行记录基本信息
        result["execution_id"] = execution_id
        result["title"] = record.title
        result["status"] = record.status
        return result

    def _compute_score(self, baseline: dict, target: dict, actual: dict) -> dict:
        """核心效果计算逻辑

        规则：
            - 对每个 metric：achievement_rate = actual / target（如果 target > 0）
            - 总分 = average(achievement_rate) * 100，上限 100
            - 自动生成 insights（如"拜访达成率 92%，超出目标"）
        """
        dimensions: dict[str, dict] = {}
        rates: list[float] = []

        # 以 target 的 key 为基准维度
        for metric_name, target_value in target.items():
            base_value = baseline.get(metric_name)
            actual_value = actual.get(metric_name)
            achievement_rate = self._safe_rate(actual_value, target_value)
            dimensions[metric_name] = {
                "baseline": base_value,
                "target": target_value,
                "actual": actual_value,
                "achievement_rate": achievement_rate,
            }
            rates.append(achievement_rate)

        # 总分：基于达成率均值
        if rates:
            avg_rate = sum(rates) / len(rates)
            score = min(100, int(round(avg_rate * 100)))
        else:
            score = 0

        # 自动生成 insights
        insights = self._generate_insights(dimensions, score)

        return {
            "score": score,
            "dimensions": dimensions,
            "insights": insights,
        }

    @staticmethod
    def _safe_rate(actual_value, target_value) -> float:
        """计算达成率，处理 None 与零值"""
        # 无法计算时返回 0
        if target_value is None or target_value == 0:
            return 0.0
        if actual_value is None:
            return 0.0
        try:
            return float(actual_value) / float(target_value)
        except (TypeError, ValueError, ZeroDivisionError):
            return 0.0

    @staticmethod
    def _generate_insights(dimensions: dict, score: int) -> list[str]:
        """根据各维度达成率自动生成洞察"""
        insights: list[str] = []
        # 中文别名映射，让 insights 更可读
        alias = {
            "visit_count": "拜访次数",
            "visit_completion": "拜访达成率",
            "coverage_rate": "覆盖率",
            "positive_rate": "反馈正面率",
            "total_points": "行为积分",
            "course_completion": "课程完成率",
            "avg_exam": "考试平均分",
            "comprehensive_score": "综合能力分",
            "enroll_count": "选课数",
            "credits_earned": "学分",
        }

        for metric_name, info in dimensions.items():
            rate = info.get("achievement_rate", 0.0)
            actual = info.get("actual")
            target = info.get("target")
            display = alias.get(metric_name, metric_name)
            rate_pct = round(rate * 100, 1)

            if actual is None:
                insights.append(f"{display}：暂无实际数据，目标 {target}")
            elif rate >= 1.0:
                insights.append(f"{display}达成率 {rate_pct}%，超出目标")
            elif rate >= 0.8:
                insights.append(f"{display}达成率 {rate_pct}%，接近目标")
            elif rate >= 0.5:
                insights.append(f"{display}达成率 {rate_pct}%，距目标有差距")
            else:
                insights.append(f"{display}达成率 {rate_pct}%，明显未达成目标")

        # 综合性洞察
        if score >= 90:
            insights.append(f"综合效果得分 {score}，决策执行优秀")
        elif score >= 75:
            insights.append(f"综合效果得分 {score}，决策执行良好")
        elif score >= 60:
            insights.append(f"综合效果得分 {score}，决策执行基本达标")
        else:
            insights.append(f"综合效果得分 {score}，决策执行未达预期，建议复盘")

        return insights

    # ──────────────────────────────────────────────
    # 查询
    # ──────────────────────────────────────────────

    def get_executions(
        self,
        user_id: int,
        tenant_id: str,
        db: Session,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """获取用户的执行记录列表

        Args:
            user_id: 用户 ID
            status: 可选状态过滤（planned/executing/completed/failed）
            limit: 返回条数上限
        """
        q = db.query(DecisionExecution).filter(
            DecisionExecution.tenant_id == tenant_id,
            DecisionExecution.is_deleted == 0,
            DecisionExecution.user_id == user_id,
        )
        if status:
            if status not in _VALID_STATUS:
                return []
            q = q.filter(DecisionExecution.status == status)
        records = q.order_by(DecisionExecution.created_at.desc()).limit(
            max(1, min(limit, 200))
        ).all()
        return [self._to_dict(r) for r in records]

    def get_execution(self, execution_id: int, tenant_id: str, db: Session) -> dict:
        """获取单条执行记录详情"""
        record = self._get_record(execution_id, tenant_id, db)
        if record is None:
            return {"error": "not_found", "execution_id": execution_id}
        return self._to_dict(record)

    # ──────────────────────────────────────────────
    # 辅助方法
    # ──────────────────────────────────────────────

    @staticmethod
    def _get_record(execution_id: int, tenant_id: str, db: Session) -> Optional[DecisionExecution]:
        """按主键 + 租户隔离获取记录"""
        return db.query(DecisionExecution).filter(
            DecisionExecution.id == execution_id,
            DecisionExecution.tenant_id == tenant_id,
            DecisionExecution.is_deleted == 0,
        ).first()

    @staticmethod
    def _to_dict(record: DecisionExecution) -> dict:
        """序列化为字典"""
        return {
            "execution_id": record.id,
            "user_id": record.user_id,
            "decision_type": record.decision_type,
            "title": record.title,
            "description": record.description,
            "baseline_metrics": record.baseline_metrics or {},
            "target_metrics": record.target_metrics or {},
            "actual_metrics": record.actual_metrics or {},
            "status": record.status,
            "started_at": record.started_at.isoformat() if record.started_at else None,
            "completed_at": record.completed_at.isoformat() if record.completed_at else None,
            "effectiveness_score": record.effectiveness_score,
            "reasoning_chain_id": getattr(record, "reasoning_chain_id", None),
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }

    # ──────────────────────────────────────────────
    # N+AI原生闭环：AI 效果归因评估（经编排器 evaluate 意图）
    # ──────────────────────────────────────────────

    async def ai_evaluate(self, execution_id: int, tenant_id: str, db: Session,
                          user: Optional[str] = None,
                          extra_payload: Optional[dict] = None) -> dict:
        """对已完成执行做 AI 效果归因评估，产出可解释的达成/未达成推理链。

        主链路经 Orchestrator 七步状态机（evaluate 意图），获得结构化评估 +
        推理链（ReasoningChain）与真实 provenance（model_version / run_id）。
        mock 模式下编排器同样跑七步，仅底层 LLM 返回 INTENT_RESPONSES 静态 JSON。
        编排器整体失败时降级到 _compute_score 确定性评估（仍返回 verdict/score）。

        Args:
            extra_payload: B 路径 §7 训练场景追加上下文
                - scenario: "training_effect" 等
                - evidence_clues: list[dict]，归因线索
                - training_meta: dict，训练元数据
        """
        record = self._get_record(execution_id, tenant_id, db)
        if record is None:
            return {"error": "not_found", "execution_id": execution_id}

        message = (
            f"评估执行 {execution_id}（{record.title}）的效果达成情况："
            f"对比 baseline={record.baseline_metrics} / target={record.target_metrics} "
            f"/ actual={record.actual_metrics}"
        )
        # B 路径：训练场景追加 evidence_clues + training_meta 进入 prompt
        if extra_payload:
            try:
                import json as _json
                message += "\n\n[上下文扩展]\n" + _json.dumps(
                    extra_payload, ensure_ascii=False, indent=2
                )
            except Exception:
                pass
        parsed = None
        reasoning_chain_id = None
        provenance = {"mode": "rule_fallback"}
        trace_id = generate_trace_id()
        source = "rule_fallback"

        try:
            from ai.orchestrator import Orchestrator
            orch = Orchestrator()
            result = await orch.chat(
                message=message,
                intent="evaluate",
                user=str(record.user_id),
                tenant_id=tenant_id,
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
                    "intent": "evaluate",
                    "agent": result.get("agent_used"),
                    "model_version": prov.get("model_version"),
                    "run_id": prov.get("run_id"),
                }
                source = "ai"
                trace_id = result.get("trace_id") or trace_id
        except Exception as exc:
            logger.warning("AI 效果评估编排失败，降级确定性计算: %s", exc)
            parsed = None

        if not parsed:
            # 降级：确定性评估
            score_result = self._compute_score(
                baseline=record.baseline_metrics or {},
                target=record.target_metrics or {},
                actual=record.actual_metrics or {},
            )
            parsed = {
                "summary": "（规则降级）" + "；".join(score_result["insights"]),
                "achievement_rate": round((score_result["score"] or 0) / 100.0, 2),
                "verdict": "achieved" if (score_result["score"] or 0) >= 80 else "partial_achieved",
                "reasons": [
                    {"factor": m, "status": "above_target" if d["achievement_rate"] >= 1.0 else "below_target",
                     "contribution": round(d["achievement_rate"], 2), "detail": f"{d['actual']} vs {d['target']}"}
                    for m, d in score_result["dimensions"].items()
                ],
            }

        # 落 reasoning_chain_id 到执行记录（关联 source 推理链，可解释/可追溯）
        if reasoning_chain_id:
            try:
                setattr(record, "reasoning_chain_id", reasoning_chain_id)
                db.commit()
                db.refresh(record)
            except Exception as exc:
                db.rollback()
                logger.warning("效果评估关联推理链失败: %s", exc)

        return {
            "execution_id": execution_id,
            "source": source,
            "summary": parsed.get("summary", ""),
            "achievement_rate": parsed.get("achievement_rate"),
            "verdict": parsed.get("verdict"),
            "reasons": parsed.get("reasons", []),
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


# ──────────────────────────────────────────────
# 全局单例
# ──────────────────────────────────────────────

effect_tracking_service = EffectTrackingService()


__all__ = ["EffectTrackingService", "effect_tracking_service"]
