"""Self-Reflection 循环引擎 - Agent 自我批评与重试机制

核心能力：
1. 质量门控（从 quality_gates.py 加载，支持运行时注册）
2. should_retry：根据门控结果与轮次判断是否需要重试
3. build_retry_prompt：构建带自我批评反馈的重试 prompt
4. run_loop：完整反思循环（给定响应生成器即可驱动）

约束：
- 最大反思轮次 MAX_REFLECTION_ROUNDS = 3
- 每轮把命中的门控反馈写回 prompt，引导 LLM 修正

B7：门控定义已迁移到 quality_gates.py，本模块仅保留引擎逻辑。
"""
from typing import Callable, Optional

from ai.quality_gates import QualityGate, get_gates


# 最大反思轮次（超过即放弃，返回最后一次响应）
MAX_REFLECTION_ROUNDS = 3


# 向后兼容：从 quality_gates 动态派生 QUALITY_GATES / QUALITY_GATE_NAMES
# 旧代码若直接引用这两个常量仍可工作
def _get_quality_gates() -> list:
    """获取门控的可调用列表（向后兼容 QUALITY_GATES）"""
    return [g for g in get_gates()]


def _get_quality_gate_names() -> list[str]:
    """获取门控描述列表（向后兼容 QUALITY_GATE_NAMES）"""
    return [g.description for g in get_gates()]


# 模块级常量（首次导入时快照，向后兼容旧代码 `from self_reflection import QUALITY_GATES`）
QUALITY_GATES = _get_quality_gates()
QUALITY_GATE_NAMES = _get_quality_gate_names()


class SelfReflectionEngine:
    """Self-Reflection 循环引擎

    通过质量门控对 LLM 响应做自我批评，未通过则在轮次上限内
    构建重试 prompt 引导 LLM 重新作答。

    B7：门控从 quality_gates.py 动态加载，支持运行时 register_gate 扩展。
    """

    def __init__(self, max_rounds: int = MAX_REFLECTION_ROUNDS, gates: Optional[list] = None):
        """
        Args:
            max_rounds: 最大反思轮次
            gates: 可选的自定义门控列表（QualityGate 对象）。
                   若 None 则从 quality_gates.py 全局注册表加载。
        """
        self.max_rounds = max_rounds
        # 每次实例化时从全局注册表加载最新门控（支持运行时 register_gate）
        self.quality_gates = gates if gates is not None else get_gates()
        # gate_names 为描述列表（用于反馈文案）
        self.gate_names = [g.description for g in self.quality_gates]

    # ──────────────────────────────────────────────
    # 门控评估
    # ──────────────────────────────────────────────

    def _evaluate_gates(self, response: str) -> list[int]:
        """评估所有门控，返回未通过的门控索引列表"""
        failed: list[int] = []
        for idx, gate in enumerate(self.quality_gates):
            try:
                # QualityGate 是可调用对象
                if gate(response):
                    failed.append(idx)
            except Exception:
                # 门控本身异常视为未通过
                failed.append(idx)
        return failed

    def get_failed_gates(self, response: str) -> list[str]:
        """返回未通过的门控名称列表（供外部观测）"""
        return [self.gate_names[i] for i in self._evaluate_gates(response)]

    # ──────────────────────────────────────────────
    # 重试决策
    # ──────────────────────────────────────────────

    def should_retry(self, response: str, round_count: int) -> bool:
        """判断是否需要重试

        规则：
        - 已达最大轮次 -> 不重试
        - 响应为 None -> 重试
        - 任一质量门控未通过 -> 重试
        - 否则不重试
        """
        if round_count >= self.max_rounds:
            return False
        if response is None:
            return True
        return len(self._evaluate_gates(response)) > 0

    # ──────────────────────────────────────────────
    # 重试 prompt 构建
    # ──────────────────────────────────────────────

    def build_retry_prompt(self, original_query: str, previous_response: str,
                           round_count: int) -> str:
        """构建重试 prompt - 把自我批评反馈写入 prompt

        Args:
            original_query: 用户的原始问题
            previous_response: 上一轮的（不合格）响应
            round_count: 当前已完成的轮次（从 1 开始）

        Returns:
            重试 prompt 字符串
        """
        failed = self._evaluate_gates(previous_response or "")
        if failed:
            critique = "；".join(self.gate_names[i] for i in failed)
        else:
            critique = "响应质量仍不达标"

        remaining = max(self.max_rounds - round_count, 0)
        prompt = (
            "你是一个严谨的医药销售 AI 助手，需要对上一轮回答进行自我批评并重新作答。\n\n"
            f"【用户原始问题】\n{original_query}\n\n"
            f"【上一轮回答】\n{previous_response or '（空）'}\n\n"
            f"【自我批评】上一轮回答存在以下问题：{critique}。\n\n"
            "【重作要求】\n"
            "1. 直接回答用户问题，不要推诿或要求用户提供更多信息；\n"
            "2. 基于已知事实与数据作答，不要编造；\n"
            "3. 如确实信息不足，请明确指出缺失的具体数据项，并给出基于现有信息的最佳建议；\n"
            "4. 回答至少 50 字，结构清晰。\n\n"
            f"（反思轮次：第 {round_count} 轮，剩余 {remaining} 轮机会）\n"
            "请直接输出改进后的回答："
        )
        return prompt

    # ──────────────────────────────────────────────
    # 完整反思循环
    # ──────────────────────────────────────────────

    def run_loop(self, original_query: str, generate: Callable[[str], str],
                 initial_response: Optional[str] = None) -> dict:
        """运行完整反思循环

        Args:
            original_query: 用户原始问题
            generate: 响应生成器，接收 prompt 返回响应文本；
                      首次调用使用 initial_response 或原始 query 作为 prompt
            initial_response: 首轮响应（若已有则直接传入，避免重复生成）

        Returns:
            {
                final_response: str,          # 最终响应
                rounds: int,                  # 实际执行轮次
                retried: bool,                # 是否触发过重试
                passed: bool,                 # 最终是否通过门控
                final_gate_failures: list[str],  # 最终未通过的门控名称
            }
        """
        # 首轮响应
        if initial_response is not None:
            response = initial_response
        else:
            response = generate(original_query)

        round_count = 1
        retried = False

        while self.should_retry(response, round_count):
            retried = True
            retry_prompt = self.build_retry_prompt(original_query, response, round_count)
            response = generate(retry_prompt)
            round_count += 1

        final_failures = self._evaluate_gates(response)
        return {
            "final_response": response,
            "rounds": round_count,
            "retried": retried,
            "passed": len(final_failures) == 0,
            "final_gate_failures": [self.gate_names[i] for i in final_failures],
        }


# 全局单例
self_reflection_engine = SelfReflectionEngine()


__all__ = [
    "SelfReflectionEngine",
    "self_reflection_engine",
    "MAX_REFLECTION_ROUNDS",
    "QUALITY_GATES",
    "QUALITY_GATE_NAMES",
]
