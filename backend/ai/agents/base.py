"""Agent 基类与 Mock 实现"""
from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Agent 基类 - 所有领域 Agent 的抽象基类"""

    # 元数据字段（子类可覆盖）
    name: str = ""
    display_name: str = ""
    domain: str = ""
    description: str = ""
    system_prompt: str = ""
    tools: list = []
    skills: list = []
    few_shot_examples: list = []
    domain_filter: list = []

    @abstractmethod
    async def invoke(self, input: dict) -> dict:
        """调用 Agent（子类实现具体逻辑）"""
        pass

    def metadata(self) -> dict:
        """返回 Agent 的元数据（不含 system_prompt）"""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "domain": self.domain,
            "description": self.description,
            "tools": list(self.tools),
            "skills": list(self.skills),
            "few_shot_examples": list(self.few_shot_examples),
            "domain_filter": list(self.domain_filter),
        }

    def full_info(self) -> dict:
        """返回完整信息（含 system_prompt）"""
        info = self.metadata()
        info["system_prompt"] = self.system_prompt
        return info


class MockAgent(BaseAgent):
    """Mock Agent 实现 - 返回预设响应，不调用真实 LLM"""

    def __init__(
        self,
        name: str = "",
        display_name: str = "",
        domain: str = "",
        description: str = "",
        system_prompt: str = "",
        tools: list = None,
        skills: list = None,
        few_shot_examples: list = None,
        domain_filter: list = None,
    ):
        self.name = name
        self.display_name = display_name
        self.domain = domain
        self.description = description
        self.system_prompt = system_prompt
        self.tools = list(tools) if tools else []
        self.skills = list(skills) if skills else []
        self.few_shot_examples = list(few_shot_examples) if few_shot_examples else []
        self.domain_filter = list(domain_filter) if domain_filter else []

    async def invoke(self, input: dict) -> dict:
        """Mock 调用 - 返回固定格式的响应"""
        return {
            "agent": self.name,
            "display_name": self.display_name,
            "response": f"[Mock] {self.display_name} 已处理您的请求",
            "actions_called": self.tools[:2] if self.tools else [],
            "input": input,
        }
