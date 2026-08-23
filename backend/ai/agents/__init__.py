"""Agent 模块 - Agent 注册与访问"""
from ai.agents.base import BaseAgent, MockAgent
from ai.agents.registry import AGENT_REGISTRY, list_agents, get_agent

__all__ = [
    "BaseAgent", "MockAgent",
    "AGENT_REGISTRY", "list_agents", "get_agent",
]
