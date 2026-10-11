"""AI API - 七步状态机 + SSE 流式协议 + 推理链 + 指标 + 事件"""
import asyncio
import json
import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db, User, ChatSession, ChatMessage
from core.response import unified_response
from middleware.auth import get_current_user, require_permission
from ai.orchestrator import Orchestrator
from ai.agents.registry import list_agents, get_agent
from ai.actions.registry import list_actions, get_action, execute as execute_action
from ai.metrics_collector import metrics_collector

from .schemas import (
    ChatSendRequest,
    ReasoningFeedbackRequest,
    DeadLetterResolveRequest,
    CollaborateRequest,
    RunResumeRequest,
)

logger = logging.getLogger(__name__)


def _log_and_fail(e: Exception, msg: str, items: bool = True):
    """统一异常降级：记录日志并返回明确错误码，避免把 str(e) 泄露给前端"""
    logger.error("%s: %s", msg, e, exc_info=True)
    payload = {"items": []} if items else None
    return unified_response(payload, code=50000, message=msg)

router = APIRouter()
orchestrator = Orchestrator()


# ──────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────

def _sse_event(event_type: str, data: dict) -> str:
    """格式化 SSE 事件"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _split_response(text: str) -> list[str]:
    """将响应文本分割为流式发送的块"""
    if not text:
        return []
    # 按换行分割，每行作为一个 chunk
    lines = text.split("\n")
    chunks = []
    for line in lines:
        if line.strip():
            chunks.append(line + "\n")
    return chunks if chunks else [text]


def _generate_suggestions(result: dict) -> list[dict]:
    """根据 AI 响应生成后续建议"""
    suggestions = []
    intent = result.get("intent", "")

    SUGGESTION_MAP = {
        "visit": [
            {"title": "查看覆盖矩阵", "action": "navigate", "target": "/sales/coverage"},
            {"title": "创建拜访计划", "action": "navigate", "target": "/sales/plans"},
        ],
        "course": [
            {"title": "查看学习路径", "action": "navigate", "target": "/training"},
            {"title": "开始模拟考试", "action": "navigate", "target": "/training"},
        ],
        "kpi": [
            {"title": "查看决策概览", "action": "navigate", "target": "/decision"},
            {"title": "KPI 仪表盘", "action": "navigate", "target": "/decision/kpi"},
        ],
        "knowledge": [
            {"title": "浏览知识库", "action": "navigate", "target": "/knowledge"},
            {"title": "查看 FAQ", "action": "navigate", "target": "/knowledge/faqs"},
        ],
        "feedback": [
            {"title": "查看拜访反馈", "action": "navigate", "target": "/sales/feedback"},
        ],
        "coverage": [
            {"title": "覆盖分管", "action": "navigate", "target": "/sales/coverage"},
        ],
    }

    return SUGGESTION_MAP.get(intent, [])


# ──────────────────────────────────────────────
# 聊天 - 普通 + SSE 流式
# ──────────────────────────────────────────────

@router.post("/ai/chat/send")
async def chat_send(
    req: ChatSendRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """普通聊天 - 七步状态机完整执行"""
    result = await orchestrator.chat(
        req.message, user, req.session_id, db=db, intent=req.intent,
    )
    return unified_response(result)


@router.post("/ai/chat/stream")
async def chat_stream(
    req: ChatSendRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """SSE 流式聊天 - 10 种事件类型（真流式 token-by-token）

    事件类型：
    1. thinking    - AI 思考中
    2. intent      - 意图识别结果
    3. routing     - Agent 路由信息
    4. skill       - Skill 匹配信息
    5. reasoning   - Nemotron 思考链片段
    6. content     - 内容片段（流式输出）
    7. tools_used  - 工具调用记录
    8. suggestions - 后续建议
    9. done        - 完成
    10. error      - 错误
    """
    async def event_generator():
        try:
            async for evt in orchestrator.stream_chat(
                req.message, user, req.session_id, db=db, intent=req.intent,
            ):
                evt_type = evt.get("type", "content")
                yield _sse_event(evt_type, evt)

        except Exception as e:
            logger.error("AI 流式聊天异常: %s", e, exc_info=True)
            yield _sse_event("error", {"message": "服务异常，请稍后重试"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/ai/chat/{session_id}/abort")
async def chat_abort(session_id: str, user: User = Depends(get_current_user)):
    """取消进行中的 chat/stream 运行（协作式；ToolLoop 轮次边界生效）。"""
    from ai.run_control import run_registry
    ok = run_registry.abort(session_id)
    return unified_response({
        "aborted": True,
        "session_id": session_id,
        "signal_set": ok,
    })


@router.get("/ai/workspace/{session_id}")
async def get_workspace_draft(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """读取工作流 SceneWorkspace 草稿（供前端会话恢复门禁/回显）。"""
    from ai.skills.scene_workspace import scene_workspace
    from ai.skills.executor import WorkflowSkillExecutor

    tenant_id = str(getattr(user, "tenant_id", "default"))
    draft = scene_workspace.load(session_id, db, tenant_id, user.id)
    # 空草稿（无门禁、无采集）视为不存在，避免前端误覆盖
    if not (draft.gates_passed or draft.collection or draft.config or draft.scenario_id):
        return unified_response(None, code=40400, message="workspace draft 不存在")
    return unified_response(WorkflowSkillExecutor._serialize_draft_state(draft))


# ──────────────────────────────────────────────
# Phase B：Run Checkpoint / Traces / Eval
# ──────────────────────────────────────────────

@router.get("/ai/runs")
async def list_agent_runs(
    session_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列出当前租户的 Agent run checkpoint。"""
    from ai.checkpoint_store import list_runs
    tenant_id = getattr(user, "tenant_id", "default")
    items = list_runs(db, tenant_id=tenant_id, session_id=session_id, limit=50)
    return unified_response({"items": items, "total": len(items)})


@router.get("/ai/runs/{run_id}")
async def get_agent_run(
    run_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from ai.checkpoint_store import load_run
    tenant_id = getattr(user, "tenant_id", "default")
    row = load_run(db, run_id, tenant_id=tenant_id)
    if not row:
        return unified_response(None, code=40400, message="run 不存在")
    return unified_response(row)


@router.post("/ai/runs/{run_id}/resume")
async def resume_agent_run(
    run_id: str,
    req: RunResumeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """从 checkpoint 续跑 ToolLoop。"""
    from ai.checkpoint_store import load_run
    tenant_id = getattr(user, "tenant_id", "default")
    loaded = load_run(db, run_id, tenant_id=tenant_id)
    if not loaded:
        return unified_response(None, code=40400, message="run 不存在")
    message = (req.message or "").strip() or (loaded.get("last_content") and "请继续完成刚才未完成的任务") or "继续"
    result = await orchestrator.chat(
        message=message,
        user=user,
        session_id=loaded.get("session_id"),
        db=db,
        intent=loaded.get("intent"),
        tenant_id=tenant_id,
        resume_run_id=run_id,
    )
    return unified_response(result)


@router.get("/ai/traces/{trace_id}")
async def get_trace_spans(
    trace_id: str,
    user: User = Depends(get_current_user),
):
    """查询进程内 OTEL 风格 span 树。"""
    from ai.otel_spans import get_spans
    spans = get_spans(trace_id)
    return unified_response({"trace_id": trace_id, "spans": spans, "total": len(spans)})


@router.post("/ai/eval/run")
async def run_eval(
    case: Optional[str] = None,
    user: User = Depends(get_current_user),
):
    """触发 Eval Harness（管理员用途；同步跑黄金用例）。"""
    from eval.runner import run_eval_suite
    summary = await asyncio.to_thread(run_eval_suite, case)
    return unified_response(summary)


# ──────────────────────────────────────────────
# 运行期指标
# ──────────────────────────────────────────────

@router.get("/ai/metrics")
async def get_metrics(user: User = Depends(get_current_user)):
    """获取 AI 运行期指标"""
    return unified_response(metrics_collector.get_summary())


@router.post("/ai/metrics/reset")
async def reset_metrics(user: User = Depends(get_current_user)):
    """重置指标（仅管理员）"""
    metrics_collector.reset()
    return unified_response({"reset": True})


# ──────────────────────────────────────────────
# 推理链
# ──────────────────────────────────────────────

@router.get("/ai/reasoning/chains")
async def list_reasoning_chains(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 20,
):
    """推理链列表"""
    try:
        from ai.reasoning_chain import reasoning_chain_builder
        chains = reasoning_chain_builder.get_chains(
            user_id=user.id,
            tenant_id=user.tenant_id,
            db=db,
            limit=limit,
        )
        return unified_response({"items": chains})
    except Exception as e:
        logger.error("获取推理链列表失败: %s", e, exc_info=True)
        return unified_response({"items": []}, code=50000, message="推理链加载失败，请稍后重试")


@router.get("/ai/reasoning/chains/{chain_id}")
async def get_reasoning_chain(
    chain_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """推理链详情"""
    try:
        from ai.reasoning_chain import reasoning_chain_builder
        chain = reasoning_chain_builder.get_chain(chain_id, user.tenant_id, db)
        if not chain:
            return unified_response(None, code=40004, message="推理链不存在")
        return unified_response(chain)
    except Exception as e:
        logger.error("获取推理链详情失败: %s", e, exc_info=True)
        return unified_response(None, code=50000, message="推理链加载失败，请稍后重试")


@router.post("/ai/reasoning/chains/{chain_id}/feedback")
async def reasoning_feedback(
    chain_id: int,
    req: ReasoningFeedbackRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """推理链用户反馈"""
    try:
        from ai.reasoning_chain import reasoning_chain_builder
        result = reasoning_chain_builder.add_feedback(
            chain_id, user.tenant_id, db, req.rating, req.feedback_text,
        )
        return unified_response(result)
    except Exception as e:
        logger.error("提交推理链反馈失败: %s", e, exc_info=True)
        return unified_response(None, code=50000, message="反馈提交失败，请稍后重试")


# ──────────────────────────────────────────────
# 主动建议
# ──────────────────────────────────────────────

@router.get("/ai/suggestions")
async def get_suggestions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取主动建议"""
    try:
        from ai.proactive_suggestions import proactive_engine
        suggestions = proactive_engine.generate(user.id, user.tenant_id, db)
        return unified_response({"items": suggestions})
    except Exception as e:
        return _log_and_fail(e, "数据加载失败")


@router.post("/ai/suggestions/{suggestion_id}/action")
async def record_suggestion_action(
    suggestion_id: str,
    action_type: str,
    suggestion_type: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """N+4: 记录用户对建议的行为（accepted/ignored/dismissed）

    自动安排 24h 后的延迟评估。
    """
    try:
        from ai.proactive_suggestions import proactive_engine
        result = proactive_engine.record_action(
            suggestion_id=suggestion_id,
            user_id=user.id,
            action_type=action_type,
            db=db,
            suggestion_type=suggestion_type,
            tenant_id=user.tenant_id,
        )
        return unified_response(result)
    except Exception as e:
        return _log_and_fail(e, "操作失败", items=False)


@router.get("/ai/suggestions/actions/history")
async def get_suggestion_action_history(
    days: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """N+4: 用户建议行动历史"""
    try:
        from ai.proactive_suggestions import proactive_engine
        history = proactive_engine.get_action_history(
            user_id=user.id, days=days, db=db, tenant_id=user.tenant_id,
        )
        return unified_response({"items": history})
    except Exception as e:
        return _log_and_fail(e, "数据加载失败")


@router.post("/ai/suggestions/actions/evaluate-pending")
async def evaluate_pending_actions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    batch: int = 50,
):
    """N+4: 评估到期的待评估行动（evaluate_after <= now）

    可由定时任务或管理员手动触发。
    """
    try:
        from ai.proactive_suggestions import proactive_engine
        count = proactive_engine.process_pending_evaluations(
            db=db, tenant_id=user.tenant_id, batch=batch,
        )
        return unified_response({"evaluated_count": count})
    except Exception as e:
        return _log_and_fail(e, "操作失败", items=False)


# ──────────────────────────────────────────────
# AI 事件
# ──────────────────────────────────────────────

@router.get("/ai/events")
async def list_ai_events(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
):
    """AI 事件列表"""
    try:
        from ai.event_bus import event_bus
        events = event_bus.get_events(
            user.tenant_id, db, event_type=event_type, status=status, limit=limit,
        )
        return unified_response({"items": events})
    except Exception as e:
        return _log_and_fail(e, "数据加载失败")


@router.get("/ai/events/dead-letters")
async def list_dead_letters(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 20,
):
    """死信队列"""
    try:
        from ai.event_bus import event_bus
        letters = event_bus.get_dead_letters(user.tenant_id, db, limit=limit)
        return unified_response({"items": letters})
    except Exception as e:
        return _log_and_fail(e, "数据加载失败")


@router.post("/ai/events/dead-letters/{letter_id}/resolve")
async def resolve_dead_letter(
    letter_id: int,
    req: DeadLetterResolveRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """人工处理死信"""
    try:
        from ai.event_bus import event_bus
        result = event_bus.resolve_dead_letter(
            letter_id, user.tenant_id, db, user.id, req.note,
        )
        return unified_response(result)
    except Exception as e:
        return _log_and_fail(e, "处理死信失败", items=False)


@router.post("/ai/events/replay/{event_id}")
async def replay_event(
    event_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """重放事件"""
    try:
        from ai.event_bus import event_bus
        result = event_bus.replay_event(event_id, user.tenant_id, db)
        return unified_response(result)
    except Exception as e:
        return _log_and_fail(e, "重放事件失败", items=False)


# ──────────────────────────────────────────────
# 缓存管理
# ──────────────────────────────────────────────

@router.delete("/ai/cache")
async def clear_cache(user: User = Depends(get_current_user)):
    """清空语义缓存"""
    from ai.llm_client import llm_client
    llm_client.clear_cache()
    return unified_response({"cleared": True})


# ──────────────────────────────────────────────
# Agent / Action 端点（保留原有）
# ──────────────────────────────────────────────

@router.get("/agents")
async def agents_list(user: User = Depends(get_current_user)):
    return unified_response({"items": list_agents()})


@router.get("/agents/{name}")
async def agent_detail(name: str, user: User = Depends(get_current_user)):
    agent = get_agent(name)
    if not agent:
        return unified_response(None, code=40001, message="Agent 不存在")
    return unified_response({
        "name": agent.name,
        "display_name": agent.display_name,
        "domain": agent.domain,
        "description": agent.description,
        "tools": agent.tools,
        "skills": agent.skills,
    })


@router.post("/agents/{name}/invoke")
async def agent_invoke(
    name: str,
    user: User = Depends(get_current_user),
    input: dict = None,
):
    agent = get_agent(name)
    if not agent:
        return unified_response(None, code=40001, message="Agent 不存在")
    result = await agent.invoke(input or {})
    return unified_response(result)


@router.get("/actions")
async def actions_list(user: User = Depends(get_current_user)):
    return unified_response({"items": list_actions()})


@router.get("/actions/{name}")
async def action_detail(name: str, user: User = Depends(get_current_user)):
    action = get_action(name)
    if not action:
        return unified_response(None, code=40001, message="Action 不存在")
    return unified_response(action)


@router.post("/actions/{name}/execute")
async def action_execute(
    name: str,
    user: User = Depends(get_current_user),
    input: dict = None,
):
    result = await execute_action(name, input or {}, user)
    return unified_response(result)


# ──────────────────────────────────────────────
# 多 Agent 协作
# ──────────────────────────────────────────────

@router.post("/ai/collaborate")
async def collaborate(
    req: CollaborateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """手动触发多 Agent 协作（调试/演示用）

    支持三种协作模式：
      - delegate：Supervisor 拆解任务 → 并行分派 → 聚合
      - orchestrate：管道串联，前一个输出作为后一个输入
      - aggregate：多 Agent 独立处理同一任务 → 合并/投票/选最佳
      - auto：自动判定模式与参与 Agent

    自动判定规则（CollaborationOrchestrator.detect_collaboration_need）：
      - 跨域关键词（销售+培训 → delegate/orchestrate，销售+决策 → aggregate）
      - 多动词（分析+推荐、评估+生成、总结+规划）
    """
    try:
        from ai.agents.collaboration import (
            CollaborationOrchestrator,
            get_collaboration_orchestrator,
        )

        tenant_id = getattr(user, "tenant_id", "default") if user else "default"
        user_id = getattr(user, "id", None) if user else None

        # 构建执行上下文
        ctx = {
            "db": db,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "user": user,
        }
        if req.context:
            ctx.update(req.context)

        # 延迟初始化 ToolLoop（仅 LLM 模式下）
        tool_loop = None
        try:
            from ai.agents.registry import get_agent_mode
            if get_agent_mode() == "llm":
                from ai.tool_loop import ToolLoop
                from ai.tools.registry import TOOL_REGISTRY
                tool_loop = ToolLoop(
                    llm_client=orchestrator.llm,
                    tool_registry=TOOL_REGISTRY,
                    max_rounds=3,  # 协作场景下减少单 Agent 工具循环轮数
                )
        except Exception as e:
            logger.warning("协作 ToolLoop 初始化失败: %s", e, exc_info=True)

        collab = get_collaboration_orchestrator()
        collab._tool_loop = tool_loop  # 注入 ToolLoop

        # 模式判定
        mode = req.mode
        agents = req.agents or []
        strategy = req.strategy

        if mode == "auto":
            # 自动判定
            detected = CollaborationOrchestrator.detect_collaboration_need(
                req.message, intent=""
            )
            if detected is None:
                return unified_response(
                    None,
                    code=40001,
                    message="未检测到协作需求，请显式指定 mode 和 agents",
                )
            mode = detected["mode"]
            agents = detected["agents"]
            strategy = detected.get("strategy", "merge")

        # 校验参数
        if not agents:
            return unified_response(
                None, code=40001, message="缺少参与 Agent 列表"
            )
        if mode not in ("delegate", "orchestrate", "aggregate"):
            return unified_response(
                None, code=40001, message=f"不支持的协作模式：{mode}"
            )

        # 执行协作
        if mode == "delegate":
            result = await collab.delegate(
                task=req.message,
                sub_agents=agents,
                ctx=ctx,
                tenant_id=tenant_id,
            )
        elif mode == "orchestrate":
            result = await collab.orchestrate(
                task=req.message,
                pipeline=agents,
                ctx=ctx,
                tenant_id=tenant_id,
            )
        else:  # aggregate
            result = await collab.aggregate(
                task=req.message,
                agent_names=agents,
                ctx=ctx,
                strategy=strategy,
                tenant_id=tenant_id,
            )

        return unified_response(result)
    except Exception as e:
        logger.exception("collaborate failed")
        return unified_response(None, code=50000, message="协同编排失败，请稍后重试")


@router.get("/ai/agents")
async def list_agents_meta(
    user: User = Depends(get_current_user),
    domain: Optional[str] = None,
):
    """列出所有 Agent 元数据（含协作能力标记）

    用于前端协作调试页面或 Agent 选择器展示。
    与 GET /agents 区别：本端点额外返回 tools 列表，便于协作时挑选 Agent。
    """
    agents = list_agents(domain=domain)
    return unified_response({"items": agents, "total": len(agents)})


@router.get("/ai/collaboration/detect")
async def detect_collaboration(
    message: str,
    user: User = Depends(get_current_user),
):
    """检测消息是否需要多 Agent 协作

    返回 {needed, mode, agents, strategy}。needed=false 表示单 Agent 即可。
    """
    from ai.agents.collaboration import CollaborationOrchestrator

    detected = CollaborationOrchestrator.detect_collaboration_need(message, intent="")
    if detected is None:
        return unified_response({
            "needed": False,
            "mode": None,
            "agents": [],
            "strategy": None,
        })
    return unified_response({
        "needed": True,
        "mode": detected["mode"],
        "agents": detected["agents"],
        "strategy": detected.get("strategy", "merge"),
    })


@router.post("/ai/insights/refresh")
async def refresh_insights(
    user: User = Depends(require_permission("platform.write")),
):
    """手动触发 AI 洞察预生成（管理员功能）

    立即为所有 13 个领域生成洞察并存入 ai_insight_cache 表。
    用于测试、首次部署或紧急刷新场景。
    正常情况下由定时任务每天自动执行。

    权限：platform.write（admin / platform_admin 可触发，普通用户 403），
    避免任意登录用户触发全租户全域 LLM 再生形成 DoS 面。
    """
    from services.insight_scheduler import trigger_insight_generation_now, SUPPORTED_DOMAINS
    # 阻塞治理：全量生成是同步长任务（含同步 LLM 调用），放入线程池避免阻塞事件循环
    results = await asyncio.to_thread(trigger_insight_generation_now)
    success = sum(1 for r in results if r["status"] == "ok")
    return unified_response({
        "total": len(SUPPORTED_DOMAINS),
        "success": success,
        "fail": len(SUPPORTED_DOMAINS) - success,
        "details": results,
    })


@router.get("/ai/suggestions/ai")
async def get_ai_suggestions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    domain: str = None,
):
    """N+AI原生闭环：生成 AI 原生主动建议（经编排器 suggest 意图）

    确定性扫描多源数据后经编排器做 AI 优先级排序与可解释包装，
    返回统一 provenance + reasoning_chain_id。编排器失败时降级确定性建议。
    """
    try:
        from ai.proactive_suggestions import proactive_engine
        result = await proactive_engine.ai_suggest(
            user_id=user.id, tenant_id=user.tenant_id, db=db, domain=domain,
        )
        return unified_response(result)
    except Exception as e:
        logger.error("生成 AI 主动建议失败: %s", e, exc_info=True)
        return unified_response({"items": []}, code=50000, message="建议生成失败，请稍后重试")


@router.get("/ai/insight/ai")
async def get_ai_insight(
    domain: str = "sales",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """N+AI原生闭环：生成 AI 原生洞察（经编排器 insight 意图）

    产出结构化洞察 + 统一 provenance + reasoning_chain_id。
    编排器整体失败时降级既有确定性/LLM 洞察逻辑。
    """
    try:
        from services.ai_insight_service import ai_insight_service
        result = await ai_insight_service.ai_generate_insight(
            domain=domain, user_id=user.id, tenant_id=user.tenant_id, db=db,
        )
        return unified_response(result)
    except Exception as e:
        return _log_and_fail(e, "操作失败", items=False)
