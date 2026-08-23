"""多 Agent 协作框架

支持三种协作模式：
  1. Delegate（委托）：Supervisor 拆解任务 → 并行分派给多个 Agent → 聚合结果
  2. Orchestrate（编排）：管道串联，前一个 Agent 输出作为后一个输入
  3. Aggregate（聚合）：多个 Agent 独立处理同一任务 → 合并/投票

B2 协作真并行化：delegate/aggregate 用 asyncio.gather 并行调用各 Agent，
orchestrate 保持串行（管道本质就是串行）。所有方法均为 async。
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CollaborationOrchestrator:
    """多 Agent 协作编排器

    在复杂任务场景下，协调多个领域 Agent 协同完成工作。
    """

    def __init__(self, llm_client=None, tool_loop=None):
        """
        Args:
            llm_client: LLMClient 实例（若 None 则延迟初始化）
            tool_loop: ToolLoop 实例（可选，用于工具调用）
        """
        self._llm_client = llm_client
        self._tool_loop = tool_loop

    def _ensure_llm(self):
        """延迟初始化 LLM client"""
        if self._llm_client is None:
            from ai.llm_client import llm_client
            self._llm_client = llm_client

    def _get_agent_prompt(self, agent_name: str) -> str:
        """从注册表获取 Agent 的 system_prompt"""
        from ai.agents.registry import get_agent
        agent = get_agent(agent_name)
        if agent is None:
            return "你是 AI 助手，请以中文回答。"
        return getattr(agent, "system_prompt", "") or "你是 AI 助手，请以中文回答。"

    def _call_agent(self, agent_name: str, task: str, ctx: dict,
                    intent: str = "", tenant_id: str = "default") -> dict:
        """调用单个 Agent（同步，直接用 llm.chat）

        Returns:
            {agent, response, tools_used}
        """
        self._ensure_llm()
        system_prompt = self._get_agent_prompt(agent_name)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]

        # 尝试使用工具循环
        tools_used = []
        if self._tool_loop is not None:
            from ai.tools.registry import TOOL_REGISTRY
            from ai.agents.registry import get_agent
            agent = get_agent(agent_name)
            agent_tools = getattr(agent, "tools", []) if agent else []
            available = [t for t in agent_tools if t in TOOL_REGISTRY]
            if available:
                loop_result = self._tool_loop.run(
                    messages=messages,
                    available_tools=available,
                    ctx=ctx,
                    intent=intent,
                    tenant_id=tenant_id,
                )
                return {
                    "agent": agent_name,
                    "response": loop_result.get("response", ""),
                    "tools_used": loop_result.get("tools_used", []),
                }

        # 无工具循环 → 直接 LLM 调用
        result = self._llm_client.chat(
            messages=messages,
            intent=intent,
            tenant_id=tenant_id,
        )
        return {
            "agent": agent_name,
            "response": result.get("content", ""),
            "tools_used": [],
        }

    async def _call_agent_async(self, agent_name: str, task: str, ctx: dict,
                                intent: str = "", tenant_id: str = "default",
                                use_tool_loop: bool = True) -> dict:
        """异步调用单个 Agent（B2 协作真并行化）

        Args:
            use_tool_loop: 是否使用 ToolLoop。
                - orchestrate（串行）: True，db session 安全
                - delegate/aggregate（并行）: False，避免多线程共享 db session 竞态

        Returns:
            {agent, response, tools_used}
        """
        self._ensure_llm()
        system_prompt = self._get_agent_prompt(agent_name)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]

        # 串行模式可使用 ToolLoop（db session 单线程使用，安全）
        if use_tool_loop and self._tool_loop is not None:
            from ai.tools.registry import TOOL_REGISTRY
            from ai.agents.registry import get_agent
            agent = get_agent(agent_name)
            agent_tools = getattr(agent, "tools", []) if agent else []
            available = [t for t in agent_tools if t in TOOL_REGISTRY]
            if available:
                loop_result = await self._tool_loop.run_async(
                    messages=messages,
                    available_tools=available,
                    ctx=ctx,
                    intent=intent,
                    tenant_id=tenant_id,
                )
                return {
                    "agent": agent_name,
                    "response": loop_result.get("response", ""),
                    "tools_used": loop_result.get("tools_used", []),
                }

        # 并行模式或无 ToolLoop → 直接 async LLM 调用（不涉及 db，并行安全）
        result = await self._llm_client.async_chat(
            messages=messages,
            intent=intent,
            tenant_id=tenant_id,
        )
        return {
            "agent": agent_name,
            "response": result.get("content", ""),
            "tools_used": [],
        }

    # ──────────────────────────────────────────────
    # 协作模式
    # ──────────────────────────────────────────────

    async def delegate(
        self,
        task: str,
        sub_agents: list,
        ctx: dict,
        tenant_id: str = "default",
    ) -> dict:
        """委托模式：Supervisor 拆解任务 → 并行分派 → 聚合

        B2 真并行化：用 asyncio.gather 并行调用各子 Agent。
        use_tool_loop=False 避免多协程共享 db session 竞态。

        Args:
            task: 复杂任务描述
            sub_agents: 参与的 Agent 名称列表
            ctx: 执行上下文
            tenant_id: 租户 ID

        Returns:
            {mode, task, sub_results, synthesized_response}
        """
        self._ensure_llm()

        # 1. Supervisor 拆解任务
        decompose_prompt = (
            f"你是 Supervisor，需要将以下复杂任务拆解为 {len(sub_agents)} 个子任务，"
            f"分别交给以下 Agent 处理：{', '.join(sub_agents)}。\n\n"
            f"任务：{task}\n\n"
            f"请为每个 Agent 生成一个明确的子任务描述，格式为 JSON：\n"
            f'```json\n{{"agents": [{{"name": "agent_name", "subtask": "子任务描述"}}]}}\n```'
        )
        messages = [
            {"role": "system", "content": "你是平台监督者（Supervisor），负责任务拆解与编排。"},
            {"role": "user", "content": decompose_prompt},
        ]
        decompose_result = await self._llm_client.async_chat(messages=messages, tenant_id=tenant_id)
        subtasks = self._parse_decomposition(decompose_result.get("content", ""), sub_agents)

        # 2. 并行调用各 Agent（asyncio.gather 真并行，use_tool_loop=False 避免 db session 竞态）
        async def _run_one(item):
            agent_name = item.get("name", "")
            subtask = item.get("subtask", task)
            if agent_name not in sub_agents:
                agent_name = sub_agents[0] if sub_agents else "Supervisor"
            return await self._call_agent_async(
                agent_name, subtask, ctx, tenant_id=tenant_id, use_tool_loop=False,
            )

        sub_results = await asyncio.gather(*[_run_one(item) for item in subtasks])
        sub_results = list(sub_results)

        # 3. 聚合结果
        synth_input = self._build_synthesis_input(task, sub_results)
        synth_messages = [
            {"role": "system", "content": "你是 Supervisor，负责综合多个 Agent 的回答，给出最终回复。"},
            {"role": "user", "content": synth_input},
        ]
        synth_result = await self._llm_client.async_chat(messages=synth_messages, tenant_id=tenant_id)

        return {
            "mode": "delegate",
            "task": task,
            "sub_results": sub_results,
            "synthesized_response": synth_result.get("content", ""),
            "agents_involved": [r["agent"] for r in sub_results],
        }

    async def orchestrate(
        self,
        task: str,
        pipeline: list,
        ctx: dict,
        tenant_id: str = "default",
    ) -> dict:
        """编排模式：管道串联，前一个输出作为后一个输入

        B2 异步化：保持串行 await（管道本质就是串行）。
        use_tool_loop=True，db session 单线程使用安全。

        Args:
            task: 初始任务
            pipeline: Agent 名称列表，按顺序执行
            ctx: 执行上下文
            tenant_id: 租户 ID

        Returns:
            {mode, task, stages, final_response}
        """
        self._ensure_llm()

        stages = []
        current_input = task

        for i, agent_name in enumerate(pipeline):
            result = await self._call_agent_async(
                agent_name, current_input, ctx, tenant_id=tenant_id, use_tool_loop=True,
            )
            stages.append({
                "stage": i + 1,
                "agent": agent_name,
                "input": current_input[:200],
                "response": result.get("response", ""),
                "tools_used": result.get("tools_used", []),
            })
            # 前一个输出作为后一个输入
            current_input = result.get("response", current_input)

        return {
            "mode": "orchestrate",
            "task": task,
            "stages": stages,
            "final_response": current_input,
            "agents_involved": pipeline,
        }

    async def aggregate(
        self,
        task: str,
        agent_names: list,
        ctx: dict,
        strategy: str = "merge",
        tenant_id: str = "default",
    ) -> dict:
        """聚合模式：多个 Agent 独立处理同一任务 → 合并

        B2 真并行化：用 asyncio.gather 并行调用各 Agent。
        use_tool_loop=False 避免多协程共享 db session 竞态。

        Args:
            task: 任务描述
            agent_names: 参与的 Agent 名称列表
            ctx: 执行上下文
            strategy: 合并策略（merge/vote/best）
            tenant_id: 租户 ID

        Returns:
            {mode, task, independent_results, aggregated_response, strategy}
        """
        self._ensure_llm()

        # 1. 各 Agent 独立处理（asyncio.gather 真并行，use_tool_loop=False 避免 db session 竞态）
        independent_results = await asyncio.gather(*[
            self._call_agent_async(
                name, task, ctx, tenant_id=tenant_id, use_tool_loop=False,
            )
            for name in agent_names
        ])
        independent_results = list(independent_results)

        # 2. 根据策略聚合
        if strategy == "vote":
            # 投票：选择多数一致的结果（简化为取最长）
            aggregated = max(independent_results, key=lambda r: len(r.get("response", ""))).get("response", "")
        elif strategy == "best":
            # 最佳：让 Supervisor 选择最佳
            best_prompt = (
                f"以下是多个 Agent 对同一任务的回答，请选择并整合最佳回答：\n\n"
                f"任务：{task}\n\n"
            )
            for i, r in enumerate(independent_results):
                best_prompt += f"\nAgent {r['agent']}：\n{r.get('response', '')}\n"
            best_prompt += "\n请给出整合后的最佳回答。"
            messages = [
                {"role": "system", "content": "你是 Supervisor，负责选择并整合最佳回答。"},
                {"role": "user", "content": best_prompt},
            ]
            best_result = await self._llm_client.async_chat(messages=messages, tenant_id=tenant_id)
            aggregated = best_result.get("content", "")
        else:
            # merge（默认）：合并所有回答
            merge_prompt = (
                f"以下是多个 Agent 对同一任务的回答，请合并为一份完整回复：\n\n"
                f"任务：{task}\n\n"
            )
            for r in independent_results:
                merge_prompt += f"\n{r['agent']}：\n{r.get('response', '')}\n"
            merge_prompt += "\n请合并以上内容，去重并保持逻辑连贯。"
            messages = [
                {"role": "system", "content": "你是 Supervisor，负责合并多个回答。"},
                {"role": "user", "content": merge_prompt},
            ]
            merge_result = await self._llm_client.async_chat(messages=messages, tenant_id=tenant_id)
            aggregated = merge_result.get("content", "")

        return {
            "mode": "aggregate",
            "task": task,
            "independent_results": independent_results,
            "aggregated_response": aggregated,
            "strategy": strategy,
            "agents_involved": agent_names,
        }

    # ──────────────────────────────────────────────
    # 复合意图判定
    # ──────────────────────────────────────────────

    @staticmethod
    def detect_collaboration_need(message: str, intent: str) -> Optional[dict]:
        """检测消息是否需要多 Agent 协作

        判定规则（关键词兜底）：
        - 跨域关键词：同时包含"销售/拜访"和"培训/课程"
        - 多动词：包含"分析+推荐"、"评估+生成"、"总结+规划"等

        使用域级 Agent（SalesAgent/TrainingAgent/DecisionAgent/CollabAgent），
        每个域 Agent 内部持有多个 Skill，由 Orchestrator 负责具体的 Skill 路由。

        Returns:
            {mode, agents} 或 None（不需要协作）
        """
        msg_lower = message.lower()

        # 跨域关键词检测
        sales_keywords = ["拜访", "销售", "覆盖", "客户", "医院", "医生", "积分"]
        training_keywords = ["培训", "课程", "学习", "考试", "演练", "能力"]
        decision_keywords = ["kpi", "归因", "模拟", "预警", "效果"]

        has_sales = any(k in message for k in sales_keywords)
        has_training = any(k in message for k in training_keywords)
        has_decision = any(k in msg_lower for k in decision_keywords)

        # 销售 + 培训 → delegate（SalesAgent 负责 sales 域 Skill，TrainingAgent 负责 training 域 Skill）
        if has_sales and has_training:
            if any(v in message for v in ["推荐", "规划", "建议", "改善"]):
                return {
                    "mode": "delegate",
                    "agents": ["SalesAgent", "TrainingAgent"],
                }
            return {
                "mode": "orchestrate",
                "agents": ["SalesAgent", "TrainingAgent"],
            }

        # 销售 + 决策 → aggregate
        if has_sales and has_decision:
            return {
                "mode": "aggregate",
                "agents": ["SalesAgent", "DecisionAgent"],
                "strategy": "best",
            }

        # 多动词检测
        multi_verb_patterns = [
            (["分析", "推荐"], "delegate", ["SalesAgent", "TrainingAgent"]),
            (["评估", "生成"], "orchestrate", ["SalesAgent", "CollabAgent"]),
            (["总结", "规划"], "orchestrate", ["CollabAgent", "SalesAgent"]),
        ]
        for verbs, mode, agents in multi_verb_patterns:
            if all(v in message for v in verbs):
                return {"mode": mode, "agents": agents}

        return None

    # ──────────────────────────────────────────────
    # 辅助方法
    # ──────────────────────────────────────────────

    @staticmethod
    def _parse_decomposition(content: str, fallback_agents: list) -> list:
        """解析 Supervisor 的任务拆解结果"""
        import json
        import re

        # 尝试解析 JSON
        pattern = r"```(?:json)?\s*\n(.*?)\n\s*```"
        matches = re.findall(pattern, content, re.DOTALL)
        if matches:
            try:
                data = json.loads(matches[0].strip())
                if isinstance(data, dict) and "agents" in data:
                    return data["agents"]
            except json.JSONDecodeError:
                pass

        # 解析失败 → 每个_agent 处理完整任务
        return [{"name": name, "subtask": ""} for name in fallback_agents]

    @staticmethod
    def _build_synthesis_input(task: str, sub_results: list) -> str:
        """构建聚合输入"""
        parts = [f"原始任务：{task}\n"]
        parts.append("各 Agent 的回答：\n")
        for r in sub_results:
            parts.append(f"\n[{r['agent']}]\n{r.get('response', '无响应')}\n")
        parts.append("\n请综合以上回答，给出完整、连贯的最终回复。")
        return "\n".join(parts)


# ──────────────────────────────────────────────
# 全局单例
# ──────────────────────────────────────────────

_collab_orchestrator: Optional[CollaborationOrchestrator] = None


def get_collaboration_orchestrator() -> CollaborationOrchestrator:
    """获取全局协作编排器单例"""
    global _collab_orchestrator
    if _collab_orchestrator is None:
        _collab_orchestrator = CollaborationOrchestrator()
    return _collab_orchestrator


__all__ = ["CollaborationOrchestrator", "get_collaboration_orchestrator"]
