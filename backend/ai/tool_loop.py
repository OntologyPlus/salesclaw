"""工具调用循环引擎

LLM 迭代调用工具，最多 N 轮：
  1. 将可用工具描述注入 system prompt
  2. 调用 LLM
  3. 解析响应中的 JSON 工具调用（prompt-based，兼容 mock/openai）
  4. 执行工具 → 回填结果 → 再调用 LLM
  5. 终止条件：LLM 不再请求工具 / 达到 max_rounds / 工具执行失败

工具调用格式（LLM 输出）：
  ```tool
  {"tool": "query_visit_records", "args": {"user_id": 1, "period": "2026-07"}}
  ```

当 LLM 不需要工具时，直接输出自然语言回答。
"""
import json
import re
import logging
from typing import Any, Callable, Optional

from core.exceptions import AppException

logger = logging.getLogger(__name__)


class ToolLoop:
    """工具调用循环引擎

    通过 prompt-based 方式让 LLM 调用工具，不依赖原生 function calling，
    兼容 mock 和 openai 两种 provider。
    """

    def __init__(
        self,
        llm_client,
        tool_registry: dict,
        max_rounds: int = 5,
    ):
        """
        Args:
            llm_client: LLMClient 实例
            tool_registry: {tool_name: callable(args: dict, ctx: dict) -> dict}
            max_rounds: 最大工具调用轮次
        """
        self.llm = llm_client
        self.tools = tool_registry
        self.max_rounds = max_rounds
        # B4：运行期状态字段（用于 snapshot）
        self._current_round: int = 0
        self._working_messages: list = []
        self._tools_used_cache: list = []
        self._last_content: str = ""

    # ──────────────────────────────────────────────
    # B4：状态快照
    # ──────────────────────────────────────────────
    def snapshot(self) -> dict:
        """B4 / Phase B：返回当前 ToolLoop 运行状态快照（含 messages 供续跑）。"""
        return {
            "round": self._current_round,
            "max_rounds": self.max_rounds,
            "tools_used": list(self._tools_used_cache),
            "messages": list(self._working_messages),
            "working_messages_count": len(self._working_messages),
            "last_content": (self._last_content or "")[:200],
        }

    def _reset_state(self) -> None:
        """B4：每次 run/run_async 开始时重置状态"""
        self._current_round = 0
        self._working_messages = []
        self._tools_used_cache = []
        self._last_content = ""

    def _aborted_result(
        self, tools_used: list, last_content: str, round_num: int
    ) -> dict:
        """Phase A：协作取消时的统一返回结构。"""
        self._tools_used_cache = tools_used
        return {
            "response": last_content or "",
            "tools_used": tools_used,
            "rounds": max(round_num, 0),
            "truncated": True,
            "aborted": True,
        }

    @staticmethod
    def _should_stop(should_cancel: Optional[Callable[[], bool]]) -> bool:
        if should_cancel is None:
            return False
        try:
            return bool(should_cancel())
        except Exception:
            return False

    @staticmethod
    def _span(name: str, ctx: Optional[dict] = None, **attrs):
        """Phase B：OTEL span 上下文（失败时退化为 nullcontext）。"""
        from contextlib import nullcontext
        try:
            from ai.otel_spans import span
            ctx = ctx or {}
            attributes = {"run_id": ctx.get("run_id"), **attrs}
            return span(name, trace_id=ctx.get("trace_id"), attributes=attributes)
        except Exception:
            return nullcontext()

    def run(
        self,
        messages: list,
        available_tools: Optional[list] = None,
        ctx: Optional[dict] = None,
        intent: str = "",
        tenant_id: str = "default",
        on_round_end: Optional[Callable[[int, dict], None]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
        resume_state: Optional[dict] = None,
        budget_deadline: Optional[float] = None,
    ) -> dict:
        """执行工具调用循环

        Args:
            messages: 初始消息列表（含 system + user）
            available_tools: 允许使用的工具名列表，None 表示使用全部注册工具
            ctx: 工具执行上下文 {db, tenant_id, user_id, ...}
            intent: 意图标签（用于缓存）
            tenant_id: 租户 ID
            on_round_end: B4 可选回调，每轮工具执行后调用 (round_num, snapshot_dict)
            resume_state: Phase B 续跑状态 {messages, tools_used, round}
            budget_deadline: time.monotonic() 截止时间，超时 truncated

        Returns:
            {
                response: str,          # 最终自然语言回答
                tools_used: list,       # [{name, args, result}]
                rounds: int,            # 实际执行轮次
                truncated: bool,        # 是否因达到 max_rounds 截断
            }
        """
        import time
        ctx = ctx or {}
        tools_used: list = []
        self._reset_state()

        # 确定可用工具集
        if available_tools is None:
            available_tools = list(self.tools.keys())

        start_round = 0
        if resume_state and resume_state.get("messages"):
            working_messages = list(resume_state["messages"])
            tools_used = list(resume_state.get("tools_used") or [])
            start_round = int(resume_state.get("round") or 0)
            last_content = resume_state.get("last_content") or ""
        else:
            tool_desc = self._build_tool_description(available_tools)
            working_messages = self._inject_tool_prompt(messages, tool_desc)
            last_content = ""
        self._working_messages = working_messages
        self._tools_used_cache = tools_used

        for round_num in range(start_round, self.max_rounds):
            if self._should_stop(should_cancel):
                return self._aborted_result(tools_used, last_content, round_num)
            if budget_deadline is not None and time.monotonic() >= budget_deadline:
                self._tools_used_cache = tools_used
                return {
                    "response": last_content,
                    "tools_used": tools_used,
                    "rounds": round_num,
                    "truncated": True,
                    "budget_exceeded": True,
                }
            self._current_round = round_num + 1
            # 调用 LLM（非流式，工具循环内部不需要流式）
            with self._span("tool_loop.llm", ctx, round=self._current_round):
                llm_result = self.llm.chat(
                    messages=working_messages,
                    intent=intent,
                    use_cache=False,  # 工具循环不缓存（中间状态无意义）
                    tenant_id=tenant_id,
                    trace_id=ctx.get("trace_id"),
                )
            content = llm_result.get("content", "")
            last_content = content
            self._last_content = content

            # 解析工具调用
            tool_call = self._parse_tool_call(content)
            if tool_call is None:
                # 没有工具调用 → 最终回答
                self._tools_used_cache = tools_used
                if on_round_end:
                    try:
                        on_round_end(self._current_round, self.snapshot())
                    except Exception as cb_err:
                        logger.debug("on_round_end 回调异常: %s", cb_err)
                return {
                    "response": content,
                    "tools_used": tools_used,
                    "rounds": round_num + 1,
                    "truncated": False,
                }

            tool_name = tool_call.get("tool", "")
            tool_args = tool_call.get("args", {}) or {}

            # 工具不存在
            if tool_name not in self.tools:
                working_messages.append({"role": "assistant", "content": content})
                working_messages.append({
                    "role": "user",
                    "content": f"工具「{tool_name}」不存在。可用工具：{', '.join(available_tools)}。请直接回答或使用可用工具。",
                })
                continue

            # 执行工具（Phase B：写工具经 Action Gateway）
            try:
                with self._span("tool_loop.tool", ctx, tool=tool_name, round=self._current_round):
                    tool_result = self._execute_tool(tool_name, tool_args, ctx)
                tools_used.append({
                    "name": tool_name,
                    "args": tool_args,
                    "result": tool_result,
                })
                logger.info(
                    "tool_loop: round=%d tool=%s success",
                    round_num + 1, tool_name,
                )
            except Exception as exc:
                tool_result = {"error": str(exc)}
                tools_used.append({
                    "name": tool_name,
                    "args": tool_args,
                    "error": str(exc),
                })
                logger.warning(
                    "tool_loop: round=%d tool=%s failed: %s",
                    round_num + 1, tool_name, exc,
                )

            # 回填工具结果，让 LLM 基于结果继续
            working_messages.append({"role": "assistant", "content": content})
            result_str = json.dumps(tool_result, ensure_ascii=False, default=str)
            # 截断过长的结果
            if len(result_str) > 2000:
                result_str = result_str[:2000] + "...(已截断)"
            working_messages.append({
                "role": "user",
                "content": f"工具「{tool_name}」执行结果：\n{result_str}\n\n请基于以上结果继续回答用户问题，或调用下一个工具。若已有足够信息，请直接给出最终回答（不要再使用工具）。",
            })
            self._working_messages = working_messages
            self._tools_used_cache = tools_used

            # B4：每轮结束回调
            if on_round_end:
                try:
                    on_round_end(self._current_round, self.snapshot())
                except Exception as cb_err:
                    logger.debug("on_round_end 回调异常: %s", cb_err)

        # 达到最大轮次
        return {
            "response": last_content,
            "tools_used": tools_used,
            "rounds": self.max_rounds,
            "truncated": True,
        }

    async def run_async(
        self,
        messages: list,
        available_tools: Optional[list] = None,
        ctx: Optional[dict] = None,
        intent: str = "",
        tenant_id: str = "default",
        on_round_end: Optional[Callable[[int, dict], None]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
        resume_state: Optional[dict] = None,
        budget_deadline: Optional[float] = None,
    ) -> dict:
        """N+5 阻塞治理：异步版本 - 用 await llm.async_chat 释放事件循环

        逻辑与 run() 完全相同，仅 LLM 调用改为 async_chat。
        WorkflowSkillExecutor.async_execute() 使用此方法，避免 8 轮 LLM 调用占用线程。
        B4：与 run() 同步增加状态快照与 on_round_end 回调。
        """
        import time
        ctx = ctx or {}
        tools_used: list = []
        self._reset_state()

        if available_tools is None:
            available_tools = list(self.tools.keys())

        start_round = 0
        if resume_state and resume_state.get("messages"):
            working_messages = list(resume_state["messages"])
            tools_used = list(resume_state.get("tools_used") or [])
            start_round = int(resume_state.get("round") or 0)
            last_content = resume_state.get("last_content") or ""
        else:
            tool_desc = self._build_tool_description(available_tools)
            working_messages = self._inject_tool_prompt(messages, tool_desc)
            last_content = ""
        self._working_messages = working_messages
        self._tools_used_cache = tools_used

        for round_num in range(start_round, self.max_rounds):
            if self._should_stop(should_cancel):
                return self._aborted_result(tools_used, last_content, round_num)
            if budget_deadline is not None and time.monotonic() >= budget_deadline:
                self._tools_used_cache = tools_used
                return {
                    "response": last_content,
                    "tools_used": tools_used,
                    "rounds": round_num,
                    "truncated": True,
                    "budget_exceeded": True,
                }
            self._current_round = round_num + 1
            # 异步调用 LLM
            llm_result = await self.llm.async_chat(
                messages=working_messages,
                intent=intent,
                use_cache=False,
                tenant_id=tenant_id,
                trace_id=ctx.get("trace_id"),
            )
            content = llm_result.get("content", "")
            last_content = content
            self._last_content = content

            tool_call = self._parse_tool_call(content)
            if tool_call is None:
                self._tools_used_cache = tools_used
                if on_round_end:
                    try:
                        on_round_end(self._current_round, self.snapshot())
                    except Exception as cb_err:
                        logger.debug("on_round_end 回调异常: %s", cb_err)
                return {
                    "response": content,
                    "tools_used": tools_used,
                    "rounds": round_num + 1,
                    "truncated": False,
                }

            tool_name = tool_call.get("tool", "")
            tool_args = tool_call.get("args", {}) or {}

            if tool_name not in self.tools:
                working_messages.append({"role": "assistant", "content": content})
                working_messages.append({
                    "role": "user",
                    "content": f"工具「{tool_name}」不存在。可用工具：{', '.join(available_tools)}。请直接回答或使用可用工具。",
                })
                continue

            try:
                tool_result = self._execute_tool(tool_name, tool_args, ctx)
                tools_used.append({
                    "name": tool_name,
                    "args": tool_args,
                    "result": tool_result,
                })
                logger.info(
                    "tool_loop_async: round=%d tool=%s success",
                    round_num + 1, tool_name,
                )
            except Exception as exc:
                tool_result = {"error": str(exc)}
                tools_used.append({
                    "name": tool_name,
                    "args": tool_args,
                    "error": str(exc),
                })
                logger.warning(
                    "tool_loop_async: round=%d tool=%s failed: %s",
                    round_num + 1, tool_name, exc,
                )

            working_messages.append({"role": "assistant", "content": content})
            result_str = json.dumps(tool_result, ensure_ascii=False, default=str)
            if len(result_str) > 2000:
                result_str = result_str[:2000] + "...(已截断)"
            working_messages.append({
                "role": "user",
                "content": f"工具「{tool_name}」执行结果：\n{result_str}\n\n请基于以上结果继续回答用户问题，或调用下一个工具。若已有足够信息，请直接给出最终回答（不要再使用工具）。",
            })
            self._tools_used_cache = tools_used

            if on_round_end:
                try:
                    on_round_end(self._current_round, self.snapshot())
                except Exception as cb_err:
                    logger.debug("on_round_end 回调异常: %s", cb_err)

        return {
            "response": last_content,
            "tools_used": tools_used,
            "rounds": self.max_rounds,
            "truncated": True,
        }

    # ──────────────────────────────────────────────
    # 内部方法
    # ──────────────────────────────────────────────

    def _execute_tool(self, name: str, args: dict, ctx: dict) -> dict:
        """执行单个工具

        v2.1 合规适配：医药代表角色硬性屏蔽销售类工具
        对应《医药代表管理办法》第 11 条第（三）项 + 第 24 条第（三）项：
        医药代表不得承担药品销售任务。
        """
        # 合规 RBAC 校验：医药代表角色不得调用销售类工具
        try:
            from services.compliance_service import is_tool_forbidden_for_role, get_user_role
            db = ctx.get("db")
            user_id = ctx.get("user_id")
            if db is not None and user_id is not None:
                user_role = get_user_role(db, user_id)
                if is_tool_forbidden_for_role(name, user_role):
                    logger.warning(
                        "[compliance] 工具 %s 被角色 %s（user_id=%s）禁止调用，"
                        "对应《医药代表管理办法》第 11 条第（三）项 / 第 24 条第（三）项",
                        name, user_role, user_id,
                    )
                    return {
                        "error": f"工具 {name} 被合规策略禁止：医药代表不得承担销售任务（对应《医药代表管理办法》第 24 条第（三）项）",
                        "compliance_blocked": True,
                        "tool": name,
                        "user_role": user_role,
                    }
        except Exception as e:
            logger.debug("[compliance] 工具 RBAC 校验异常（降级放行）: %s", e)
            user_role = None

        # F4.5: 绩效边界防御性校验（借鉴诊断体系 §10.3）
        # 禁止 AI 自动调用 PIP / 淘汰 / 扣薪等高风险处置工具
        try:
            from core.performance_policy import check_performance_action_boundary
            check_performance_action_boundary(name, user_role)
        except AppException as e:
            logger.warning(
                "[performance] 工具 %s 被绩效边界策略禁止（user_role=%s）",
                name, user_role,
            )
            return {
                "error": e.message,
                "performance_blocked": True,
                "tool": name,
                "user_role": user_role,
            }

        tool_fn = self.tools[name]
        # Phase B：写工具经 Action Gateway（幂等账本）
        try:
            from action.gateway import action_gateway
            return action_gateway.dispatch_tool(name, args, ctx, tool_fn)
        except Exception as gw_err:
            logger.warning("[gateway] 调度失败，降级直调工具 %s: %s", name, gw_err)
            return tool_fn(args, ctx)

    def _build_tool_description(self, available_tools: list) -> str:
        """构建工具描述文本（从 Ontology ACTIONS + 注册表元数据生成）"""
        # 尝试从 Ontology 读取 action 元数据
        action_map = {}
        try:
            from ontology import ACTION_MAP
            action_map = action_map or {}
        except Exception as e:
            logger.debug("加载 Ontology ACTION_MAP 失败: %s", e, exc_info=True)

        lines = ["你可以使用以下工具来获取信息或执行操作。"]
        lines.append("如需调用工具，请在回复中单独一行输出如下格式（JSON 包在 ```tool 代码块中）：")
        lines.append("```tool")
        lines.append('{"tool": "工具名", "args": {"参数名": "值"}}')
        lines.append("```")
        lines.append("调用工具后我会把结果告诉你，你可以基于结果继续回答或再调用下一个工具。")
        lines.append("当已有足够信息时，请直接给出自然语言回答，不要调用工具。\n")
        lines.append("可用工具：\n")

        for name in available_tools:
            if name not in self.tools:
                continue
            # 从 Ontology 获取描述
            action_def = action_map.get(name, {})
            display_name = action_def.get("display_name", name)
            description = action_def.get("description", "")
            input_schema = action_def.get("input_schema", {})

            lines.append(f"- **{name}**：{display_name}。{description}")
            if input_schema:
                params = ", ".join(f"{k}({v})" for k, v in input_schema.items())
                lines.append(f"  参数：{params}")

        return "\n".join(lines)

    # ──────────────────────────────────────────────
    # B13：原生 function calling 支持
    # ──────────────────────────────────────────────

    # Ontology 类型字符串 → JSON Schema 类型映射
    _TYPE_MAP = {
        "int": "integer", "integer": "integer",
        "float": "number", "number": "number",
        "str": "string", "string": "string",
        "bool": "boolean", "boolean": "boolean",
        "list": "array", "array": "array",
        "dict": "object", "object": "object",
    }

    def _build_tools_schema(self, available_tools: list) -> list:
        """B13：构建 OpenAI tools schema（从 Ontology ACTION_MAP）

        Args:
            available_tools: 允许使用的工具名列表

        Returns:
            [{"type":"function","function":{"name","description","parameters"}}]
        """
        try:
            from ontology import ACTION_MAP
        except Exception as e:
            logger.debug("加载 Ontology ACTION_MAP 失败: %s", e, exc_info=True)
            ACTION_MAP = {}

        schema = []
        for name in available_tools:
            if name not in self.tools:
                continue
            action_def = ACTION_MAP.get(name, {})
            # 将 Ontology input_schema（{field: type_str}）转为 JSON Schema properties
            raw_input = action_def.get("input_schema", {}) or {}
            properties = {}
            for field, type_str in raw_input.items():
                json_type = self._TYPE_MAP.get(str(type_str).lower(), "string")
                properties[field] = {"type": json_type}

            display_name = action_def.get("display_name", name)
            description = action_def.get("description", "")
            schema.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": f"{display_name}. {description}",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": [],
                    },
                },
            })
        return schema

    def run_native(
        self,
        messages: list,
        available_tools: Optional[list] = None,
        ctx: Optional[dict] = None,
        intent: str = "",
        tenant_id: str = "default",
        on_round_end: Optional[Callable[[int, dict], None]] = None,
        trace_id: str = None,
        should_cancel: Optional[Callable[[], bool]] = None,
        resume_state: Optional[dict] = None,
        budget_deadline: Optional[float] = None,
    ) -> dict:
        """B13：原生 function calling 模式

        与 run() 的差异：
        1. 用 chat_with_tools() 替代 chat()，传 tools schema
        2. 解析 resp.tool_calls（而非 prompt 代码块）
        3. 工具结果用 {"role":"tool","tool_call_id":...,"content":...} 回传
        4. 单次可返回多个 tool_calls（并行执行）
        5. 若 chat_with_tools 返回 fallback_to_prompt=True → 降级到 run()

        Returns:
            与 run() 相同的返回结构
        """
        ctx = ctx or {}
        tools_used: list = []
        self._reset_state()

        if available_tools is None:
            available_tools = list(self.tools.keys())

        # 构建 tools schema
        tools_schema = self._build_tools_schema(available_tools)

        # 若无可用 schema（Ontology 未定义这些工具）→ 直接降级到 prompt 模式
        if not tools_schema:
            logger.debug("tool_loop_native: 无可用 schema，降级到 prompt 模式")
            return self.run(
                messages=messages, available_tools=available_tools,
                ctx=ctx, intent=intent, tenant_id=tenant_id,
                on_round_end=on_round_end,
                should_cancel=should_cancel,
                resume_state=resume_state,
                budget_deadline=budget_deadline,
            )

        # 仍需注入工具提示作为 system prompt 上下文（让 LLM 知道工具用途）
        # 但不依赖 LLM 输出 ```tool``` 格式
        tool_desc = self._build_tool_description(available_tools)
        working_messages = self._inject_tool_prompt(messages, tool_desc)
        self._working_messages = working_messages

        last_content = ""
        import time as _time
        for round_num in range(self.max_rounds):
            if self._should_stop(should_cancel):
                return self._aborted_result(tools_used, last_content, round_num)
            if budget_deadline is not None and _time.monotonic() >= budget_deadline:
                self._tools_used_cache = tools_used
                return {
                    "response": last_content,
                    "tools_used": tools_used,
                    "rounds": round_num,
                    "truncated": True,
                    "budget_exceeded": True,
                }
            self._current_round = round_num + 1
            # 调用 LLM（带 tools schema）
            result = self.llm.chat_with_tools(
                messages=working_messages,
                tools_schema=tools_schema,
                intent=intent,
                tenant_id=tenant_id,
                trace_id=trace_id,
            )

            # 降级检查：native 调用失败且需降级 → 切到 prompt 模式
            if result.get("fallback_to_prompt"):
                logger.info(
                    "tool_loop_native: round=%d fallback_to_prompt → 降级到 prompt 模式",
                    round_num + 1,
                )
                # 把已累积的 tools_used 传递下去（虽然通常为空）
                prompt_result = self.run(
                    messages=working_messages,
                    available_tools=available_tools,
                    ctx=ctx,
                    intent=intent,
                    tenant_id=tenant_id,
                    on_round_end=on_round_end,
                    should_cancel=should_cancel,
                    budget_deadline=budget_deadline,
                )
                # 合并 tools_used
                if tools_used:
                    prompt_result["tools_used"] = tools_used + prompt_result.get("tools_used", [])
                return prompt_result

            content = result.get("content", "")
            tool_calls = result.get("tool_calls", []) or []
            last_content = content
            self._last_content = content

            # 无 tool_calls → 最终回答
            if not tool_calls:
                self._tools_used_cache = tools_used
                if on_round_end:
                    try:
                        on_round_end(self._current_round, self.snapshot())
                    except Exception as cb_err:
                        logger.debug("on_round_end 回调异常: %s", cb_err)
                return {
                    "response": content,
                    "tools_used": tools_used,
                    "rounds": round_num + 1,
                    "truncated": False,
                }

            # 有 tool_calls → 执行工具
            # 先把 assistant 消息（含 tool_calls）加入 working_messages
            # OpenAI 协议要求 assistant 消息保留 tool_calls 字段
            assistant_msg = {"role": "assistant", "content": content or ""}
            assistant_msg["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["arguments"], ensure_ascii=False),
                    },
                }
                for tc in tool_calls
            ]
            working_messages.append(assistant_msg)

            # 执行所有 tool_calls（串行执行，避免对 DB 上下文的并发冲突）
            for tc in tool_calls:
                tc_id = tc["id"]
                tool_name = tc["name"]
                tool_args = tc["arguments"] or {}

                if tool_name not in self.tools:
                    # 工具不存在 → 回传错误
                    working_messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": f"工具「{tool_name}」不存在。可用工具：{', '.join(available_tools)}",
                    })
                    continue

                try:
                    tool_result = self._execute_tool(tool_name, tool_args, ctx)
                    tools_used.append({
                        "name": tool_name,
                        "args": tool_args,
                        "result": tool_result,
                    })
                    logger.info(
                        "tool_loop_native: round=%d tool=%s success",
                        round_num + 1, tool_name,
                    )
                except Exception as exc:
                    tool_result = {"error": str(exc)}
                    tools_used.append({
                        "name": tool_name,
                        "args": tool_args,
                        "error": str(exc),
                    })
                    logger.warning(
                        "tool_loop_native: round=%d tool=%s failed: %s",
                        round_num + 1, tool_name, exc,
                    )

                # 回填工具结果（role=tool）
                result_str = json.dumps(tool_result, ensure_ascii=False, default=str)
                if len(result_str) > 2000:
                    result_str = result_str[:2000] + "...(已截断)"
                working_messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": result_str,
                })

            self._tools_used_cache = tools_used

            if on_round_end:
                try:
                    on_round_end(self._current_round, self.snapshot())
                except Exception as cb_err:
                    logger.debug("on_round_end 回调异常: %s", cb_err)

        # 达到最大轮次
        return {
            "response": last_content,
            "tools_used": tools_used,
            "rounds": self.max_rounds,
            "truncated": True,
        }

    async def run_native_async(
        self,
        messages: list,
        available_tools: Optional[list] = None,
        ctx: Optional[dict] = None,
        intent: str = "",
        tenant_id: str = "default",
        on_round_end: Optional[Callable[[int, dict], None]] = None,
        trace_id: str = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> dict:
        """B13：原生 function calling 异步版本

        用 await llm.chat_with_tools_async 释放事件循环。
        逻辑与 run_native() 完全相同，仅 LLM 调用改为异步。
        """
        ctx = ctx or {}
        tools_used: list = []
        self._reset_state()

        if available_tools is None:
            available_tools = list(self.tools.keys())

        tools_schema = self._build_tools_schema(available_tools)

        if not tools_schema:
            logger.debug("tool_loop_native_async: 无可用 schema，降级到 prompt 模式")
            return await self.run_async(
                messages=messages, available_tools=available_tools,
                ctx=ctx, intent=intent, tenant_id=tenant_id,
                on_round_end=on_round_end,
                should_cancel=should_cancel,
            )

        tool_desc = self._build_tool_description(available_tools)
        working_messages = self._inject_tool_prompt(messages, tool_desc)
        self._working_messages = working_messages

        last_content = ""
        for round_num in range(self.max_rounds):
            if self._should_stop(should_cancel):
                return self._aborted_result(tools_used, last_content, round_num)
            self._current_round = round_num + 1
            result = await self.llm.chat_with_tools_async(
                messages=working_messages,
                tools_schema=tools_schema,
                intent=intent,
                tenant_id=tenant_id,
                trace_id=trace_id,
            )

            if result.get("fallback_to_prompt"):
                logger.info(
                    "tool_loop_native_async: round=%d fallback_to_prompt → 降级",
                    round_num + 1,
                )
                prompt_result = await self.run_async(
                    messages=working_messages,
                    available_tools=available_tools,
                    ctx=ctx,
                    intent=intent,
                    tenant_id=tenant_id,
                    on_round_end=on_round_end,
                    should_cancel=should_cancel,
                )
                if tools_used:
                    prompt_result["tools_used"] = tools_used + prompt_result.get("tools_used", [])
                return prompt_result

            content = result.get("content", "")
            tool_calls = result.get("tool_calls", []) or []
            last_content = content
            self._last_content = content

            if not tool_calls:
                self._tools_used_cache = tools_used
                if on_round_end:
                    try:
                        on_round_end(self._current_round, self.snapshot())
                    except Exception as cb_err:
                        logger.debug("on_round_end 回调异常: %s", cb_err)
                return {
                    "response": content,
                    "tools_used": tools_used,
                    "rounds": round_num + 1,
                    "truncated": False,
                }

            assistant_msg = {"role": "assistant", "content": content or ""}
            assistant_msg["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["arguments"], ensure_ascii=False),
                    },
                }
                for tc in tool_calls
            ]
            working_messages.append(assistant_msg)

            for tc in tool_calls:
                tc_id = tc["id"]
                tool_name = tc["name"]
                tool_args = tc["arguments"] or {}

                if tool_name not in self.tools:
                    working_messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": f"工具「{tool_name}」不存在。可用工具：{', '.join(available_tools)}",
                    })
                    continue

                try:
                    tool_result = self._execute_tool(tool_name, tool_args, ctx)
                    tools_used.append({
                        "name": tool_name,
                        "args": tool_args,
                        "result": tool_result,
                    })
                    logger.info(
                        "tool_loop_native_async: round=%d tool=%s success",
                        round_num + 1, tool_name,
                    )
                except Exception as exc:
                    tool_result = {"error": str(exc)}
                    tools_used.append({
                        "name": tool_name,
                        "args": tool_args,
                        "error": str(exc),
                    })
                    logger.warning(
                        "tool_loop_native_async: round=%d tool=%s failed: %s",
                        round_num + 1, tool_name, exc,
                    )

                result_str = json.dumps(tool_result, ensure_ascii=False, default=str)
                if len(result_str) > 2000:
                    result_str = result_str[:2000] + "...(已截断)"
                working_messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": result_str,
                })

            self._tools_used_cache = tools_used

            if on_round_end:
                try:
                    on_round_end(self._current_round, self.snapshot())
                except Exception as cb_err:
                    logger.debug("on_round_end 回调异常: %s", cb_err)

        return {
            "response": last_content,
            "tools_used": tools_used,
            "rounds": self.max_rounds,
            "truncated": True,
        }

    def _inject_tool_prompt(self, messages: list, tool_desc: str) -> list:
        """将工具描述注入 system prompt"""
        working = [m.copy() for m in messages]
        injected = False
        for m in working:
            if m.get("role") == "system":
                m["content"] = m["content"] + "\n\n" + tool_desc
                injected = True
                break
        if not injected:
            working.insert(0, {"role": "system", "content": tool_desc})
        return working

    @staticmethod
    def _parse_tool_call(content: str) -> Optional[dict]:
        """从 LLM 响应中解析工具调用

        支持两种格式：
        1. ```tool\n{"tool": "name", "args": {...}}\n```
        2. 行内 JSON（兼容不规范的输出）
        """
        if not content:
            return None

        # 格式 1：```tool 代码块
        pattern1 = r"```tool\s*\n(.*?)\n\s*```"
        matches = re.findall(pattern1, content, re.DOTALL)
        if matches:
            try:
                data = json.loads(matches[0].strip())
                if isinstance(data, dict) and "tool" in data:
                    return data
            except json.JSONDecodeError:
                pass

        # 格式 2：行内 ```json 中包含 tool 字段
        pattern2 = r"```(?:json)?\s*\n(.*?)\n\s*```"
        matches = re.findall(pattern2, content, re.DOTALL)
        for match in matches:
            try:
                data = json.loads(match.strip())
                if isinstance(data, dict) and "tool" in data:
                    return data
            except json.JSONDecodeError:
                continue

        return None


__all__ = ["ToolLoop"]
