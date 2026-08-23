"""质量门控配置（B7 配置化抽取）

从 self_reflection.py 迁移而来的质量门控定义：
- 每个门控为 {name, description, check: Callable[[str], bool]} 字典
- check 返回 True 表示该门控"未通过"（需要重试）

新增工具函数：
- register_gate(name, description, check)：运行时注册新门控
- get_gates()：获取所有已注册门控
- unregister_gate(name)：移除门控（主要用于测试）
"""
from typing import Callable, Optional


# 门控类型
GateCheck = Callable[[str], bool]


class QualityGate:
    """单个质量门控"""

    def __init__(self, name: str, description: str, check: GateCheck):
        self.name = name
        self.description = description
        self.check = check

    def __call__(self, response: str) -> bool:
        try:
            return self.check(response)
        except Exception:
            # 门控本身异常视为未通过
            return True

    def to_dict(self) -> dict:
        return {"name": self.name, "description": self.description}


# ──────────────────────────────────────────────
# 默认门控（从 self_reflection.py 迁移）
# ──────────────────────────────────────────────

_DEFAULT_GATES: list[QualityGate] = [
    QualityGate(
        name="empty_or_too_short",
        description="响应为空或过短（<10 字符）",
        check=lambda resp: not resp or len(resp.strip()) < 10,
    ),
    QualityGate(
        name="llm_failure_marker",
        description="响应包含失败标记 [LLM调用失败]",
        check=lambda resp: "[LLM调用失败]" in (resp or ""),
    ),
    QualityGate(
        name="evasive_phrases",
        description="响应包含推诿话术（请提供更多/需要更多信息）",
        check=lambda resp: ("请提供更多" in (resp or "")) or ("需要更多信息" in (resp or "")),
    ),
    QualityGate(
        name="mock_fallback",
        description="命中 Mock 兜底响应（目前我已理解您的请求）",
        check=lambda resp: "目前我已理解您的请求" in (resp or ""),
    ),
]


# 运行时可扩展的门控注册表（含默认门控）
_registry: list[QualityGate] = list(_DEFAULT_GATES)


def register_gate(name: str, description: str, check: GateCheck) -> None:
    """运行时注册新门控

    若同名门控已存在，则覆盖。
    """
    # 移除同名旧门控
    _registry[:] = [g for g in _registry if g.name != name]
    _registry.append(QualityGate(name, description, check))


def unregister_gate(name: str) -> bool:
    """移除门控（主要用于测试）

    Returns:
        True 表示移除成功，False 表示门控不存在
    """
    before = len(_registry)
    _registry[:] = [g for g in _registry if g.name != name]
    return len(_registry) < before


def get_gates() -> list[QualityGate]:
    """获取所有已注册门控（含默认门控）"""
    return list(_registry)


def get_gate_dicts() -> list[dict]:
    """获取所有门控的字典表示（用于序列化展示）"""
    return [g.to_dict() for g in _registry]


__all__ = [
    "QualityGate",
    "GateCheck",
    "register_gate",
    "unregister_gate",
    "get_gates",
    "get_gate_dicts",
]
