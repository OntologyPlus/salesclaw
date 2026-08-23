"""AI 运行期指标采集 - 工业级 AI 可观测性

采集维度：
- 请求总量 / 成功率 / 失败率
- 缓存命中率
- 意图分布 / Agent 使用频次
- 延迟采样（avg / p50 / p95 / p99）
- Self-Reflection 触发次数
- 幻觉检测拒绝次数
- 安全阀拦截次数

线程安全：使用 threading.Lock 保护内部状态。
"""
import threading
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Optional


class MetricsCollector:
    """AI 运行期指标采集器（进程内单例）"""

    _instance: Optional["MetricsCollector"] = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._lock = threading.Lock()
        self._latency_max_samples = 1000
        self._reset()
        self._initialized = True

    def _reset(self):
        self._metrics = {
            "total_requests": 0,
            "success_count": 0,
            "failure_count": 0,
            "cache_hits": 0,
            "cache_writes": 0,
            "intent_counts": defaultdict(int),
            "agent_usage": defaultdict(int),
            "latency_samples": deque(maxlen=self._latency_max_samples),
            "reflection_count": 0,
            "hallucination_rejected": 0,
            "hallucination_review": 0,
            "safety_valve_blocked": 0,
            "event_published": 0,
            "dead_letter_count": 0,
            # B12：token 用量追踪
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
            "tenant_token_usage": defaultdict(int),
        }
        self._started_at = datetime.utcnow()

    def record_request(
        self,
        intent: str,
        agent: str,
        latency_ms: float,
        success: bool,
        cache_hit: bool = False,
        reflection_triggered: bool = False,
        hallucination_rejected: bool = False,
        hallucination_review: bool = False,
        safety_valve_blocked: bool = False,
    ):
        """记录一次 AI 请求的全生命周期指标"""
        with self._lock:
            self._metrics["total_requests"] += 1
            if success:
                self._metrics["success_count"] += 1
            else:
                self._metrics["failure_count"] += 1
            if cache_hit:
                self._metrics["cache_hits"] += 1
            if intent:
                self._metrics["intent_counts"][intent] += 1
            if agent:
                self._metrics["agent_usage"][agent] += 1
            self._metrics["latency_samples"].append(float(latency_ms))
            if reflection_triggered:
                self._metrics["reflection_count"] += 1
            if hallucination_rejected:
                self._metrics["hallucination_rejected"] += 1
            if hallucination_review:
                self._metrics["hallucination_review"] += 1
            if safety_valve_blocked:
                self._metrics["safety_valve_blocked"] += 1

    def record_cache_write(self):
        with self._lock:
            self._metrics["cache_writes"] += 1

    def record_token_usage(self, prompt_tokens: int, completion_tokens: int,
                           tenant_id: str = "default"):
        """B12：记录 token 用量（按租户累计）"""
        with self._lock:
            self._metrics["total_prompt_tokens"] += int(prompt_tokens or 0)
            self._metrics["total_completion_tokens"] += int(completion_tokens or 0)
            self._metrics["total_tokens"] += int(prompt_tokens or 0) + int(completion_tokens or 0)
            self._metrics["tenant_token_usage"][tenant_id] += int(prompt_tokens or 0) + int(completion_tokens or 0)

    def record_event_published(self):
        with self._lock:
            self._metrics["event_published"] += 1

    def record_dead_letter(self):
        with self._lock:
            self._metrics["dead_letter_count"] += 1

    @staticmethod
    def _percentile(samples: list, p: float) -> float:
        if not samples:
            return 0.0
        sorted_samples = sorted(samples)
        k = (len(sorted_samples) - 1) * (p / 100.0)
        f = int(k)
        c = min(f + 1, len(sorted_samples) - 1)
        if f == c:
            return float(sorted_samples[f])
        return float(sorted_samples[f] + (sorted_samples[c] - sorted_samples[f]) * (k - f))

    def get_summary(self) -> dict:
        """获取指标摘要（适合 API 返回 / 前端展示）"""
        with self._lock:
            samples = list(self._metrics["latency_samples"])
            total = self._metrics["total_requests"]
            return {
                "total_requests": total,
                "success_rate": round(self._metrics["success_count"] / max(total, 1), 4),
                "failure_count": self._metrics["failure_count"],
                "cache_hit_rate": round(self._metrics["cache_hits"] / max(total, 1), 4),
                "cache_writes": self._metrics["cache_writes"],
                "avg_latency_ms": round(sum(samples) / max(len(samples), 1), 2),
                "p50_latency_ms": round(self._percentile(samples, 50), 2),
                "p95_latency_ms": round(self._percentile(samples, 95), 2),
                "p99_latency_ms": round(self._percentile(samples, 99), 2),
                "intent_distribution": dict(self._metrics["intent_counts"]),
                "agent_usage": dict(self._metrics["agent_usage"]),
                "reflection_count": self._metrics["reflection_count"],
                "hallucination_rejected": self._metrics["hallucination_rejected"],
                "hallucination_review": self._metrics["hallucination_review"],
                "safety_valve_blocked": self._metrics["safety_valve_blocked"],
                "event_published": self._metrics["event_published"],
                "dead_letter_count": self._metrics["dead_letter_count"],
                # B12：token 用量摘要
                "total_prompt_tokens": self._metrics["total_prompt_tokens"],
                "total_completion_tokens": self._metrics["total_completion_tokens"],
                "total_tokens": self._metrics["total_tokens"],
                "tenant_token_usage": dict(self._metrics["tenant_token_usage"]),
                "uptime_seconds": (datetime.utcnow() - self._started_at).total_seconds(),
            }

    def reset(self):
        """重置所有指标（仅供测试用）"""
        with self._lock:
            self._reset()


# 全局单例
metrics_collector = MetricsCollector()


__all__ = ["MetricsCollector", "metrics_collector"]
