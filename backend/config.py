"""应用配置 - 从 .env 读取"""
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 应用
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # JWT（JWT_SECRET 必须为环境变量，禁止硬编码默认值，避免离线伪造 token）
    JWT_SECRET: str
    JWT_EXPIRE_HOURS: int = 1
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    # ─── 数据库路径 ───────────────────────────────────────────────────────────
    DB_PATH: str = "./data/psp.db"
    VEC_DB_PATH: str = "./data/psp_vec.db"

    DB_BACKEND: str = "sqlite"  # "sqlite" | "postgresql"
    BUSINESS_DATABASE_URL: str = ""   # 仅 DB_BACKEND=postgresql 时使用

    # ──────────────────────────────────────────────
    # Phase 3 监管报送外部平台对接（省级药监/卫健报送 API）
    # 留空则仅生成结构化数据包 / 本地导出，不实际外推。
    # ──────────────────────────────────────────────
    REGULATORY_SUBMISSION_ENDPOINT: str = ""   # 外部报送 API base URL
    REGULATORY_SUBMISSION_TOKEN: str = ""      # 外部平台鉴权 token（如 bearer）
    REGULATORY_SUBMISSION_TIMEOUT: float = 30.0

    # AI
    LLM_PROVIDER: str = "mock"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o"
    LLM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    LLM_ENABLE_THINKING: bool = True
    LLM_REASONING_BUDGET: int = 16384
    LLM_TEMPERATURE: float = 1.0
    LLM_TOP_P: float = 0.95
    LLM_MAX_TOKENS: int = 16384
    # B13：工具调用模式 - auto（按 provider 自动）/ native（强制原生 function calling）/ prompt（强制降级）
    LLM_TOOL_CALL_MODE: str = "auto"
    # ──────────────────────────────────────────────
    # 嵌入配置（向量模型）
    # 当前：qwen3（modelscope Qwen3-Embedding-0.6B）
    # 兜底：hash（sklearn HashingVectorizer，零下载）
    # 后期：切到 OpenAI Embedding（text-embedding-3-small/large）
    #   - 改 EMBEDDING_PROVIDER="openai" + EMBEDDING_MODEL="text-embedding-3-small"
    #   - Embedder 自动走 langchain_openai.OpenAIEmbeddings
    # ──────────────────────────────────────────────
    EMBEDDING_PROVIDER: str = "qwen3"  # qwen3 | hash | openai
    EMBEDDING_MODEL: str = "Qwen/Qwen3-Embedding-0.6B"   # modelscope 仓库 id
    EMBEDDING_DIM: int = 1024              # Qwen3-Embedding-0.6B 输出维度
    EMBEDDING_DEVICE: str = "cpu"          # cuda / cpu / mps
    EMBEDDING_MAX_LENGTH: int = 8192       # Qwen3 支持长文本
    # modelscope 缓存目录（None = 走 SDK 默认 ~/.cache/modelscope/hub，
    # 也可通过 MODELSCOPE_CACHE 环境变量覆盖；部署到服务器时建议显式配置）
    MODELSCOPE_CACHE: str | None = None

    # 其他
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = "http://localhost:5173"

    # ──────────────────────────────────────────────
    # 第 13 批：图存储后端（Neo4j 唯一主存）
    # 必须保证 Neo4j 可用：生产环境强制使用 Neo4j，不留 LightGraph 内存回退。
    # ──────────────────────────────────────────────
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "neo4j123"
    NEO4J_DATABASE: str = "neo4j"
    NEO4J_TIMEOUT: float = 5.0
    # 共享 driver 连接池调优（生产并发建议显式配置）
    #  - max_connection_pool_size：driver 同进程并发连接上限（neo4j 默认 100）
    #  - acquire_timeout：从池里拿连接的等待上限（秒，默认 60）
    # 调整建议：
    #  - 高并发场景把 pool 调到 200，acquire_timeout 调到 30
    #  - 资源受限场景 pool 调小到 50
    NEO4J_MAX_POOL_SIZE: int = 100
    NEO4J_ACQUIRE_TIMEOUT: float = 60.0

    # 第 14 批：原 NEO4J_ENABLED 已删除；4 个 store 后端选型字段也删除，
    #          Neo4j 是唯一主存，工厂不识别 sqlite/auto 选项。
    #   替代说明：版本库/溯源库/候选审核库后端 = Neo4j（常量强制）
    #   graph_store / versioning / provenance / governance 全部走 Neo4jConnectionManager 共享 driver。

    # ──────────────────────────────────────────────
    # F1 审批流 SLA 配置（借鉴企业级诊断体系 §7.4）
    # ──────────────────────────────────────────────
    APPROVAL_SLA_NORMAL: int = 48       # 普通审批 2 工作日（小时）
    APPROVAL_SLA_RED: int = 168         # 红灯 7 自然日
    APPROVAL_SLA_BLACK: int = 48        # 黑灯 48h
    APPROVAL_REMINDER_THRESHOLD: float = 0.8  # 剩余 20% 时间触发提醒
    # 默认同意排除项（高风险不允许默认同意），逗号分隔
    DEFAULT_APPROVE_EXCLUDED_TYPES: str = "compliance_violation,appeal_decision,rule_change,black_alert"

    # ──────────────────────────────────────────────
    # F3 任务负载阀门配置（借鉴企业级诊断体系 §9.1）
    # ──────────────────────────────────────────────
    MAX_DAILY_TASKS_PER_USER: int = 10           # 单用户单日新任务上限
    MAX_ACTIVE_TASKS_PER_USER: int = 50          # 单用户在途任务上限
    TASK_QUOTA_DROP_STRATEGY: str = "priority_then_due"  # 超配额丢弃策略

    # ──────────────────────────────────────────────
    # F4 培训效果因果归因配置（B 路径：CEO 培训效果看板）
    # 设计文档：SalesClaw_培训效果因果归因_B路径_规划.md §12
    # ──────────────────────────────────────────────
    # 滞后窗口：培训完成后多久回收 actual 快照（天）。多窗口便于曲线对比。
    TRAINING_LAG_WINDOWS: tuple = (30, 90, 180)
    # 画像显著提升阈值（分）：画像 ≥ 此阈值视为"明显提升"
    TRAINING_LAG_DELTA_THRESHOLD: float = 5.0
    # KPI 显著提升阈值（比例）：相对 baseline 增幅 > 此比例视为"明显提升"
    TRAINING_KPI_DELTA_THRESHOLD_RATIO: float = 0.10
    # 类比组最小样本：treated_n / control_n 任意一端 < 此值时不下结论
    TRAINING_COHORT_MIN_SAMPLE: int = 8
    # AI 归因置信度下限（落库时记录，不达标人工复核）
    TRAINING_EVAL_CONFIDENCE_FLOOR: float = 0.6
    # AI 归因自动触发延迟（小时）：滞后窗口结束 N 小时后自动调用 ai_evaluate
    TRAINING_EVAL_AUTO_RUN_HOURS: int = 24
    # 培训声称目标缺省增量（分）：target_metrics 缺省时按此值
    TRAINING_TARGET_SCORE_DEFAULT: float = 3.0

    @property
    def default_approve_excluded_list(self) -> list[str]:
        """默认同意排除项列表（解析 DEFAULT_APPROVE_EXCLUDED_TYPES）"""
        return [t.strip() for t in self.DEFAULT_APPROVE_EXCLUDED_TYPES.split(",") if t.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    def ensure_dirs(self):
        """确保数据目录存在。

        第 14 批：双库合一后只剩业务库 + 向量库两个目录预创建；Neo4j 库不占本地文件系统。
        """
        for db_path in (self.DB_PATH, self.VEC_DB_PATH):
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def validate_security(self):
        """启动时安全校验，缺失关键密钥直接拒绝启动"""
        if not getattr(self, "JWT_SECRET", None):
            raise RuntimeError(
                "JWT_SECRET 未配置：请在 .env 中设置强随机值"
                "（如 `openssl rand -hex 32`），禁止留空。"
            )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
settings.ensure_dirs()
settings.validate_security()
