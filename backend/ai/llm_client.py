"""统一 LLM 客户端 - 支持 mock/openai 模式

核心能力：
1. Mock 模式：基于关键词的预设响应（复用 INTENT_RESPONSES）
2. 真实模式：OpenAI API 调用
3. 令牌桶限流：rate=2.0, capacity=10
4. 指数退避重试：3 次，区分 429 和 timeout
5. 语义缓存：相似度≥0.92 命中，TTL 1 小时（基于 SQLite）
6. 优雅降级：重试耗尽返回 Mock 响应
7. LLM 调用日志：记录到 LlmCallLog 表
"""
import hashlib
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from config import settings
from database import BusinessSessionLocal, LlmCallLog
from ai.metrics_collector import metrics_collector

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 令牌桶限流
# ──────────────────────────────────────────────

class TokenBucket:
    """令牌桶限流器"""

    def __init__(self, rate: float = 2.0, capacity: int = 10):
        self.rate = rate
        self.capacity = capacity
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, timeout: float = 5.0) -> bool:
        """尝试获取一个令牌，超时返回 False"""
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
                self._last_refill = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True
                wait = (1.0 - self._tokens) / self.rate
            if time.monotonic() + wait > deadline:
                return False
            time.sleep(min(wait, 0.1))


# ──────────────────────────────────────────────
# 语义缓存
# ──────────────────────────────────────────────

class SemanticCache:
    """语义缓存 - 精确 hash + embedding 余弦相似度

    Phase A：模糊匹配从 Jaccard 改为向量余弦（默认 hash embedder，零下载、低延迟）。
    策略：
    - 精确 hash 命中（O(1)）
    - 模糊匹配：embedding cosine ≥ 阈值
    - TTL 1 小时
    """

    def __init__(self, ttl_seconds: int = 3600, similarity_threshold: float = 0.92):
        self.ttl = timedelta(seconds=ttl_seconds)
        self.threshold = similarity_threshold
        self._lock = threading.Lock()
        # 内存缓存：{cache_key: {response, query, ts, embedding}}
        self._store: dict[str, dict] = {}
        self._embedder = None

    def _get_embedder(self):
        """延迟初始化：缓存专用 hash 后端，避免冷启动拉 qwen3。"""
        if self._embedder is None:
            try:
                from embeddings import TextEmbedder
                self._embedder = TextEmbedder(backend="hash", dim=256)
            except Exception as e:
                logger.debug("SemanticCache embedder 初始化失败: %s", e)
                self._embedder = False
        return self._embedder if self._embedder is not False else None

    def _embed(self, text: str):
        embedder = self._get_embedder()
        if embedder is None or not text:
            return None
        try:
            import numpy as np
            vec = embedder.embed([text])[0]
            return np.asarray(vec, dtype=np.float32)
        except Exception as e:
            logger.debug("SemanticCache embed 失败: %s", e)
            return None

    @staticmethod
    def _cosine(a, b) -> float:
        if a is None or b is None:
            return 0.0
        import numpy as np
        a = np.asarray(a, dtype=np.float32).ravel()
        b = np.asarray(b, dtype=np.float32).ravel()
        denom = (float(np.linalg.norm(a)) * float(np.linalg.norm(b))) + 1e-12
        return float(np.clip(np.dot(a, b) / denom, 0.0, 1.0))

    def _cache_key(self, query: str, intent: str = "") -> str:
        raw = f"{intent}:{query.strip().lower()}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def lookup(self, query: str, intent: str = "") -> Optional[dict]:
        """查询缓存"""
        with self._lock:
            key = self._cache_key(query, intent)
            now = datetime.utcnow()

            # 1. 精确匹配
            entry = self._store.get(key)
            if entry and (now - entry["ts"]) < self.ttl:
                return {
                    "response": entry["response"],
                    "cache_hit": True,
                    "cache_similarity": 1.0,
                    "matched_query": entry["query"],
                }

            # 2. 模糊匹配（embedding cosine）
            query_vec = self._embed(query)
            best_score = 0.0
            best_entry = None
            if query_vec is not None:
                for stored in self._store.values():
                    if (now - stored["ts"]) >= self.ttl:
                        continue
                    if stored.get("intent", "") != intent:
                        continue
                    score = self._cosine(query_vec, stored.get("embedding"))
                    if score > best_score:
                        best_score = score
                        best_entry = stored

            if best_entry and best_score >= self.threshold:
                return {
                    "response": best_entry["response"],
                    "cache_hit": True,
                    "cache_similarity": round(best_score, 4),
                    "matched_query": best_entry["query"],
                }

            # 清理过期
            expired = [k for k, v in self._store.items() if (now - v["ts"]) >= self.ttl]
            for k in expired:
                del self._store[k]

            return None

    def write(self, query: str, response: str, intent: str = ""):
        """写入缓存"""
        if not response or len(response.strip()) < 10:
            return
        with self._lock:
            key = self._cache_key(query, intent)
            self._store[key] = {
                "query": query,
                "response": response,
                "intent": intent,
                "embedding": self._embed(query),
                "ts": datetime.utcnow(),
            }
            metrics_collector.record_cache_write()


# ──────────────────────────────────────────────
# LLM 客户端
# ──────────────────────────────────────────────

class LLMClient:
    """统一 LLM 客户端"""

    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.model = settings.LLM_MODEL
        self.api_key = settings.LLM_API_KEY
        self.base_url = settings.LLM_BASE_URL
        self.enable_thinking = settings.LLM_ENABLE_THINKING
        self.temperature = settings.LLM_TEMPERATURE
        self.top_p = settings.LLM_TOP_P
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.bucket = TokenBucket(rate=10.0, capacity=50)  # N+5 阻塞治理：从 2/10 提到 10/50
        self.cache = SemanticCache(ttl_seconds=3600, similarity_threshold=0.92)
        self.max_retries = 3
        self._client = None  # OpenAI client（延迟初始化）

    def _get_openai_client(self):
        """延迟初始化 OpenAI 兼容客户端（支持 Nemotron 等 base_url 自定义的模型）"""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    timeout=60.0,  # N+5 阻塞治理：60s 超时（默认 600s 太长）
                    max_retries=0,  # 禁用 SDK 层重试（由 self.max_retries 控制）
                )
            except ImportError:
                return None
        return self._client

    def _log_call(self, provider: str, model: str, prompt_tokens: int,
                  completion_tokens: int, duration_ms: int, status: str,
                  tenant_id: str = "default"):
        """记录 LLM 调用日志"""
        try:
            db = BusinessSessionLocal()
            try:
                log = LlmCallLog(
                    tenant_id=tenant_id,
                    provider=provider,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    duration_ms=duration_ms,
                    status=status,
                    ts=datetime.utcnow(),
                )
                db.add(log)
                db.commit()
            finally:
                db.close()
        except Exception:
            # 日志失败不影响主流程
            pass

    def _call_openai(self, messages: list, temperature: float = None,
                     max_tokens: int = None, stream: bool = False,
                     intent: str = "", tenant_id: str = "default",
                     trace_id: str = None) -> dict:
        """调用 OpenAI 兼容 API（含重试 + Nemotron 思考链支持）

        Args:
            messages: 消息列表
            temperature: 采样温度，None 时使用 self.temperature
            max_tokens: 最大 token，None 时使用 self.max_tokens
            stream: 是否流式返回；流式模式返回生成器

        Returns:
            非流式：{success, content, reasoning, prompt_tokens, completion_tokens, ...}
            流式：{success, stream: True, iterator: generator}
        """
        client = self._get_openai_client()
        if client is None:
            return {"success": False, "error": "openai 库未安装", "provider": "none"}

        # 参数默认值
        temp = self.temperature if temperature is None else temperature
        max_tok = self.max_tokens if max_tokens is None else max_tokens

        # Nemotron 思考链参数（extra_body）
        # 注意：不带 reasoning_budget —— NVIDIA API 的 V2 model runner 不支持
        # thinking_token_budget，携带该参数会 400 拒绝（2026-08 实测）
        extra_body = None
        if self.enable_thinking:
            extra_body = {
                "chat_template_kwargs": {"enable_thinking": True},
            }

        # N+5 阻塞治理：紧凑退避 + 总超时上限
        RETRY_BACKOFF = [0.5, 1.0, 2.0]  # 替代 2^attempt（1/2/4）
        MAX_TOTAL_TIME = 90.0  # 单次 chat() 总耗时上限 90s
        total_start = time.monotonic()

        last_error = None
        for attempt in range(self.max_retries):
            # 总超时检查
            if time.monotonic() - total_start > MAX_TOTAL_TIME:
                last_error = "total_time_exceeded"
                break
            # 令牌桶限流：不等待，拿不到令牌短退避再试。
            # 限流等待不消耗 attempt（上限约 2s + 受总超时约束）：
            # 此前 0.1s 拿不到令牌就 continue 会快速耗尽 3 次重试并误报 rate_limit_no_token
            got_token = False
            token_waited = 0.0
            while True:
                if self.bucket.acquire(timeout=0.0):
                    got_token = True
                    break
                if (
                    token_waited >= 2.0
                    or time.monotonic() - total_start > MAX_TOTAL_TIME
                ):
                    break
                time.sleep(0.1)
                token_waited += 0.1
            if not got_token:
                last_error = "rate_limit_no_token"
                continue

            try:
                start = time.monotonic()

                # 流式模式：返回生成器
                if stream:
                    stream_iter = client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=temp,
                        top_p=self.top_p,
                        max_tokens=max_tok,
                        extra_body=extra_body,
                        stream=True,
                    )
                    return {
                        "success": True,
                        "stream": True,
                        "iterator": stream_iter,
                        "provider": "openai",
                        "model": self.model,
                        "attempt": attempt + 1,
                    }

                # 非流式：完整响应
                resp = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temp,
                    top_p=self.top_p,
                    max_tokens=max_tok,
                    extra_body=extra_body,
                )
                duration_ms = int((time.monotonic() - start) * 1000)

                content = resp.choices[0].message.content or ""
                # Nemotron 思考链（reasoning_content）
                reasoning = getattr(resp.choices[0].message, "reasoning_content", None) or ""

                # B11：trace_id 关联日志
                _tid = trace_id or "no-trace"
                _ptoks = resp.usage.prompt_tokens if resp.usage else 0
                _ctoks = resp.usage.completion_tokens if resp.usage else 0
                logger.info(
                    "[llm] trace_id=%s intent=%s model=%s ptoks=%d ctoks=%d duration=%dms",
                    _tid, intent, self.model, _ptoks, _ctoks, duration_ms,
                )

                return {
                    "success": True,
                    "content": content,
                    "reasoning": reasoning,
                    "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                    "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
                    "duration_ms": duration_ms,
                    "provider": "openai",
                    "model": self.model,
                    "attempt": attempt + 1,
                }
            except Exception as e:
                last_error = str(e)
                err_str = str(e).lower()
                # timeout：不重试，直接降级（Nemotron reasoning 慢，重试更慢）
                if "timeout" in err_str or "timed out" in err_str:
                    break
                # 429 限流或其他错误：紧凑退避
                backoff = RETRY_BACKOFF[attempt] if attempt < len(RETRY_BACKOFF) else 2.0
                time.sleep(backoff)

        return {"success": False, "error": last_error, "provider": "openai"}

    # ──────────────────────────────────────────────
    # B13：原生 function calling 支持
    # ──────────────────────────────────────────────

    def _tool_call_mode(self) -> str:
        """B13：读取工具调用模式配置

        Returns:
            "auto"（按 provider 自动）/ "native"（强制原生）/ "prompt"（强制降级）
        """
        try:
            from config import settings
            mode = getattr(settings, "LLM_TOOL_CALL_MODE", "auto")
        except Exception:
            mode = "auto"
        if mode not in ("auto", "native", "prompt"):
            mode = "auto"
        return mode

    def _call_openai_with_tools(
        self,
        messages: list,
        tools_schema: list,
        temperature: float = None,
        max_tokens: int = None,
        intent: str = "",
        tenant_id: str = "default",
        trace_id: str = None,
    ) -> dict:
        """B13：原生 function calling 路径

        使用 OpenAI tools 参数让 LLM 原生决定是否调用工具，
        相比 prompt-based 解析更可靠、更省 token。

        Args:
            messages: 消息列表
            tools_schema: OpenAI tools 格式 [{"type":"function","function":{...}}]
            temperature: 采样温度
            max_tokens: 最大 token
            intent: 意图标签（日志用）
            tenant_id: 租户 ID
            trace_id: 链路追踪 ID

        Returns:
            {
                success: bool,
                content: str,                    # 自然语言内容（可能为空）
                tool_calls: list,                # [{id, name, arguments(dict)}]
                prompt_tokens, completion_tokens,
                duration_ms, provider, model,
                fallback_to_prompt: bool,        # True 表示需降级到 prompt 模式
            }
        """
        client = self._get_openai_client()
        if client is None:
            return {
                "success": False,
                "fallback_to_prompt": True,
                "error": "openai 库未安装",
                "provider": "none",
            }

        # api_key 缺失或模型名为空 → 降级到 prompt 模式（避免 OpenAI SDK 抛错）
        if not self.api_key or not self.model:
            return {
                "success": False,
                "fallback_to_prompt": True,
                "error": f"LLM_API_KEY 或 LLM_MODEL 未配置（provider={self.provider}）",
                "provider": self.provider,
            }

        # 无工具 schema → 直接走普通 chat
        if not tools_schema:
            result = self._call_openai(
                messages, temperature, max_tokens, stream=False,
                intent=intent, tenant_id=tenant_id, trace_id=trace_id,
            )
            return {**result, "tool_calls": [], "fallback_to_prompt": False}

        temp = self.temperature if temperature is None else temperature
        max_tok = self.max_tokens if max_tokens is None else max_tokens

        # Nemotron 思考链参数（不带 reasoning_budget，同 _call_openai 注释）
        extra_body = None
        if self.enable_thinking:
            extra_body = {
                "chat_template_kwargs": {"enable_thinking": True},
            }

        start = time.monotonic()
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temp,
                top_p=self.top_p,
                max_tokens=max_tok,
                extra_body=extra_body,
                tools=tools_schema,
                tool_choice="auto",
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            message = resp.choices[0].message
            content = message.content or ""
            reasoning = getattr(message, "reasoning_content", None) or ""

            # 解析 tool_calls
            tool_calls = []
            raw_tcs = getattr(message, "tool_calls", None) or []
            for tc in raw_tcs:
                tc_id = getattr(tc, "id", "") or ""
                fn = getattr(tc, "function", None)
                if fn is None:
                    continue
                fn_name = getattr(fn, "name", "") or ""
                fn_args_str = getattr(fn, "arguments", "") or "{}"
                try:
                    fn_args = json.loads(fn_args_str) if fn_args_str else {}
                except Exception:
                    fn_args = {}
                tool_calls.append({
                    "id": tc_id,
                    "name": fn_name,
                    "arguments": fn_args,
                })

            _tid = trace_id or "no-trace"
            _ptoks = resp.usage.prompt_tokens if resp.usage else 0
            _ctoks = resp.usage.completion_tokens if resp.usage else 0
            logger.info(
                "[llm-native] trace_id=%s intent=%s model=%s ptoks=%d ctoks=%d "
                "tool_calls=%d duration=%dms",
                _tid, intent, self.model, _ptoks, _ctoks,
                len(tool_calls), duration_ms,
            )

            return {
                "success": True,
                "content": content,
                "reasoning": reasoning,
                "tool_calls": tool_calls,
                "prompt_tokens": _ptoks,
                "completion_tokens": _ctoks,
                "duration_ms": duration_ms,
                "provider": "openai",
                "model": self.model,
                "fallback_to_prompt": False,
            }
        except Exception as e:
            err_str = str(e).lower()
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.warning(
                "[llm-native] trace_id=%s failed: %s (duration=%dms) → fallback_to_prompt",
                trace_id or "no-trace", e, duration_ms,
            )
            # 模型不支持 function calling（400/422 错误）→ 降级
            # timeout / 429 也降级（由 prompt 模式的重试机制处理）
            return {
                "success": False,
                "fallback_to_prompt": True,
                "error": str(e),
                "provider": "openai",
                "duration_ms": duration_ms,
            }

    def chat_with_tools(
        self,
        messages: list,
        tools_schema: list,
        intent: str = "",
        tenant_id: str = "default",
        trace_id: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ) -> dict:
        """B13：带工具的 chat（自动按 provider/mode 选 native/prompt）

        Returns:
            native 模式：{success, content, tool_calls, ...}
            prompt 降级模式：{success, content, tool_calls: [], fallback_to_prompt: True}
                             + 调用方应走 prompt-based ToolLoop 解析
        """
        mode = self._tool_call_mode()
        # auto 模式：openai provider → native；mock provider → prompt
        # native 模式：强制走原生（mock provider 仍降级）
        # prompt 模式：强制走普通 chat（返回空 tool_calls，调用方走 prompt 解析）
        if self.provider == "openai" and mode != "prompt":
            return self._call_openai_with_tools(
                messages, tools_schema, temperature, max_tokens,
                intent=intent, tenant_id=tenant_id, trace_id=trace_id,
            )
        # mock 或强制 prompt 模式 → 普通 chat，tool_calls 为空（由 ToolLoop 走 prompt 解析）
        result = self.chat(
            messages, intent=intent, temperature=temperature,
            max_tokens=max_tokens, use_cache=False,
            tenant_id=tenant_id, trace_id=trace_id,
        )
        return {**result, "tool_calls": [], "fallback_to_prompt": True}

    async def chat_with_tools_async(
        self,
        messages: list,
        tools_schema: list,
        intent: str = "",
        tenant_id: str = "default",
        trace_id: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ) -> dict:
        """B13：chat_with_tools 的异步包装（释放事件循环）"""
        import asyncio
        return await asyncio.to_thread(
            self.chat_with_tools,
            messages, tools_schema, intent, tenant_id, trace_id,
            temperature, max_tokens,
        )

    def _call_mock(self, messages: list, intent: str = "") -> dict:
        """Mock 模式 - 返回预设响应"""
        from ai.orchestrator import INTENT_RESPONSES

        start = time.monotonic()
        # 模拟一点延迟
        time.sleep(0.05)
        duration_ms = int((time.monotonic() - start) * 1000)

        response = INTENT_RESPONSES.get(intent)
        if not response:
            # 提取最后一条用户消息
            user_msg = ""
            for m in reversed(messages):
                if m.get("role") == "user":
                    user_msg = m.get("content", "")
                    break
            response = (
                f"我是 AI 助手，已收到您的消息：\"{user_msg[:50]}\"。\n"
                "目前我已理解您的请求，但需要更多信息才能给出精确建议。"
                "您可以尝试询问关于拜访、KPI、课程、知识库等具体问题。"
            )

        return {
            "success": True,
            "content": response,
            "prompt_tokens": len(str(messages)) // 4,
            "completion_tokens": len(response) // 4,
            "duration_ms": duration_ms,
            "provider": "mock",
            "model": "mock-v1",
            "attempt": 1,
        }

    def chat(
        self,
        messages: list,
        intent: str = "",
        temperature: float = None,
        max_tokens: int = None,
        use_cache: bool = True,
        tenant_id: str = "default",
        stream: bool = False,
        trace_id: str = None,
    ) -> dict:
        """主入口 - 调用 LLM（含缓存、重试、降级）

        Args:
            stream: 流式模式（仅 openai provider 支持）。流式模式下返回 {stream: True, iterator}，
                    调用方需自行迭代 iterator 并解析 chunk.choices[0].delta.content / reasoning_content。

        Returns:
            非流式：
                {
                    content: str,          # 响应文本
                    reasoning: str,        # 思考链（Nemotron reasoning_content）
                    provider: str,         # mock/openai
                    cache_hit: bool,       # 是否命中缓存
                    cache_similarity: float,
                    matched_query: str,    # 缓存命中时的原查询
                    prompt_tokens: int,
                    completion_tokens: int,
                    duration_ms: int,
                    degraded: bool,        # 是否降级到 mock
                }
            流式：
                {stream: True, iterator, provider, model}
        """
        # 1. 语义缓存查询（流式模式不查缓存）
        if use_cache and not stream:
            user_msg = ""
            for m in reversed(messages):
                if m.get("role") == "user":
                    user_msg = m.get("content", "")
                    break
            cached = self.cache.lookup(user_msg, intent)
            if cached:
                return {
                    "content": cached["response"],
                    "reasoning": "",
                    "provider": "cache",
                    "cache_hit": True,
                    "cache_similarity": cached["cache_similarity"],
                    "matched_query": cached["matched_query"],
                    "prompt_tokens": 0,
                    "completion_tokens": len(cached["response"]) // 4,
                    "duration_ms": 0,
                    "degraded": False,
                }

        # 2. 根据模式调用
        if self.provider == "mock":
            result = self._call_mock(messages, intent)
        else:
            result = self._call_openai(messages, temperature, max_tokens, stream=stream,
                                       intent=intent, tenant_id=tenant_id, trace_id=trace_id)
            # 流式模式直接返回（不做降级，调用方自行处理）
            if stream:
                return result
            # 真实模式失败 → 降级到 mock
            if not result.get("success"):
                self._log_call(
                    provider=result.get("provider", "openai"),
                    model=self.model,
                    prompt_tokens=0,
                    completion_tokens=0,
                    duration_ms=0,
                    status=f"failed: {result.get('error', '')[:200]}",
                    tenant_id=tenant_id,
                )
                # 降级
                mock_result = self._call_mock(messages, intent)
                mock_result["degraded"] = True
                mock_result["degrade_reason"] = result.get("error", "")
                result = mock_result

        # 3. 记录日志
        self._log_call(
            provider=result.get("provider", "unknown"),
            model=result.get("model", "unknown"),
            prompt_tokens=result.get("prompt_tokens", 0),
            completion_tokens=result.get("completion_tokens", 0),
            duration_ms=result.get("duration_ms", 0),
            status="ok" if result.get("success") else "failed",
            tenant_id=tenant_id,
        )
        # B12：token 用量采集到 metrics_collector
        _ptoks = result.get("prompt_tokens", 0) or 0
        _ctoks = result.get("completion_tokens", 0) or 0
        if _ptoks > 0 or _ctoks > 0:
            try:
                metrics_collector.record_token_usage(
                    prompt_tokens=_ptoks,
                    completion_tokens=_ctoks,
                    tenant_id=tenant_id,
                )
            except Exception:
                pass

        # 4. 写入缓存（仅成功响应、非降级、非流式）
        if result.get("success") and use_cache and not result.get("degraded") and not stream:
            user_msg = ""
            for m in reversed(messages):
                if m.get("role") == "user":
                    user_msg = m.get("content", "")
                    break
            if user_msg:
                self.cache.write(user_msg, result["content"], intent)

        return {
            "content": result.get("content", ""),
            "reasoning": result.get("reasoning", ""),
            "provider": result.get("provider", "unknown"),
            "cache_hit": False,
            "cache_similarity": 0.0,
            "matched_query": None,
            "prompt_tokens": result.get("prompt_tokens", 0),
            "completion_tokens": result.get("completion_tokens", 0),
            "duration_ms": result.get("duration_ms", 0),
            "degraded": result.get("degraded", False),
            # B12：统一 usage 字段（None 表示 mock/缓存命中，无 token 消耗）
            "usage": {
                "prompt_tokens": result.get("prompt_tokens", 0),
                "completion_tokens": result.get("completion_tokens", 0),
                "total_tokens": (result.get("prompt_tokens", 0) or 0)
                                 + (result.get("completion_tokens", 0) or 0),
            } if (result.get("prompt_tokens", 0) or result.get("completion_tokens", 0)) else None,
        }

    def clear_cache(self):
        """清空缓存"""
        self.cache._store.clear()

    # ──────────────────────────────────────────────
    # 异步包装：解决同步 LLM 调用阻塞 asyncio 事件循环问题
    # ──────────────────────────────────────────────

    async def async_chat(self, *args, **kwargs) -> dict:
        """异步调用 chat() - 把同步调用放到线程池执行

        用法：
            result = await llm_client.async_chat(messages=..., intent=...)

        原理：
            asyncio.to_thread 把同步函数丢到默认线程池（40 workers）执行，
            释放 asyncio 事件循环，避免阻塞其他端点。
        """
        import asyncio
        return await asyncio.to_thread(self.chat, *args, **kwargs)

    async def async_stream(self, *args, **kwargs):
        """异步流式调用包装（仅返回元数据，迭代需在同步上下文）

        注意：流式迭代器无法跨线程高效传输，本方法仅包装初始化调用。
        完整流式响应应在同步线程中消费。
        """
        import asyncio
        return await asyncio.to_thread(self.chat, *args, **kwargs)


# 全局单例
llm_client = LLMClient()


__all__ = ["LLMClient", "llm_client", "TokenBucket", "SemanticCache"]
