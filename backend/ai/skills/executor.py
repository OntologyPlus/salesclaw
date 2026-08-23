"""Skill 执行引擎

将 Skill 从"上下文注入"升级为"可执行单元"：
1. 加载 Skill instructions 作为 system prompt
2. 使用 Skill 的 allowed_tools 限制 ToolLoop 可用工具
3. 通过 ToolLoop 执行 Skill 步骤（LLM 调用工具完成任务）
4. 验证输出是否符合 Skill 的 output format

N+4 升级：支持 depends_on 递归执行（Skill 组合链）
- execute() 先递归执行依赖 Skill，再执行当前 Skill
- 依赖结果通过 _inject_dep_results 注入主 Skill 消息上下文
- 深度限制 MAX_SKILL_DEPENDENCY_DEPTH=5，防止无限递归
- _dep_cache 显式传递，避免实例状态污染

仅在 LLM_PROVIDER=openai 时激活，mock 模式下 Skill 仍仅做上下文注入。
"""
import json
import logging
import re
from typing import Any, Optional

from core.constants import MAX_SKILL_DEPENDENCY_DEPTH

logger = logging.getLogger(__name__)


class SkillExecutor:
    """Skill 执行引擎

    Usage:
        executor = SkillExecutor(llm_client=llm, tool_registry=TOOL_REGISTRY)
        result = executor.execute(
            skill_name="visit-planner",
            message="帮我生成本周拜访计划",
            ctx={"db": db, "tenant_id": tenant_id, "user_id": user_id},
        )
        # result = {skill_name, success, response, tools_used, steps_completed, output_valid}
    """

    def __init__(self, llm_client: Any, tool_registry: dict):
        self.llm = llm_client
        self.tools = tool_registry

    def execute(
        self,
        skill_name: str,
        message: str,
        ctx: dict,
        tenant_id: str = "default",
        _depth: int = 0,
        _dep_cache: Optional[dict] = None,
    ) -> dict:
        """执行 Skill（N+4 支持依赖链递归执行）

        Args:
            skill_name: Skill 名称（如 visit-planner）
            message: 用户消息
            ctx: 执行上下文 {db, tenant_id, user_id, ...}
            tenant_id: 租户 ID
            _depth: 内部递归深度（防止无限递归，> MAX_SKILL_DEPENDENCY_DEPTH 拒绝）
            _dep_cache: 内部依赖结果缓存（避免重复执行同一依赖 Skill）

        Returns:
            {
                skill_name: str,
                success: bool,
                response: str,
                tools_used: list,
                steps_completed: int,
                output_valid: bool,
                raw_output: str,
                error: str | None,
                deps: list,           # N+4 依赖 Skill 名称列表
                dep_results: dict,    # N+4 依赖结果
                depth: int,          # N+4 实际递归深度
            }
        """
        # 1. 防递归爆炸
        if _depth > MAX_SKILL_DEPENDENCY_DEPTH:
            return self._error_result(
                skill_name,
                f"Skill 依赖链过深（>{MAX_SKILL_DEPENDENCY_DEPTH}）",
            )

        # 2. 初始化依赖缓存
        if _dep_cache is None:
            _dep_cache = {}

        # 3. 加载 Skill
        try:
            from ai.skills.loader import skill_loader
            skill = skill_loader.load_skill(skill_name)
            if not skill:
                return self._error_result(skill_name, f"Skill '{skill_name}' 不存在")
        except Exception as e:
            return self._error_result(skill_name, f"加载 Skill 失败: {e}")

        metadata = skill.get("metadata", {})
        deps = metadata.get("depends_on", []) or []

        # 4. 递归执行依赖 Skill（结果缓存避免重复）
        dep_results: dict = {}
        for dep in deps:
            dep_name = dep.get("skill") or dep.get("name") if isinstance(dep, dict) else dep
            if not dep_name or dep_name in _dep_cache:
                if dep_name in _dep_cache:
                    dep_results[dep_name] = _dep_cache[dep_name]
                continue
            dep_result = self.execute(
                dep_name, message, ctx, tenant_id,
                _depth=_depth + 1, _dep_cache=_dep_cache,
            )
            _dep_cache[dep_name] = dep_result
            dep_results[dep_name] = dep_result

        # 5. 将依赖结果注入当前 Skill 消息上下文
        enriched_message = message
        if dep_results:
            enriched_message = self._inject_dep_results(message, dep_results)
            ctx = {**ctx, "dep_results": dep_results}

        # 6. 执行当前 Skill（原逻辑）
        result = self._execute_single(skill, skill_name, enriched_message, ctx, tenant_id)

        # 7. 追加依赖元信息
        result["deps"] = list(dep_results.keys())
        result["dep_results"] = dep_results
        result["depth"] = _depth

        # 8. 顶层发布 skill_chain_executed 事件（仅顶层，避免事件爆炸）
        if _depth == 0 and dep_results:
            try:
                from ai.event_bus import event_bus
                event_bus.publish(
                    "skill_chain_executed",
                    {
                        "root_skill": skill_name,
                        "deps": list(dep_results.keys()),
                        "depth": _depth,
                    },
                    tenant_id=tenant_id,
                    consistency="eventual",
                    affected_domains=["ai"],
                )
            except Exception as e:
                logger.debug(f"发布 skill_chain_executed 事件失败: {e}")

        return result

    def _execute_single(
        self,
        skill: dict,
        skill_name: str,
        message: str,
        ctx: dict,
        tenant_id: str = "default",
    ) -> dict:
        """执行单个 Skill（原 execute() 逻辑，不含依赖递归）"""
        instructions = skill.get("instructions", "")
        metadata = skill.get("metadata", {})
        allowed_tools = metadata.get("allowed_tools", [])

        if not instructions:
            return self._error_result(skill_name, "Skill 指令为空")

        # 构建 system prompt
        system_prompt = self._build_system_prompt(skill_name, instructions, allowed_tools)

        # 取 allowed_tools 与 TOOL_REGISTRY 交集
        available_tools = [t for t in allowed_tools if t in self.tools]
        if not available_tools:
            # 无可用工具时直接调用 LLM
            logger.info(f"Skill '{skill_name}' 无可用工具，直接调用 LLM")
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ]
                llm_result = self.llm.chat(messages=messages, intent=skill_name, tenant_id=tenant_id)
                response = llm_result.get("content", "")
                return {
                    "skill_name": skill_name,
                    "success": True,
                    "response": response,
                    "tools_used": [],
                    "steps_completed": 1,
                    "output_valid": self._validate_output(response),
                    "raw_output": response,
                    "error": None,
                }
            except Exception as e:
                return self._error_result(skill_name, f"LLM 调用失败: {e}")

        # 调用 ToolLoop 执行
        try:
            from ai.tool_loop import ToolLoop
            tool_loop = ToolLoop(
                llm_client=self.llm,
                tool_registry=self.tools,
                # N+5：max_rounds 限到 2，避免 LLM 反复 tool_call 引发多次串行 LLM 调用导致 timeout
                max_rounds=2,
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ]

            loop_result = tool_loop.run(
                messages=messages,
                available_tools=available_tools,
                ctx=ctx,
                intent=skill_name,
                tenant_id=tenant_id,
            )

            response = loop_result.get("response", "")
            tools_used = loop_result.get("tools_used", [])
            rounds = loop_result.get("rounds", 0)
            truncated = loop_result.get("truncated", False)

            # N+5：truncated 或 response 为空时，兜底用 LLM 总结工具结果
            if (not response) and tools_used:
                try:
                    import asyncio as _aio
                    import json as _json
                    from ai.llm_client import LLMClient
                    llm_client = self.llm if isinstance(self.llm, LLMClient) else self.llm
                    summary_msgs = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": (
                            "基于以下工具返回的数据，用简洁自然的中文给用户回答（不要列 JSON）。\n"
                            f"用户问题：{message}\n"
                            f"工具结果：{_json.dumps(tools_used, ensure_ascii=False, default=str)[:1500]}"
                        )},
                    ]
                    async def _summarize():
                        return await llm_client.async_chat(
                            messages=summary_msgs,
                            intent=skill_name,
                            tenant_id=tenant_id,
                            use_cache=False,
                        )
                    # SkillExecutor.execute() 是同步方法（在 to_thread 中跑），新建独立 loop 安全
                    fb = _aio.run(_summarize())
                    response = (fb.get("content", "") if fb else "") or response
                except Exception as e:
                    logger.debug("SkillExecutor 兜底总结失败: %s", e, exc_info=True)

            # 验证输出格式
            output_valid = self._validate_output(response)

            return {
                "skill_name": skill_name,
                "success": True,
                "response": response,
                "tools_used": tools_used,
                "steps_completed": rounds,
                "output_valid": output_valid,
                "raw_output": response,
                "truncated": truncated,
                "error": None,
            }

        except Exception as e:
            logger.exception(f"Skill '{skill_name}' 执行失败")
            return self._error_result(skill_name, f"执行失败: {e}")

    def _inject_dep_results(self, message: str, dep_results: dict) -> str:
        """N+4: 将依赖 Skill 输出注入主 Skill 的消息上下文

        Args:
            message: 原始用户消息
            dep_results: 依赖 Skill 执行结果 {skill_name: result_dict}

        Returns:
            注入依赖上下文后的增强消息
        """
        if not dep_results:
            return message
        context_str = json.dumps(
            {
                k: v.get("response", v) if isinstance(v, dict) else v
                for k, v in dep_results.items()
            },
            ensure_ascii=False,
            default=str,
        )
        return (
            f"{message}\n\n"
            f"[依赖 Skill 输出上下文]\n"
            f"{context_str}\n"
            f"请基于以上依赖 Skill 的输出结果继续执行当前 Skill。"
        )

    def _build_system_prompt(
        self, skill_name: str, instructions: str, allowed_tools: list
    ) -> str:
        """构建 system prompt"""
        tools_desc = ", ".join(allowed_tools) if allowed_tools else "无"
        return (
            f"你正在执行 Skill: {skill_name}\n\n"
            f"{instructions}\n\n"
            f"可用工具: {tools_desc}\n\n"
            "执行要求:\n"
            "1. 按照执行步骤逐步完成任务\n"
            "2. 需要数据时调用工具获取\n"
            "3. 最终输出必须符合输出格式要求\n"
            "4. 如果输出格式是 JSON，确保输出有效的 JSON\n"
        )

    def _validate_output(self, response: str) -> bool:
        """验证输出是否为有效 JSON（如果输出包含 JSON）"""
        if not response:
            return False
        # 尝试提取 JSON 块
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
        if json_match:
            try:
                json.loads(json_match.group(1))
                return True
            except json.JSONDecodeError:
                pass
        # 尝试直接解析
        try:
            json.loads(response.strip())
            return True
        except (json.JSONDecodeError, ValueError):
            pass
        # 尝试提取裸 JSON
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                json.loads(json_match.group())
                return True
            except json.JSONDecodeError:
                pass
        # 非 JSON 输出也算有效（文本响应）
        return len(response.strip()) > 0

    def _error_result(self, skill_name: str, error: str) -> dict:
        """构建错误返回"""
        return {
            "skill_name": skill_name,
            "success": False,
            "response": "",
            "tools_used": [],
            "steps_completed": 0,
            "output_valid": False,
            "raw_output": "",
            "error": error,
        }


# 全局单例（延迟初始化）
_skill_executor: Optional[SkillExecutor] = None


def get_skill_executor() -> SkillExecutor:
    """获取 SkillExecutor 全局单例"""
    global _skill_executor
    if _skill_executor is None:
        from ai.llm_client import llm_client
        from ai.tools.registry import TOOL_REGISTRY
        _skill_executor = SkillExecutor(llm_client, TOOL_REGISTRY)
    return _skill_executor


class WorkflowSkillExecutor(SkillExecutor):
    """工作流型 Skill 执行器（多轮门禁驱动）

    与 SkillExecutor 的区别：
    - 跨多轮对话维护 draft 状态（通过 SceneWorkspace + EpisodicMemory 持久化）
    - 每轮根据 draft.current_step 决定推进的 Step
    - system_prompt 注入当前 Step 指令 + draft 上下文 + 门禁规则
    - ToolLoop max_rounds 提升到 8（容纳多原语调用）
    - 返回结构包含 draft_state 和 next_step_hint
    """

    MAX_WORKFLOW_ROUNDS = 8

    def execute(
        self,
        skill_name: str,
        message: str,
        ctx: dict,
        tenant_id: str = "default",
        session_id: str = None,
    ) -> dict:
        """执行工作流型 Skill（单轮对话内推进当前 Step）

        Args:
            session_id: 会话 ID（必须，用于加载/保存 draft）
        """
        if not session_id:
            return self._error_result(skill_name, "工作流 Skill 缺少 session_id")

        db = ctx.get("db")
        user_id = ctx.get("user_id")
        if not db or not user_id:
            return self._error_result(skill_name, "工作流 Skill 缺少 db/user_id")

        # 1. 加载 Skill
        try:
            from ai.skills.loader import skill_loader
            skill = skill_loader.load_skill(skill_name)
            if not skill:
                return self._error_result(skill_name, f"Skill '{skill_name}' 不存在")
        except Exception as e:
            return self._error_result(skill_name, f"加载 Skill 失败: {e}")

        metadata = skill.get("metadata", {})
        # SKILL.md frontmatter 中 is_workflow/steps/gates/allowed_tools 等字段
        # 在 frontmatter 顶层；但 is_workflow/steps/gates 嵌套在 metadata: 子段下。
        # 此处兼容两种写法：优先读嵌套 metadata，回退到顶层。
        nested_meta = metadata.get("metadata", {}) if isinstance(metadata.get("metadata"), dict) else {}
        if not metadata.get("is_workflow"):
            is_workflow_flag = bool(nested_meta.get("is_workflow"))
        else:
            is_workflow_flag = bool(metadata.get("is_workflow"))

        if not is_workflow_flag:
            # 不是工作流 Skill，降级到父类
            return super().execute(skill_name, message, ctx, tenant_id)

        instructions = skill.get("instructions", "")
        # steps/gates/allowed_tools 在 frontmatter 顶层
        steps = metadata.get("steps") or nested_meta.get("steps", [])
        gates = metadata.get("gates") or nested_meta.get("gates", [])

        # 2. 加载草稿
        from ai.skills.scene_workspace import scene_workspace
        draft = scene_workspace.load(session_id, db, tenant_id, user_id)

        # 3. 构建 system_prompt（含当前 Step 指令 + draft 状态 + 门禁规则）
        system_prompt = self._build_workflow_system_prompt(
            skill_name, instructions, steps, gates, draft, message,
        )

        # 4. 取 allowed_tools 与 TOOL_REGISTRY 交集
        allowed_tools = metadata.get("allowed_tools", [])
        available_tools = [t for t in allowed_tools if t in self.tools]
        if not available_tools:
            return self._error_result(skill_name, "工作流 Skill 无可用工具")

        # 5. 调用 ToolLoop（max_rounds=8 容纳多原语）
        from ai.tool_loop import ToolLoop
        tool_loop = ToolLoop(
            llm_client=self.llm,
            tool_registry=self.tools,
            max_rounds=self.MAX_WORKFLOW_ROUNDS,
        )

        # 注入 session_id 到 ctx（工具函数依赖）
        workflow_ctx = {**ctx, "session_id": session_id}

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ]

        try:
            loop_result = tool_loop.run(
                messages=messages,
                available_tools=available_tools,
                ctx=workflow_ctx,
                intent=skill_name,
                tenant_id=tenant_id,
            )
        except Exception as e:
            logger.exception(f"WorkflowSkill '{skill_name}' 执行失败")
            return self._error_result(skill_name, f"工作流执行失败: {e}")

        response = loop_result.get("response", "")
        tools_used = loop_result.get("tools_used", [])

        # 6. 重新加载 draft（工具可能修改了状态）
        draft = scene_workspace.load(session_id, db, tenant_id, user_id)

        # 7. 返回工作流结果（含 draft_state 供前端展示进度）
        return {
            "skill_name": skill_name,
            "success": True,
            "response": response,
            "tools_used": tools_used,
            "steps_completed": loop_result.get("rounds", 0),
            "output_valid": self._validate_output(response),
            "raw_output": response,
            "truncated": loop_result.get("truncated", False),
            "error": None,
            "draft_state": {
                "current_step": draft.current_step,
                "gates_passed": list(draft.gates_passed),
                "scenario_id": draft.scenario_id,
            },
            "next_step_hint": draft.current_step if draft.current_step != "done" else "done",
        }

    async def async_execute(
        self,
        skill_name: str,
        message: str,
        ctx: dict,
        tenant_id: str = "default",
        session_id: str = None,
    ) -> dict:
        """N+5 阻塞治理：异步执行工作流 Skill

        逻辑与 execute() 相同，但 ToolLoop 用 run_async() 替代 run()，
        避免在 asyncio.to_thread 中占用线程 8 轮。
        """
        if not session_id:
            return self._error_result(skill_name, "工作流 Skill 缺少 session_id")

        db = ctx.get("db")
        user_id = ctx.get("user_id")
        if not db or not user_id:
            return self._error_result(skill_name, "工作流 Skill 缺少 db/user_id")

        # 1. 加载 Skill
        try:
            from ai.skills.loader import skill_loader
            skill = skill_loader.load_skill(skill_name)
            if not skill:
                return self._error_result(skill_name, f"Skill '{skill_name}' 不存在")
        except Exception as e:
            return self._error_result(skill_name, f"加载 Skill 失败: {e}")

        metadata = skill.get("metadata", {})
        # 兼容 SKILL.md frontmatter 嵌套写法
        nested_meta = metadata.get("metadata", {}) if isinstance(metadata.get("metadata"), dict) else {}
        is_workflow_flag = bool(metadata.get("is_workflow") or nested_meta.get("is_workflow"))
        if not is_workflow_flag:
            # 非工作流 Skill：丢到线程池调父类 execute
            import asyncio
            return await asyncio.to_thread(
                super().execute, skill_name, message, ctx, tenant_id,
            )

        instructions = skill.get("instructions", "")
        steps = metadata.get("steps") or nested_meta.get("steps", [])
        gates = metadata.get("gates") or nested_meta.get("gates", [])

        # 2. 加载草稿
        from ai.skills.scene_workspace import scene_workspace
        draft = scene_workspace.load(session_id, db, tenant_id, user_id)

        # 3. 构建 system_prompt
        system_prompt = self._build_workflow_system_prompt(
            skill_name, instructions, steps, gates, draft, message,
        )

        # 4. 取 allowed_tools 与 TOOL_REGISTRY 交集
        allowed_tools = metadata.get("allowed_tools", [])
        available_tools = [t for t in allowed_tools if t in self.tools]
        if not available_tools:
            return self._error_result(skill_name, "工作流 Skill 无可用工具")

        # 5. 异步调用 ToolLoop
        from ai.tool_loop import ToolLoop
        tool_loop = ToolLoop(
            llm_client=self.llm,
            tool_registry=self.tools,
            max_rounds=self.MAX_WORKFLOW_ROUNDS,
        )

        workflow_ctx = {**ctx, "session_id": session_id}

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ]

        try:
            loop_result = await tool_loop.run_async(
                messages=messages,
                available_tools=available_tools,
                ctx=workflow_ctx,
                intent=skill_name,
                tenant_id=tenant_id,
            )
        except Exception as e:
            logger.exception(f"WorkflowSkill '{skill_name}' async 执行失败")
            return self._error_result(skill_name, f"工作流 async 执行失败: {e}")

        response = loop_result.get("response", "")
        tools_used = loop_result.get("tools_used", [])

        # 6. 重新加载 draft
        draft = scene_workspace.load(session_id, db, tenant_id, user_id)

        # 7. 返回工作流结果
        return {
            "skill_name": skill_name,
            "success": True,
            "response": response,
            "tools_used": tools_used,
            "steps_completed": loop_result.get("rounds", 0),
            "output_valid": self._validate_output(response),
            "raw_output": response,
            "truncated": loop_result.get("truncated", False),
            "error": None,
            "draft_state": {
                "current_step": draft.current_step,
                "gates_passed": list(draft.gates_passed),
                "scenario_id": draft.scenario_id,
            },
            "next_step_hint": draft.current_step if draft.current_step != "done" else "done",
        }

    def _build_workflow_system_prompt(
        self, skill_name: str, instructions: str, steps: list, gates: list, draft, message: str,
    ) -> str:
        """构建工作流 system prompt（含当前 Step 指令 + draft 摘要 + 门禁规则）"""
        import json as _json

        current_step_name = draft.current_step
        current_step_def = next((s for s in steps if s.get("name") == current_step_name), None)
        step_instruction = ""
        if current_step_def:
            step_instruction = (
                f"当前 Step：{current_step_def.get('name')} - {current_step_def.get('description', '')}\n"
                f"关联门禁：{current_step_def.get('gates', [])}\n"
                f"可用原语：{current_step_def.get('primitives', [])}\n"
                f"用户可见输出：{current_step_def.get('user_visible', '')}\n"
            )

        # draft 摘要（不含 contextPayload 内容，保密红线）
        draft_summary = {
            "current_step": draft.current_step,
            "gates_passed": list(draft.gates_passed),
            "config_ready": bool(draft.config),
            "collection_ready": bool(draft.collection),
            "title_bg_ready": bool(draft.title_bg),
            "knowledge_finalized": bool((draft.knowledge or {}).get("finalized")),
            "context_payload_ready": bool((draft.context_payload or {}).get("ready")),
            "submit_confirmed": draft.submit_confirmed,
            "scenario_id": draft.scenario_id,
        }

        gates_summary = "\n".join(
            f"- {g.get('name')}: {g.get('description')} (check: {g.get('check_field')})"
            for g in gates
        )

        return (
            f"你正在执行工作流型 Skill: {skill_name}\n\n"
            f"{instructions}\n\n"
            f"━━━ 当前工作流状态 ━━━\n"
            f"{step_instruction}\n"
            f"已通过门禁：{draft.gates_passed}\n"
            f"Draft 摘要：{_json.dumps(draft_summary, ensure_ascii=False)}\n\n"
            f"━━━ 门禁清单 ━━━\n{gates_summary}\n\n"
            f"━━━ 执行要求 ━━━\n"
            "1. 必须按当前 Step 的 primitives 顺序调用工具\n"
            "2. 每完成一道门禁，必须调用 validate_scene_gate(gate=Gx) 确认\n"
            "3. 禁止跳过任何门禁\n"
            "4. create_scene_record 失败时禁止自动重试，告知用户失败原因\n"
            "5. Step1 同一轮除环境准备提示外不输出业务内容\n"
            "6. 不向用户暴露 contextPayload 键名或内部 ID\n"
            "7. 输出最终为自然语言回复（中文），不要求 JSON\n"
        )


# WorkflowSkillExecutor 全局单例
_workflow_skill_executor: Optional[WorkflowSkillExecutor] = None


def get_workflow_skill_executor() -> WorkflowSkillExecutor:
    """获取 WorkflowSkillExecutor 全局单例"""
    global _workflow_skill_executor
    if _workflow_skill_executor is None:
        from ai.llm_client import llm_client
        from ai.tools.registry import TOOL_REGISTRY
        _workflow_skill_executor = WorkflowSkillExecutor(llm_client, TOOL_REGISTRY)
    return _workflow_skill_executor
