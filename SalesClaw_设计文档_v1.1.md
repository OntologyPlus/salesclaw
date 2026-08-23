# SalesClaw 详细设计说明书（SDD）

> 文档版本：v1.1
> 适用产品：SalesClaw - 药企医药代表 AI 原生统一平台
> 文档性质：技术 + 架构详细设计说明书（Software Design Description）
> 读者对象：架构师、后端 / 前端 / AI 工程师、测试工程师、运维

---

## 0. 文档说明

### 0.1 编写目的

本文档对 SalesClaw 平台的**系统架构、模块划分、数据模型、接口契约、AI 编排算法、关键流程、安全模型、部署与运维**进行**单一权威**的定义。研发实现、测试用例、运维手册以本文档为依据；若实现与本文档冲突，以本文档为准并通过变更流程修订。

### 0.2 与需求文档的关系

| 维度 | 需求文档 | 设计文档 |
|---|---|---|
| 关注点 | 业务价值、功能全集、验收标准 | 技术实现、架构决策、运行机制 |
| 读者 | 产品、业务、测试 | 开发、运维 |
| 颗粒度 | 业务能力 | 模块 / 类 / 表 / API |

---

## 1. 总体架构

### 1.1 架构总览

```
┌──────────────────────────────────────────────────────────────────────┐
│                            Frontend (Browser)                        │
│  React 18 + TS 5.4 + Vite + Tailwind + Framer Motion + i18n          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │ Portal   │ │ Sales    │ │ Training │ │ Decision │ │ Collab   │ ...│
│  │ Pages    │ │ Pages    │ │ Pages    │ │ Pages    │ │ Pages    │    │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘    │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ AI Embedding Layer: AIAssistantPanel, AIInsightPanel,        │   │
│  │  AIActionButton, ProactiveSuggestions, AISidebar, ReasoningView│  │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────┬────────────────────────────────────────────────┘
                      │ HTTPS / SSE
                      │ Authorization: Bearer <JWT>
┌─────────────────────▼────────────────────────────────────────────────┐
│                       FastAPI Backend                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────────┐  │
│  │ Middleware   │→│ API Router   │→│ 14 个 API 包 (按域拆分)       │  │
│  │ Tenant/Auth/ │ │  /v1/...     │ │ auth/portal/ai/ontology/     │  │
│  │ Logging/     │ └──────────────┘ │ sales/training/decision/     │  │
│  │ ErrorHandler │                  │ collab/knowledge/crm/cfm/    │  │
│  └──────────────┘                  │ tools/platform/mdm/audit/    │  │
│                                    │ observability/settings/      │  │
│                                    └─────────────┬────────────────┘  │
│                                                  │                    │
│  ┌───────────────────────────────────────────────▼──────────────┐    │
│  │              AI Orchestrator (七步状态机)                    │    │
│  │  Guardrails → Cache → Intent → Slot → Agent+Reflection       │    │
│  │  → Hallucination → Persist + Metrics + Event + Reasoning     │    │
│  │  6 类推理意图：diagnose / attribute / derive_paradigm /      │    │
│  │    evaluate / suggest / insight（均落 reasoning_chain_id）   │    │
│  └───────────────────────────────────────────────┬──────────────┘    │
│                                                  │                    │
│  ┌────────────┐ ┌─────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │ 13 业务    │ │ AI 模块层   │ │ Ontology 层  │ │ Core 层      │   │
│  │ Services   │ │ (15 文件)   │ │ (静态注册表) │ │ (公共工具 +  │   │
│  │            │ │            │ │              │ │  ServicePort)│   │
│  └─────┬──────┘ └─────┬──────┘ └──────────────┘ └──────────────┘   │
│        │                │                                             │
│        │    ┌───────────▼──────────────┐                              │
│        │    │    ServicePort 协议层    │  跨域解耦：禁止直接 import   │
│        └────│  registry.get(Port)     │──────────────────────────────│
│             └───────────┬─────────────┘                              │
│                         │                                            │
│             ┌───────────▼─────────────┐                              │
│             │   事件总线因果链        │  causation_id /              │
│             │  + 9 个订阅者           │  affected_domains /          │
│             │  (5 原有 + 4 跨域闭环)  │  correlate()                 │
│             └─────────────────────────┘                              │
└─────────────────────┬────────────────────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────────────────────┐
│                       Data Layer                                     │
│  ┌─────────────────────────┐  ┌─────────────────────────────────┐   │
│  │  Business DB (SQLite)   │  │  Ontology DB (SQLite)           │   │
│  │  psp.db                 │  │  psp_ontology.db                │   │
│  │  30+ 业务表             │  │  Object/Link/Action/Permission  │   │
│  └─────────────────────────┘  └─────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Optional: 迁移到 PostgreSQL（生产环境）                        │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────────────────────┐
│                  External Services (Optional)                        │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐                       │
│  │ LLM API    │ │ SMTP       │ │ Object     │                       │
│  │ (Nemotron/ │ │ (邮件)     │ │ Storage    │                       │
│  │  OpenAI)   │ │            │ │ (附件)     │                       │
│  └────────────┘ └────────────┘ └────────────┘                       │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.2 架构原则

| 原则 | 体现 |
|---|---|
| **AI 原生** | AI 能力不是外挂插件，而是编排器的核心：每个域的页面均嵌入 AI 元素，每个 API 均可被 LLM 调用；进一步引入 AI 学习闭环（apply_feedback 基于建议有效率自动调整洞察权重）；引入门禁驱动 WorkflowSkillExecutor，引入合规 RBAC 阻断 |
| **少量 Agent + 多 Skill** | 6 个域 Agent 持有 26 个 Skill（含 pharma-rep-onboarding / academic-activity-lifecycle），避免 Agent 爆炸 |
| **三层 AI 抽象** | 域 Agent（业务层）→ Skill（能力层）→ Tool（数据层） |
| **高内聚低耦合** | 跨域调用通过 ServicePort Protocol + ServiceRegistry 解耦；跨域直接 import 被 linter 禁止 |
| **功能深度提升及融合** | 4 条跨域闭环事件链：采集→画像→培训、培训→拜访、洞察→派单、接受→反馈；数据流追踪 + 因果链贯穿全栈 |
| **合规双轨制** | 保留销售管理模块（sales 角色）+ 新建学术推广模块（pharma_rep 角色）；医药代表角色禁止调用销售类工具（compute_roi/compute_kpi/积分等） |
| **合规体系** | CSO 委托管理三件套 / 22 项禁止行为规则引擎 / 违规事件 + 合规预警 / 30 日时效扫描 / 学术推广工作流（8 门禁）/ 上岗备案工作流（7 门禁），对应《医药代表管理办法》2026-08-01 施行 |
| **可观测** | 推理链、事件、指标全程落库；增加 DataLineage 数据血缘追踪 |
| **可审计** | 所有写操作 + 所有 AI 输出可追溯；增加因果链可解释性；v2.1 增加链式证据 AuditLog（SHA-256 哈希链） |
| **多租户** | 租户级 `tenant_id` 强制隔离，配置可独立；增加 `Tenant.settings.insight_weights[domain]` 洞察权重持久化 |
| **异步优先** | 所有 I/O 操作异步；同步 LLM 调用通过 `asyncio.to_thread` 包装；LLM 客户端 timeout=60s + max_retries=0 防止阻塞 |
| **配置外置** | 所有可调参数走 .env / 数据库 settings 表，不硬编码 |
| **存储只留主路径**（第 14 批） | 不再有 "SQLite 回退到 Neo4j" 降级；Neo4j 不可达即 fail-fast（运营要求） |
| **共享 driver**（第 13 批） | 4 个 Neo4j store 共享 1 个 driver 实例，连接池上限 `NEO4J_MAX_POOL_SIZE=100` |

### 1.4 数据层重塑

| 子系统 | v1.0 之前 | v1.1 现在 |
|---|---|---|
| 业务库 | `psp.db` | `psp.db`（含 ontology 全部 schema + 历史 ontology 数据） |
| 本体库 | `psp_ontology.db`（独立文件） | **合并到 psp.db**（同引擎 / 同 schema / 同 alembic 树） |
| 图存储（候选层） | Neo4jGraphStore / LightGraph 二选一 | **Neo4jGraphStore 唯一** |
| 版本库 | Neo4jVersionStore / VersionStore 二选一 | **Neo4jVersionStore 唯一** |
| 溯源库 | Neo4jProvenanceStorage / SQLiteStorage 二选一 | **Neo4jProvenanceStorage 唯一** |
| 候选审核库 | Neo4jCandidateStore / CandidateStore 二选一 | **Neo4jCandidateStore 唯一** |
| 向量检索 | Python numpy 算 cosine | **sqlite-vec vec0 + `vec_distance_cosine` SQL** |
| Neo4j 连接 | 4 store 各自 `GraphDatabase.driver()` | **Neo4jConnectionManager 共享单 driver** |

**关键设计**：

- **启动期 fail-fast**：`bootstrap.require_neo4j()` 通过 `Neo4jConnectionManager.latency_probe()` 硬探测；Neo4j 不可达立刻 `RuntimeError`，进程退出 / 容器重启。
- **共享 driver**：4 store（同进程）共享 1 个 `neo4j.Driver` 实例；shutdown 由 `main.py` lifespan 统一 `Neo4jConnectionManager.close_all()`。
- **双库合一**：`database.business_engine is database.ontology_engine`（同一 `Engine`），业务/本体表共享单一 Alembic tree（`alembic/versions/business/`）。
- **数据迁移**：`bootstrap/merge_ontology_to_business.py` 一次性脚本——从源库反推 DDL + 逐表 `INSERT OR IGNORE`；幂等 marker `data/.merge_ontology_to_business.done`；迁移后源库归档为 `*.archived`。
- **归档保留**（30 天观察期）：`data/psp_ontology.db.archived` + `psp_ontology_versions.db.archived` + `psp_provenance.db.archived` + `psp_review.db.archived`。

### 1.5 嵌入式向量检索（第 18 批：sqlite-vec 真主路径）

```
入库：  add(item_id, vector)
        └─→ vec0 虚拟表 item_id TEXT PRIMARY KEY, embedding float[1024]
                └─→ JSON 字符串 "[x0,x1,...]"（Qwen3 dim=1024 时约 8 KB / 行）

检索：  search(query, k)
        └─→ SELECT item_id, vec_distance_cosine(embedding, ?) AS d
            FROM vec_items ORDER BY d ASC LIMIT k
                └─→ similarity = 1 - distance，按 sim 降序返回
                    （全部在 SQLite C 端执行，Python 端仅解析结果行）
```

**为什么改**：v1.0 之前的 path 是 `SELECT item_id, embedding FROM vec_items` 然后 Python 端 `numpy.linalg.norm` + `np.dot`。N 行有 N 次反序列化 + 1024 维矩阵运算；Python 反序列化是 O(N×dim) 级开销。v1.1 把这一步下沉到 SQLite C 端（vec0 扩展 native 实现），Python 端仅做 `1 - d` 转换与 top-k 切片。

**兜底**：vec0 加载失败时（极少数 hardened SQLite 不允许 `enable_load_extension`，如 alpine slim），回退到 BLOB + numpy 算 cosine（保留 degraded path）。

### 1.6 健康探针（第 13 批）

| 端点 | 用途 |
|---|---|
| `GET /health` | 基础健康 + alembic 版本 + neo4j connected/latency（轻量） |
| `GET /health/neo4j` | 深探测：init_info（连接池参数）+ probe（latency_ms）+ counts（4 子系统节点/边统计）+ warning（>200ms red, >100ms yellow） |

两个探针都复用 `Neo4jConnectionManager.latency_probe()` 与 `system_snapshot()`，与 4 store 共用同一连接池，无额外 IO 开销。

### 1.7 技术栈定型

| 层 | 选型 | 理由 |
|---|---|---|
| 后端语言 | Python 3.12 | AI 生态完善（OpenAI SDK、sklearn、PyYAML） |
| Web 框架 | FastAPI | 异步原生、OpenAPI 自动生成、Pydantic 集成 |
| ORM | SQLAlchemy 2.0 | 成熟、类型安全、迁移友好 |
| 数据库 | SQLite（开发）/ PostgreSQL（生产） | 零配置起步，迁移简单 |
| 前端框架 | React 18.3 + TypeScript 5.4 | 生态完善、类型安全 |
| 构建工具 | Vite 5 | 启动快、HMR 流畅 |
| 样式 | Tailwind CSS 3 | 原子化、效率高 |
| 动画 | Framer Motion | 流畅、易用 |
| 状态 | Zustand | 轻量、TS 友好 |
| 国际化 | i18next + react-i18next | 标准方案 |
| LLM | OpenAI 兼容 API | 支持 Nemotron / OpenAI / vLLM 自托管 |
| 密码哈希 | bcrypt 4.x | 安全性高、跨版本兼容 |
| RAG | sklearn TfidfVectorizer + cosine_similarity | 轻量、无外部依赖 |

---

## 2. 目录结构与模块划分

### 2.1 后端目录

```
backend/
├── main.py                         # FastAPI 入口（CORS / 中间件 / 启动钩子）
├── config.py                       # 配置（LLM / DB / 租户 / 业务阈值）
├── database.py                     # 数据模型（3 个 Base + 50+ 表）
├── requirements.txt
├── .env / .env.example
│
├── core/                           # 核心公共工具
│   ├── security.py                 # bcrypt + JWT
│   ├── response.py                 # unified_response 统一响应
│   ├── exceptions.py               # AppException + 错误码
│   ├── pagination.py               # 分页工具
│   ├── validators.py               # 自定义校验器
│   ├── service_ports.py            # 8 个 ServicePort Protocol 协议
│   ├── service_registry.py         # ServiceRegistry 注册表
│   └── constants.py                # 跨域共享常量（MAX_SKILL_DEPENDENCY_DEPTH / ABILITY_DIMENSIONS / DECAY_RATE 等）
│
├── middleware/                     # 中间件层
│   ├── tenant.py                   # 多租户上下文注入
│   ├── auth.py                     # JWT 认证
│   ├── logging.py                  # 结构化日志
│   └── error_handler.py            # 全局异常处理
│
├── ontology/                       # 静态本体注册表
│   ├── objects.py                  # 30+ 业务实体定义
│   ├── links.py                    # 实体关系
│   ├── actions.py                  # 业务操作（含风险等级）
│   └── permissions.py              # 角色权限矩阵
│
├── services/                       # 业务服务层（17 个域 + 数据流服务 + v2.2 合规服务）
│   ├── sales_service.py
│   ├── training_service.py         # 含 recommend_scenarios / apply_session_to_ability
│   ├── profile_service.py          # 综合能力画像 + 5 维能力函数（update_ability_score / apply_decay / detect_weakness）
│   ├── decision_service.py         # 含 穿透 6 函数（attribute_change / simulate / penetrate / derive_recommendations / accept_recommendation / list_recommendations）
│   ├── collab_service.py
│   ├── knowledge_service.py
│   ├── crm_service.py
│   ├── cfm_service.py
│   ├── ai_insight_service.py      # 13 域洞察 + 因果链（generate_causal_insight / trace_to_root_cause）+ AI 学习闭环（apply_feedback）+ AI 原生洞察（ai_generate_insight，经编排器 insight 意图，统一 provenance）
│   ├── collection_service.py      # 采集域规则引擎（validate / derive / check_rules / apply_ability_impact）
│   ├── data_lineage_service.py    # 数据流追踪（record_lineage / trace_upstream / trace_downstream / get_impact_chain）
│   ├── ppt_speech_service.py      # PPT 演讲训战 + 7 维评分（score_session_7d）
│   ├── insight_scheduler.py        # 06:00 定时调度
│   ├── effect_tracking_service.py  # 效果追踪 + 效果计算（_compute_score）+ AI 效果归因评估（ai_evaluate，经编排器 evaluate 意图，落 reasoning_chain_id）
│   ├── ai_paradigm_service.py       # 范式沉淀（derive_paradigm，经编排器 derive_paradigm 意图，落 reasoning_chain_id；失败降级 followup_loop_service.extract_paradigms）
│   ├── observability_service.py
│   ├── audit_service.py
│   ├── platform_service.py
│   ├── mdm_service.py
│   ├── settings_service.py
│   ├── tools_service.py
│   ├── auth_service.py
│   ├── seed_service.py             # 种子数据
│   ├── compliance_service.py       # 合规管理（备案/承诺/链式 AuditLog/22 项规则/违规/预警/30 日时效/上岗准入）
│   ├── academic_activity_service.py # 学术推广活动全生命周期（CRUD/审批/协议/签到/费用/反馈/归档）
│   └── partner_service.py          # CSO 委托管理三件套（合作机构/管理协议/授权书）
│
├── api/                            # 路由层（17 个包，含 v2.2 合规三件套）
│   ├── auth.py                     # /v1/auth/*
│   ├── portal.py                   # /v1/portal/*
│   ├── ai/                         # /v1/ai/*
│   │   ├── __init__.py             # 仅导出 router
│   │   ├── routes.py
│   │   └── schemas.py
│   ├── ontology.py
│   ├── sales/
│   ├── training/
│   ├── decision/
│   ├── collab/
│   ├── knowledge/
│   ├── crm/
│   ├── cfm/
│   ├── tools/
│   ├── platform/
│   ├── mdm/
│   ├── audit/
│   ├── observability/
│   ├── settings/
│   ├── compliance/                 # /v1/compliance/*（备案/承诺/AuditLog/22 项规则/违规/预警/时效/上岗准入）
│   ├── academic/                   # /v1/academic/*（学术推广活动全生命周期）
│   └── partner/                    # /v1/partner/*（CSO 委托管理三件套）
│
└── ai/                             # AI 模块（15 个核心文件 + 子目录）
    ├── orchestrator.py             # 七步状态机主控
    ├── llm_client.py               # LLM 客户端（OpenAI 兼容 + Mock + async）
    ├── intent_classifier.py        # 混合意图分类
    ├── memory_service.py           # 四层记忆
    ├── reasoning_chain.py          # 推理链构建与查询
    ├── self_reflection.py          # 自我反思循环
    ├── hallucination_detector.py   # 4 策略幻觉检测
    ├── safety_valves.py            # 输入/输出安全阀
    ├── event_bus.py                # 事件总线（强/最终一致 + causation_id + affected_domains + correlate）
    ├── event_subscribers.py        # 事件订阅者（9 个：5 原有 + 4 跨域闭环）
    ├── proactive_suggestions.py    # 主动建议引擎（+ record_action / 24h 评估 / effectiveness_score）
    ├── tool_loop.py                # 工具调用循环
    ├── metrics_collector.py        # AI 指标采集
    │
    ├── rag/                        # RAG 检索
    │
    ├── skills/                     # Skill 框架
    │   ├── loader.py               # SKILL.md 三层加载
    │   ├── registry.py             # Skill 注册表
    │   ├── executor.py             # Skill 执行器（支持 depends_on 递归执行，最大深度 5）
    │   └── definitions/            # 24 个 SKILL.md
    │       ├── visit-planner/SKILL.md
    │       ├── course-recommender/SKILL.md
    │       └── ... (共 24 个)
    │
    ├── tools/                      # 工具注册表
    │   └── registry.py             # 30+ 工具
    │
    ├── agents/                     # Agent 框架
    │   ├── base.py                 # Agent 基类（MockAgent）
    │   ├── llm_agent.py            # LLMAgent（真实 LLM）
    │   ├── registry.py             # 6 个域 Agent
    │   └── collaboration.py        # 协作编排（Delegate/Orchestrate/Aggregate）
    │
    ├── actions/                    # Action 注册表
    │   └── registry.py
    │
    └── prompts/                    # 提示词模板
        └── __init__.py
```

**API 包规范**：每个 API 包拆分为 `__init__.py`（仅 `from .routes import router`）、`routes.py`（FastAPI 路由）、`schemas.py`（Pydantic 模型）。

### 2.2 前端目录

```
frontend/
├── index.html
├── package.json / package-lock.json
├── vite.config.ts / tsconfig.json
├── tailwind.config.js / postcss.config.js
│
└── src/
    ├── main.tsx                    # 入口
    ├── App.tsx                     # 根组件 + 路由 + 全局 AI Sidebar
    ├── index.css
    │
    ├── pages/                      # 26+ 页面
    │   ├── auth/LoginPage.tsx
    │   ├── portal/PortalPage.tsx
    │   ├── ai/AIAssistantPage.tsx
    │   ├── ontology/OntologyPage.tsx
    │   ├── sales/                  # SalesRoutes.tsx + 8 页面
    │   ├── training/               # TrainingRoutes.tsx + 7 页面
    │   ├── decision/               # DecisionRoutes.tsx + 6 页面
    │   ├── collab/                 # CollabRoutes.tsx + 4 页面
    │   ├── knowledge/              # KnowledgeRoutes.tsx + 3 页面
    │   ├── crm/CrmPage.tsx
    │   ├── cfm/CfmPage.tsx
    │   ├── tools/ToolsPage.tsx
    │   ├── platform/PlatformPage.tsx
    │   ├── mdm/MdmPage.tsx
    │   ├── settings/SettingsPage.tsx
    │   ├── audit/AuditPage.tsx
    │   ├── observability/ObservabilityPage.tsx
    │   └── profile/                # 综合能力画像（ProfileRoutes.tsx + Page）
    │
    ├── components/
    │   ├── ai/                     # AI 嵌入组件（8 个）
    │   │   ├── AIAssistantPanel.tsx       # AI 对话主面板
    │   │   ├── AIInsightPanel.tsx         # 域 AI 洞察（嵌在 13 个概览页）
    │   │   ├── AIReasoningBadge.tsx       # 推理链标识
    │   │   ├── AIActionButton.tsx         # AI 动作按钮（嵌在 15 个列表页）
    │   │   ├── AISidebar.tsx              # 全局 AI 侧边栏
    │   │   ├── CommandPalette.tsx         # Cmd+K 命令面板
    │   │   ├── ProactiveSuggestions.tsx   # 主动建议（右侧 1/3）
    │   │   └── ReasoningChainView.tsx     # 推理链可视化
    │   ├── layout/                 # Header, Sidebar, Layout, ProtectedLayout
    │   ├── data/                   # DataTable, PageHeader, StatCard
    │   ├── forms/                  # FormField
    │   └── ui/                     # Button, Input, Modal, Tabs, Toast, ...（10 个）
    │
    ├── hooks/                      # 自定义 Hooks
    │   ├── useAI.ts                # 普通 AI 调用
    │   ├── useAIStream.ts          # SSE 流式（10 事件类型解析）
    │   ├── useFetch.ts             # 通用 GET 包装
    │   ├── useTheme.ts             # 主题切换
    │   └── useToast.ts             # Toast 通知
    │
    ├── services/                   # API 客户端（13 个）
    │   ├── api.ts                  # Axios 实例（拦截器 + 错误处理）
    │   ├── auth.ts, sales.ts, training.ts, decision.ts, collab.ts,
    │   ├── knowledge.ts, crm.ts, cfm.ts, tools.ts, platform.ts,
    │   ├── mdm.ts, audit.ts, observability.ts, ontology.ts,
    │   ├── profile.ts, settings.ts, effectTracking.ts, ai.ts
    │
    ├── stores/                     # Zustand 状态
    │   ├── auth.ts, app.ts
    │   ├── aiAssistant.ts          # AI 对话历史
    │   └── commandPalette.ts
    │
    ├── i18n/                       # 国际化
    │   ├── index.ts
    │   ├── zh-CN.json              # 默认
    │   └── en.json
    │
    └── types/                      # 共享 TypeScript 类型
        └── index.ts
```

### 2.3 模块依赖图

```
                    ┌─────────────┐
                    │  main.py    │
                    └──────┬──────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
      ┌──────────┐  ┌──────────┐  ┌──────────┐
      │ Middleware│  │ API      │  │ Startup  │
      │  (4 个)   │  │ Router   │  │ Hook     │
      └────┬─────┘  └────┬─────┘  └────┬─────┘
           │             │             │
           │             ▼             │
           │      ┌──────────┐         │
           │      │ Services │         │
           │      │ (18 个)  │         │
           │      └────┬─────┘         │
           │           │               │
           │     ┌─────▼─────┐         │
           │     │ Database  │◄────────┤
           │     │ (50+ 表)  │         │
           │     └───────────┘         │
           │                           ▼
           │                    ┌────────────┐
           ▼                    │ Insight    │
      ┌──────────────┐          │ Scheduler  │
      │  AI          │          └────────────┘
      │ Orchestrator │
      └──────┬───────┘
             │
   ┌─────────┼─────────┬──────────┬──────────┬──────────┐
   ▼         ▼         ▼          ▼          ▼          ▼
 Intent   Memory   Reasoning  Reflection Hallucin.  Event Bus
Classif.  Service  Chain     Loop       Detector
   │         │         │          │          │          │
   └─────────┴─────────┴──────────┴──────────┴──────────┘
                            │
                  ┌─────────┼─────────┐
                  ▼         ▼         ▼
              Skills     Tools     Agents
              (24)      (30+)     (6 + collab)
```

---

## 3. 数据模型设计

### 3.1 总体设计原则

1. **多租户隔离**：所有业务表均含 `tenant_id`，建索引
2. **软删除**：所有业务表均含 `is_deleted` (0/1) + `deleted_at`
3. **审计字段**：`created_at / updated_at / created_by / updated_by`（混入 `BaseFields`）
4. **业务主键**：自增 `Integer`（不用 UUID，提升性能）
5. **关联主键**：外键 + 索引
6. **JSON 字段**：用 SQLAlchemy `JSON` 类型存半结构化数据（设置 / 复杂 payload）
7. **时间字段**：数据库存 UTC，应用层转本地

### 3.2 核心表 ER 概要

```
┌─────────┐      ┌──────────────┐      ┌──────────────┐
│ Tenant  │1───N│    User      │N───M│    Role      │
└─────────┘      └──────┬───────┘      └──────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
  ┌──────────┐    ┌──────────┐     ┌──────────┐
  │VisitPlan │    │Course    │     │ChatSession│
  │(1:N)     │    │          │     │          │
  └────┬─────┘    └────┬─────┘     └────┬─────┘
       │               │                │
       ▼               ▼                ▼
  ┌──────────┐    ┌──────────┐     ┌──────────┐
  │VisitRecd │    │Learning  │     │ChatMessage│
  │          │    │Progress  │     │          │
  └────┬─────┘    └──────────┘     └──────────┘
       │                                │
       ▼                                ▼
  ┌──────────┐                    ┌──────────────┐
  │VisitFdbk │                    │ReasoningChain│
  └──────────┘                    └──────┬───────┘
                                          │
                                          ▼
                                    ┌──────────────┐
                                    │  AIEvent     │
                                    └──────────────┘
```

### 3.3 关键表结构（节选）

所有业务表均混入 `BaseFields`（见 §3.1）：`id`（自增 PK）、`tenant_id`（索引）、`is_deleted`（软删）、`deleted_at`、`created/updated_at`、`created/updated_by`。

**销售域**

| 表 | 关键字段 | 说明 |
|---|---|---|
| `visit_plans` | `user_id, plan_date, period, status, total_items, notes` | 拜访计划 |
| `visit_records` | `plan_id, hospital_id, doctor_id, product_id, visit_date, duration_min, content, raw_text, sentiment` | 拜访记录 |
| `visit_feedback` | `record_id, doctor_id, sentiment(positive/neutral/negative), objections(JSON), action_items(JSON), importance` | 拜访反馈（异议/待办） |

**培训域**

| 表 | 关键字段 | 说明 |
|---|---|---|
| `courses` | `title, category, difficulty, duration_min, is_mandatory, description` | 课程 |
| `learning_paths` | `name, template_type, course_ids(JSON), milestones(JSON)` | 学习路径 |

**决策域**

| 表 | 关键字段 | 说明 |
|---|---|---|
| `kpi_definitions` | `code, name, target_value, unit, owner_role` | KPI 定义 |
| `simulation_scenarios` | `name, variables(JSON), predicted_kpi(JSON), confidence_lower/upper` | 模拟推演 |
| `executions` | `suggestion_id, user_id, accepted, completed, improved, baseline_kpi, final_kpi` | 建议效果追踪 |

**AI 元数据**

| 表 | 关键字段 | 说明 |
|---|---|---|
| `chat_sessions` | `id(VARCHAR PK), user_id, title, last_active_at` | 会话 |
| `chat_messages` | `session_id, role, content, agent_used, intent, reasoning_chain_id, latency_ms` | 消息 |
| `reasoning_chains` | `user_id, query, intent, agent, steps(JSON), hallucination_score, rating, feedback_text` | 推理链 |
| `ai_events` | `event_type, payload(JSON), status(pending/processed/failed/dead_lettered), attempts, last_error` | AI 事件 |
| `dead_letter_queue` | `event_id, failure_reason, attempts, resolved, resolved_by, resolved_at, resolution_note` | 死信队列 |
| `ai_insight_cache` | `domain, insight_date, content, metrics(JSON), generated_at`；唯一键 `(tenant_id, domain, insight_date)` | 洞察缓存 |

**索引策略**：`users(tenant_id, username)`、`visit_records(tenant_id, visit_date)`、`visit_feedback(tenant_id, record_id)`、`courses(tenant_id, category)`、`ai_events(tenant_id, status, event_type)`、`reasoning_chains(tenant_id, user_id, created_at)`。

### 3.4 迁移机制

历史：v1.0 文档原采用 `main.py._migrate_*` 手写函数链启动期扫表升级（`_migrate_weekly_report` / `_migrate_data_lineage` / `_migrate_ability_profile` / `_migrate_collection_template_rules` / `_migrate_decision_recommendation` 等十余个手写迁移函数，参见 §15 演进路线）。

**当前（第 14-15 批起）：集中式迁移 = Alembic + 一次性数据脚本。**

执行流程（`bootstrap.run_startup()` 内）：

1. `settings.ensure_dirs()` —— 业务库 / 向量库目录
2. `require_neo4j()` —— **fail-fast**：Neo4j 不可达即抛 `RuntimeError`（运营要求"必须保证 Neo4j 可用"）
3. `database.init_db()` —— `BusinessBase.metadata.create_all(business_engine)` + `OntologyBase.metadata.create_all(business_engine)`（单 schema / 双 base / 同引擎） + `run_migrations()`（创建索引兜底）+ `seed_default_data()`
4. `alembic_run.upgrade_to_head(['business'])` —— **单 tree**（`alembic/versions/business/`）；第 15 批起 `ontology` section 已删
5. （一次性，仅历史部署）`bootstrap/merge_ontology_to_business.py` —— 把 `psp_ontology.db` 1325 行迁入 `psp.db`；幂等 marker `data/.merge_ontology_to_business.done`

策略：

- **ORM 兜底**：`create_all` 对已存在表是 no-op；正常情况下 Alembic 已升级到 head。
- **不破坏性**：只增不删；字段类型变更需手写迁移脚本（落 `alembic/versions/business/`）。
- **种子数据**：`seed_service.py` 在 `init_db` 后填充（用户、产品、医院、医生、KPI 定义、Skill 等）。

### 3.5 新增表结构

| 表 | 关键字段 | 说明 |
|---|---|---|
| `data_lineage` | `source_type/source_id, target_type/target_id, transformation(record_create/ability_update/...), payload(JSON), causation_id, affected_domains(JSON), user_id, occurred_at` | 数据流追踪；索引 `(source_type, source_id)`、`(target_type, target_id)` |
| `insight_chains` | `insight_id, domain, chain(JSON 三层 root/intermediate/surface), root_cause, natural_language_conclusion` | 洞察因果链 |
| `ability_profiles` | `user_id, dimension(5 维), score(默认 50.0), last_updated_at, evidence(JSON)`；唯一键 `(tenant_id, user_id, dimension)` | 5 维能力画像 |
| `profile_history` | `user_id, dimension, old/new/delta_score, source, source_id, evidence(JSON), occurred_at` | 画像变更历史 |
| `suggestion_actions` | `suggestion_id, user_id, action_type(accepted/rejected/dismissed), suggestion_type, executed_at, evaluate_after(now+24h), evaluated_at, effectiveness_score(0-1), evaluation_payload(JSON)` | 建议行动 + 24h 评估 |
| `decision_recommendations` | `insight_id, insight_chain_id, target_user_id, domain(sales/training/collection), priority(high/medium/low), title, suggested_action, action_params(JSON), status(pending/accepted/rejected/expired), expires_at` | 可派单决策建议 |

### 3.6 合规基础表

| 表 | 关键字段 | 说明 |
|---|---|---|
| `pharma_rep_profiles` | `user_id, registration_no(备案号), registration_status(draft/submitted/confirmed/revoked/deleted/pending_change), id_card_*, gender, photo_url, education_level, major, contract_start/end, drug_categories(JSON), therapeutic_areas(JSON), authorized_regions(JSON), authenticity_statement, has_bribery_record, bribery_record_detail, revoke_scheduled_at(撤销后 30 日内删除)` | 医药代表资质档案（第 14-18 条）；索引 `(tenant_id, user_id)`、`(tenant_id, registration_status)` |
| `compliance_commitments` | `user_id, commitment_type(onboarding/annual/specific), commitment_text, version, course_id, exam_record_id, signed_at, signer_ip, signer_ua` | 合规承诺书（第 9、10、15 条） |

> `audit_logs` 表追加扩展字段（链式证据，第 26 条）：`prev_hash`、`record_hash`、`actor_role`、`is_compliance_critical`（默认 0）。

### 3.7 合规体系扩展表

| 表 | 关键字段 | 说明 |
|---|---|---|
| `partner_organizations` | `org_code, org_name, org_type(CSO/Distributor/Agency), credit_code, contact_*, banking_account, contract_start/end, status(active/suspended/terminated)` | CSO 委托合作机构（第 8 条） |
| `management_agreements` | `agreement_no, partner_org_id(FK), holder_tenant_id, start/end_date, scope(JSON), status(draft/signed/active/expired/terminated), signed_at` | 医药代表管理协议（第 8 条三件套之一） |
| `authorization_letters` | `letter_no, partner_org_id, agreement_id, pharma_rep_user_id, authorized_products(JSON), authorized_regions(JSON), authorized_period(JSON), status(draft/issued/active/revoked/expired), issued_at, revoked_at, revoke_reason` | 医药代表授权书（第 8 条三件套之二） |
| `compliance_violation_rules` | `code(A11_1/A12_3...), article, subject(持有人/CSO/医药代表/医疗机构), description, severity(critical/high/medium/low), trigger_scenes(JSON), check_type(keyword/forbidden_action/role_blacklist/amount_limit), check_config(JSON), is_active` | 22 项禁止行为规则配置（第 11、12、24、25 条）；索引 `(tenant_id, subject, is_active)` |
| `compliance_violation_events` | `rule_code, rule_id, scene, actor_id, actor_role, target_type/id, evidence(JSON), severity, status(pending/investigating/resolved/dismissed), handle_result, handled_by/at` | 违规事件 |
| `academic_activities` | `activity_code, title, activity_type(congress/salon/webinar/hospital_meeting), holder_tenant_id, organizer_org_id, sponsor_org_id, planned/actual_date, planned_location, planned/actual_attendees, status, protocol_url(协议流), checkin_count(签到流), expense_total(费用流), feedback_summary, approved_by/at` | 学术推广活动（第 19-22 条，三流合一） |
| `compliance_alerts` | `alert_type(deadline_change/deadline_revoke/violation/overdue), severity, source_type/id, title, description, deadline_at(第 17 条 30 日时效), days_left, status(pending/acknowledged/resolved/ignored), handle_result, handled_by/at` | 合规预警；索引 `(tenant_id, status, deadline_at)` |

**Phase 2 迁移函数链**（在 `startup()` 内按序调用，位于 `init_db()` 之后，均幂等）：`_migrate_phase2_partner_tables()`（三张 CSO 表）、`_migrate_phase2_compliance_rule_tables()`（规则/事件/预警三张表）、`_migrate_phase2_academic_activity()`（学术活动表）、`_migrate_phase2_seed_violation_rules()`（22 项规则 seed 入库）。

**Phase 2 迁移函数链**（在 startup() 内按序调用，位于 init_db() 之后）：
- `_migrate_phase2_partner_tables()` — 三张 CSO 表幂等校验
- `_migrate_phase2_compliance_rule_tables()` — 规则/事件/预警三张表
- `_migrate_phase2_academic_activity()` — 学术活动表
- `_migrate_phase2_seed_violation_rules()` — 22 项规则 seed 入库

---

## 4. 中间件设计

### 4.1 请求处理管道

```
Request
  │
  ▼
┌─────────────────┐
│ CORSMiddleware  │  跨域
└────────┬────────┘
         ▼
┌─────────────────┐
│ TenantMiddleware│  从 JWT 提取 tenant_id，挂到 request.state
└────────┬────────┘
         ▼
┌─────────────────┐
│ LoggingMiddleware│  生成 request_id，记录开始/结束/耗时
└────────┬────────┘
         ▼
┌─────────────────┐
│ get_current_user │  校验 JWT，挂到 user（Depends）
│   (依赖项)       │
└────────┬────────┘
         ▼
┌─────────────────┐
│   Route Handler │
└────────┬────────┘
         ▼
┌─────────────────┐
│ ExceptionHandler│  AppException / ValidationError / 兜底
└─────────────────┘
         │
         ▼
       Response
```

### 4.2 错误码体系

| 范围 | 类型 | 示例 |
|---|---|---|
| 0 | 成功 | 0 |
| 1xxxx | 通用 | 10001=参数错误 |
| 2xxxx | 业务 | 20001=用户不存在 |
| 3xxxx | 权限 | 30001=未登录 |
| 4xxxx | 资源 | 40001=资源不存在 |
| 5xxxx | 系统 | 50000=服务器错误 |

### 4.3 统一响应格式

由 `core/response.py` 的 `unified_response(data, code=0, message="ok")` 统一封装为 `{"code", "message", "data"}` 三层结构；前端 axios 拦截器统一处理：`code != 0` 时弹出 toast 提示。

---

## 5. 认证与权限

### 5.1 认证流程

```
┌────────┐                ┌────────┐                ┌────────┐
│ Client │── POST /login─▶│  Auth  │── SELECT user ─│   DB   │
│        │                │  API   │                │        │
│        │                │        │── bcrypt.check  │        │
│        │                │        │                │        │
│        │◀─ {access_tk, ─│        │                │        │
│        │    refresh_tk} │        │                │        │
│        │                │        │                │        │
│        │── GET /v1/... ─▶        │                │        │
│        │  Authorization: │        │                │        │
│        │  Bearer <jwt>   │        │                │        │
└────────┘                └────────┘                └────────┘
```

### 5.2 JWT 设计

- 算法：HS256
- payload：`{user_id, tenant_id, role, exp, iat}`
- access_token 过期：1h
- refresh_token 过期：24h
- 密钥：从 `.env.JWT_SECRET` 读取（生产环境必须用强随机）

### 5.3 密码哈希

`core/security.py` 使用 bcrypt：`hash_password` 经 `bcrypt.gensalt()` 加盐后生成哈希串，`verify_password` 用 `bcrypt.checkpw` 校验。

**兼容性**：bcrypt 4.x 同时支持 `$2b$ / $2a$ / $2y$ 三种前缀，存量 passlib 哈希可平滑迁移。

### 5.4 多租户隔离

`TenantMiddleware`（继承 `BaseHTTPMiddleware`）在 `dispatch` 中从 `Authorization` 头解析 JWT（HS256，密钥取自 `settings.JWT_SECRET`），将 `tenant_id / user_id / role` 挂到 `request.state`，随后放行请求。服务层所有查询强制追加 `tenant_id` 过滤（约定 + lint 规则），确保租户数据隔离。

### 5.5 权限模型

| 层 | 实现 |
|---|---|
| API 层 | Depends 注入校验登录 + 角色；合规 / 知识模块路由进一步接入 `require_permission` 细粒度校验（只读接口校验 `*.read`、写接口校验 `*.write`，权限矩阵见 `backend/ontology/permissions.py`） |
| 业务层 | 服务方法显式检查角色 |
| 数据层 | tenant_id 强制隔离 |
| Action 层 | ontology.permissions 矩阵查询 |

---

## 6. AI 编排器设计（核心）

### 6.1 七步状态机

```
                          ┌─────────────────────┐
                          │   用户输入 message   │
                          └──────────┬──────────┘
                                     ▼
                          ┌─────────────────────┐
                  ┌───────│ Step 1: Guardrails  │  prompt 注入防御
                  │       │  - 长度限制          │
                  │       │  - 注入模式正则       │
                  │       └──────────┬──────────┘
                  │ 失败             ▼
                  │       ┌─────────────────────┐
                  │       │ Step 2: Cache       │  TF-IDF 相似度查询
                  │       │  - threshold=0.85   │
                  │       └──────────┬──────────┘
                  │ 命中             ▼
                  │       ┌─────────────────────┐
                  │       │ Step 3: Intent      │  混合分类（规则+LLM）
                  │       │  - 4 级仲裁         │
                  │       └──────────┬──────────┘
                  │                  ▼
                  │       ┌─────────────────────┐
                  │       │ Step 4: Slot        │  实体/时间/动作抽取
                  │       └──────────┬──────────┘
                  │                  ▼
                  │       ┌─────────────────────┐
                  │       │ Step 4.5: Safety    │  输入安全阀
                  │       │  - 角色权限          │  拦截
                  │       │  - 敏感操作          │
                  │       └──────────┬──────────┘
                  │ 拦截             ▼
                  │       ┌─────────────────────┐
                  │       │ Step 5: Agent+Reflect│  Agent 派发
                  │       │  - 复合意图 → 协作   │  + Self-Reflection
                  │       │  - 单意图 → ToolLoop │  循环
                  │       │  - 反思 ≤ 3 次       │
                  │       └──────────┬──────────┘
                  │                  ▼
                  │       ┌─────────────────────┐
                  │       │ Step 6: Hallucin.   │  4 策略检测
                  │       │  - 实体 / 关系 /     │
                  │       │    来源 / 口径       │
                  │       │  - refuse / review   │
                  │       └──────────┬──────────┘
                  │                  ▼
                  │       ┌─────────────────────┐
                  │       │ Step 7: Persist     │  写缓存
                  │       │  - 指标采集         │  + 记忆存储
                  │       │  - 事件发布         │  + 推理链
                  │       └──────────┬──────────┘
                  │                  ▼
                  │       ┌─────────────────────┐
                  └──────▶│      Response        │
                          └─────────────────────┘
```

**关键代码路径**：`backend/ai/orchestrator.py::Orchestrator.chat()` / `stream_chat()`

### 6.2 意图分类

`ai/intent_classifier.py::IntentClassifier.classify()` 采用三级混合分类：
1. **规则匹配**（毫秒级）：置信度 > 0.9 直接返回；
2. **LLM 分类**：仅当规则置信度 < 0.5 时调用（mock 模式降级）；
3. **冲突仲裁**：规则与 LLM 意图不一致时，`_arbitrate` 裁决。

**24 个意图**：`visit / coverage / feedback / scoring / roi / matrix / kol / course / exam / live / path / scene / practice / kpi / attribution / simulation / alert / task / approval / meeting / report / knowledge / rag / outsend`

### 6.3 槽位提取

| 槽位类型 | 提取方式 | 示例 |
|---|---|---|
| 时间范围 | 正则（本周 / 本月 / 近 N 天） | "近 7 天" → `{time_range: "days", days: 7}` |
| 动作类型 | 关键词（创建 / 查询 / 更新 / 删除） | "查询我的拜访" → `{action: "query"}` |
| 医生名 | 正则（X 医生 / X 教授） | "张主任" → `{doctor_name: "张"}` |
| 医院名 | 正则（X 医院 / 卫生院） | "协和医院" → `{hospital_name: "协和医院"}` |
| 指标名 | 关键词表 | "拜访达成率" → `{metric_name: "拜访达成率"}` |

### 6.4 Agent + Skill 映射

三类映射表：`INTENT_KEYWORDS`（28 个意图关键词表，含 4 个 AI 原生推理意图）、`DOMAIN_AGENT_MAP`（domain → Agent 名称）、`INTENT_SKILL_MAP`（intent → Skill 名称）。

**28 个意图分布**：
- 业务/工作流意图：24 个（visit / training / diagnose / attribute / query / …）
- AI 原生推理意图（见 §6.24）：4 个 —— `derive_paradigm` / `evaluate` / `suggest` / `insight`，均路由到 `decision` 域 `DecisionAgent`，与 `diagnose`/`attribute` 同构。

**映射链**：
```
用户消息
  → intent_classifier.classify() → intent="visit"
  → DOMAIN_AGENT_MAP["sales"] = "SalesAgent"
  → INTENT_SKILL_MAP["visit"] = "visit-planner"
  → skill_loader.load_skill_context("visit-planner") → L2 指令
  → SkillExecutor.execute("visit-planner") → 调用 LLM + Tool
  → LLM 返回响应 → 持久化
```

### 6.5 工具调用循环

`ai/tool_loop.py::ToolLoop.run()` 最多执行 `max_rounds=5` 轮：每轮由 LLM 决策调用哪个工具或直接输出答案——若有 `tool_calls`，依次执行工具并将结果回写 messages；否则返回最终答案。超出最大轮次则返回降级提示。

**异步化**：`run()` 为同步实现，外层用 `asyncio.to_thread()` 包装，避免阻塞事件循环。

### 6.6 Self-Reflection

`ai/self_reflection.py::SelfReflectionEngine`：
- `should_retry(response, current_retry)`：当置信度估计 < 0.6 且重试次数 < 3 时返回 `True`；
- `build_retry_prompt(...)`：把上一次回答拼入提示，要求重新审视、更具体准确地改进。

### 6.7 幻觉检测（4 策略）

`ai/hallucination_detector.py::HallucinationDetector.detect()` 对响应做四项打分取平均，按阈值给出处置建议：
1. **实体一致性** `_entity_check`（对照本体 `ontology_data`）
2. **关系一致性** `_relation_check`
3. **来源可引用** `_source_check`（对照 `context`）
4. **数字口径** `_metric_check`

| 平均分数 | 处置 |
|---|---|
| < 0.3 | `refuse`（拒绝） |
| 0.3–0.6 | `review`（人工复核） |
| ≥ 0.6 | `accept`（接受） |

### 6.8 多 Agent 协作

`ai/agents/collaboration.py::CollaborationOrchestrator` 支持三种协作模式：
- **detect_collaboration_need**：关键词探测（如消息同时含"销售"+"培训"→ 委派；含"总结"+"建议"→ 聚合）。
- **delegate**：Supervisor 拆解任务 → 并行分派子 Agent → 聚合（`_synthesize`）。
- **orchestrate**：管道串联，逐 Agent 顺序处理。
- **aggregate**：多 Agent 独立处理 → 合并/投票（`_merge`，支持 `merge` 等策略）。

### 6.9 Skill 三层加载

```yaml
# backend/ai/skills/definitions/visit-planner/SKILL.md
---
name: visit-planner
display_name: 拜访计划助手
domain: sales
description: 基于分管医生、最近拜访、反馈情感推荐今日拜访
trigger_intents: [visit]
agent: SalesAgent
version: 1.0
---

# L2: 指令层
当用户询问"拜访"相关时：
1. 查询用户分管的医生列表（CoverageAssignment）
2. 反查近 30 天 VisitRecord，识别未拜访医生
3. 查询近期 VisitFeedback，识别负面反馈
4. 按优先级排序输出 top 10

# L3: 资源层
## 激活的 Objects
- Doctor, Hospital, CoverageAssignment
## 激活的 Links
- doctor_coverage, hospital_doctor
## 激活的 Actions
- list_visit_plans, create_visit_plan
```

**加载时机**：
- L1（目录）：应用启动时全量加载（24 个 Skill 的元信息）
- L2（指令）：意图路由匹配时加载（仅当前 Skill）
- L3（资源）：Skill 执行时按需加载（OAG 上下文）

### 6.10 异步 LLM 调用

`ai/llm_client.py::LLMClient` 提供三种调用方式：
- `chat()`（同步，仅内部）：mock 模式走 `_mock_chat`，否则走 `_openai_chat`；
- `async_chat()`（异步，推荐）：用 `asyncio.to_thread` 包装同步调用，避免阻塞事件循环；
- `chat_stream()`（流式生成器）：mock 返回整段，否则 `_openai_chat_stream`。

**关键设计**：暴露给编排器的接口均为 `async def`，同步 LLM SDK 调用经 `asyncio.to_thread` 丢到线程池。

### 6.11 推理链

`ai/reasoning_chain.py::ReasoningChainBuilder.build()` 将七步流水线固化为 `ReasoningChain` 记录（步骤以 JSON 存储，含 `guardrails/cache/intent/slot/agent/hallucination` 各步结果与 `hallucination_score`），落库后返回 `chain_id` 供前端回溯。

**前端可视化**（`ReasoningChainView.tsx`）：折叠式步骤列表 + 置信度条形图 + 5 星评分入口。

### 6.12 主动建议

`ai/proactive_suggestions.py::ProactiveSuggestionsEngine.generate()` 依据多类触发条件生成建议：Trigger 1（30 天未拜访）、Trigger 2（负面反馈）、Trigger 3（能力短板）、Trigger 4（KPI 异常）等，每条含 `id/type/priority/title/reason/action` 并排序后返回（如未拜访取 top 3，跳转 `/sales/plans?doctor_id=...`）。

**前端组件**（`ProactiveSuggestions.tsx`）：右侧 1/3 面板，7 张优先级排序的卡片，点击直接跳转。

### 6.13 事件总线 + Write-Back

`ai/event_bus.py::EventBus`：
- `publish(event_type, payload, tenant_id, consistency)`：写入 `AIEvent`（`consistency="eventual"` 时状态 `pending`，否则 `processing` 并同步 `_execute`）。
- `_execute(event, db)`：调用 `WriteBackEngine.execute` 回写业务表；异常时 `attempts+1`，达到 3 次进入死信队列（`DeadLetterQueue`，状态 `dead_lettered`）。

**12 种事件**：`safety_valve_blocked / reflection_retried / hallucination_rejected / course_completed / visit_recorded / feedback_negative / kpi_dropped / alert_raised / training_enrolled / exam_failed / approval_pending / knowledge_outdated`

**后台消费者**（`main.py._process_pending_events`）：`while` 循环每 30s 调用 `event_bus.process_pending(db, batch_size=10)` 拉取一批 `pending` 事件异步执行。

### 6.14 洞察预生成

`services/insight_scheduler.py`：`daily_insight_generation()` 每日 06:00 为所有租户的 13 个域（`SUPPORTED_DOMAINS`）调用 `ai_insight_service.generate`，结果以 `db.merge`（upsert）写入 `ai_insight_cache` 缓存表；`start_insight_scheduler()` 用 `schedule` 注册定时任务并起后台守护线程轮询。

**页面查询**：`GET /v1/{domain}/ai-insights` → 直接查 `ai_insight_cache` 表（< 5ms）。

### 6.15 ServicePort 协议层

跨域调用通过 Python `Protocol`（鸭子类型）+ `ServiceRegistry` 解耦，**禁止业务服务之间直接 import**。共定义 8 个 ServicePort（实际 5 个核心示例如下），`main.py startup()` 中统一 `registry.register(port, impl)`，`get()` 未命中返回 `None` 实现安全降级。

| ServicePort | 关键方法 |
|---|---|
| `ProfileServicePort` | `update_ability_score / apply_decay / get_ability_summary / get_weakest_dimensions / detect_weakness(threshold=70)` |
| `CollectionServicePort` | `apply_ability_impact / validate_item_values / compute_derived_fields` |
| `TrainingServicePort` | `recommend_scenarios / apply_session_to_ability` |
| `DecisionServicePort` | `derive_recommendations / accept_recommendation` |
| `DataLineageServicePort` | `record_lineage / trace_upstream / trace_downstream / get_impact_chain` |

**业务层调用约定**：正确方式为 `registry.get(ProfileServicePort)`（判空后调用）；`from services.profile_service import detect_weakness` 此类直接 import 被 linter 禁止。

### 6.16 数据流追踪与洞察因果链

#### 6.16.1 DataLineage 数据血缘

`services/data_lineage_service.py`：
- `record_lineage(db, source, target, transformation, ...)`：写入 `DataLineage` 记录（`transformation` 取值如 `record_create / ability_update / insight_generate`，`payload` 存 source/target 快照）。
- `trace_upstream(db, target_type, target_id)`：按 `occurred_at` 倒序返回某实体的全部上游来源。

#### 6.16.2 InsightChain 3 层因果链

`services/ai_insight_service.py::generate_causal_insight(db, domain, tenant_id)` 流程：
1. 查询近 7 天该 domain 的 `DataLineage`；
2. 构建 3 层因果链（根因最早权重 0.5 / 中间因素 0.3 / 表象最新 0.2）；
3. 生成自然语言结论；
4. 落 `InsightChain`（含 `chain`、`root_cause`、`natural_language_conclusion`）；
5. 反向记录 `insight_generate` lineage；
6. 发布 `insight_generated` 事件（`affected_domains=["decision","notification"]`）触发决策派单。

### 6.17 跨域闭环事件订阅者

`event_subscribers.py` 中注册 4 个 订阅者，全部通过 ServicePort 调用，单个订阅者失败不阻塞其他订阅者：

`event_subscribers.py` 注册 4 个订阅者，全部通过 ServicePort 调用，单个失败不阻塞其他：

- **`on_collection_published`**（`collection_item_published`，采集→画像→培训闭环）：`collection.apply_ability_impact` 回写画像（容错）→ `profile.detect_weakness(threshold=70)` 检弱项 → 每个弱项最多推 2 个训战场景（`training.recommend_scenarios` + `push_suggestion`）。
- **`on_practice_session_completed`**（`practice_session_completed`，培训→拜访传导）：`profile.get_ability_summary` 取维度分，达 80 阈值推送进阶拜访建议（`coverage_reminder`）。
- **`on_insight_generated`**（`insight_generated`，洞察→建议→派单闭环）：`decision.derive_recommendations` 派生建议并推送（`kpi_alert`）。
- **`on_recommendation_accepted`**（`recommendation_accepted`，接受→行动→24h 评估→AI 学习反馈）：`proactive_engine.record_action`（内置 `evaluate_after=now+24h`）+ `ai_insight_service.apply_feedback` 同步触发权重调整。

### 6.18 AI 学习闭环

`services/ai_insight_service.py::apply_feedback(db, suggestion_type, domain, tenant_id)` 基于建议历史有效率动态调整洞察生成权重（持久化于 `Tenant.settings.insight_weights`）：

- 查询 `proactive_engine.effectiveness_score(...)` 历史有效率；
- 有效率 < 0.3：降权 0.2（最低 0.3）；> 0.7：升权 0.1（最高 1.5）；否则维持；
- 权重变动时写回 `Tenant.settings` 并发布 `suggestion_outcome_evaluated` 事件（`affected_domains=["ai"]`）。

**闭环示意**：
```
洞察生成 → 派单建议 → 用户接受 → record_action(evaluate_after=now+24h)
                                                      │
                                                      ▼ (24h 后)
                                    suggestion_evaluation_scheduler 扫描
                                                      │
                                                      ▼
                                    evaluate_outcome → effectiveness_score
                                                      │
                                                      ▼
                                    apply_feedback → 调整 insight_weights[domain]
                                                      │
                                                      ▼
                                    suggestion_outcome_evaluated 事件
                                                      │
                                                      ▼
                                    下次 generate_causal_insight 受权重影响
```

### 6.19 采集域规则引擎

`services/collection_service.py::publish_item()` 升级为 5 步流程：① 字段校验（`validate_item_values`）→ ② 派生字段计算（`compute_derived_fields`，基于 AST 白名单算术求值 `_safe_arithmetic`，仅允许 `BinOp/Add/Sub/Mult/Div/Mod`）→ ③ 画像回写（`apply_ability_impact`，经 `ProfileServicePort`）→ ④ 数据流追踪（`DataLineageServicePort.record_lineage`，`transformation="ability_update"`）→ ⑤ 发布 `collection_item_published` 事件（`affected_domains=["profile","training"]`）。

### 6.20 合规 RBAC 工具阻断（tool_loop）

对应《医药代表管理办法》第 11 条第（三）项 + 第 24 条第（三）项：医药代表不得承担药品销售任务。`ToolLoop._execute_tool` 执行工具前先查当前角色，若为 `pharma_rep` 且工具名命中 `FORBIDDEN_TOOLS_FOR_PHARMA_REP` 黑名单（`compute_roi / compute_kpi / compute_coverage_gap / list/create_behavior_point_record / list/create_instruction_point_record` 等），则追加合规 `AuditLog`（`is_compliance_critical=1`，动作 `tool.forbidden.blocked`）并返回阻断提示，不调用工具。

**对应合规条款**：第 11 条第（三）项禁止持有人向医药代表分配销售任务；第 24 条第（三）项禁止医药代表承担药品销售任务、实施收款和处理购销票据等销售行为。

### 6.21 22 项禁止行为规则引擎

`compliance_service.check_violations()` 是 Phase 2 规则引擎的运行时入口，在学术活动立项/签到/费用核销/拜访提交/承诺签署等 5 种触发场景（`SCENE_ACTIVITY_CREATE / SCENE_ACTIVITY_CHECKIN / SCENE_ACTIVITY_EXPENSE / SCENE_VISIT_SUBMIT / SCENE_COMMITMENT_SIGN`）下被自动调用。处理流程：

1. 加载租户下全部启用规则（`is_active=1`）；
2. 仅保留 `trigger_scenes` 包含当前 `scene` 的规则；
3. 逐条 `_apply_rule_check(rule, context, actor_role)` 分派检查类型：
   - **keyword**（关键词匹配）：拼接 `title+description` 小写，命中 `check_config.keywords` 即违规；
   - **forbidden_action**（禁止行为）：`context.action` 命中 `forbidden_actions`（如商业贿赂、统计处方量）；
   - **role_blacklist**（角色黑名单）：`actor_role` 在 `roles` 且 `action` 命中 `blocked_actions`（医药代表调用销售行为）；
   - **amount_limit**（金额上限）：`context.amount > check_config.amount_limit`（如单次活动费用 ≤ 50 万）；
4. 命中后写 `ComplianceViolationEvent`（`status=pending`）+ 生成 `ComplianceAlert`（`alert_type=violation`）；
5. 返回 `{scene, violations, total}`。

**22 项规则分布**（自动 seed 入库，对应第 11/12/24/25 条）：

| 主体 | 条款 | 数量 | 示例 |
|---|---|---|---|
| 持有人 | 第 11 条 | 4 项 | A11_3 向医药代表分配销售任务 |
| CSO | 第 12 条 | 4 项 | A12_2 指使医药代表商业贿赂 |
| 医药代表 | 第 24 条 | 9 项 | A24_3 承担销售任务 / A24_6 给予回扣 |
| 医疗机构 | 第 25 条 | 5 项 | A25_3 接受附加销售条件的捐赠 |

### 6.22 门禁驱动工作流 Skill

Phase 2 引入两个新的 `is_workflow: true` Skill，采用 v2.0 门禁驱动框架（SceneWorkspace + WorkflowSkillExecutor），与 Phase 1 业务 Skill 的"指令式"不同：

#### 6.22.1 pharma-rep-onboarding（7 门禁 G1-G7 + 6 Step）

| Step | 门禁 | 描述 |
|---|---|---|
| Step1 | G1, G2 | 鉴权 + 拉取上岗清单（培训清单 + 考核要求 + 承诺书版本） |
| Step2 | G3 | 采集档案信息（学历 / 专业 / 授权区域 / 产品范围） |
| Step3 | G4 | 完成培训课程并考核合格 |
| Step4 | G5 | 签署合规承诺书（onboarding 类型） |
| Step5 | G6 | 提交备案（生成备案号 PR-YYYYMMDD-XXXX） |
| Step6 | G7 | 上岗准入二次校验（学术活动发起前再次检查三件套） |

**对应《医药代表管理办法》第 9、10、14-18 条**：培训-考核-承诺闭环 + 备案号生成 + 上岗准入。

#### 6.22.2 academic-activity-lifecycle（8 门禁 G1-G8 + 7 Step）

| Step | 门禁 | 描述 |
|---|---|---|
| Step1 | G1, G2 | 鉴权 + 上岗准入校验（医药代表三件套齐备） |
| Step2 | G3 | 采集活动基本信息（标题 / 类型 / 时间 / 地点 / 主办方 / CSO 机构） |
| Step3 | G4 | 22 项规则预校验（关键词 / 角色黑名单 / 金额上限） |
| Step4 | G5 | 协议流上传 + 审批通过 |
| Step5 | G6 | 签到流（实际参会人数 vs 计划） |
| Step6 | G7 | 费用流核销（金额上限 + 22 项规则复校） |
| Step7 | G8 | 反馈收集（含不良反应收集，第 21 条） |

**对应第 19-22 条学术推广活动管理**：三流合一（协议流 / 签到流 / 费用流）+ 22 项规则运行时校验 + 上岗准入强制。

### 6.23 30 日时效预警

对应第 17 条：医药代表已备案信息变更 / 停止授权后，30 日内必须完成。`scan_deadline_alerts(db, tenant_id)` 扫描即将到期（≤7 日）或已到期的备案变更/撤销任务，自动生成 `ComplianceAlert`：

1. 查询 `pending_change` 状态档案（变更须 30 日内完成）与 `revoked` 状态且 `revoke_scheduled_at` 临近的档案；
2. 对每条计算 `deadline`（`revoke_scheduled_at` 或 `updated_at + 30d`）、`days_left`，按阈值定 `severity`（0 天 `critical`、≤3 `high`、否则 `medium`）；
3. 生成 `ComplianceAlert`（`deadline_change` 或 `deadline_revoke`）；
4. 返回 `{scanned, new_alerts}`。

### 6.24 AI 原生全链路闭环（4 类推理意图）

诊断 / 归因之外的三类核心链路（范式沉淀、效果归因评估、主动建议、智能洞察）全部接入 `Orchestrator` 七步状态机，与 `diagnose` / `attribute` 主链路**同构**：同一状态机、同一推理链（`ReasoningChain`）、同一来源 / 血缘（`provenance`）呈现体系，mock 与真实 LLM 走同一条链路。

四条新意图统一在 `ai/intent_routes.py` 注册（`INTENT_KEYWORDS` / `INTENT_SKILL_MAP` / `INTENT_RESPONSES`），并通过 `orchestrator.py` 的 `_DECISION_INTENTS` 集合路由到 `decision` 域 `DecisionAgent`：

| 意图 | Skill | 触发 API | 后端服务方法 | 落库字段 |
|---|---|---|---|---|
| `derive_paradigm` | `paradigm-distiller` | `POST /v1/decision/paradigm/derive` | `ai_paradigm_service.derive_paradigm()`（async） | `Paradigm.reasoning_chain_id` |
| `evaluate` | `effect-evaluator` | `POST /v1/decision/effect/evaluate` | `effect_tracking_service.ai_evaluate()`（实例方法，async） | `DecisionExecution.reasoning_chain_id` |
| `suggest` | `proactive-advisor` | `GET /v1/ai/suggestions/ai` | `proactive_engine.ai_suggest()`（async） | 返回 `reasoning_chain_id`（内存态） |
| `insight` | `insight-generator` | `GET /v1/ai/insight/ai` | `ai_insight_service.ai_generate_insight()`（async） | 返回 `reasoning_chain_id`（内存态） |

**统一执行契约**（以 `derive_paradigm` 为例，其余同构）：`ai_paradigm_service.derive_paradigm(db, tenant_id, execution_id, domain)` 构造闭环经验沉淀消息，调用 `Orchestrator().chat(intent="derive_paradigm", ...)` 走七步状态机；解析响应（`_safe_parse_json` 兼容免责声明尾部）提取 `reasoning_chain_id` 与 `provenance`（含 `model_version`/`run_id`），落 `Paradigm` 表；编排异常时降级到确定性实现 `followup_loop_service.extract_paradigms`。

**可解释 / 可追溯保证**：
- `reasoning_chain_id` 由 `_post_pipeline` 在每次编排后统一落库（`ReasoningChain`），前端经 `/v1/decision/reasoning-chain/{id}` 拉取时间线。
- `provenance.model_version` 在 mock 下为 `nvidia/nemotron-3-ultra-550b-a55b`，真实 LLM 下为实际模型标识。
- 四条链路均保留**确定性降级**：编排器整体异常时回退到原规则实现（`extract_paradigms` / `_compute_score` / `generate` / `generate_insight_internal`），保证可用性。

---

## 7. 关键流程设计

### 7.1 AI 对话完整流程

```
Client                 Backend                  AI Modules
  │                       │                          │
  │ POST /ai/chat/send    │                          │
  │ {message, session_id} │                          │
  ├──────────────────────▶│                          │
  │                       │ Orchestrator.chat()      │
  │                       ├─────────────────────────▶│
  │                       │                          │ Step 1: Guardrails
  │                       │                          │   (regex check)
  │                       │                          │ Step 2: Cache
  │                       │                          │   (TF-IDF lookup)
  │                       │                          │ Step 3: Intent
  │                       │                          │   (hybrid classify)
  │                       │                          │ Step 4: Slot
  │                       │                          │   (regex/keyword)
  │                       │                          │ Step 4.5: Safety
  │                       │                          │ Step 5: Agent+Tool
  │                       │                          │   (LLM call via async)
  │                       │                          │ Step 6: Hallucination
  │                       │                          │ Step 7: Persist
  │                       │                          │   (cache, memory, event)
  │                       │◀─────────────────────────┤
  │                       │  response + reasoning    │
  │◀──────────────────────┤                          │
  │ {code: 0, data: {     │                          │
  │   response,           │                          │
  │   reasoning_chain,    │                          │
  │   hallucination_check,│                          │
  │   agent_used,         │                          │
  │   intent, slots...    │                          │
  │ }}                    │                          │
```

### 7.2 SSE 流式流程

```
Client                 Backend                  LLM
  │                       │                       │
  │ POST /ai/chat/stream  │                       │
  ├──────────────────────▶│                       │
  │                       │ event: thinking       │ → Step 1
  │◀──────────────────────┤                       │
  │                       │ event: intent         │ → Step 3
  │◀──────────────────────┤                       │
  │                       │ event: routing        │ → Step 5 前
  │◀──────────────────────┤                       │
  │                       │ event: skill          │ → Skill 匹配
  │◀──────────────────────┤                       │
  │                       │ LLM.stream()          │
  │                       ├──────────────────────▶│
  │                       │ event: reasoning      │ ← 思考链片段
  │◀──────────────────────┤                       │
  │                       │ event: content        │ ← token 片段
  │◀──────────────────────┤                       │
  │                       │ event: content        │
  │◀──────────────────────┤                       │
  │                       │ ... (多次)             │
  │                       │ event: done           │ → Step 7
  │◀──────────────────────┤                       │
  │ connection close      │                       │
```

### 7.3 拜访记录 → 培训推荐闭环

```
医药代表完成拜访
  │
  ▼
POST /v1/sales/records (口述/表单)
  │
  ▼
sales_service.create_record()
  ├─→ 结构化抽取 (feedback-extractor Skill / NER)
  ├─→ 写入 visit_records
  ├─→ 抽取异议关键词 → visit_feedback
  └─→ profile_service.get_learning_needs()
        ├─ 查询近 30 天反馈中的高频异议
        ├─ 关联产品分类
        ├─ 匹配课程 (排除已完成)
        └─ 返回 suggested_training
  │
  ▼
Response 携带 suggested_training
  │
  ▼
前端展示 "推荐学习《客户异议处理》"
  │
  ▼
用户点击课程 → POST /v1/training/enroll
  │
  ▼
training_service.update_course_progress() 进度 100%
  │
  ▼
profile_service.recalculate_ability_score()
  └─→ 对应能力维度 +X 分
  │
  ▼
下次拜访推荐更准（飞轮形成）
```

### 7.4 复合意图协作流程

```
用户问："我这个季度表现如何？哪些地方要提升？怎么补？"
  │
  ▼
Orchestrator
  │
  ├─→ Intent Classifier
  │   检测到多动词：表现（决策）+ 提升（培训）+ 补（培训）
  │   + 跨域：销售 + 培训 + 决策
  │
  ├─→ CollaborationOrchestrator.detect_collaboration_need()
  │   返回 {mode: "delegate", agents: [SalesAgent, TrainingAgent, DecisionAgent]}
  │
  ├─→ CollaborationOrchestrator.delegate()
  │   ├─ 拆解任务：
  │   │   sub1 = "本季度 KPI 表现分析"  → DecisionAgent
  │   │   sub2 = "识别能力短板"          → TrainingAgent
  │   │   sub3 = "建议提升路径"          → TrainingAgent
  │   │
  │   ├─ 并行执行（asyncio.gather）
  │   │
  │   └─ 合成最终回答
  │
  ▼
Response 包含 synthesized_response + sub_results[]
```

### 7.5 负面反馈 → 主动建议

```
visit_feedback 写入（sentiment=negative）
  │
  ▼
event_bus.publish("feedback_negative", payload)
  │
  ▼
后台任务 _process_pending_events() 拉取
  │
  ▼
WriteBackEngine.execute("feedback_negative", payload)
  │
  ├─ 标记医生进入"重点关注"池
  ├─ 给培训经理推送通知
  └─ 触发 proactive_suggestions 重算
  │
  ▼
用户下次进入首页
  │
  ▼
ProactiveSuggestionsEngine.generate()
  └─ 看到"医生 X 上次反馈负面，建议本周内安排并准备话术"
```

### 7.6 采集→画像→培训 跨域闭环

```
医药代表录入采集项并发布
  │
  ▼
collection_service.publish_item(db, tenant_id, item_id, user_id)
  ├─ Step 1: validate_item_values（字段校验 + 跨字段规则）
  ├─ Step 2: compute_derived_fields（AST 白名单算术求值）
  ├─ Step 3: apply_ability_impact（通过 ProfileServicePort 回写画像）
  ├─ Step 4: data_lineage.record_lineage（数据流追踪）
  └─ Step 5: event_bus.publish("collection_item_published", ...)
                │
                ▼
event_subscribers.on_collection_published(payload, tenant_id, db)
  │
  ├─ 1. registry.get(CollectionServicePort).apply_ability_impact(...)
  │     └─ ability_profiles 表更新（5 维能力增量）
  │
  ├─ 2. registry.get(ProfileServicePort).detect_weakness(db, user_id, threshold=70.0)
  │     └─ 返回低于 70 分的维度清单（如 ["visit_skill", "product_knowledge"]）
  │
  └─ 3. 对每个弱项维度调用 registry.get(TrainingServicePort).recommend_scenarios(...)
        │
        ├─ 匹配 PracticeScenario.target_skills / scoring_dimensions
        ├─ 排除近 30 天已完成场景
        └─ Top5 推荐场景
              │
              ▼
        proactive_engine.push_suggestion(...)
              │
              ▼
        前端 ProactiveSuggestions.tsx 显示
        "检测到「visit_skill」能力偏弱，推荐训战《XXX》"
```

### 7.7 决策→行动→洞察 AI 学习回环

```
06:00 定时任务触发（或手动 /v1/ai/insights/refresh）
  │
  ▼
ai_insight_service.generate_causal_insight(db, domain, tenant_id)
  ├─ 查询近 7 天 DataLineage
  ├─ 构建 3 层因果链（根因 0.5 / 中间 0.3 / 表象 0.2）
  ├─ 写 InsightChain 表
  ├─ record_lineage（反向记录）
  └─ event_bus.publish("insight_generated", ...)
                │
                ▼
event_subscribers.on_insight_generated(payload, tenant_id, db)
  │
  ├─ registry.get(DecisionServicePort).derive_recommendations(db, insight_id, tenant_id)
  │   └─ 从 InsightChain 因果链派生 DecisionRecommendation（每层 1 条）
  │       ├─ 根因层：高优先级建议
  │       ├─ 中间层：中优先级建议
  │       └─ 表象层：低优先级建议
  │
  └─ proactive_engine.push_suggestion(user_id, tenant_id, "kpi_alert", ...)
              │
              ▼
        前端显示"AI 洞察已生成"建议卡
              │
              ▼
        用户点击"接受"
              │
              ▼
decision_service.accept_recommendation(db, rec_id, user_id, tenant_id)
  ├─ 更新 decision_recommendations.status = 'accepted'
  └─ event_bus.publish("recommendation_accepted", ...)
                │
                ▼
event_subscribers.on_recommendation_accepted(payload, tenant_id, db)
  │
  ├─ 1. proactive_engine.record_action(
  │        suggestion_id=f"rec_{rec_id}", user_id=user_id,
  │        action_type="accepted", db=db,
  │        suggestion_type="kpi_alert", tenant_id=tenant_id,
  │     )
  │     └─ suggestion_actions 表插入记录
  │        evaluate_after = now + 24h
  │
  └─ 2. ai_insight_service.apply_feedback(
           db=db, suggestion_type="kpi_alert",
           domain=domain, tenant_id=tenant_id,
        )
              │
              ▼
        proactive_engine.effectiveness_score(suggestion_type, db, tenant_id)
              │
              ▼
        读取历史有效率（如 0.25）
              │
              ▼
        读取 Tenant.settings.insight_weights[domain]（如 1.0）
              │
              ▼
        effectiveness < 0.3 → new_weight = max(0.3, 1.0 - 0.2) = 0.8
              │
              ▼
        写回 Tenant.settings.insight_weights[domain] = 0.8
              │
              ▼
        event_bus.publish("suggestion_outcome_evaluated", ...)
              │
              ▼
        下次 generate_causal_insight 受权重影响（AI 自我学习闭环形成）

─ ─ ─ ─ ─ ─ ─ ─ ─ ─ 24h 后 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─

suggestion_evaluation_scheduler 定时扫描
  │
  ▼
发现到期 action（evaluate_after <= now）
  │
  ▼
proactive_engine.evaluate_outcome(suggestion_id, db)
  ├─ 对比 baseline_kpi 与 final_kpi
  └─ 写入 effectiveness_score（0-1）
```

---

## 8. 关键 API 设计

### 8.1 通用约定

- 前缀：`/v1`
- 认证：`Authorization: Bearer <jwt>`
- 响应：`{"code":0,"message":"ok","data":{...}}`
- 错误码：见 §4.2
- 分页：`?page=1&size=20` 或 `?limit=20&offset=0`

### 8.2 AI 模块 API

| 方法 | 端点 | 说明 |
|---|---|---|
| POST | `/v1/ai/chat/send` | 普通对话（返回完整结果） |
| POST | `/v1/ai/chat/stream` | SSE 流式（10 事件类型） |
| POST | `/v1/ai/chat/{session_id}/abort` | 中止 |
| GET | `/v1/ai/metrics` | AI 运行期指标 |
| POST | `/v1/ai/metrics/reset` | 重置指标（管理员） |
| GET | `/v1/ai/reasoning/chains` | 推理链列表 |
| GET | `/v1/ai/reasoning/chains/{id}` | 推理链详情 |
| POST | `/v1/ai/reasoning/chains/{id}/feedback` | 用户反馈 |
| GET | `/v1/ai/suggestions` | 主动建议（确定性） |
| GET | `/v1/ai/suggestions/ai` | AI 原生主动建议（经编排器 suggest 意图，统一 provenance） |
| GET | `/v1/ai/insight/ai` | AI 原生智能洞察（经编排器 insight 意图，统一 provenance） |
| GET | `/v1/ai/agents` | Agent 元数据（含 skills） |
| POST | `/v1/ai/collaborate` | 手动触发协作 |
| GET | `/v1/ai/collaboration/detect` | 协作需求检测 |
| POST | `/v1/ai/insights/refresh` | 手动刷新洞察 |
| GET | `/v1/ai/events` | 事件列表 |
| GET | `/v1/ai/events/dead-letters` | 死信队列 |
| POST | `/v1/ai/events/dead-letters/{id}/resolve` | 处理死信 |
| POST | `/v1/ai/events/replay/{id}` | 重放事件 |
| DELETE | `/v1/ai/cache` | 清空缓存 |
| GET | `/v1/agents` | Agent 列表 |
| GET | `/v1/agents/{name}` | Agent 详情 |
| POST | `/v1/agents/{name}/invoke` | 调用 Agent |
| GET | `/v1/actions` | Action 列表 |
| GET | `/v1/actions/{name}` | Action 详情 |
| POST | `/v1/actions/{name}/execute` | 执行 Action |

### 8.3 销售域 API（节选）

| 方法 | 端点 | 说明 |
|---|---|---|
| GET | `/v1/sales/plans` | 拜访计划列表 |
| POST | `/v1/sales/plans` | 创建计划 |
| GET | `/v1/sales/plans/{id}` | 计划详情 |
| POST | `/v1/sales/plans/ai-recommend` | AI 推荐今日计划 |
| GET | `/v1/sales/records` | 拜访记录列表 |
| POST | `/v1/sales/records` | 创建记录（自然语言） |
| GET | `/v1/sales/feedback` | 反馈列表 |
| GET | `/v1/sales/coverage` | 覆盖矩阵 |
| POST | `/v1/sales/coverage/compute-gap` | 计算覆盖空白 |
| GET | `/v1/sales/scoring` | 积分排行 |
| GET | `/v1/sales/roi` | ROI 分析 |
| GET | `/v1/sales/matrix` | 相关性矩阵 |
| GET | `/v1/sales/kol` | KOL 画像 |

### 8.4 决策域 API（节选）

| 方法 | 端点 | 说明 |
|---|---|---|
| GET | `/v1/decision/overview` | 决策概览 |
| GET | `/v1/decision/kpi` | KPI 监控 |
| GET | `/v1/decision/attribution` | 归因分析 |
| POST | `/v1/decision/simulate` | What-if 模拟 |
| GET | `/v1/decision/alerts` | 预警列表 |
| GET | `/v1/decision/executions` | 效果追踪 |
| POST | `/v1/decision/attribute-change` | 基于因果链归因贡献度 |
| POST | `/v1/decision/penetrate` | 按 region/hospital/doctor 逐层下钻 |
| GET | `/v1/decision/recommendations` | 决策建议列表（可派单） |
| GET | `/v1/decision/recommendations/{id}` | 决策建议详情 |
| POST | `/v1/decision/recommendations/{id}/accept` | 接受建议，触发 recommendation_accepted 事件 |
| POST | `/v1/decision/paradigm/derive` | 范式沉淀（经编排器 derive_paradigm 意图，落 reasoning_chain_id） |
| POST | `/v1/decision/effect/evaluate` | AI 效果归因评估（经编排器 evaluate 意图，落 reasoning_chain_id） |
| GET | `/v1/decision/reasoning-chain/{chain_id}` | 拉取推理链时间线（来源/血缘/七步） |

### 8.5 数据流与因果链 API

| 方法 | 端点 | 说明 |
|---|---|---|
| GET | `/v1/ai/lineage/trace-upstream` | 数据流向上追溯（target_type + target_id） |
| GET | `/v1/ai/lineage/trace-downstream` | 数据流向下追溯（source_type + source_id） |
| GET | `/v1/ai/lineage/impact-chain` | 影响链查询（跨域影响树） |
| GET | `/v1/ai/insight-chains` | 洞察因果链列表 |
| GET | `/v1/ai/insight-chains/{id}` | 洞察因果链详情（含 3 层结构 + 自然语言结论） |
| GET | `/v1/ai/insight-chains/{id}/explain` | 异常解释（追溯上游 lineage） |
| GET | `/v1/profile/ability` | 5 维能力画像摘要 |
| GET | `/v1/profile/ability/weakness` | 弱项维度检测 |

### 8.6 13 域 AI 洞察 API

每个域都有一个 `/v1/{domain}/ai-insights` 端点，查询 ai_insight_cache：

| 域 | 端点 |
|---|---|
| 销售 | GET /v1/sales/ai-insights |
| 培训 | GET /v1/training/ai-insights |
| 决策 | GET /v1/decision/ai-insights |
| 协同 | GET /v1/collab/ai-insights |
| 知识 | GET /v1/knowledge/ai-insights |
| 门户 | GET /v1/portal/ai-insights |
| 个人 | GET /v1/profile/ai-insights |
| CRM | GET /v1/crm/ai-insights |
| CFM | GET /v1/cfm/ai-insights |
| 工具 | GET /v1/tools/ai-insights |
| 平台 | GET /v1/platform/ai-insights |
| 主数据 | GET /v1/mdm/ai-insights |
| 可观测 | GET /v1/observability/ai-insights |

### 8.7 AI 嵌入点

| 类型 | 数量 | 端点 / 组件 |
|---|---|---|
| AIInsightPanel（域概览页） | 13 | 上述 13 域 |
| AIActionButton（列表页动作按钮） | 15 | 销售/培训/决策/协同/知识/CRM/CFM/工具 等列表页 |
| AIAssistantPanel | 1 | AIAssistantPage |
| AISidebar（全局） | 1 | App.tsx |
| ProactiveSuggestions | 1 | PortalPage / AIAssistantPage |
| CommandPalette（Cmd+K） | 1 | 全局快捷键 |

### 8.8 合规 / 学术 / CSO API

| 方法 | 端点 | 说明 |
|---|---|---|
| GET | `/v1/compliance/violation-rules` | 22 项禁止行为规则列表（可按 subject 过滤） |
| GET | `/v1/compliance/violation-rules/{code}` | 单条规则详情（如 A24_3） |
| GET | `/v1/compliance/violation-events` | 违规事件列表（分页 + 状态/严重度过滤） |
| POST | `/v1/compliance/violation-events/{event_id}/handle` | 处置违规事件（resolved / dismissed） |
| GET | `/v1/compliance/alerts` | 合规预警列表（含 30 日时效预警） |
| POST | `/v1/compliance/alerts/{alert_id}/handle` | 处置合规预警 |
| POST | `/v1/compliance/deadlines/scan` | 触发 30 日时效扫描（第 17 条） |
| GET | `/v1/compliance/onboarding-gate/{user_id}` | 上岗准入校验（学术活动发起前强制） |
| GET | `/v1/compliance/profile/{user_id}` | 医药代表资质档案 |
| PUT | `/v1/compliance/profile/{user_id}` | 更新档案（触发 30 日变更时效预警） |
| POST | `/v1/compliance/profile/{user_id}/submit-registration` | 提交备案（生成备案号） |
| POST | `/v1/compliance/profile/{user_id}/revoke` | 撤销备案（30 日内删除） |
| GET | `/v1/compliance/pending-revokes` | 待删除备案列表 |
| POST | `/v1/compliance/commitment/sign` | 签署合规承诺书 |
| GET | `/v1/compliance/onboarding-check/{user_id}` | 上岗三件套检查 |
| GET | `/v1/compliance/audit-chain/verify` | 验证 AuditLog 链式证据完整性 |
| GET | `/v1/compliance/forbidden-behaviors` | 22 项禁止行为清单查询 |
| GET | `/v1/compliance/forbidden-tools` | 医药代表角色禁止工具清单 |
| GET | `/v1/audit/export` | 审计日志导出（CSV / JSON，可按 action / actor_id 过滤，需 `audit.read`） |
| GET | `/v1/academic/activities` | 学术活动列表 |
| POST | `/v1/academic/activities` | 创建学术活动（含上岗准入 + 22 项规则预校验） |
| GET | `/v1/academic/activities/{id}` | 学术活动详情 |
| POST | `/v1/academic/activities/{id}/approve` | 审批学术活动 |
| POST | `/v1/academic/activities/{id}/protocol` | 上传协议 |
| POST | `/v1/academic/activities/{id}/checkin` | 签到（22 项规则复校） |
| POST | `/v1/academic/activities/{id}/expense` | 费用核销（22 项规则复校） |
| POST | `/v1/academic/activities/{id}/feedback` | 反馈收集（含不良反应） |
| POST | `/v1/academic/activities/{id}/archive` | 归档活动 |
| POST | `/v1/academic/activities/{id}/cancel` | 取消活动 |
| GET | `/v1/partner/organizations` | CSO 合作机构列表 |
| POST | `/v1/partner/organizations` | 创建 CSO 机构 |
| GET/PUT/DELETE | `/v1/partner/organizations/{id}` | CSO 机构 CRUD |
| GET | `/v1/partner/agreements` | 管理协议列表 |
| POST | `/v1/partner/agreements` | 创建管理协议 |
| POST | `/v1/partner/agreements/{id}/sign` | 签署管理协议 |
| GET | `/v1/partner/letters` | 授权书列表 |
| POST | `/v1/partner/letters` | 创建授权书 |
| POST | `/v1/partner/letters/{id}/issue` | 下发授权书 |
| POST | `/v1/partner/letters/{id}/revoke` | 撤销授权书 |

---

## 9. 前端架构

### 9.1 技术栈

| 维度 | 选型 |
|---|---|
| 框架 | React 18.3 + TypeScript 5.4 |
| 路由 | React Router 6 |
| 构建 | Vite 5 |
| 样式 | Tailwind CSS 3 + clsx |
| 动画 | Framer Motion |
| 状态 | Zustand |
| 国际化 | i18next + react-i18next |
| HTTP | Axios（拦截器） |
| 图表 | Recharts |
| 表单 | React Hook Form + Zod（推荐） |

### 9.2 路由设计

前端基于 `BrowserRouter` + `ProtectedLayout` 布局路由（未登录仅 `/login`），业务域以嵌套路由分组：

```
/login                         LoginPage
ProtectedLayout
├─ /                            PortalPage（首页）
├─ /ai                         AIAssistantPage
├─ /sales/*                    SalesRoutes
├─ /training/*                 TrainingRoutes
├─ /decision/*                 DecisionRoutes
├─ /collab/*                   CollabRoutes
├─ /knowledge/*                KnowledgeRoutes
├─ /profile/*                  ProfileRoutes
├─ /ontology/*                 OntologyRoutes
├─ /crm                        CrmPage
├─ /cfm                        CfmPage
├─ /tools                      ToolsPage
├─ /platform                   PlatformPage
├─ /mdm                        MdmPage
├─ /settings                   SettingsPage
├─ /audit                      AuditPage
└─ /observability              ObservabilityPage
```

### 9.3 状态管理

| Store | 内容 |
|---|---|
| authStore | JWT、user、tenant、role |
| appStore | 主题、语言、侧边栏折叠 |
| aiAssistantStore | AI 对话历史、当前会话 |
| commandPaletteStore | Cmd+K 状态 |

### 9.4 AI 流式客户端

`hooks/useAIStream.ts` 暴露 `useAIStream()`，维护 `events`（`SSEEvent[]`）与 `isStreaming` 状态：调用 `stream(message, sessionId)` 时先清空、置 `isStreaming=true`，向 `/v1/ai/chat/stream` 发起带 `Authorization` 的 POST 请求，用 `response.body.getReader()` 逐块读取并以 `TextDecoder` 解码，经 `parseSSE` 累积解析后逐条 `setEvents` 追加，读到 `done` 置 `isStreaming=false`。

### 9.5 关键组件

| 组件 | 职责 | 嵌入点 |
|---|---|---|
| AIAssistantPanel | AI 对话主面板（左 2/3） | AIAssistantPage |
| AIInsightPanel | 域 AI 洞察卡 | 13 个概览页 |
| AIActionButton | 列表项的"AI 解读"按钮 | 15 个列表页 |
| ProactiveSuggestions | 主动建议卡（右 1/3） | PortalPage / AIAssistantPage |
| AISidebar | 全局 AI 入口 | App.tsx 始终可见 |
| ReasoningChainView | 推理链可视化 | AIAssistantPanel / AuditPage |
| CommandPalette | Cmd+K 全局搜索 | 全局 |

### 9.6 AI 原生决策流呈现（全产品闭环）

四类 AI 原生推理意图在前端统一以「来源 / 血缘 / 推理链」体系呈现，与 `diagnose` / `attribute` 主链路同构：

| 页面 / 组件 | AI 原生呈现 | 触发 |
|---|---|---|
| `PortalPage`（首页） | 新增「AI 决策流」卡片，聚合 suggest / insight / evaluate / paradigm 四类链路，每卡显示「AI 编排/规则」徽标 + 来源推理链入口 | 进入首页自动拉取 4 个 AI 接口 |
| `decision/ParadigmPage` | 范式卡片新增「来源推理链」链接（`/v1/decision/reasoning-chain/{id}`） | 列表渲染 |
| `decision/EffectTrackingPage` | 已完成执行新增「AI 评估」按钮，展开区显示可解释归因（因子/达标状态/贡献度）+ 来源推理链入口 | 点击「AI 评估」→ `/v1/decision/effect/evaluate` |
| `components/ai/ProactiveSuggestions` | 标题栏新增「AI 原生」开关，切换后调用 `/v1/ai/suggestions/ai`（编排器 suggest 意图）生成可解释建议 | 开关切换 |
| `components/ai/AIInsightPanel` | 标题栏新增「AI 原生」按钮，切换后调用 `/v1/ai/insight/ai`（编排器 insight 意图）生成统一 provenance 洞察 | 按钮切换 |

**统一来源 / 血缘徽标**：来源推理链入口统一跳转到 `/v1/decision/reasoning-chain/{id}`（复用 `ReasoningChainView` / `ReasoningTimeline`），展示七步状态机轨迹、置信度、provenance（model_version / run_id）。

---

## 10. 安全模型

### 10.1 纵深防御

| 层 | 措施 |
|---|---|
| 边界 | HTTPS（生产）、CORS 白名单、Rate Limit（建议 Nginx 层） |
| 认证 | JWT 1h 过期、bcrypt 4.x 哈希、Refresh Token |
| 授权 | 角色 × 资源 × 操作 三维矩阵 |
| 租户隔离 | tenant_id 中间件层强制注入 |
| 输入校验 | Pydantic 强类型 + 长度限制 + 字符集白名单 |
| Prompt 注入 | Guardrail 正则拦截 |
| 输出过滤 | 敏感词过滤 + PII 脱敏 |
| 审计 | 所有写操作 + 所有 AI 推理链 |
| 加密 | 密码 bcrypt、传输 TLS、DB 字段级加密（未来） |

### 10.2 攻击面

| 攻击 | 防御 |
|---|---|
| SQL 注入 | SQLAlchemy 参数化 + Pydantic |
| XSS | React 默认转义 + CSP header |
| CSRF | JWT 无状态 + CORS |
| Prompt 注入 | Guardrail 正则 + LLM system prompt 防御 |
| 暴力破解 | 登录限频（建议 5 次/分钟/IP） |
| 越权访问 | 角色 + 租户双校验 |
| 数据泄露 | 日志脱敏 + 审计告警 |
| LLM 越狱 | Safety Valves + 输出 review |

### 10.3 安全配置

```env
# .env
JWT_SECRET=<强随机 64 字节>
JWT_ALGORITHM=HS256
JWT_ACCESS_TTL=3600
JWT_REFRESH_TTL=86400
CORS_ORIGINS=["https://app.salesclaw.com"]
LLM_PROVIDER=openai
LLM_API_KEY=<密钥>
LLM_BASE_URL=https://integrate.api.nvidia.com/v1
LLM_ENABLE_THINKING=true
LLM_REASONING_BUDGET=16384
LOG_LEVEL=INFO
SQL_ECHO=false
```

---

## 11. 性能与可观测

### 11.1 性能基线

| 指标 | 目标 | 实测方法 |
|---|---|---|
| 列表 API P95 | ≤ 300ms | `time curl -w "%{time_total}"` |
| 决策 API P95 | ≤ 5s | 同上 |
| 洞察查询 P95 | ≤ 5ms | 同上（走缓存） |
| AI 流式首字 P95 | ≤ 1s | 浏览器 DevTools |
| 页面首屏 P95 | ≤ 1.5s | Lighthouse |

### 11.2 性能优化策略

| 策略 | 实施 |
|---|---|
| 异步 LLM | `asyncio.to_thread` 包装所有同步 SDK 调用 |
| 语义缓存 | TF-IDF + 余弦相似度，阈值 0.85 |
| 洞察预生成 | 06:00 定时生成，页面查缓存 |
| 数据库索引 | tenant_id + 业务字段联合索引 |
| 前端懒加载 | React.lazy + Suspense |
| Vite 打包 | tree-shaking + code-splitting |
| SSE 流式 | 用户体验上消除长白屏 |
| 事件异步处理 | eventual consistency 后台批处理 |

### 11.3 可观测指标

**12 个 AI 指标**（`metrics_collector`）：

| 指标 | 含义 |
|---|---|
| total_requests | 总请求数 |
| cache_hits | 缓存命中数 |
| cache_hit_rate | 命中率 |
| reflection_count | 反思重试次数 |
| reflection_rate | 反思率 |
| hallucination_rejected | 拒绝数 |
| hallucination_review | review 数 |
| tool_call_count | 工具调用总数 |
| avg_latency_ms | 平均延迟 |
| p95_latency_ms | P95 延迟 |
| intent_distribution | 意图分布 |
| agent_distribution | Agent 调用分布 |

**业务指标**（`observability`）：API 错误率、慢查询、AI 成本、租户用量排行。告警、AI 事件流（`GET /v1/observability/events`）与死信队列（`GET /v1/observability/dead-letters`）均基于 `LlmCallLog` / `AuditLog` / `DeadLetter` 等真实数据表动态派生，不使用硬编码假数据。

**前端埋点**（可选）：页面停留、操作路径、AI 调用转化。

### 11.4 Neo4j 健康探针（第 13 批）

| 端点 | 用途 |
|---|---|
| `GET /health` | 基础健康 + alembic 版本 + neo4j `{connected, latency_ms, ok}` |
| `GET /health/neo4j` | 深探测：init_info（首次 connect 时的参数）+ probe（latency_ms）+ counts（4 子系统节点/边统计）+ warning（>200ms red, >100ms yellow） |

实现复用 `Neo4jConnectionManager.latency_probe()` 与 `system_snapshot()`，探针与 4 store 共用同一连接池，无额外 IO 开销。Fail-fast 退路：connection refused 返回 200 + `ok: false`（运维体检友好，不破坏 k8s liveness）。

---

## 附录 A：环境变量清单

| 变量 | 默认值 | 说明 |
|---|---|---|
| APP_ENV | development | 运行环境 |
| APP_HOST | 0.0.0.0 | 监听地址 |
| APP_PORT | 8000 | 监听端口 |
| DB_PATH | ./data/psp.db | 业务库 + 本体库（同引擎，第 14 批双库合一） |
| VEC_DB_PATH | ./data/psp_vec.db | 向量库（sqlite-vec vec0 虚拟表） |
| DB_BACKEND | sqlite | 后端（sqlite / postgresql） |
| BUSINESS_DATABASE_URL | （空） | DB_BACKEND=postgresql 时使用 |
| NEO4J_URI | bolt://localhost:7687 | Neo4j bolt URI |
| NEO4J_USER | neo4j | 用户名 |
| NEO4J_PASSWORD | neo4j123 | 密码 |
| NEO4J_DATABASE | neo4j | 数据库名 |
| NEO4J_TIMEOUT | 5.0 | connect timeout（秒） |
| NEO4J_MAX_POOL_SIZE | 100 | driver 同进程并发连接上限 |
| NEO4J_ACQUIRE_TIMEOUT | 60.0 | acquire timeout（秒） |
| EMBEDDING_PROVIDER | qwen3 | 后端（qwen3 / openai / hash） |
| EMBEDDING_MODEL | Qwen/Qwen3-Embedding-0.6B | 模型名 |
| EMBEDDING_DIM | 1024 | 向量维度 |
| EMBEDDING_MAX_LENGTH | 512 | tokenizer 最大长度 |
| EMBEDDING_DEVICE | cpu | 设备（cpu / cuda） |
| MODELSCOPE_CACHE | （空） | modelscope SDK 缓存目录；部署侧显式设置 |
| JWT_SECRET | （必须修改） | JWT 签名密钥 |
| JWT_ALGORITHM | HS256 | JWT 算法 |
| JWT_ACCESS_TTL | 3600 | access token 过期秒数 |
| JWT_REFRESH_TTL | 86400 | refresh token 过期秒数 |
| CORS_ORIGINS | ["http://localhost:5173"] | 跨域白名单 |
| LLM_PROVIDER | mock | LLM 提供方（mock / openai） |
| LLM_API_KEY | （空） | LLM API 密钥 |
| LLM_BASE_URL | https://integrate.api.nvidia.com/v1 | LLM 网关 |
| LLM_MODEL | nvidia/nemotron | 模型名 |
| LLM_TEMPERATURE | 1.0 | 温度 |
| LLM_TOP_P | 0.95 | top_p |
| LLM_MAX_TOKENS | 16384 | 最大 token |
| LLM_ENABLE_THINKING | true | 启用思考链 |
| LLM_REASONING_BUDGET | 16384 | 思考链预算 |
| INSIGHT_GENERATION_HOUR | 6 | 洞察生成小时（24h 制） |
| LOG_LEVEL | INFO | 日志级别 |
| SQL_ECHO | false | SQL 回显 |
| TRAINING_LAG_WINDOWS | (30, 90, 180) | B 路径：培训归因滞后窗口（天） |
| TRAINING_LAG_DELTA_THRESHOLD | 5.0 | B 路径：画像显著提升阈值（分） |
| TRAINING_KPI_DELTA_THRESHOLD_RATIO | 0.10 | B 路径：KPI 显著提升阈值（比例） |
| TRAINING_COHORT_MIN_SAMPLE | 8 | B 路径：同期类比组最小样本 |
| TRAINING_EVAL_CONFIDENCE_FLOOR | 0.6 | B 路径：AI 归因置信度下限 |
| TRAINING_EVAL_AUTO_RUN_HOURS | 24 | B 路径：AI 归因自动触发延迟（小时） |
| TRAINING_TARGET_SCORE_DEFAULT | 3.0 | B 路径：培训声称目标缺省增量（分） |

---

## 附录 B：核心错误码

| 错误码 | 含义 |
|---|---|
| 0 | 成功 |
| 10001 | 参数错误 |
| 10002 | 参数缺失 |
| 20001 | 业务不存在 |
| 20002 | 业务冲突 |
| 30001 | 未登录 |
| 30002 | 无权限 |
| 30003 | 租户不匹配 |
| 40001 | 资源不存在 |
| 40004 | 数据不存在 |
| 50000 | 服务器内部错误 |
| 50001 | LLM 调用失败 |
| 50002 | 外部服务失败 |
