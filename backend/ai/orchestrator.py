"""AI 编排器 - 七步状态机（AI 原生增强版）

七步流程：guardrails → cache → intent → slot → agent+reflection → hallucination → persist+metrics
所有 AI 能力在 LLM_PROVIDER="mock" 下可用，真实 LLM 是增强而非依赖。
"""
import asyncio
import logging
import json
import re
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Optional

from ai.agents.registry import AGENT_REGISTRY, get_agent, list_agents
from ai.actions.registry import execute as execute_action
from ai.rag import RAGRetriever
from ai.prompts import get_prompt
from ai.llm_client import llm_client
from ai.metrics_collector import metrics_collector
# B3：意图路由配置从 intent_routes.py 导入（原硬编码常量已迁移）
from ai.intent_routes import (
    INTENT_KEYWORDS,
    DOMAIN_AGENT_MAP,
    INTENT_SKILL_MAP,
    INTENT_RESPONSES,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────

def _split_response(text: str) -> list[str]:
    """将响应文本分割为流式发送的块（用于 mock 降级模式）"""
    if not text:
        return []
    lines = text.split("\n")
    chunks = []
    for line in lines:
        if line.strip():
            chunks.append(line + "\n")
    return chunks if chunks else [text]


class Orchestrator:
    """AI 编排器 - 七步状态机（AI 原生增强版）

    七步流程：
    1. Guardrails  - 输入安全检查（prompt 注入防御）
    2. Cache       - 语义缓存查询
    3. Intent      - 混合意图分类
    4. Slot        - 槽位提取
    5. Agent+Reflect - Agent 执行 + Self-Reflection 循环
    6. Hallucination - 4 策略幻觉检测
    7. Persist     - 缓存写入 + 指标采集 + 事件发布 + 推理链持久化
    """

    def __init__(self):
        self.rag = RAGRetriever()
        self.llm = llm_client
        self.metrics = metrics_collector
        # 延迟导入避免循环依赖
        self._intent_classifier = None
        self._memory_service = None
        self._reasoning_chain_builder = None
        self._safety_valves = None
        self._self_reflection = None
        self._hallucination_detector = None
        self._event_bus = None

    def _get_intent_classifier(self):
        if self._intent_classifier is None:
            from ai.intent_classifier import intent_classifier
            self._intent_classifier = intent_classifier
        return self._intent_classifier

    def _get_memory_service(self):
        if self._memory_service is None:
            from ai.memory_service import memory_service
            self._memory_service = memory_service
        return self._memory_service

    def _get_reasoning_chain_builder(self):
        if self._reasoning_chain_builder is None:
            from ai.reasoning_chain import reasoning_chain_builder
            self._reasoning_chain_builder = reasoning_chain_builder
        return self._reasoning_chain_builder

    def _get_safety_valves(self):
        if self._safety_valves is None:
            from ai.safety_valves import safety_valves_engine
            self._safety_valves = safety_valves_engine
        return self._safety_valves

    def _get_self_reflection(self):
        if self._self_reflection is None:
            from ai.self_reflection import self_reflection_engine
            self._self_reflection = self_reflection_engine
        return self._self_reflection

    def _get_hallucination_detector(self):
        if self._hallucination_detector is None:
            from ai.hallucination_detector import hallucination_detector
            self._hallucination_detector = hallucination_detector
        return self._hallucination_detector

    def _get_event_bus(self):
        if self._event_bus is None:
            from ai.event_bus import event_bus
            self._event_bus = event_bus
        return self._event_bus

    async def _run_tool_loop(
        self, messages, agent, intent_name, tenant_id, db, user_id,
        should_cancel=None,
        *,
        session_id: Optional[str] = None,
        agent_name: str = "",
        skill_name: Optional[str] = None,
        skill_meta: Optional[dict] = None,
        is_workflow: bool = False,
        trace_id: Optional[str] = None,
        resume_run_id: Optional[str] = None,
    ):
        """执行 ToolLoop 并返回 (response, tools_used, llm_result, meta)

        Phase B：动态预算 + checkpoint + OTEL span。
        """
        from ai.tool_loop import ToolLoop
        from ai.tools.registry import TOOL_REGISTRY
        from ai.budget import resolve_budget
        from ai.checkpoint_store import begin_run, save_checkpoint, finish_run, load_run
        from ai.otel_spans import span

        available_tools = [t for t in agent.get("tools", []) if t in TOOL_REGISTRY]
        budget = resolve_budget(
            intent=intent_name,
            skill_meta=skill_meta,
            is_workflow=is_workflow,
        )
        meta = {
            "run_id": None,
            "budget": budget.to_dict(),
            "trace_id": trace_id,
        }
        if not available_tools:
            llm_result = await self.llm.async_chat(
                messages=messages, intent=intent_name, tenant_id=tenant_id,
                trace_id=trace_id,
            )
            return llm_result.get("content", ""), [], llm_result, meta

        resume_state = None
        run_id = resume_run_id
        if resume_run_id and db is not None:
            loaded = load_run(db, resume_run_id, tenant_id=tenant_id)
            if loaded and loaded.get("status") in ("running", "aborted", "failed"):
                resume_state = {
                    "messages": loaded.get("messages") or [],
                    "tools_used": loaded.get("tools_used") or [],
                    "round": loaded.get("cursor_round") or 0,
                    "last_content": loaded.get("last_content") or "",
                }
                run_id = resume_run_id
        if not run_id:
            run_id = begin_run(
                db,
                tenant_id=tenant_id,
                session_id=session_id,
                user_id=user_id,
                intent=intent_name,
                agent_name=agent_name,
                skill_name=skill_name,
                max_rounds=budget.max_rounds,
                budget=budget.to_dict(),
                trace_id=trace_id,
            )
        meta["run_id"] = run_id

        tool_loop = ToolLoop(
            llm_client=self.llm,
            tool_registry=TOOL_REGISTRY,
            max_rounds=budget.max_rounds,
        )
        ctx = {
            "db": db,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "session_id": session_id,
            "run_id": run_id,
            "trace_id": trace_id,
        }

        def _on_round_end(round_num, snap):
            save_checkpoint(
                db, run_id,
                cursor_round=round_num,
                messages=snap.get("messages") or [],
                tools_used=snap.get("tools_used") or [],
                last_content=snap.get("last_content") or "",
                status="running",
            )

        import asyncio
        mode = self.llm._tool_call_mode()
        use_native = mode == "native" or (mode == "auto" and self.llm.provider == "openai")
        runner = tool_loop.run_native if use_native else tool_loop.run
        budget_deadline = time.monotonic() + (budget.max_latency_ms / 1000.0)

        with span(
            "tool_loop.run",
            trace_id=trace_id,
            attributes={
                "intent": intent_name,
                "max_rounds": budget.max_rounds,
                "run_id": run_id or "",
                "native": use_native,
            },
        ):
            loop_result = await asyncio.to_thread(
                runner,
                messages=messages,
                available_tools=available_tools,
                ctx=ctx,
                intent=intent_name,
                tenant_id=tenant_id,
                should_cancel=should_cancel,
                on_round_end=_on_round_end,
                resume_state=resume_state,
                budget_deadline=budget_deadline,
            )
        response = loop_result.get("response", "")
        tools_used = loop_result.get("tools_used", [])
        meta["truncated"] = bool(loop_result.get("truncated"))
        meta["budget_exceeded"] = bool(loop_result.get("budget_exceeded"))
        meta["aborted"] = bool(loop_result.get("aborted"))

        if not response and tools_used:
            try:
                summarize_msgs = messages + [{
                    "role": "user",
                    "content": (
                        "基于以下工具返回的数据，用简洁自然的中文给用户回答（不要列 JSON）。\n"
                        f"用户问题：{messages[-1].get('content', '')}\n"
                        f"工具结果：{json.dumps(tools_used, ensure_ascii=False, default=str)[:1500]}"
                    ),
                }]
                fb = await self.llm.async_chat(
                    messages=summarize_msgs,
                    intent=intent_name,
                    tenant_id=tenant_id,
                    use_cache=False,
                    trace_id=trace_id,
                )
                response = fb.get("content", "") or response
            except Exception as e:
                logger.debug("ToolLoop 兜底总结失败: %s", e, exc_info=True)

        status = "completed"
        if meta.get("aborted"):
            status = "aborted"
        elif meta.get("budget_exceeded") or meta.get("truncated"):
            status = "failed" if not response else "completed"
        finish_run(db, run_id, status=status, last_content=response)

        llm_result = {
            "content": response,
            "reasoning": "",
            "cache_hit": False,
            "provider": "openai",
            "degraded": False,
            "run_id": run_id,
            "budget": budget.to_dict(),
        }
        return response, tools_used, llm_result, meta

    async def _execute_agent_turn(
        self,
        *,
        message: str,
        user: Any,
        session_id: str,
        db: Any,
        tenant_id: str,
        user_id: Any,
        intent_result: dict,
        intent_name: str,
        agent_name: str,
        slots: dict,
        should_cancel=None,
        trace_id: Optional[str] = None,
        resume_run_id: Optional[str] = None,
    ) -> dict:
        """Phase A/B：chat / stream_chat 共享的 Agent 执行核。

        含：协作 → Skill/ToolLoop → Self-Reflection → 幻觉检测。
        不含：pre_pipeline / post_pipeline / SSE 事件发射。
        """
        from ai.run_control import RunAborted, run_registry
        from ai.otel_spans import span

        def _check():
            if should_cancel and should_cancel():
                raise RunAborted(session_id)
            run_registry.check(session_id)

        _check()
        agent = self._dispatch_agent(intent_result)
        context = self._build_context(user, intent_result, db, message)

        turn_span_cm = span(
            "agent.turn",
            trace_id=trace_id,
            attributes={"intent": intent_name, "agent": agent_name, "session_id": session_id},
        )
        turn_span_cm.__enter__()
        try:
            return await self._execute_agent_turn_body(
                message=message, user=user, session_id=session_id, db=db,
                tenant_id=tenant_id, user_id=user_id,
                intent_result=intent_result, intent_name=intent_name,
                agent_name=agent_name, slots=slots,
                should_cancel=should_cancel, trace_id=trace_id,
                resume_run_id=resume_run_id,
                agent=agent, context=context,
                _check=_check,
            )
        finally:
            try:
                turn_span_cm.__exit__(None, None, None)
            except Exception:
                pass

    async def _execute_agent_turn_body(
        self,
        *,
        message, user, session_id, db, tenant_id, user_id,
        intent_result, intent_name, agent_name, slots,
        should_cancel, trace_id, resume_run_id,
        agent, context, _check,
    ) -> dict:
        """_execute_agent_turn 的主体（便于 span finally 包裹）。"""
        from ai.run_control import RunAborted

        rag_results = []
        skill_used = None
        memory_context = ""
        draft_state = None
        tools_used = []
        run_meta = {}
        response = ""
        llm_result = {
            "content": "",
            "reasoning": "",
            "cache_hit": False,
            "provider": "mock",
            "degraded": False,
        }

        collaboration_result = None
        collaboration_triggered = False
        try:
            from ai.agents.registry import get_agent_mode
            if get_agent_mode() == "llm" and db is not None:
                from ai.agents.collaboration import (
                    CollaborationOrchestrator,
                    get_collaboration_orchestrator,
                )
                detected = CollaborationOrchestrator.detect_collaboration_need(
                    message, intent_name
                )
                if detected is not None:
                    _check()
                    collab = get_collaboration_orchestrator()
                    try:
                        from ai.tool_loop import ToolLoop
                        from ai.tools.registry import TOOL_REGISTRY
                        if collab._tool_loop is None:
                            collab._tool_loop = ToolLoop(
                                llm_client=self.llm,
                                tool_registry=TOOL_REGISTRY,
                                max_rounds=3,
                            )
                    except Exception as e:
                        logger.warning("协作 ToolLoop 注入失败: %s", e, exc_info=True)

                    ctx = {"db": db, "tenant_id": tenant_id, "user_id": user_id, "user": user}
                    mode = detected["mode"]
                    collab_agents = detected["agents"]
                    collab_strategy = detected.get("strategy", "merge")

                    if mode == "delegate":
                        collaboration_result = await collab.delegate(
                            task=message, sub_agents=collab_agents,
                            ctx=ctx, tenant_id=tenant_id,
                        )
                        response = collaboration_result.get("synthesized_response", "")
                    elif mode == "orchestrate":
                        collaboration_result = await collab.orchestrate(
                            task=message, pipeline=collab_agents,
                            ctx=ctx, tenant_id=tenant_id,
                        )
                        response = collaboration_result.get("final_response", "")
                    else:
                        collaboration_result = await collab.aggregate(
                            task=message, agent_names=collab_agents,
                            ctx=ctx, strategy=collab_strategy,
                            tenant_id=tenant_id,
                        )
                        response = collaboration_result.get("aggregated_response", "")

                    collaboration_triggered = True
                    for sub in (collaboration_result.get("sub_results", []) +
                                collaboration_result.get("independent_results", []) +
                                collaboration_result.get("stages", [])):
                        for t in sub.get("tools_used", []):
                            tools_used.append(t)
                    llm_result = {
                        "content": response,
                        "reasoning": "",
                        "cache_hit": False,
                        "provider": "openai",
                        "degraded": False,
                    }
                    agent_name = f"collab:{mode}"
        except RunAborted:
            raise
        except Exception:
            collaboration_triggered = False

        if not collaboration_triggered:
            _check()
            import asyncio as _asyncio

            async def _load_skill_ctx():
                if not db:
                    return None, None
                try:
                    from ai.skills.loader import skill_loader
                    sk = self._match_skill(intent_name)
                    if sk:
                        ctx = await _asyncio.to_thread(
                            skill_loader.load_skill_context, sk, tenant_id, db
                        )
                        return sk, ctx
                except Exception as e:
                    logger.debug("技能上下文加载失败: %s", e, exc_info=True)
                return None, None

            async def _load_rag():
                if intent_name in ("knowledge", "rag") and db:
                    try:
                        return await _asyncio.to_thread(
                            self.rag.retrieve, message, tenant_id, db, 5
                        )
                    except Exception as e:
                        logger.debug("RAG 检索失败: %s", e, exc_info=True)
                return []

            async def _load_memory():
                if db and user_id:
                    try:
                        mem_service = self._get_memory_service()
                        return await _asyncio.to_thread(
                            mem_service.build_context, user_id, tenant_id, message, db
                        )
                    except Exception as e:
                        logger.debug("记忆上下文构建失败: %s", e, exc_info=True)
                return ""

            _skill_tuple, rag_results, memory_context = await _asyncio.gather(
                _load_skill_ctx(), _load_rag(), _load_memory()
            )
            skill_used = _skill_tuple[0]
            skill_context = _skill_tuple[1]

            messages = self._build_llm_messages(
                message, intent_name, memory_context, context,
                skill_context=skill_context, rag_results=rag_results,
            )

            use_tool_loop = False
            try:
                from ai.agents.registry import get_agent_mode
                use_tool_loop = get_agent_mode() == "llm" and db is not None
            except Exception as e:
                logger.debug("Agent 模式检测失败: %s", e, exc_info=True)

            _check()
            if use_tool_loop:
                if skill_used:
                    is_workflow = False
                    _skill_meta = None
                    try:
                        from ai.skills.loader import skill_loader
                        _skill_meta = skill_loader.load_skill(skill_used)
                        _meta = (_skill_meta or {}).get("metadata", {}) or {}
                        _nested_meta = _meta.get("metadata", {}) or {}
                        is_workflow = bool(_meta.get("is_workflow") or _nested_meta.get("is_workflow"))
                    except Exception:
                        pass

                    try:
                        if is_workflow:
                            from ai.skills.executor import get_workflow_skill_executor
                            workflow_executor = get_workflow_skill_executor()
                            ctx = {"db": db, "tenant_id": tenant_id, "user_id": user_id}
                            skill_result = await workflow_executor.async_execute(
                                skill_name=skill_used,
                                message=message,
                                ctx=ctx,
                                tenant_id=tenant_id,
                                session_id=session_id,
                            )
                        else:
                            from ai.skills.executor import get_skill_executor
                            skill_executor = get_skill_executor()
                            ctx = {"db": db, "tenant_id": tenant_id, "user_id": user_id}
                            import asyncio
                            skill_result = await asyncio.to_thread(
                                skill_executor.execute,
                                skill_name=skill_used,
                                message=message,
                                ctx=ctx,
                                tenant_id=tenant_id,
                            )
                        if skill_result.get("success"):
                            response = skill_result.get("response", "")
                            tools_used = skill_result.get("tools_used", [])
                            draft_state = skill_result.get("draft_state")
                            llm_result = {
                                "content": response,
                                "reasoning": "",
                                "cache_hit": False,
                                "provider": "workflow" if is_workflow else "openai",
                                "degraded": False,
                            }
                        else:
                            raise Exception(skill_result.get("error", "Skill 执行失败"))
                    except RunAborted:
                        raise
                    except Exception:
                        response, tools_used, llm_result, run_meta = await self._run_tool_loop(
                            messages, agent, intent_name, tenant_id, db, user_id,
                            should_cancel=should_cancel,
                            session_id=session_id, agent_name=agent_name,
                            skill_name=skill_used, skill_meta=_skill_meta if skill_used else None,
                            is_workflow=False, trace_id=trace_id,
                            resume_run_id=resume_run_id,
                        )
                else:
                    try:
                        response, tools_used, llm_result, run_meta = await self._run_tool_loop(
                            messages, agent, intent_name, tenant_id, db, user_id,
                            should_cancel=should_cancel,
                            session_id=session_id, agent_name=agent_name,
                            skill_name=None, skill_meta=None,
                            is_workflow=False, trace_id=trace_id,
                            resume_run_id=resume_run_id,
                        )
                    except RunAborted:
                        raise
                    except Exception:
                        llm_result = await self.llm.async_chat(
                            messages=messages, intent=intent_name, tenant_id=tenant_id,
                            trace_id=trace_id,
                        )
                        response = llm_result.get("content", "")
            else:
                llm_result = await self.llm.async_chat(
                    messages=messages,
                    intent=intent_name,
                    tenant_id=tenant_id,
                    trace_id=trace_id,
                )
                response = llm_result.get("content", "")

        _check()
        reflection_count = 0
        reflection_triggered = False
        try:
            reflection = self._get_self_reflection()
            while reflection.should_retry(response, reflection_count):
                _check()
                reflection_count += 1
                reflection_triggered = True
                retry_prompt = reflection.build_retry_prompt(message, response, reflection_count)
                retry_messages = self._build_llm_messages(retry_prompt, intent_name, memory_context, context)
                retry_result = await self.llm.async_chat(
                    messages=retry_messages, intent=intent_name,
                    tenant_id=tenant_id, use_cache=False, trace_id=trace_id,
                )
                response = retry_result.get("content", response)
                if reflection_count >= 3:
                    break
        except RunAborted:
            raise
        except Exception as e:
            logger.debug("Self-Reflection 失败: %s", e, exc_info=True)

        _check()
        hallucination_check = None
        try:
            detector = self._get_hallucination_detector()
            ontology_data = self._build_ontology_data(context, slots)
            hallucination_check = detector.detect(response, context, ontology_data)
            if hallucination_check["recommendation"] == "refuse":
                response = "抱歉，我无法确认相关信息的准确性，建议您直接查询系统数据。"
                self._safe_publish("hallucination_rejected", {
                    "score": hallucination_check["score"],
                    "user_id": user_id,
                }, tenant_id, db)
            elif hallucination_check["recommendation"] == "review":
                response += "\n\n⚠️ 以上信息仅供参考，建议人工复核。"
        except Exception as e:
            logger.warning("幻觉检测失败: %s", e, exc_info=True)

        return {
            "response": response,
            "tools_used": tools_used,
            "llm_result": llm_result,
            "agent_name": agent_name,
            "agent": agent,
            "skill_used": skill_used,
            "rag_results": rag_results,
            "memory_context": memory_context,
            "context": context,
            "reflection_count": reflection_count,
            "reflection_triggered": reflection_triggered,
            "hallucination_check": hallucination_check,
            "collaboration_result": collaboration_result,
            "draft_state": draft_state,
            "run_id": (run_meta or {}).get("run_id") or (llm_result or {}).get("run_id"),
            "budget": (run_meta or {}).get("budget") or (llm_result or {}).get("budget"),
            "trace_id": trace_id,
        }

    async def chat(self, message: str, user: Any = None,
                   session_id: Optional[str] = None, db: Any = None,
                   intent: Optional[str] = None,
                   tenant_id: Optional[str] = None,
                   resume_run_id: Optional[str] = None) -> dict:
        """主入口 - 七步状态机

        Phase A：执行核与 stream_chat 共用 `_execute_agent_turn`。
        Phase B：resume_run_id 续跑 ToolLoop checkpoint。
        """
        from ai.run_control import RunAborted, run_registry

        start_time = time.monotonic()
        trace_id = str(uuid.uuid4())[:8]

        # 续跑：从 checkpoint 恢复 session / intent / trace
        if resume_run_id and db is not None:
            from ai.checkpoint_store import load_run
            _loaded = load_run(db, resume_run_id, tenant_id=tenant_id)
            if _loaded:
                session_id = session_id or _loaded.get("session_id")
                intent = intent or _loaded.get("intent")
                trace_id = _loaded.get("trace_id") or trace_id

        pre = await self._pre_pipeline(
            message, user, session_id, db,
            intent_override=intent, tenant_id_override=tenant_id,
        )
        if pre["early_return"]:
            return pre["early_return"]

        session_id = pre["session_id"]
        tenant_id = pre["tenant_id"]
        user_id = pre["user_id"]
        intent_result = pre["intent_result"]
        intent_name = pre["intent_name"]
        agent_name = pre["agent_name"]
        slots = pre["slots"]

        run_registry.begin(session_id)
        should_cancel = run_registry.cancel_callback(session_id)
        try:
            turn = await self._execute_agent_turn(
                message=message, user=user, session_id=session_id, db=db,
                tenant_id=tenant_id, user_id=user_id,
                intent_result=intent_result, intent_name=intent_name,
                agent_name=agent_name, slots=slots,
                should_cancel=should_cancel,
                trace_id=trace_id,
                resume_run_id=resume_run_id,
            )
        except RunAborted:
            return {
                "session_id": session_id,
                "response": "请求已取消。",
                "agent_used": agent_name,
                "actions_called": [],
                "references": [],
                "intent": intent_name,
                "slots": slots,
                "cache_hit": False,
                "aborted": True,
                "reasoning_chain": None,
                "hallucination_check": None,
                "trace_id": trace_id,
            }
        finally:
            run_registry.end(session_id)

        agent = turn["agent"]
        tools_used = turn["tools_used"]
        result = self._post_pipeline(
            message=message,
            response=turn["response"],
            intent_name=intent_name,
            agent_name=turn["agent_name"],
            slots=slots,
            tools_used=tools_used,
            rag_results=turn["rag_results"],
            llm_result=turn["llm_result"],
            skill_used=turn["skill_used"],
            reflection_count=turn["reflection_count"],
            reflection_triggered=turn["reflection_triggered"],
            hallucination_check=turn["hallucination_check"],
            user=user,
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            db=db,
            start_time=start_time,
            collaboration_result=turn["collaboration_result"],
            context=turn["context"],
            trace_id=trace_id,
        )
        if turn.get("draft_state") is not None:
            result["draft_state"] = turn["draft_state"]
        if turn.get("run_id"):
            result["run_id"] = turn["run_id"]
        if turn.get("budget"):
            result["budget"] = turn["budget"]
        result["actions_called"] = (
            [t["name"] for t in tools_used] if tools_used
            else (agent.get("tools", [])[:2] if isinstance(agent, dict) else [])
        )
        return result

    async def stream_chat(self, message: str, user: Any = None,
                          session_id: Optional[str] = None, db: Any = None,
                          intent: Optional[str] = None):
        """流式聊天生成器 - yield SSE 事件 dict

        Phase A：与 chat() 共用 `_execute_agent_turn`（Skill/ToolLoop/协作），
        再将结果以 thinking/skill/tools_used/content/done 事件推送。
        intent：工作流页程序化意图覆盖。
        """
        from ai.run_control import RunAborted, run_registry

        start_time = time.monotonic()
        trace_id = str(uuid.uuid4())[:8]

        # 若客户端已带 session_id，尽早注册以便 abort 竞态
        if session_id:
            run_registry.begin(session_id)

        pre = await self._pre_pipeline(
            message, user, session_id, db, intent_override=intent,
        )
        if pre["early_return"]:
            early = pre["early_return"]
            if early.get("safety_blocked") or pre["intent_name"] == "blocked":
                yield {"type": "error", "message": early.get("response", "请求被拦截")}
            elif early.get("cache_hit"):
                yield {"type": "content", "chunk": early.get("response", "")}
                yield {
                    "type": "done", "session_id": pre["session_id"], "cache_hit": True,
                    "skill_used": None, "reasoning_chain_id": None, "latency_ms": 0,
                }
            else:
                yield {"type": "error", "message": early.get("response", "请求被拦截")}
            run_registry.end(pre["session_id"])
            return

        session_id = pre["session_id"]
        tenant_id = pre["tenant_id"]
        user_id = pre["user_id"]
        intent_result = pre["intent_result"]
        intent_name = pre["intent_name"]
        agent_name = pre["agent_name"]
        slots = pre["slots"]

        run_registry.begin(session_id)
        should_cancel = run_registry.cancel_callback(session_id)

        yield {"type": "thinking", "message": "AI 正在思考..."}
        await asyncio.sleep(0.02)
        yield {"type": "intent", "intent": intent_name, "method": intent_result.get("method", "hybrid")}
        await asyncio.sleep(0.01)
        yield {"type": "routing", "agent": agent_name, "slots": slots}

        try:
            if run_registry.is_aborted(session_id):
                raise RunAborted(session_id)

            turn = await self._execute_agent_turn(
                message=message, user=user, session_id=session_id, db=db,
                tenant_id=tenant_id, user_id=user_id,
                intent_result=intent_result, intent_name=intent_name,
                agent_name=agent_name, slots=slots,
                should_cancel=should_cancel,
                trace_id=trace_id,
            )
        except RunAborted:
            yield {"type": "error", "message": "请求已取消", "aborted": True}
            yield {
                "type": "done", "session_id": session_id, "aborted": True,
                "intent": intent_name, "agent_used": agent_name, "latency_ms":
                int((time.monotonic() - start_time) * 1000),
                "trace_id": trace_id,
            }
            run_registry.end(session_id)
            return
        except Exception as e:
            logger.error("stream_chat 执行失败: %s", e, exc_info=True)
            yield {"type": "error", "message": str(e)}
            run_registry.end(session_id)
            return

        try:
            skill_used = turn["skill_used"]
            tools_used = turn["tools_used"]
            response_text = turn["response"] or ""
            llm_result = turn["llm_result"] or {}
            provider = llm_result.get("provider", "mock")
            draft_state = turn.get("draft_state")
            hallucination_check = turn["hallucination_check"]
            agent_name = turn["agent_name"]

            if skill_used:
                yield {"type": "skill", "name": skill_used, "status": "matched"}

            reasoning_text = llm_result.get("reasoning") or ""
            if reasoning_text:
                yield {"type": "reasoning", "chunk": reasoning_text}

            if tools_used:
                yield {
                    "type": "tools_used",
                    "items": [
                        {"name": t.get("name", t) if isinstance(t, dict) else str(t)}
                        for t in tools_used
                    ],
                }

            for line in _split_response(response_text):
                if run_registry.is_aborted(session_id):
                    yield {"type": "error", "message": "请求已取消", "aborted": True}
                    break
                yield {"type": "content", "chunk": line}
                await asyncio.sleep(0)

            post_result = self._post_pipeline(
                message=message, response=response_text, intent_name=intent_name,
                agent_name=agent_name, slots=slots, tools_used=tools_used,
                rag_results=turn["rag_results"],
                llm_result={
                    "cache_hit": llm_result.get("cache_hit", False),
                    "provider": provider,
                    "degraded": llm_result.get("degraded", False),
                    "reasoning": reasoning_text,
                },
                skill_used=skill_used,
                reflection_count=turn["reflection_count"],
                reflection_triggered=turn["reflection_triggered"],
                hallucination_check=hallucination_check,
                user=user, session_id=session_id, tenant_id=tenant_id,
                user_id=user_id, db=db, start_time=start_time,
                collaboration_result=turn["collaboration_result"],
                context=turn["context"],
                trace_id=trace_id,
            )

            suggestions = self._generate_suggestions(intent_name)
            if suggestions:
                yield {"type": "suggestions", "items": suggestions}

            _reasoning_chain = post_result.get("reasoning_chain") or {}
            done_evt = {
                "type": "done",
                "session_id": session_id,
                "intent": intent_name,
                "agent_used": agent_name,
                "cache_hit": llm_result.get("cache_hit", False),
                "latency_ms": post_result["latency_ms"],
                "skill_used": skill_used,
                "reasoning_chain_id": _reasoning_chain.get("chain_id"),
                "hallucination_check": hallucination_check,
                "provider": provider,
                "provenance": post_result.get("provenance"),
                "trace_id": post_result.get("trace_id"),
            }
            if draft_state is not None:
                done_evt["draft_state"] = draft_state
            if turn.get("run_id"):
                done_evt["run_id"] = turn["run_id"]
            if turn.get("budget"):
                done_evt["budget"] = turn["budget"]
            yield done_evt
        finally:
            run_registry.end(session_id)

    # ──────────────────────────────────────────────
    # B1：抽取公共 Pipeline（chat 与 stream_chat 共享）
    # ──────────────────────────────────────────────

    async def _pre_pipeline(self, message: str, user: Any,
                            session_id: Optional[str], db: Any,
                            intent_override: Optional[str] = None,
                            tenant_id_override: Optional[str] = None) -> dict:
        """B1：前置流程（Step 1-4.5）

        intent_override: 程序化调用时直接指定意图（如 "diagnose"/"attribute"），
        跳过自然语言分类器，确保编排器稳定进入对应 skill 分支。

        包含：guardrails → cache lookup → intent classify → slots → safety valves

        Returns:
            {
                session_id, tenant_id, user_id, user_role,
                intent_result, intent_name, agent_name, slots,
                early_return: Optional[dict]  # 非空表示需要直接返回（拦截/cache 命中）
            }
        """
        start_time = time.monotonic()
        session_id = session_id or str(uuid.uuid4())
        if tenant_id_override:
            tenant_id = tenant_id_override
        else:
            tenant_id = getattr(user, "tenant_id", "default") if user else "default"
        user_id = getattr(user, "id", user) if user else None
        user_role = self._get_user_role(user)

        # Step 1: Guardrails - 输入安全检查
        guardrail = self._guardrails(message)
        if not guardrail["passed"]:
            self.metrics.record_request("default", "Supervisor", 0, False, safety_valve_blocked=True)
            return {
                "session_id": session_id, "tenant_id": tenant_id,
                "user_id": user_id, "user_role": user_role,
                "intent_result": None, "intent_name": "blocked",
                "agent_name": "Supervisor", "slots": {},
                "early_return": self._error_response(session_id, guardrail["reason"]),
            }

        # Step 2: 语义缓存查询
        cached = self.llm.cache.lookup(message)
        if cached:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            self.metrics.record_request("default", "cache", latency_ms, True, cache_hit=True)
            return {
                "session_id": session_id, "tenant_id": tenant_id,
                "user_id": user_id, "user_role": user_role,
                "intent_result": None, "intent_name": "cached",
                "agent_name": "cache", "slots": {},
                "early_return": {
                    "session_id": session_id,
                    "response": cached["response"],
                    "agent_used": "cache",
                    "actions_called": [],
                    "references": [],
                    "intent": "cached",
                    "slots": {},
                    "cache_hit": True,
                    "cache_similarity": cached.get("cache_similarity", 1.0),
                    "reasoning_chain": None,
                    "hallucination_check": None,
                },
            }

        # Step 3: 意图分类（支持程序化 intent 覆盖）
        if intent_override:
            # 程序化调用：跳过自然语言分类器，按 INTENT_KEYWORDS / 特判表解析 domain
            intent_name = intent_override
            domain = "global"
            for _kws, iname, idomain in INTENT_KEYWORDS:
                if iname == intent_override:
                    domain = idomain
                    break
            _DECISION_INTENTS = (
                "diagnose", "attribute", "derive_paradigm",
                "evaluate", "suggest", "insight",
            )
            if intent_override in _DECISION_INTENTS:
                domain = "decision"
            intent_result = {
                "intent": intent_name,
                "domain": domain,
                "agent": DOMAIN_AGENT_MAP.get(domain, "Supervisor"),
                "matched_keyword": "override",
                "raw_message": message,
                "method": "override",
            }
        else:
            try:
                classifier = self._get_intent_classifier()
                import asyncio
                intent_result = await asyncio.to_thread(
                    classifier.classify,
                    message, db=db, user_id=user_id, tenant_id=tenant_id,
                )
            except Exception:
                intent_result = self._understand_intent(message)
                intent_result["method"] = "keyword_fallback"

        intent_name = intent_result.get("intent", "default")
        agent_name = intent_result.get("agent", "Supervisor")

        # Step 4: 槽位提取
        slots = self._extract_slots(message, intent_name)

        # Step 4.5: 安全护栏检查
        try:
            safety = self._get_safety_valves()
            action_desc = {"type": "query", "intent": intent_name}
            safety_result = safety.check(action_desc, {"message": message, "slots": slots}, user_role, intent_name)
            if not safety_result["passed"]:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                self.metrics.record_request(intent_name, agent_name, latency_ms, False, safety_valve_blocked=True)
                self._safe_publish("safety_valve_blocked", {
                    "violations": safety_result.get("violations", []),
                    "user_id": user_id,
                }, tenant_id, db)
                return {
                    "session_id": session_id, "tenant_id": tenant_id,
                    "user_id": user_id, "user_role": user_role,
                    "intent_result": intent_result, "intent_name": intent_name,
                    "agent_name": agent_name, "slots": slots,
                    "early_return": {
                        "session_id": session_id,
                        "response": f"抱歉，该操作被安全护栏拦截：{', '.join(safety_result.get('violations', []))}",
                        "agent_used": agent_name,
                        "actions_called": [],
                        "references": [],
                        "intent": intent_name,
                        "slots": slots,
                        "cache_hit": False,
                        "safety_blocked": True,
                    },
                }
        except Exception as e:
            logger.warning("安全护栏检查失败: %s", e, exc_info=True)

        return {
            "session_id": session_id, "tenant_id": tenant_id,
            "user_id": user_id, "user_role": user_role,
            "intent_result": intent_result, "intent_name": intent_name,
            "agent_name": agent_name, "slots": slots,
            "early_return": None,
        }

    def _post_pipeline(
        self,
        message: str,
        response: str,
        intent_name: str,
        agent_name: str,
        slots: dict,
        tools_used: list,
        rag_results: list,
        llm_result: dict,
        skill_used: Optional[str],
        reflection_count: int,
        reflection_triggered: bool,
        hallucination_check: Optional[dict],
        user: Any,
        session_id: str,
        tenant_id: str,
        user_id: Optional[int],
        db: Any,
        start_time: float,
        collaboration_result: Optional[dict] = None,
        context: Any = None,
        trace_id: Optional[str] = None,
    ) -> dict:
        """B1：后置流程（Step 6-7）

        包含：幻觉检测后处理 → 缓存写入 → 指标采集 → 记忆存储 → 推理链构建 → provenance/trace_id

        Returns:
            完整的 chat 响应字典（含 latency_ms / reasoning_chain / provenance / trace_id 等）
        """
        latency_ms = int((time.monotonic() - start_time) * 1000)

        # 写入缓存
        if not llm_result.get("cache_hit") and len(response.strip()) >= 10:
            self.llm.cache.write(message, response, intent_name)

        # 记录指标
        self.metrics.record_request(
            intent=intent_name,
            agent=agent_name,
            latency_ms=latency_ms,
            success=True,
            cache_hit=llm_result.get("cache_hit", False),
            reflection_triggered=reflection_triggered,
            hallucination_rejected=(hallucination_check or {}).get("recommendation") == "refuse",
            hallucination_review=(hallucination_check or {}).get("recommendation") == "review",
        )

        # 存储情景记忆
        if db and user_id:
            try:
                mem_service = self._get_memory_service()
                mem_service.store(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    content=f"用户: {message}\n助手: {response[:200]}",
                    memory_type="episodic",
                    session_id=session_id,
                    db=db,
                    importance=5,
                )
            except Exception as e:
                logger.warning("记忆存储失败: %s", e, exc_info=True)

        # 构建推理链
        reasoning_chain = None
        if db and user_id:
            try:
                chain_builder = self._get_reasoning_chain_builder()
                reasoning_chain = chain_builder.build(
                    query=message,
                    intent=intent_name,
                    agent=agent_name,
                    context=context if context is not None else self._build_context(user, {"intent": intent_name, "agent": agent_name}, db, message),
                    response=response,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    db=db,
                )
                # 更新幻觉分数和反思次数
                if hallucination_check:
                    chain_builder.update_hallucination_score(
                        reasoning_chain.get("chain_id"), tenant_id, db,
                        int(hallucination_check["score"] * 100),
                    )
                if reflection_count > 0 and reasoning_chain.get("chain_id"):
                    self._safe_publish("reflection_retried", {
                        "chain_id": reasoning_chain.get("chain_id"),
                        "rounds": reflection_count,
                        "user_id": user_id,
                    }, tenant_id, db)
            except Exception as e:
                logger.debug("推理链构建失败: %s", e, exc_info=True)

        # 发布反思事件
        if reflection_triggered:
            self.metrics._metrics["reflection_count"] = self.metrics._metrics.get("reflection_count", 0)

        # F2.5: provenance 与 trace_id（B11：优先用传入的 trace_id）
        _provenance = None
        _trace_id = trace_id
        try:
            from core.ai_output_schema import build_provenance, generate_trace_id
            from config import settings
            _provenance = build_provenance(
                model_version=settings.LLM_MODEL or "mock",
                rule_versions={"compliance": "v2.2"},
                run_id=reasoning_chain.get("chain_id") if reasoning_chain else None,
            )
            # B11：未传入 trace_id 时才生成新的
            if not _trace_id:
                _trace_id = generate_trace_id()
        except Exception as e:
            logger.debug("provenance 构建失败: %s", e, exc_info=True)

        return {
            "session_id": session_id,
            "response": response,
            "agent_used": agent_name,
            "tools_used": tools_used,
            "references": [
                {"title": r.get("title"), "source": r.get("source"), "score": r.get("score")}
                for r in rag_results
            ],
            "intent": intent_name,
            "slots": slots,
            "cache_hit": llm_result.get("cache_hit", False),
            "cache_similarity": llm_result.get("cache_similarity", 0.0),
            "provider": llm_result.get("provider", "mock"),
            "degraded": llm_result.get("degraded", False),
            "reasoning": llm_result.get("reasoning", ""),
            "skill_used": skill_used,
            "reasoning_chain": reasoning_chain,
            "hallucination_check": hallucination_check,
            "reflection_count": reflection_count,
            "latency_ms": latency_ms,
            "collaboration": collaboration_result,
            "provenance": _provenance,
            "trace_id": _trace_id,
        }

    def _error_response(self, session_id: str, reason: str) -> dict:
        return {
            "session_id": session_id,
            "response": f"抱歉，请求被拒绝：{reason}",
            "agent_used": "Supervisor",
            "actions_called": [],
            "references": [],
            "intent": "blocked",
            "slots": {},
            "cache_hit": False,
        }

    def _get_user_role(self, user: Any) -> Optional[str]:
        """从用户对象提取角色"""
        if not user:
            return None
        role = getattr(user, "role", None)
        if role:
            return role
        role_id = getattr(user, "role_id", None)
        if role_id:
            # 简单映射
            role_map = {1: "admin", 2: "sales_rep", 3: "regional_manager", 4: "sales_director"}
            return role_map.get(role_id, "sales_rep")
        return "sales_rep"

    # ──────────────────────────────────────────────
    # 七步状态机 - 各步实现
    # ──────────────────────────────────────────────

    def _guardrails(self, message: str) -> dict:
        """Step 1: 输入安全检查 - prompt 注入防御"""
        if not message or not message.strip():
            return {"passed": False, "reason": "消息为空"}
        if len(message) > 5000:
            return {"passed": False, "reason": "消息过长（超过 5000 字符）"}
        # 检测 prompt 注入
        injection_patterns = [
            r"ignore\s+(previous|above|all)\s+instructions",
            r"disregard\s+(previous|above|all)",
            r"你\s*是\s*(一个\s*)?DAN",
            r"忘记\s*(之前|以上|所有).*指令",
        ]
        for pattern in injection_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return {"passed": False, "reason": "检测到 prompt 注入尝试"}
        return {"passed": True}

    def _extract_slots(self, message: str, intent: str) -> dict:
        """Step 4: 槽位提取 - 从用户消息中提取实体与参数"""
        slots = {}
        SLOT_TEMPLATES = {
            "visit": ["doctor_name", "hospital_name", "date_range", "action"],
            "course": ["course_name", "category", "difficulty"],
            "kpi": ["metric_name", "time_period"],
            "knowledge": ["keyword", "category"],
            "feedback": ["doctor_name", "sentiment"],
            "coverage": ["zone", "hospital_level"],
        }

        # 通用提取：日期
        date_patterns = [
            (r"近?\s*(\d+)\s*天", "days"),
            (r"本周", "this_week"),
            (r"本月", "this_month"),
            (r"上(?:周|月)", "last_period"),
        ]
        for pattern, key in date_patterns:
            if re.search(pattern, message):
                slots["time_range"] = key
                m = re.search(pattern, message)
                if m and m.groups():
                    slots["days"] = int(m.group(1))
                break

        # 通用提取：动作
        if any(w in message for w in ["创建", "新增", "生成", "制定", "make", "create"]):
            slots["action"] = "create"
        elif any(w in message for w in ["查询", "查看", "看看", "了解", "list", "show"]):
            slots["action"] = "query"
        elif any(w in message for w in ["更新", "修改", "调整", "update", "edit"]):
            slots["action"] = "update"
        elif any(w in message for w in ["删除", "取消", "delete", "remove"]):
            slots["action"] = "delete"

        # 意图特定提取（Mock 模式下基于关键词推断）
        template = SLOT_TEMPLATES.get(intent, [])
        if "doctor_name" in template:
            # 尝试匹配"X医生""X教授""X主任"
            m = re.search(r"([\u4e00-\u9fff]{2,4})\s*(?:医生|教授|主任|院长|博士)", message)
            if m:
                slots["doctor_name"] = m.group(1)
        if "hospital_name" in template:
            m = re.search(r"([\u4e00-\u9fff]{2,10}(?:医院|卫生院|中心))", message)
            if m:
                slots["hospital_name"] = m.group(1)
        if "metric_name" in template:
            for metric in ["拜访达成率", "覆盖率", "满意度", "KPI", "ROI"]:
                if metric.lower() in message.lower():
                    slots["metric_name"] = metric
                    break

        return slots

    def _build_llm_messages(self, message: str, intent: str,
                            memory_context: str, context: dict,
                            skill_context: dict = None,
                            rag_results: list = None) -> list:
        """构建 LLM 消息列表（含 Skill 指令 + OAG 上下文 + RAG 检索结果）"""
        import json as _json

        system_parts = ["你是医药销售领域的 AI 助手。"]
        if memory_context:
            system_parts.append(f"\n记忆上下文：\n{memory_context}")
        if intent != "default":
            system_parts.append(f"\n当前意图：{intent}")

        # Skill 指令注入（L2 指令层）
        if skill_context:
            instructions = skill_context.get("instructions")
            if instructions:
                system_parts.append(f"\n激活的 Skill 指令：\n{instructions}")
            # OAG 上下文注入（L3 资源层：objects/links/actions）
            oag = skill_context.get("oag_context")
            if oag:
                system_parts.append(f"\nOAG 上下文：\n{_json.dumps(oag, ensure_ascii=False)}")

        # RAG 检索结果注入（knowledge/rag 意图）
        if rag_results:
            rag_text = "\n".join(
                f"[{i+1}] {r.get('title', '')}\n{r.get('content', '')[:200]}"
                for i, r in enumerate(rag_results)
            )
            system_parts.append(f"\n知识库检索结果：\n{rag_text}")

        return [
            {"role": "system", "content": "\n".join(system_parts)},
            {"role": "user", "content": message},
        ]

    def _build_ontology_data(self, context: dict, slots: dict) -> dict:
        """构建幻觉检测所需的本体数据 - 查询真实 Ontology 注册表

        根据当前意图推断相关实体域，从 ontology.objects/links 查询真实定义，
        供幻觉检测器的关系验证策略使用。
        """
        from ontology import OBJECTS, LINKS

        intent = context.get("intent", "default")

        # 意图 → 实体域映射
        intent_domain_map = {
            "visit": "sales", "coverage": "sales", "feedback": "sales",
            "scoring": "sales", "roi": "sales", "matrix": "sales",
            "course": "training", "exam": "training", "path": "training",
            "live": "training", "scene": "training",
            "knowledge": "system", "rag": "system",
            "task": "system", "approval": "system",
            "meeting": "system", "kol": "sales",
            "report": "system", "outsend": "system",
        }
        domain = intent_domain_map.get(intent, "sales")

        # 查询该域的所有 Object
        domain_objects = [obj for obj in OBJECTS if obj.get("domain") == domain]

        # 查询该域的 Link 关系（source 或 target 在该域 Object 集合中）
        domain_object_names = {obj["name"] for obj in domain_objects}
        domain_links = [
            link for link in LINKS
            if link.get("source_object") in domain_object_names
            or link.get("target_object") in domain_object_names
        ]

        # 汇聚真实业务数值指标，供幻觉检测器 _check_numerical 校验响应中声称的数值
        # （蓝图片段 2.3 / 幻觉数值锚点修复：此前遗漏 metrics 键导致数值维恒定 0.5）
        metrics = self._collect_reference_metrics(context, slots)

        return {
            "slots": slots,
            "intent": intent,
            "user_id": context.get("user_id"),
            "tenant_id": context.get("tenant_id"),
            "mock": False,  # 标记为真实数据
            "domain": domain,
            "objects": [obj["name"] for obj in domain_objects],
            "object_fields": {obj["name"]: obj.get("fields", []) for obj in domain_objects},
            "links": [
                {
                    "name": l.get("name"),
                    "source": l.get("source_object"),
                    "target": l.get("target_object"),
                    "cardinality": l.get("cardinality"),
                }
                for l in domain_links
            ],
            "metrics": metrics,
        }

    @staticmethod
    def _collect_reference_metrics(context: dict, slots: dict) -> dict:
        """从真实业务上下文/槽位汇聚数值型参考指标。

        供幻觉检测器 _check_numerical 使用：当响应声称"覆盖率 85%"时，
        若 metrics 中存在 coverage_rate=0.82，则可判定数值偏差。
        """
        NUMERIC_HINTS = ("rate", "count", "score", "value", "amount", "coverage",
                         "percent", "ratio", "total", "avg", "average", "sum",
                         "duration", "frequency", "times", "num", "number")
        metrics: dict = {}

        def _scan(src: dict, prefix: str = ""):
            if not isinstance(src, dict):
                return
            for k, v in src.items():
                if isinstance(v, bool):
                    continue
                if isinstance(v, (int, float)):
                    key = f"{prefix}{k}".lower()
                    if any(h in key for h in NUMERIC_HINTS) or isinstance(v, (int, float)) and prefix:
                        metrics[key] = float(v)
                elif isinstance(v, dict):
                    _scan(v, prefix=f"{prefix}{k}_")

        _scan(context)
        _scan(slots)
        return metrics

    def _safe_publish(self, event_type: str, payload: dict, tenant_id: str, db: Any):
        """安全发布事件（失败不影响主流程）"""
        try:
            bus = self._get_event_bus()
            bus.publish(event_type, payload, tenant_id=tenant_id, consistency="eventual", db=db)
        except Exception as e:
            logger.debug("事件发布失败: %s", e, exc_info=True)

    def _match_skill(self, intent: str) -> Optional[str]:
        """意图 → Skill 名称映射

        返回匹配的 Skill 名称（如 'visit-planner'），无匹配返回 None。
        覆盖全部 24 个意图，Skill 定义位于 backend/ai/skills/definitions/{name}/SKILL.md
        """
        return INTENT_SKILL_MAP.get(intent)

    # ──────────────────────────────────────────────
    # 五阶段实现
    # ──────────────────────────────────────────────

    def _understand_intent(self, message: str) -> dict:
        """阶段 1：意图理解 - 简单关键词匹配"""
        message_lower = message.lower()
        # N+5：优先识别 scenario-create 工作流意图
        # 当消息同时含"创建/新建/设计/生成/做一个/建一个"等动词与"场景"名词时，
        # 强制路由到 scenario-create（避免被 visit 的"拜访"关键词抢占）
        if re.search(r"(创建|新建|设计|生成|做一个|建一个|想做).{0,15}场景", message) or "场景创建" in message or "创建培训场景" in message:
            return {
                "intent": "scenario-create",
                "domain": "training",
                "agent": "TrainingAgent",
                "matched_keyword": "scenario-create-pattern",
                "raw_message": message,
            }
        for keywords, intent_name, domain in INTENT_KEYWORDS:
            for kw in keywords:
                if kw in message_lower:
                    return {
                        "intent": intent_name,
                        "domain": domain,
                        "agent": DOMAIN_AGENT_MAP.get(domain, "Supervisor"),
                        "matched_keyword": kw,
                        "raw_message": message,
                    }
        # 默认意图
        return {
            "intent": "default",
            "domain": "global",
            "agent": "Supervisor",
            "matched_keyword": None,
            "raw_message": message,
        }

    def _build_context(self, user: Any, intent: dict, db: Any = None, message: str = "") -> dict:
        """阶段 2：上下文构建"""
        return {
            "user": user,
            "intent": intent.get("intent", "default"),
            "agent": intent.get("agent", "Supervisor"),
            "tenant_id": getattr(user, "tenant_id", None) if user else None,
            "user_id": getattr(user, "id", None) if user else None,
            "role": getattr(user, "role", None) if user else None,
            "message": message,
            "mock": False,
        }

    def _dispatch_agent(self, intent: dict) -> dict:
        """阶段 3：Agent 派发 - 基于意图选择 Agent"""
        agent_name = intent["agent"]
        agent = get_agent(agent_name)
        if agent is None:
            # 降级到 Supervisor
            agent = get_agent("Supervisor")
        return agent.metadata() if agent else {"name": "Supervisor", "tools": []}

    def _safety_check(self, agent: dict, intent: dict) -> None:
        """[DEPRECATED] 已被 Step 4.5 的 safety_valves_engine.check() 替代

        保留此方法仅为向后兼容，新代码应使用 _get_safety_valves().check()。
        此方法不再被 chat() 或 stream_chat() 调用。
        """
        pass

    def _generate_response(self, message: str, agent: dict, context: dict) -> str:
        """[DEPRECATED] 已被 self.llm.chat() 替代

        保留此方法仅为向后兼容，新代码应使用 llm_client.chat()。
        此方法不再被 chat() 或 stream_chat() 调用。
        """
        intent_name = context.get("intent", "default")
        # 优先使用预设响应
        if intent_name in INTENT_RESPONSES:
            return INTENT_RESPONSES[intent_name]
        # 默认兜底响应
        return (
            f"我是 {agent.get('display_name', 'AI 助手')}，已收到您的消息：\n"
            f"\"{message}\"\n"
            "目前我已理解您的请求，但需要更多信息才能给出精确建议。"
            "您可以尝试询问关于拜访、KPI、课程、知识库等具体问题。"
        )

    # ──────────────────────────────────────────────
    # 辅助方法
    # ──────────────────────────────────────────────

    def list_available_agents(self) -> list[dict]:
        """列出所有可用的 Agent"""
        return list_agents()

    def _generate_suggestions(self, intent: str) -> list[dict]:
        """根据意图生成后续建议"""
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

    async def execute_action(self, name: str, input: dict, user: Any = None) -> dict:
        """执行一个 Action（Mock）"""
        return await execute_action(name, input, user)

    async def recommend_visit_plan(self, db, user: Any = None) -> dict:
        """AI 推荐拜访计划（基于真实数据）

        查询逻辑：
        1. 取用户分管的医生（CoverageAssignment）
        2. 反查近 30 天 VisitRecord，识别未拜访医生
        3. 查询近 30 天 VisitFeedback，识别负面反馈医生
        4. 按优先级排序：未拜访 > 负面反馈 > 例行跟进
        """
        from database import CoverageAssignment, VisitRecord, VisitFeedback, Hospital, Doctor, Product
        from datetime import datetime, timedelta

        tenant_id = getattr(user, "tenant_id", None) if user else None
        user_id = getattr(user, "id", None) if user else None

        if not tenant_id or not user_id or db is None:
            return {"recommendations": [], "total_suggested": 0, "coverage_gap": 0,
                    "ai_summary": "用户信息缺失，无法生成推荐"}

        month_ago = datetime.utcnow().date() - timedelta(days=30)

        # 1. 查询用户分管的医生
        coverages = db.query(CoverageAssignment).filter(
            CoverageAssignment.tenant_id == tenant_id,
            CoverageAssignment.is_deleted == 0,
            CoverageAssignment.user_id == user_id,
        ).all()

        # 2. 反查近 30 天拜访记录
        recent_visits = db.query(VisitRecord).filter(
            VisitRecord.tenant_id == tenant_id,
            VisitRecord.is_deleted == 0,
            VisitRecord.user_id == user_id,
            VisitRecord.visit_date >= month_ago,
        ).all()
        visited_doctor_ids = {v.doctor_id for v in recent_visits if v.doctor_id}

        recommendations = []
        for cov in coverages:
            doctor = db.query(Doctor).filter(Doctor.id == cov.doctor_id).first() if cov.doctor_id else None
            hospital = db.query(Hospital).filter(Hospital.id == cov.hospital_id).first() if cov.hospital_id else None
            product = db.query(Product).filter(Product.id == cov.product_id).first() if cov.product_id else None

            if not doctor:
                continue

            # 优先级判定
            if cov.doctor_id not in visited_doctor_ids:
                priority = "high"
                reason = "30 天未拜访，需重点跟进"
            else:
                recent_feedback = db.query(VisitFeedback).join(
                    VisitRecord, VisitRecord.id == VisitFeedback.record_id
                ).filter(
                    VisitRecord.user_id == user_id,
                    VisitRecord.doctor_id == cov.doctor_id,
                    VisitRecord.visit_date >= month_ago,
                ).order_by(VisitFeedback.created_at.desc()).first()

                if recent_feedback and recent_feedback.sentiment in ("negative", "neutral"):
                    priority = "high"
                    reason = f"上次反馈{recent_feedback.sentiment}，需修复关系"
                else:
                    priority = "medium"
                    reason = "例行跟进"

            recommendations.append({
                "hospital_id": cov.hospital_id,
                "hospital_name": hospital.name if hospital else "",
                "doctor_id": cov.doctor_id,
                "doctor_name": doctor.name if doctor else "",
                "product_id": cov.product_id,
                "product_name": product.name if product else "",
                "priority": priority,
                "reason": reason,
                "suggested_date": (datetime.utcnow().date() + timedelta(days=len(recommendations) + 1)).isoformat(),
                "visit_type": "学术拜访" if priority == "high" else "日常拜访",
            })

        # 按优先级排序
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda x: priority_order.get(x["priority"], 3))
        recommendations = recommendations[:10]

        high_count = sum(1 for r in recommendations if r["priority"] == "high")
        summary = f"本周建议拜访 {len(recommendations)} 位医生，其中 {high_count} 位需重点跟进（30天未拜访或反馈负面）。"

        return {
            "recommendations": recommendations,
            "total_suggested": len(recommendations),
            "coverage_gap": high_count,
            "ai_summary": summary,
        }

    async def recommend_learning_path(self, db, user: Any = None) -> dict:
        """AI 推荐学习路径（基于真实拜访数据）

        查询逻辑：
        1. 取近 30 天 VisitFeedback.objections 高频关键词
        2. 取近 30 天 VisitRecord.product_id 关联 Product.category
        3. 查询 Course 表匹配 category，排除已完成的课程
        4. 生成 ai_summary（基于真实异议关键词与薄弱点）
        """
        from services import profile_service

        tenant_id = getattr(user, "tenant_id", None) if user else None
        user_id = getattr(user, "id", None) if user else None

        if not tenant_id or not user_id:
            return {
                "recommendations": [],
                "total": 0,
                "ai_summary": "用户信息缺失，无法生成推荐。",
            }

        # 复用 profile_service.get_learning_needs 的查询逻辑
        learning_needs = profile_service.get_learning_needs(db, tenant_id, user_id)
        recommendations = learning_needs.get("recommendations", [])
        objections = learning_needs.get("objections", [])
        weaknesses = learning_needs.get("weaknesses", [])

        # 生成 ai_summary（基于真实数据）
        if recommendations:
            top_rec = recommendations[0]
            summary = f"根据您近 30 天的拜访数据，推荐学习「{top_rec.get('title', '相关课程')}」"
            if objections:
                top_obj = objections[0]
                summary += f"。客户反馈高频异议：「{top_obj.get('keyword', '')}」（{top_obj.get('count', 0)} 次）"
            if weaknesses:
                summary += f"。能力薄弱点：{weaknesses[0].get('dimension', '')}"
        else:
            summary = "暂无推荐课程，请保持拜访记录以获取个性化推荐。"

        return {
            "recommendations": recommendations,
            "total": len(recommendations),
            "objections": objections,
            "weaknesses": weaknesses,
            "ai_summary": summary,
        }

    async def generate_exam(self, topic: str = None, question_count: int = 5,
                            difficulty: str = "medium") -> dict:
        """AI 生成试卷 - LLM 驱动（mock 降级兜底）

        优先调用 LLM 生成题目，解析 JSON 失败或 provider=mock 时降级到预设题目。
        """
        # 构建系统提示
        system_prompt = (
            f'你是医药培训专家。请围绕"{topic or "产品知识"}"生成 {question_count} 道考试题。\n'
            f'难度：{difficulty}\n'
            '题型：单选(single)、多选(multiple)、判断(judge)、填空(fill)、简答(short) 混合\n'
            '输出纯 JSON 数组（不要 markdown code block），每题包含：\n'
            'question_type, content, options(含 key 和 text 的数组), answer(数组), explanation, difficulty, points'
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f'请生成 {question_count} 道关于「{topic or "产品知识"}」的考试题'},
        ]

        try:
            result = self.llm.chat(messages=messages, intent="exam", tenant_id="default")
            if result.get("provider") != "mock" and result.get("content"):
                json_str = self._extract_json(result["content"])
                if json_str:
                    import json
                    questions = json.loads(json_str)
                    if isinstance(questions, list) and len(questions) > 0:
                        return {
                            "topic": topic,
                            "difficulty": difficulty,
                            "question_count": len(questions),
                            "questions": questions,
                            "provider": result["provider"],
                        }
        except Exception as e:
            logger.debug("LLM 试卷生成失败: %s", e, exc_info=True)

        # 降级：使用预设题目
        return self._generate_mock_exam(topic, question_count, difficulty)

    def _generate_mock_exam(self, topic: str = None, question_count: int = 5,
                            difficulty: str = "medium") -> dict:
        """预设题目（降级兜底）"""
        questions = [
            {
                "question_type": "single",
                "content": f"关于{topic or '产品'}的核心适应症，以下正确的是？",
                "options": [
                    {"key": "A", "text": "高血压"},
                    {"key": "B", "text": "心绞痛"},
                    {"key": "C", "text": "心律失常"},
                    {"key": "D", "text": "心力衰竭"},
                ],
                "answer": ["A"],
                "explanation": "根据说明书，主要适应症为高血压。",
                "difficulty": difficulty,
                "points": 5,
            },
            {
                "question_type": "multiple",
                "content": f"以下属于{topic or '产品'}常见不良反应的有？",
                "options": [
                    {"key": "A", "text": "头痛"},
                    {"key": "B", "text": "水肿"},
                    {"key": "C", "text": "心动过速"},
                    {"key": "D", "text": "皮疹"},
                ],
                "answer": ["A", "B"],
                "explanation": "水肿与头痛是最常见的不良反应。",
                "difficulty": difficulty,
                "points": 10,
            },
            {
                "question_type": "judge",
                "content": f"{topic or '产品'}可与葡萄柚汁同服。",
                "options": [
                    {"key": "A", "text": "正确"},
                    {"key": "B", "text": "错误"},
                ],
                "answer": ["B"],
                "explanation": "葡萄柚汁会升高本品血药浓度，禁用。",
                "difficulty": difficulty,
                "points": 5,
            },
            {
                "question_type": "fill",
                "content": f"{topic or '本品'}的起始剂量为____mg。",
                "options": [],
                "answer": ["10"],
                "explanation": "推荐起始剂量 10mg 每日一次。",
                "difficulty": difficulty,
                "points": 8,
            },
            {
                "question_type": "short",
                "content": f"请简述{topic or '本品'}的作用机制。",
                "options": [],
                "answer": ["钙通道阻滞"],
                "explanation": "通过阻滞钙离子跨膜进入平滑肌细胞，扩张外周血管，降低血压。",
                "difficulty": difficulty,
                "points": 12,
            },
        ]
        if question_count and question_count < len(questions):
            questions = questions[:question_count]
        return {
            "topic": topic,
            "difficulty": difficulty,
            "question_count": len(questions),
            "questions": questions,
            "provider": "mock",
        }

    @staticmethod
    def _extract_json(text: str) -> str:
        """从 LLM 响应中提取 JSON 数组（兼容 markdown code block 包裹）"""
        if not text:
            return ""
        text = text.strip()
        # 尝试提取 ```json ... ``` 中的内容
        import re
        code_block = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if code_block:
            return code_block.group(1).strip()
        # 尝试直接找到 JSON 数组起始
        start = text.find('[')
        end = text.rfind(']')
        if start >= 0 and end > start:
            return text[start:end + 1]
        return ""

    async def practice_reply(self, scenario: Any, messages: list) -> str:
        """AI 演练回复 - LLM 驱动（mock 降级兜底）

        优先调用 LLM 以客户角色生成回复，provider=mock 或失败时降级到关键词匹配。
        """
        scenario_title = getattr(scenario, "title", "") if scenario else ""
        scenario_type = getattr(scenario, "scenario_type", "visit") if scenario else "visit"

        system_prompt = (
            f'你是医药销售演练中的客户角色。\n'
            f'场景：{scenario_title}\n'
            f'场景类型：{scenario_type}\n'
            '请以客户（医生/主任）视角回复销售代表的话术，保持专业但适度刁难，模拟真实拜访场景。\n'
            '回复控制在 2-3 句话，不要使用 markdown 格式。'
        )

        # 构建对话历史（角色翻转：销售代表=user → LLM 视角为 assistant）
        llm_messages = [{"role": "system", "content": system_prompt}]
        for m in (messages or [])[-6:]:
            role = "assistant" if m.get("role") == "user" else "user"
            llm_messages.append({"role": role, "content": m.get("content", "")})

        try:
            result = self.llm.chat(messages=llm_messages, intent="scene", tenant_id="default")
            if result.get("provider") != "mock" and result.get("content"):
                return result["content"].strip()
        except Exception as e:
            logger.debug("LLM 演练回复失败: %s", e, exc_info=True)

        # 降级：关键词匹配
        return self._mock_practice_reply(scenario, messages)

    @staticmethod
    def _mock_practice_reply(scenario: Any, messages: list) -> str:
        """关键词匹配回复（降级兜底）"""
        last_user_msg = ""
        for m in reversed(messages or []):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "")
                break
        scenario_type = getattr(scenario, "scenario_type", "visit") if scenario else "visit"

        if any(kw in last_user_msg for kw in ["你好", "您好", "主任", "医生", "辛苦", "打扰"]):
            return (
                "你好，请坐。我正好有几分钟时间，您今天来是为了什么产品？"
                "希望能简短一些，门诊还有几个病人。"
            )
        if any(kw in last_user_msg for kw in ["产品", "心血通", "介绍", "新品"]):
            return (
                "嗯，心血通我听说过一些。你们的产品和现在临床上常用的相比，"
                "优势在哪？我比较关注降压效果和安全性。"
            )
        if any(kw in last_user_msg for kw in ["数据", "临床", "研究", "文献", "试验"]):
            return (
                "临床数据倒是有点意思。不过我担心药物相互作用，"
                "我这里不少老年患者合并用药比较多。这方面安全性怎么样？"
            )
        if any(kw in last_user_msg for kw in ["安全", "副作用", "不良", "相互作用"]):
            return (
                "安全性数据我看可以接受。但是价格方面，你们的产品比我现在用的贵不少，"
                "性价比怎么体现？医院现在控费压力也不小。"
            )
        if any(kw in last_user_msg for kw in ["价格", "费用", "贵", "便宜", "性价比", "成本"]):
            if scenario_type == "objection":
                return (
                    "价格确实是主要顾虑。如果能证明在长期预后上的优势，"
                    "我可以考虑在部分患者中试用，但需要更具体的卫生经济学数据。"
                    "你能提供吗？"
                )
            return (
                "价格是个现实问题。我们科室目前正在做控费，"
                "如果有卫生经济学数据支持长期获益，会更有说服力。"
            )
        if any(kw in last_user_msg for kw in ["试用", "样品", "体验", "尝试"]):
            return (
                "试用可以，先在小范围合适患者中用几例看看。"
                "你下周三来一趟，我们科室有个小会，可以简单介绍一下。"
                "记得带上简明扼要的资料。"
            )
        if any(kw in last_user_msg for kw in ["谢谢", "感谢", "再见", "告辞", "下次"]):
            return (
                "好的，不客气。我期待下周的讨论，资料记得提前发我邮箱。"
                "再见。"
            )
        return (
            "嗯，我理解您的意思。不过作为临床医生，我最看重的还是循证证据和患者实际获益。"
            "您能针对我的关注点再具体说明一下吗？"
        )


__all__ = ["Orchestrator"]
