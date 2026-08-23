"""决策支持 API - KPI 监控、归因分析、模拟推演、预警中心"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.response import unified_response

logger = logging.getLogger(__name__)


def _log_and_fail(e: Exception, msg: str, items: bool = True):
    """统一异常降级：记录日志并返回明确错误码，避免把 str(e) 泄露给前端"""
    logger.error("%s: %s", msg, e, exc_info=True)
    payload = {"items": []} if items else None
    return unified_response(payload, code=50000, message=msg)
from middleware.auth import get_current_user
from database import User, Role, get_db
from services import decision_service
from .schemas import (
    SimulateRequest, CreateExecutionRequest, UpdateProgressRequest,
    ConfirmDiagnosisRequest, CompleteLoopRequest,
    AiDiagnoseRequest, ConfirmDiagnosisByIdRequest, AdvanceDiagnosisRequest,
    ClearSignalRequest, ParadigmListRequest, ParadigmDeriveRequest,
)

router = APIRouter(prefix="/decision")


@router.get("/overview")
async def overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """决策总览：汇总关键 KPI + 预警数"""
    return unified_response(decision_service.get_overview(db, user.tenant_id, user.id))


@router.get("/kpi")
async def kpi_dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """KPI 监控看板：销售域 + 培训域详细指标"""
    # User 模型仅有 role_id，需解析为角色 code 供 ABAC 列级脱敏使用
    viewer_role = "admin"
    if user.role_id is not None:
        role = db.query(Role).filter(
            Role.tenant_id == user.tenant_id,
            Role.id == user.role_id,
            Role.is_deleted == 0,
        ).first()
        if role is not None:
            viewer_role = role.code or viewer_role
    return unified_response(decision_service.get_kpi_dashboard(
        db, user.tenant_id, user.id, viewer_role=viewer_role, viewer_id=user.id))


@router.get("/attribution")
async def attribution(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """归因分析：各维度对综合能力分的贡献度"""
    return unified_response(decision_service.get_attribution(db, user.tenant_id, user.id))


@router.post("/simulate")
async def simulate(req: SimulateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """模拟推演：What-if 分析"""
    return unified_response(decision_service.simulate_what_if(
        db, user.tenant_id, user.id, req.visit_change, req.training_change,
    ))


@router.get("/alerts")
async def alerts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """预警中心：异常预警列表"""
    return unified_response(decision_service.get_alerts(db, user.tenant_id, user.id))


@router.get("/diagnosis")
async def diagnosis(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """统一诊断（吸收参考2 诊断体系映射）

    将合规告警与决策预警归并为 4 色灯（GREEN/YELLOW/RED/BLACK）+ SLA。
    """
    return unified_response(decision_service.evaluate_diagnosis(db, user.tenant_id, user.id))


# ──────────────────────────────────────────────
# 本体论 + AI 原生改造：AI 诊断 / 归因 / 状态机端点
# ──────────────────────────────────────────────
@router.post("/ai-diagnose")
async def ai_diagnose(
    req: AiDiagnoseRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """AI 优先诊断：调用 AI 编排器（七步状态机）生成 Diagnosis 草稿 + Signal 实体（status=draft）"""
    return unified_response(await decision_service.ai_diagnose(
        db, user.tenant_id, user.id, domain=req.domain,
        target_type=req.target_type, target_id=req.target_id, user=str(user.id),
    ))


@router.post("/ai-attribute")
async def ai_attribute(
    req: AiDiagnoseRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """AI 优先归因：结构化因素 + 根因分析（经编排器七步）"""
    return unified_response(await decision_service.ai_attribute(
        db, user.tenant_id, user.id, domain=req.domain,
        target_type=req.target_type, target_id=req.target_id, user=str(user.id),
    ))


@router.post("/diagnosis/confirm")
async def confirm_diagnosis(
    req: ConfirmDiagnosisByIdRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """人工确认诊断草稿 → confirmed（合规闸门，AI 不自动执行）"""
    return unified_response(decision_service.confirm_diagnosis(
        db, user.tenant_id, req.diagnosis_id, user=str(user.id),
    ))


@router.post("/diagnosis/advance")
async def advance_diagnosis(
    req: AdvanceDiagnosisRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """推进诊断状态机（需 API 触发）：executing / verified / closed"""
    return unified_response(decision_service.advance_diagnosis(
        db, user.tenant_id, req.diagnosis_id, req.to_status, user=str(user.id),
    ))


@router.get("/diagnoses")
async def list_diagnoses(
    status: str | None = None,
    domain: str | None = None,
    rep_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列出当前代表/租户下的诊断实体（含信号）。

    rep_id 不传时默认取当前登录人；代表维度诊断页可传 rep_id 拉取指定代表的诊断。
    """
    target_rep = rep_id if rep_id is not None else user.id
    return unified_response(decision_service.list_diagnoses(
        db, user.tenant_id, target_rep, status=status, domain=domain,
    ))


@router.get("/reason/{target_type}/{target_id}")
async def reason(
    target_type: str, target_id: int,
    explanation_type: str = "causal",
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """可解释推理（吸收参考1 决策可解释思路）：基于 InsightChain 因果链输出解释"""
    return unified_response(decision_service.reason(db, target_type, target_id, explanation_type))


@router.get("/confidence/{chain_id}")
async def confidence(chain_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """置信度查询（吸收参考1 置信融合思路）"""
    return unified_response({"chain_id": chain_id, "confidence": decision_service.confidence(db, chain_id)})


@router.get("/loop")
async def diagnosis_loop(user: User = Depends(get_current_user), db: Session = Depends(get_db),
                         scope: str = "all"):
    """诊断闭环总览（吸收参考1 决策闭环 + 参考2 诊断体系）

    4 色灯 + 个人短板榜（下钻到代表）+ 团队短板（上卷）+ 各 rep 培训建议。
    仅诊断 + 建议，不自动触发执行/验证（符合医药合规人工留痕）。
    """
    from services import diagnosis_loop_service
    return unified_response(diagnosis_loop_service.run_diagnosis_loop(
        db, user.tenant_id, scope=scope, user_id=user.id if scope == "mine" else None))


@router.get("/loop/rep/{rep_id}")
async def loop_rep(rep_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """代表级诊断归因：短板维度 + 推荐培训课程（含 baseline/target 供下游验证）"""
    from services import diagnosis_loop_service
    return unified_response(diagnosis_loop_service.attribute_to_rep(db, user.tenant_id, rep_id))


@router.get("/loop/team/{region}")
async def loop_team(region: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """团队级诊断上卷：团队短板聚合 + 团队培训计划建议"""
    from services import diagnosis_loop_service
    loop = diagnosis_loop_service.run_diagnosis_loop(db, user.tenant_id, scope=region)
    return unified_response({
        "region": region,
        "team_summary": loop.get("team_summary"),
        "dimension_distribution": loop.get("dimension_distribution"),
        "rep_board": loop.get("rep_board"),
        "downstream_hint": loop.get("downstream_hint"),
    })


# ──────────────────────────────────────────────
# 随访闭环（吸收参考2 随访闭环体系）
#  诊断建议 → 确认执行 → 效果验证 → 判定闭环 → 范式沉淀
# ──────────────────────────────────────────────


@router.post("/loop/confirm")
async def loop_confirm(
    req: "ConfirmDiagnosisRequest",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """确认诊断建议 → 创建执行记录，进入随访闭环"""
    from services import followup_loop_service
    return unified_response(followup_loop_service.confirm_diagnosis_action(
        db=db,
        tenant_id=user.tenant_id,
        rep_id=req.rep_id,
        domain=req.domain,
        suggestion=req.suggestion,
        user_id=user.id,
    ))


@router.get("/loop/followup/{execution_id}")
async def loop_followup(
    execution_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """随访全链路追踪：诊断→执行→验证→判定 五步进度"""
    from services import followup_loop_service
    return unified_response(followup_loop_service.track_followup_chain(
        db, user.tenant_id, execution_id,
    ))


@router.post("/loop/complete/{execution_id}")
async def loop_complete(
    execution_id: int,
    req: "CompleteLoopRequest",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """完成执行 → 自动效果验证 → 信号消除矩阵判定闭环"""
    from services import followup_loop_service
    result = followup_loop_service.complete_and_review(
        db=db,
        tenant_id=user.tenant_id,
        execution_id=execution_id,
        actual_metrics=req.actual_metrics,
        force_closure_state=req.force_closure_state,
    )
    if "error" in result:
        return unified_response(None, code=40004, message=result.get("error", "未知错误"))
    return unified_response(result)


@router.get("/loop/paradigms")
async def loop_paradigms(
    execution_id: int | None = None,
    domain: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """通用范式库 — 从成功闭环记录中提取有效解决方法"""
    from services import followup_loop_service
    return unified_response(followup_loop_service.extract_paradigms(
        db=db,
        tenant_id=user.tenant_id,
        execution_id=execution_id,
        domain=domain,
    ))


@router.get("/loop/history/{rep_id}")
async def loop_history(
    rep_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """代表随访历史（一人一院知识沉淀）"""
    from services import followup_loop_service
    return unified_response(followup_loop_service.get_rep_followup_history(
        db, user.tenant_id, rep_id,
    ))


@router.get("/loop/team-closure")
async def loop_team_closure(
    region: str | None = None,
    month: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """团队闭环面板 — 信号消除矩阵团队视图"""
    from services import followup_loop_service
    return unified_response(followup_loop_service.team_closure_panel(
        db=db,
        tenant_id=user.tenant_id,
        region=region,
        month_label=month,
    ))


@router.post("/signal/clear")
async def clear_signal(
    req: ClearSignalRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """消除异常信号（需 API 触发，满足合规人工留痕）"""
    from services import ai_diagnosis_service
    return unified_response(ai_diagnosis_service.clear_signal(db, req.signal_id))


@router.get("/reasoning-chain/{chain_id}")
async def get_reasoning_chain(
    chain_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """推理链详情 — AI 原生可观测性入口"""
    from ai.reasoning_chain import ReasoningChainBuilder
    chain = ReasoningChainBuilder().get_chain(chain_id, user.tenant_id, db)
    return unified_response(chain)


@router.get("/paradigms")
async def list_paradigms(
    req: ParadigmListRequest = Depends(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """范式库（本体 Paradigm 实体，新表）"""
    from services import ai_paradigm_service
    return unified_response(ai_paradigm_service.list_paradigms(db, user.tenant_id, req.domain))


@router.post("/paradigm/derive")
async def derive_paradigm(
    req: ParadigmDeriveRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """从已闭环执行沉淀通用解题范式（经编排器七步状态机：derive_paradigm 意图）"""
    from services import ai_paradigm_service
    result = await ai_paradigm_service.derive_paradigm(
        db, user.tenant_id, req.execution_id, req.domain)
    return unified_response(result)


@router.post("/effect/evaluate")
async def ai_evaluate_execution(
    req: ParadigmDeriveRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """N+AI原生闭环：对已完成执行做 AI 效果归因评估（经编排器 evaluate 意图）

    产出可解释的达成/未达成推理链，关联 DecisionExecution.reasoning_chain_id。
    """
    from services.effect_tracking_service import effect_tracking_service
    result = await effect_tracking_service.ai_evaluate(
        execution_id=req.execution_id, tenant_id=user.tenant_id, db=db,
        user=str(user.id),
    )
    return unified_response(result)


# ──────────────────────────────────────────────
# 决策效果追踪
# ──────────────────────────────────────────────


@router.get("/executions")
async def list_executions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status: str = None,
    limit: int = 20,
):
    """决策执行列表"""
    try:
        from services.effect_tracking_service import effect_tracking_service
        return unified_response({
            "items": effect_tracking_service.get_executions(
                user.id, user.tenant_id, db, status=status, limit=limit,
            )
        })
    except Exception as e:
        return _log_and_fail(e, "执行列表加载失败")


@router.post("/executions")
async def create_execution(
    req: CreateExecutionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建决策执行记录"""
    try:
        from services.effect_tracking_service import effect_tracking_service
        return unified_response(effect_tracking_service.create_execution(
            user.id, user.tenant_id, db,
            req.decision_type, req.title, req.description,
            req.baseline, req.target,
        ))
    except Exception as e:
        return _log_and_fail(e, "操作失败", items=False)


@router.get("/executions/{execution_id}")
async def get_execution(
    execution_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """决策执行详情"""
    try:
        from services.effect_tracking_service import effect_tracking_service
        result = effect_tracking_service.get_execution(execution_id, user.tenant_id, db)
        if not result:
            return unified_response(None, code=40004, message="执行记录不存在")
        return unified_response(result)
    except Exception as e:
        return _log_and_fail(e, "操作失败", items=False)


@router.post("/executions/{execution_id}/start")
async def start_execution(
    execution_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """开始执行"""
    try:
        from services.effect_tracking_service import effect_tracking_service
        return unified_response(effect_tracking_service.start_execution(
            execution_id, user.tenant_id, db,
        ))
    except Exception as e:
        return _log_and_fail(e, "操作失败", items=False)


@router.post("/executions/{execution_id}/progress")
async def update_progress(
    execution_id: int,
    req: UpdateProgressRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新进度"""
    try:
        from services.effect_tracking_service import effect_tracking_service
        return unified_response(effect_tracking_service.update_progress(
            execution_id, user.tenant_id, db, req.actual_metrics,
        ))
    except Exception as e:
        return _log_and_fail(e, "操作失败", items=False)


@router.post("/executions/{execution_id}/complete")
async def complete_execution(
    execution_id: int,
    req: UpdateProgressRequest = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """完成执行并计算效果"""
    try:
        from services.effect_tracking_service import effect_tracking_service
        actual = req.actual_metrics if req else None
        return unified_response(effect_tracking_service.complete_execution(
            execution_id, user.tenant_id, db, actual,
        ))
    except Exception as e:
        return _log_and_fail(e, "操作失败", items=False)


@router.get("/executions/{execution_id}/effectiveness")
async def get_effectiveness(
    execution_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """计算效果得分"""
    try:
        from services.effect_tracking_service import effect_tracking_service
        return unified_response(effect_tracking_service.compute_effectiveness(
            execution_id, user.tenant_id, db,
        ))
    except Exception as e:
        return _log_and_fail(e, "操作失败", items=False)


@router.post("/ai-insights")
async def decision_ai_insights(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """AI 决策洞察（查询预生成缓存）"""
    from services.ai_insight_service import ai_insight_service
    result = ai_insight_service.get_cached_insight(domain="decision", tenant_id=user.tenant_id, user_id=user.id, db=db)
    return unified_response(result)
