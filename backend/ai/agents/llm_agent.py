"""LLM 驱动的 Agent - 使用真实 LLM + 工具循环

与 MockAgent 相对，LLMAgent 在 invoke() 中：
  1. 构建 messages（system_prompt + 用户输入）
  2. 调用 ToolLoop 执行工具调用循环
  3. 返回 {agent, display_name, response, tools_used, reasoning}

当 LLM_PROVIDER=mock 时，ToolLoop 仍可工作（LLM 返回的 mock 响应
不会包含工具调用，因此直接返回 mock 文本）。
"""
import logging
from typing import Optional

from ai.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class LLMAgent(BaseAgent):
    """真实 LLM 驱动的 Agent

    通过 ToolLoop 实现工具调用，适用于 LLM_PROVIDER=openai 模式。
    """

    def __init__(
        self,
        defn: dict,
        llm_client=None,
        tool_loop=None,
    ):
        """
        Args:
            defn: Agent 定义字典（name, display_name, domain, system_prompt, tools, ...）
            llm_client: LLMClient 实例（若 None 则延迟初始化）
            tool_loop: ToolLoop 实例（若 None 则延迟初始化）
        """
        self.name = defn.get("name", "")
        self.display_name = defn.get("display_name", "")
        self.domain = defn.get("domain", "")
        self.description = defn.get("description", "")
        self.system_prompt = defn.get("system_prompt", "")
        self.tools = list(defn.get("tools", []))
        self.skills = list(defn.get("skills", []))
        self.few_shot_examples = list(defn.get("few_shot_examples", []))
        self.domain_filter = list(defn.get("domain_filter", []))

        self._llm_client = llm_client
        self._tool_loop = tool_loop

    def _ensure_clients(self):
        """延迟初始化 LLM client 和 ToolLoop（避免循环导入）"""
        if self._llm_client is None:
            from ai.llm_client import llm_client
            self._llm_client = llm_client
        if self._tool_loop is None:
            from ai.tool_loop import ToolLoop
            from ai.tools.registry import TOOL_REGISTRY
            self._tool_loop = ToolLoop(
                llm_client=self._llm_client,
                tool_registry=TOOL_REGISTRY,
                max_rounds=5,
            )

    async def invoke(self, input: dict) -> dict:
        """调用 Agent

        Args:
            input: {message, ctx, intent, tenant_id}
                - message: 用户消息
                - ctx: 工具执行上下文 {db, tenant_id, user_id}
                - intent: 意图标签
                - tenant_id: 租户 ID

        Returns:
            {agent, display_name, response, tools_used, reasoning}
        """
        self._ensure_clients()

        message = input.get("message", "")
        ctx = input.get("ctx", {})
        intent = input.get("intent", "")
        tenant_id = input.get("tenant_id", "default")

        # 构建 messages
        messages = [
            {"role": "system", "content": self.system_prompt or "你是 AI 助手，请以中文回答。"},
            {"role": "user", "content": message},
        ]

        # 确定可用工具：Agent 定义中的 tools 列表，与 TOOL_REGISTRY 取交集
        from ai.tools.registry import TOOL_REGISTRY
        available_tools = [t for t in self.tools if t in TOOL_REGISTRY]

        # 如果没有可用工具，直接调用 LLM
        if not available_tools:
            llm_result = self._llm_client.chat(
                messages=messages,
                intent=intent,
                tenant_id=tenant_id,
            )
            return {
                "agent": self.name,
                "display_name": self.display_name,
                "response": llm_result.get("content", ""),
                "tools_used": [],
                "reasoning": llm_result.get("reasoning", ""),
            }

        # 执行工具循环
        loop_result = self._tool_loop.run(
            messages=messages,
            available_tools=available_tools,
            ctx=ctx,
            intent=intent,
            tenant_id=tenant_id,
        )

        return {
            "agent": self.name,
            "display_name": self.display_name,
            "response": loop_result.get("response", ""),
            "tools_used": loop_result.get("tools_used", []),
            "reasoning": "",
            "rounds": loop_result.get("rounds", 0),
            "truncated": loop_result.get("truncated", False),
        }


__all__ = ["LLMAgent"]
