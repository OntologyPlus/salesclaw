# SalesClaw

> 药企医药代表 AI 原生统一平台

## 项目简介

SalesClaw 是面向药企医药代表的一体化 AI 平台，融合销售执行、智能培训、决策支持、协同办公、知识库五大业务域，并以"AI 原生"为架构基座：每个域配备专属 AI Agent，Agent 可调度 Skills（业务能力）、Tools（数据查询）、LLM（推理生成），并通过 RAG、知识库、记忆系统持续增强。

## 核心特性

- **域 Agent 架构**：6 个域 Agent（Supervisor + SalesAgent + TrainingAgent + DecisionAgent + CollabAgent + KnowledgeAgent），每个 Agent 持有 2-7 个 Skill（Phase 2 后共 27 个 Skill）
- **AI 原生编排器**：七步状态机（guardrails → cache → intent → slot → agent+reflection → hallucination → persist+metrics）
- **混合意图分类器**：规则 + LLM 双轨，4 级仲裁（规则 / LLM / 冲突仲裁 / 反馈校准）
- **四层记忆系统**：Working / Episodic / Semantic / Procedural，支持跨会话传递
- **Skills 三层加载**：L1 目录（启动）/ L2 指令（路由）/ L3 资源（按需），Token 经济学优化；支持 `depends_on` 递归编排（最大深度 5）
- **门禁驱动工作流**：引入 SceneWorkspace + WorkflowSkillExecutor + WorkflowChatLayout 通用框架，每个工作流 Skill 由 N 道门禁 + N 个 Step 严格保流程不跳步（如学术活动 8 门禁 8 Step / 上岗备案 7 门禁 6 Step）
- **SSE 流式协议**：10 种事件类型（thinking / intent / routing / skill / reasoning / content / tools_used / suggestions / done / error）
- **多 Agent 协作**：Delegate / Orchestrate / Aggregate 三种模式，跨域任务自动协调
- **AI 洞察定时预生成**：每天 06:00 定时任务为 13 个域生成洞察，页面查询 < 5ms
- **异步 LLM 调用**：所有同步 LLM 调用通过 `asyncio.to_thread` 包装，不阻塞事件循环
- **ServicePort 协议层**：跨域调用通过 `Protocol` + `ServiceRegistry` 解耦，禁止跨域直接 import
- **事件因果链**：事件总线支持 `causation_id` / `affected_domains`，可通过 `correlate()` 溯源
- **数据流追踪（DataLineage）**：跨域数据血缘完整记录，支持 `trace_upstream` / `trace_downstream` / `get_impact_chain`
- **洞察因果链（InsightChain）**：3 层因果结构（根因 0.5 → 中间 0.3 → 表象 0.2）自动构建
- **5 维能力画像**：product_knowledge / visit_skill / customer_relation / compliance / ai_application，含 30 天衰减机制（-5%）和证据链（最近 5 条）
- **采集域规则引擎**：JSON 模板定义字段校验 + 派生计算 + 跨字段规则 + 画像回写，使用 AST 白名单节点安全求值
- **决策域穿透**：归因（attribute_change）+ 模拟（simulate）+ 穿透（penetrate）+ 建议派单（derive_recommendations）+ 接受（accept_recommendation）
- **7 维评分引擎**：PPT 演讲训战 7 维评分（内容准确性 / 表达流畅度 / 逻辑结构 / 时间管理 / 互动应对 / 转场恢复 / 总结升华）
- **4 个跨域闭环事件链**：采集→画像→培训、培训→拜访能力传导、洞察→建议→派单、接受→行动→24h 评估→AI 反馈

## 合规适配路线（《医药代表管理办法》2026-08-01 施行）

| 阶段 | 范围 | 状态 |
|---|---|---|
| **Phase 1（最小合规）** | 医药代表备案档案 / 合规承诺书 / 链式 AuditLog / 22 项清单查询 / RBAC 工具阻断 | ✅ 已完成 |
| **Phase 2（中等合规体系）** | CSO 委托管理三件套 / 22 项规则运行时引擎 / 违规事件 + 合规预警 / 30 日时效扫描 / 学术推广工作流 / 上岗备案工作流 | ✅ 已完成 |
| **Phase 3（完整合规体系）** | 备案信息公示 / 监管接口对接 / 反商业贿赂风险图谱 / 年度合规审计报告 | ⏳ 待启动 |

### 合规能力清单

- **链式证据 AuditLog**：prev_hash + record_hash（SHA-256）构造不可篡改证据链，对应第 26 条全过程留痕
- **22 项禁止行为规则引擎**：第 11/12/24/25 条共 22 项规则运行时校验，4 种检查类型（keyword / forbidden_action / role_blacklist / amount_limit），5 种触发场景
- **学术推广三流合一**：协议流 / 签到流 / 费用流（第 21 条），8 道门禁驱动 G1-G8 工作流
- **双轨制架构**：保留销售管理模块（sales 角色）+ 新建学术推广模块（pharma_rep 角色），医药代表角色禁止调用销售类工具（compute_roi/compute_kpi 等）
- **CSO 委托管理三件套**：合作机构 + 管理协议 + 授权书（第 8 条），覆盖授权下发/撤销/30 日删除全生命周期
- **上岗备案工作流**：7 道门禁 G1-G7 + 6 个 Step，对应第 9、10、14-18 条（培训-考核-承诺闭环 + 备案号生成 + 上岗准入二次校验）
- **AI 学习闭环**：基于建议历史有效率（effectiveness_score）自动调整 `Tenant.settings.insight_weights[domain]`，实现 AI 自我学习
- **RBAC 接口鉴权**：合规 / 知识模块全路由接入 `require_permission` 依赖，只读校验 `*.read`、写校验 `*.write`，权限矩阵见 `backend/ontology/permissions.py`（`admin` / `sales_director` 持有 `*` 全权限）

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic |
| 业务库 | SQLite（默认）/ PostgreSQL（`DB_BACKEND=postgresql` 切换） |
| 图存储 + 版本 + 溯源 + 候选 | **Neo4j 5.x** |
| 向量检索 | sqlite-vec vec0 虚拟表（`vec_distance_cosine` SQL 主路径）+ numpy 兜底 |
| 前端 | React 18.3, TypeScript 5.4, Vite, Tailwind CSS, Framer Motion |
| AI | OpenAI 兼容 API；嵌入=Qwen3-Embedding-0.6B / OpenAI / HashingVectorizer |
| 工具 | uvicorn, httpx, sklearn (TF-IDF/HashingVectorizer), bcrypt, modelscope SDK |

## 目录结构

```
salesclaw/
├── backend/                       # FastAPI 后端
│   ├── main.py                    # 应用入口
│   ├── config.py                  # 配置（LLM、DB、租户）
│   ├── database.py                # 数据模型（业务库与本体库共用同一 engine；v1.1 起单 SQLite 文件，包含 BusinessBase + OntologyBase 12x 表）
│   ├── core/                      # 核心工具
│   │   ├── security.py            # bcrypt + JWT
│   │   ├── response.py            # 统一响应
│   │   ├── exceptions.py          # 错误码
│   │   ├── pagination.py          # 分页
│   │   ├── validators.py          # 校验器
│   │   ├── service_ports.py       # 8 个 Protocol 协议接口
│   │   ├── service_registry.py    # ServiceRegistry 注册表
│   │   ├── neo4j_driver.py        # Neo4jConnectionManager（共享 driver + health probe；v1.1）
│   │   └── constants.py           # 跨域共享常量
│   ├── middleware/                # 中间件（tenant / auth / logging / error）
│   ├── ontology/                  # 本体（objects / links / actions / permissions）
│   ├── services/                  # 业务服务（27 个域，含合规）
│   │   ├── sales_service.py       # 销售执行
│   │   ├── training_service.py    # 智能培训（含 recommend_scenarios / apply_session_to_ability）
│   │   ├── profile_service.py     # 综合能力画像（5 维能力 + 衰减机制）
│   │   ├── decision_service.py    # 决策支持（含穿透 / 模拟 / 派单）
│   │   ├── collection_service.py  # 采集域（规则引擎 + 画像回写）
│   │   ├── collab_service.py      # 协同办公
│   │   ├── knowledge_service.py   # 知识库
│   │   ├── crm_service.py         # CRM
│   │   ├── cfm_service.py         # CFM
│   │   ├── ai_insight_service.py  # AI 洞察（因果链 + apply_feedback AI 学习）
│   │   ├── data_lineage_service.py # 数据流追踪（trace_upstream / downstream）
│   │   ├── ppt_speech_service.py  # PPT 演讲训战（7 维评分）
│   │   ├── effect_tracking_service.py
│   │   ├── observability_service.py
│   │   ├── audit_service.py
│   │   ├── platform_service.py
│   │   ├── mdm_service.py
│   │   ├── compliance_service.py  # 合规管理（备案/承诺/22 项规则/违规/预警/30 日时效）
│   │   ├── academic_activity_service.py  # 学术推广活动全生命周期
│   │   ├── partner_service.py     # CSO 委托管理三件套
│   │   └── insight_scheduler.py   # 定时调度器（每天 06:00）
│   ├── ai/                        # AI 模块（15 个文件）
│   │   ├── orchestrator.py        # 七步状态机
│   │   ├── llm_client.py          # LLM 客户端
│   │   ├── intent_classifier.py   # 混合意图分类器
│   │   ├── memory_service.py      # 四层记忆
│   │   ├── reasoning_chain.py     # 推理链
│   │   ├── self_reflection.py     # 自我反思
│   │   ├── hallucination_detector.py
│   │   ├── safety_valves.py       # 安全阀
│   │   ├── event_bus.py           # 事件总线（含 causation_id / affected_domains / correlate）
│   │   ├── event_subscribers.py   # 事件订阅者（9 个：5 原有 + 4 跨域闭环）
│   │   ├── proactive_suggestions.py # 主动建议引擎（含 record_action / 24h 评估）
│   │   ├── tool_loop.py           # 工具调用循环（含 v2.1 合规 RBAC 阻断）
│   │   ├── metrics_collector.py   # AI 指标采集
│   │   ├── rag/                   # RAG 检索
│   │   ├── skills/                # Skills（27 个 SKILL.md + 加载器 + 执行器，支持 depends_on 递归 + 门禁驱动 WorkflowSkillExecutor）
│   │   ├── tools/                 # 工具注册表（90 个工具，含 v2.0+ 工作流原语）
│   │   └── agents/                # Agent 定义 + 协作
│   ├── api/                       # FastAPI 路由（27 个包，含合规/学术/CSO）
│   │   ├── auth.py                # 认证
│   │   ├── sales/                 # 销售
│   │   ├── training/              # 培训
│   │   ├── decision/              # 决策
│   │   ├── collab/                # 协同
│   │   ├── knowledge/             # 知识
│   │   ├── ai/                    # AI 对话
│   │   ├── compliance/            # 合规管理（备案/承诺/AuditLog/22 项规则/违规/预警/时效）
│   │   ├── academic/              # 学术推广活动
│   │   ├── partner/               # CSO 委托管理
│   │   └── ...（crm / cfm / tools / mdm / audit / observability / settings / platform / collection / ppt_speech）
│   └── .env                       # 环境变量
├── frontend/                      # React 前端
│   └── src/
│       ├── pages/                 # 30+ 页面
│       │   ├── portal/            # 门户
│       │   ├── ai/                # AI 助手
│       │   ├── sales/             # 销售域 8 页面
│       │   ├── training/          # 培训域（含 PersonaLibrary / ScenarioParse / PPTSpeech / Experience 排行）
│       │   ├── decision/          # 决策域（含 ContextSwitcher 三维上下文）
│       │   ├── collab/            # 协同
│       │   ├── knowledge/         # 知识
│       │   └── ...
│       ├── components/            # 公共组件（含 ai/ AI 嵌入）
│       │   └── ai/               # ContextSwitcher / AIAssistantPanel / ProactiveSuggestions ...
│       ├── hooks/                 # 自定义 Hooks（useAIStream / useFetch）
│       ├── services/              # API 客户端
│       ├── stores/                # Zustand 状态（含 context.ts 三维上下文 store）
│       └── i18n/                  # 国际化（zh-CN / en）
└──
```

## 快速开始

```bash
# 任选一种方式启动 Neo4j 5.x
docker run -d --name salesclaw-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/neo4j123 \
  neo4j:5
# 或本地装：https://neo4j.com/download/
```

Neo4j 不可达时应用会**启动失败**。

### 1. 启动后端

```bash
conda activate salesclaw        # 建议使用 conda 环境 salesclaw（Python 3.12）
cd backend
pip install -r requirements.txt # 首次安装依赖
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

服务启动后：
- `bootstrap.require_neo4j()` 通过共享 `Neo4jConnectionManager.latency_probe()` 硬探测
- `bootstrap.run_startup()` 业务库 + Alembic 单树升级 + 种子数据
- 每天 06:00 定时任务为 13 个域预生成 AI 洞察
- `/health` + `/health/neo4j` 两个探针端点可观测系统状态

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:5173`，后端在 `http://localhost:8000`。前端 `/v1` 代理已指向 `http://127.0.0.1:8000`（避免 `localhost` 被解析为 IPv6 导致连接失败）。

### 3. 登录

默认账号（`admin / demo123 / demo`、`rep-001`、`mgr-001`，密码均为 `demo123`）。

### 4. 历史部署一次性数据迁移（可选）

如果从旧 v1.0 版本升级 + 已有 `psp_ontology.db`，可手动跑：

```bash
cd backend
python bootstrap/merge_ontology_to_business.py
```

合并 ontology 数据到 `psp.db`，原库归档为 `data/psp_ontology.db.archived`。幂等 marker `data/.merge_ontology_to_business.done` 存在时自动跳过。

## API 端点（按域分组）

| 域 | 端点前缀 | 说明 |
|---|---|---|
| 销售 | `/v1/sales/*` | 拜访计划 / 拜访记录 / 反馈 / 覆盖 / 积分 / 矩阵 / KOL / ROI |
| 培训 | `/v1/training/*` | 课程 / 考试 / 直播 / 路径 / 演练 / 进度 / 上岗备案工作流 |
| 决策 | `/v1/decision/*` | KPI / 归因 / What-if 模拟 / 预警 / AI 洞察 |
| 协同 | `/v1/collab/*` | 任务 / 审批 / 公告 / 文档 / 学术推广活动 |
| 知识 | `/v1/knowledge/*` | 空间 / 文档 / FAQ / 检索 |
| AI | `/v1/ai/*` | 对话 / 流式 / Skills / Agents / 协作 / 洞察刷新 |
| **合规** | `/v1/compliance/*` | **备案档案 / 承诺书 / AuditLog 校验 / 22 项规则 / 违规事件 / 预警 / 30 日时效 / 上岗准入** |
| **学术推广** | `/v1/academic/*` | **活动 CRUD / 审批 / 协议 / 签到 / 费用 / 反馈 / 归档 / 取消** |
| **CSO 委托** | `/v1/partner/*` | **合作机构 / 管理协议 / 授权书（含下发/撤销）** |
| CRM | `/v1/crm/*` | 客户管理 / 会议 |
| CFM | `/v1/cfm/*` | 配餐 / 留言 |
| 系统 | `/v1/mdm/*`、`/v1/platform/*`、`/v1/settings/*` | 主数据 / 平台 / 设置 |
| 可观测 | `/v1/audit/*`、`/v1/observability/*` | 审计（含 `/export` CSV/JSON 导出）/ 监控（告警、AI 事件流、死信队列均基于真实表动态派生） |

## 关键架构决策

### 1. 6 个域 Agent + 27 个 Skill

```
Supervisor（全局路由）
├── SalesAgent（销售执行域）
│   ├── visit-planner
│   ├── coverage-analyzer
│   ├── feedback-extractor
│   ├── scoring-analyzer
│   ├── roi-analyzer
│   ├── matrix-builder
│   ├── kol-analyzer
│   └── territory-reporter
├── TrainingAgent（智能培训域）
│   ├── course-recommender
│   ├── exam-generator
│   ├── live-scheduler
│   ├── path-optimizer
│   ├── scenario-generator
│   ├── practice-coach
│   └── pharma-rep-onboarding          # 医药代表上岗备案
├── DecisionAgent（决策支持域）
│   ├── kpi-monitor
│   ├── attribution-analyzer
│   ├── what-if-simulator
│   └── alert-manager
├── CollabAgent（协同办公域）
│   ├── task-prioritizer
│   ├── approval-assistant
│   ├── meeting-organizer
│   ├── report-builder
│   ├── report-generator
│   └── academic-activity-lifecycle    # 学术推广活动
└── KnowledgeAgent（知识库域）
    ├── rag-qa
    └── content-outsender
```

意图 → Skill 映射：1 个 Skill 覆盖 1 个意图（共 28 个意图全覆盖），三层映射 `INTENT_KEYWORDS → DOMAIN_AGENT_MAP → INTENT_SKILL_MAP`。其中 2 个 Phase 2 工作流 Skill 采用门禁驱动模式：`pharma-rep-onboarding`（7 门禁 6 Step）和 `academic-activity-lifecycle`（8 门禁 8 Step）。

### 2. 异步 LLM 调用

所有同步 LLM 调用都通过 `asyncio.to_thread` 包装（`llm_client.py::async_chat`），避免阻塞 uvicorn 事件循环。

### 3. AI 洞察定时预生成

| 时点 | 操作 |
|---|---|
| 每天 06:00 | 定时任务为所有租户 × 13 个域生成 AI 洞察，写入 `ai_insight_cache` 表 |
| 页面请求 | 直接查缓存表，命中今日 → < 5ms 返回 |

手动触发：`POST /v1/ai/insights/refresh`。

### 4. 27 个 API 包规范

每个 API 包拆分为：
- `__init__.py`：精简导出 `from .routes import router`
- `routes.py`：FastAPI 路由定义
- `schemas.py`：Pydantic 模型

### 5. 深度融合：ServicePort 协议层

跨域调用通过 Python `Protocol`（鸭子类型）+ `ServiceRegistry` 解耦，禁止跨域直接 import：业务层用 `registry.get(ProfileServicePort)` 获取接口（`get` 未命中返回 `None` 安全降级）。已注册 8 个 ServicePort：ProfileServicePort / CollectionServicePort / TrainingServicePort / DecisionServicePort / DataLineageServicePort 等。

### 6. 深度融合：4 个跨域闭环事件链

| 闭环 | 触发事件 | 跨域链路 |
|---|---|---|
| 采集→培训 | `collection_item_published` | 采集→画像回写→弱项检测→培训推荐→推送 |
| 培训→拜访 | `practice_session_completed` | 训练完成→能力提升→突破 80 阈值→推送进阶拜访建议 |
| 洞察→派单 | `insight_generated` | 洞察生成→决策建议派单→推送 KPI 告警 |
| 接受→反馈 | `recommendation_accepted` | 建议接受→行动记录→24h 自动评估→AI 学习反馈（调整权重） |

### 7. 深度融合：AI 学习闭环

`ai_insight_service.apply_feedback` 依据建议历史有效率自动调整洞察生成权重（持久化于 `Tenant.settings.insight_weights[domain]`）：有效率 < 0.3 降权 0.2（下限 0.3），> 0.7 升权 0.1（上限 1.5）。

### 8. 数据层

| 子系统 | v1.0 | v1.1 |
|---|---|---|
| 业务库 | `psp.db` | `psp.db`（本体合并进来） |
| 本体库 | `psp_ontology.db`（双库） | **合并到 psp.db**（同引擎 / 同 alembic 单树） |
| 图存储 + 版本 + 溯源 + 候选 | Neo4j / SQLite 二选一 | **Neo4j 强制**（运营要求）；启动 fail-fast |

关键路径：

- `bootstrap.require_neo4j()` 启动期硬探测；不可达抛 RuntimeError
- `Neo4jConnectionManager.acquire()` 懒初始化；4 store 共 1 个 driver
- `settings.NEO4J_MAX_POOL_SIZE=100` / `NEO4J_ACQUIRE_TIMEOUT=60.0`
- `GET /health/neo4j` 报连接池参数 + latency + 4 子系统节点/边计数
- 一次性数据迁移：`bootstrap/merge_ontology_to_business.py`（仅历史部署需要）

## 测试账号

| 角色 | 用户名 | 密码 | 租户 |
|---|---|---|---|
| 管理员 | admin | demo123 | demo |
| 代表 | rep-001 | demo123 | demo |
| 经理 | mgr-001 | demo123 | demo |

## License

内部项目，未开源。
