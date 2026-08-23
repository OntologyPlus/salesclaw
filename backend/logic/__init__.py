"""Logic 平面 — 本体驱动的可执行动作编排层。

把已验证的资产闭合为「目标 → 规划 → 风险门禁 → 执行 → 溯源」主线的最后一环：
    - plan.build_plan：目标 → 有序 Action 序列（复用 ontology.actions 元数据）
    - executor.ActionExecutor：风险门禁 + 权限校验 + provenance 溯源执行
    - registry：动作 handler 注册表（port 模式，可注入真实业务实现）

"""
from .plan import LogicPlan, PlanStep, build_plan
from .executor import ActionExecutor, ExecutionResult, StepResult
from .registry import ActionHandlerRegistry, registry as handler_registry, dispatch

__all__ = [
    "LogicPlan",
    "PlanStep",
    "build_plan",
    "ActionExecutor",
    "ExecutionResult",
    "StepResult",
    "ActionHandlerRegistry",
    "handler_registry",
    "dispatch",
]
