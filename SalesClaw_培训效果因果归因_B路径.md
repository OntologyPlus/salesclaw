# SalesClaw 培训效果因果归因 — B 路径规划

> 文档版本：v0.9（规划稿，未实施）
> 编写日期：2026-08-22
> 适用产品：SalesClaw - 药企医药代表 AI 原生统一平台
> 文档性质：业务 + 技术规划文档（Planning Doc）
> 读者对象：架构师、后端 / AI 工程师、PM、CEO 助理（产品侧）

---

## 0. 文档说明

### 0.1 背景与定位

CEO 最近的关注点集中在"**培训是否产生了效果**"。本年度公司在培训内容、学分、实战演练上投入了大量预算，但**实际工作产出是否因为培训而提升、哪些培训对哪些 KPI 有显著影响、不同人群对培训的反应是否不同**——这些问题目前数据无法回答。

本文档对应 **路径 B：1 周因果归因**（相比路径 A 的"2 天浅看板"和路径 C 的"1 月产品化"，路径 B 是平衡深度与时效的最优选项），目标是：

1. 在不破现有架构的前提下，**贯通"培训完成 → 能力画像变化 → 工作 KPI 变化"的因果链路**；
2. 用 **3 种归因方法** 交叉验证，形成 CEO 可信服的结论；
3. 复用既有 v1.1 的 AI 编排器（`evaluate` 意图），避免重复造轮子。

### 0.2 与既有文档的关系

- 与 **`SalesClaw_设计文档_v1.1.md`** 的关系：本文档属于 v1.1 中"决策域"（§5）的业务子方案，实施完成后，相关 data flow / API / 表结构将以 v1.1 修订版形式正式落库。
- 与 **`SalesClaw_backend_架构重组蓝图.md`** 的关系：架构蓝图约束"决策与效果归因走同一 AI 编排链路"，本文档是该约束的首次落点。

---

## 1. 业务背景

### 1.1 业务问题：CEO 的盲点

| 维度 | 现状 | 期望 |
|---|---|---|
| 培训投入产出 | 只能统计"上了多少课、考了多少分" | 能说出"某类培训平均让拜访量提升 X%" |
| 单次培训价值 | 无法回答"这次内训值不值" | 能开一份归因报告 |
| 培训差异化效果 | 无法区分"对谁有效" | 能分人群、分区域的疗效归因 |
| 内容迭代依据 | 只看考试通过率 | 能看实际工作行为变化 |
| KPI 影响归因 | 拜访 / 销售 KPI 涨了，猜原因 | 能把指标变化归到"是培训带来的" |

### 1.2 现有数据基础盘点（已无需新建的）

经过对 v1.1 配套代码的盘点，B 路径 **80% 组件已经具备**，本次实施是在"贯通数据流 + 加 AI 归因"两个方向上投入：

| 组件 | 位置 | 是否复用 | 复用方式 |
|---|---|---|---|
| `DecisionExecution` 表 | `backend/database.py:669` | ✅ 直接复用 | `decision_type='training'` |
| `DecisionExecution.baseline_metrics / target_metrics / actual_metrics` | 同上 | ✅ 直接复用 | 用画像 5 维 + 行为 KPI 做指标字典 |
| `EffectTrackingService._compute_score` | `backend/services/effect_tracking_service.py:204` | ✅ 直接复用 | 确定性达成率算法 |
| `EffectTrackingService.ai_evaluate` | 同上 `:383` | ✅ 直接复用 | 经编排器 `evaluate` 意图 |
| `apply_session_to_ability` | `backend/services/training_service.py:1237` | ✅ 直接复用 | 训练 → 能力画像更新 |
| `profile_service.update_ability_score` | `backend/services/profile_service.py:480` | ✅ 直接复用 | 增量 + 历史 + lineage |
| `profile_service.apply_decay` | 同上 `:593` | ✅ 直接复用 | 衰减反算基线 |
| `ProfileHistory` 表 | `backend/database.py` | ✅ 直接复用 | 提供时序能力快照 |
| `ability_decay_applied` 事件 / 事件总线 | `ai/event_bus.py` | ✅ 直接复用 | 训练→画像→归因闭环 |
| `evaluate` 编排意图（`effect-evaluator` agent） | v1.1 §6.24 | ✅ 直接复用 | AI 归因核心 |
| `ReasoningChain` / `provenance` | `governance/` | ✅ 直接复用 | 可解释、可追溯 |
| `GET /v1/decision/executions` 等 API 路由 | `routers/decision.py` | ✅ 直接复用 | 看板展示 |

**核心缺口（3 个）：**

1. ❌ 培训完成的瞬间**没有自动建 `DecisionExecution(decision_type='training')`**——这是数据流断裂；
2. ❌ `actual_metrics` 在滞后窗口结束后**没有异步回填机制**——画像快照无法自取；
3. ❌ 培训→画像→KPI 的因果证据**没有可解释的提示模板**——AI 归因需要补充 prompt 模板。

### 1.3 与 v1.1 既有能力的关系

v1.1 §6.24 已定义了 **`evaluate` 意图**：

| 意图 | Agent | API | 服务 | 落库 |
|---|---|---|---|---|
| `evaluate` | `effect-evaluator` | `POST /v1/decision/effect/evaluate` | `effect_tracking_service.ai_evaluate()` | `DecisionExecution.reasoning_chain_id` |

v1.1 §15.1 还规定了"四类 AI 原生推理意图"必须用统一 reasoning chain 与 provenance 呈现。本次规划严格执行：

- 不新增 Agent，复用 `effect-evaluator`；
- 不绕过编排器（七步状态机），所有 AI 归因都过 `Guardrails → Cache → Intent → Slot → Agent+Reflection → Hallucination → Persist`；
- AI 归因报告输出必须含 `reasoning_chain_id` + `provenance`（model_version / run_id）。

---

## 2. 目标与成功标准

### 2.1 业务成功标准

- **M1 / 2 天内**：打通"培训完成 → DecisionExecution 创建"管线，落首批 training 类型执行记录；
- **M2 / 1 周内**：上线 KPI 归因看板，CEO 能看见"最近 30 天培训带来的能力画像变化"和"同期对照组 KPI 差值"；
- **M3 / 1 周内**：对每条已完成的 training 执行，可生成 AI 归因报告（含 verdict / reasons / reasoning_chain_id）。

### 2.2 技术成功标准

- 培训完成的同步延迟：**< 500 ms**（在当前主流程上 +1 次 INSERT）；
- 滞后窗口回填任务的 SLA：< 30 分钟（最坏的 180 天窗口情况，每天跑一次足够）；
- AI 归因评估的端到端时延 P50：**< 3 s**（mock 模式）/ **< 15 s**（真实 LLM）；
- 系统不破坏现有路径——回滚成本仅为下线 1 个事件订阅者。

### 2.3 不在本次范围

- ❌ A/B 测试（对照组）的实验分组功能（路径 C 才做）；
- ❌ 跨租户的总体归因（路径 C 才做）；
- ❌ 自动化的"低效培训下线"建议（路径 C 才做）；
- ❌ 单次培训内容的 NLP 智能分析（路径 C 才做）。

---

## 3. 设计原则

| 原则 | 说明 |
|---|---|
| P1 复用优先 | 任何能用现有 v1.1 组件解决的功能，**禁止新建**。 |
| P2 同步少，异步多 | 培训完成同步只做"建 DecisionExecution(planned) + baseline 快照"；actual 采集全异步调度。 |
| P3 可解释 | 所有 AI 归因输出必须经过编排器七步，落 `reasoning_chain_id`，前端可点开看到 reasoning 链。 |
| P4 失败降级 | 任一环节失败，必须有可观测的降级路径（确定性算法 / mock orchestrator / 看板降级）。 |
| P5 不破坏现存路径 | 新增管线必须"挂接式"而非"改造式"——通过事件订阅 + 新建领域 service，避免动到调用链热点。 |
| P6 数据最小化 | 不为本次规划新增任何 PII 字段；所有指标聚合后才能展示，不暴露个人明细到日志。 |
| P7 同源性 | 任何用于归因的画像分数，必须来自同一份 `AbilityProfile`，且能通过 `ProfileHistory.delta` 推回原始 `source`。 |

---

## 4. 总体方案概览

### 4.1 三种归因方法一图概括

```
┌──────────────────────────────────────────────────────────────────────┐
│                       培训效果因果归因（B 路径）                     │
│                                                                      │
│   培训完成事件                                                        │
│       │                                                              │
│       ├──→ M1 同步路径 ──→ DecisionExecution(decision_type="training")│
│       │       写 baseline_metrics = 当前画像快照                       │
│       │       写 target_metrics = 培训宣称目标                         │
│       │       status = planned                                        │
│       │                                                              │
│   滞后窗口到期（30/90/180 d）                                          │
│       │                                                              │
│       ├──→ M2 异步路径 ──→ 回填 actual_metrics，重新算 effectiveness_score │
│       │                                                              │
│       │                                                              │
│       ▼                                                              │
│   归因引擎（4 个）                                                    │
│   ┌────────────────────────────────────────────────────────────┐     │
│   │ M_a 滞后期效果曲线（lag curve）                              │     │
│   │   拉 [t0-d0, t0+30, t0+90, t0+180] 4 个时间点                │     │
│   │   对比画像 5 维 + KPI 多维                                    │     │
│   ├────────────────────────────────────────────────────────────┤     │
│   │ M_b 同期类比组（cohort comparison）                          │     │
│   │   同 cohort 中"修了培训" vs "未修" 同期 KPI 差               │     │
│   ├────────────────────────────────────────────────────────────┤     │
│   │ M_c AI 归因（causal attribution）                            │     │
│   │   经编排器 evaluate 意图，给出 verdict + reasons            │     │
│   │   复用 effect_tracking_service.ai_evaluate + ReasoningChain │     │
│   └────────────────────────────────────────────────────────────┘     │
│       │                                                              │
│       ▼                                                              │
│   CEO 看板：培训投入产出总结 + 每条 DecisionExecution 的归因报告        │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.2 数据流全景（端到端）

```
1. 训练完成事件（course_completed / practice_session_completed / exam_passed）
        │
        │  event_bus.publish("training_session_completed", payload)
        ▼
2. 新事件订阅者（event_subscribers.py 中新增）
        │  take_snapshot_of_ability_profile(user_id)
        │  effect_tracking_service.create_execution(
        │      decision_type="training",
        │      baseline=<5 维画像快照 + 行为 KPI 快照>,
        │      target=<培训宣称的目标画像维增量 / KPI 目标>)
        │  写 DecisionExecution，status=planned
        ▼
3. （30/90/180 天后）异步调度器
        │  take_snapshot_now(user_id) → actual_metrics
        │  effect_tracking_service.update_progress() → status=executing
        ▼
4. 滞后到期（窗口终点的当下）
        │  effect_tracking_service.complete_execution()
        │  → 自动 _compute_score → effectiveness_score
        │  → status=completed
        ▼
5. 看板 / 报告：
        │  M_a：effective_lag_curve(user_id, training_id)
        │  M_b：cohort_compare(group_a, group_b, period)
        │  M_c：effect_tracking_service.ai_evaluate(execution_id) ← 复用
```

### 4.3 与既有 9 个事件订阅者的关系

v1.1 §11 已经规定了 9 个事件订阅者（5 原有 + 4 跨域闭环）。本次新增 **第 10 个订阅者**——专门处理 `"course_completed" / "practice_session_completed" / "exam_passed"` 三类事件，任务只有 2 个：

1. 同步写 DecisionExecution；
2. 调度滞后回填（用 `core/scheduler.py` 的轻量队列）。

不在原有订阅者职责里加新功能，是为了遵守 v1.1 架构蓝图的"订阅者 = 单职责"约束。

---

## 5. 方法 A — 滞后期效果曲线（lag curve）

### 5.1 算法

**核心思想**：以"培训完成时刻"为 t0，沿着固定时间轴 [t0-7d, t0+30d, t0+90d, t0+180d] 采集同一画像 + 同一组 KPI 的快照，画曲线看是否分时段提升。

**4 个采样点**：

| 时刻 | 命名 | 数据来源 |
|---|---|---|
| t0 - 7d | 基线 | `ProfileHistory` 中 t0-7d 附近的 + `BehaviorPointRecord` 月度统计 |
| t0（培训完成瞬间） | 教学期 | `AbilityProfile` 当下快照（已存在） |
| t0 + 30d | 短期 | `AbilityProfile` + 当月 `VisitRecord` 聚合 |
| t0 + 90d | 中期 | 同上 |
| t0 + 180d | 长期 | 同上 |

**计算逻辑**（伪代码）：

```python
def lag_curve(user_id, training_execution_id, windows=(30, 90, 180)):
    training_exec = get_execution(training_execution_id)
    t0 = training_exec.created_at

    # t0 基线 = baseline_metrics（已经是快照）
    series = [{"t": 0, "label": "t0_baseline", "snapshot": training_exec.baseline_metrics}]

    for w in windows:
        snap = snapshot_at(user_id, t0 + timedelta(days=w))
        series.append({"t": w, "label": f"t0+{w}d", "snapshot": snap})

    # 维度 diff 序列
    diff_series = {}
    for dim in ABILITY_DIMENSION_KEYS + KPI_DIMENSION_KEYS:
        diff_series[dim] = [
            {"t": point["t"], "delta": point["snapshot"][dim] - series[0]["snapshot"][dim]}
            for point in series
        ]

    return {"series": series, "diffs": diff_series}
```

### 5.2 数据需求

- `DecisionExecution.baseline_metrics` 中已经存了 t0 基线；
- `ProfileHistory`（已有的画像历史表）天然提供 5 维画像的时序；
- t0+30/90/180 的 KPI 来自 `VisitRecord`、`BehaviorPointRecord`、`VisitFeedback` 等月度聚合。

**因此方法 A 不需要新表，只是一个查询 + 聚合函数。**

### 5.3 阈值的含义

| 维度 | "显著提升"判定 |
|---|---|
| 5 维画像 | 较 t0 ± 5 分以上 |
| 月拜访量 | 较 t0 ± 10% 以上 |
| 反馈正面率 | 较 t0 ± 5% |
| 月新增医生 | 较 t0 ± 10% |

阈值可配（见 §12）。如果培训宣称的目标是"拜访技巧 +5"，那么画像的 `visit_skill` 至少 ≥ 5 时点亮。

---

## 6. 方法 B — 同期类比组（cohort comparison）

### 6.1 算法

**核心思想**：在**同一 cohort**（同一部门、同一角色、同一区域、同一入司季度）中，找出"修了同一类培训"和"未修"两个子群，比较同期 KPI 的**差值**与**差值的统计显著性**。

**步骤**：

1. 给每次培训打上 `cohort_key`（如 `"region=East, role=MR, quarter=2026Q3"`）；
2. 在同一 `cohort_key` 中，按"是否修了某类培训"做二分；
3. 取同期 30/90/180 天的 KPI 序列，做**双样本 t 检验**（或 Mann-Whitney U 检验，对小样本稳健）；
4. 输出：差值估计 + p-value + 95% CI。

### 6.2 控制变量

| 控制维度 | 来源 |
|---|---|
| 同一 cohort_key | `User.dept_id / region / role / hire_quarter` |
| 同期窗口 | KPI 窗口与训练完成日对齐 |
| 移除离群点 | 单月 KPI 离群 (z-score > 3) 排除 |
| 朴素调整 | 多变量回归（控制画像基线、年龄、机构规模）— 后置步骤（M2 内可选） |

### 6.3 数据需求

- `User` 表已有 `dept_id / region / role / hire_quarter`；
- 同期 KPI 复用方法 A 的聚合；
- 训练修了哪类从 `Course.category` / `PracticeScenario.target_skills` 提取。

### 6.4 输出

```json
{
  "cohort_key": "region=East, role=MR, quarter=2026Q3",
  "treated_n": 38,
  "control_n": 24,
  "metric": "monthly_visit_count",
  "treated_mean": 18.2,
  "control_mean": 14.7,
  "diff": 3.5,
  "p_value": 0.013,
  "ci95": [0.8, 6.2],
  "is_significant": true
}
```

---

## 7. 方法 C — AI 归因开方（causal attribution via Orchestrator）

### 7.1 编排器链路（reuse）

直接复用 `effect_tracking_service.ai_evaluate()`。但需要在 prompt 与 evidence 上做培训场景适配：

```
                                 ┌───────────────────────────┐
                                 │   Orchestrator 七步状态机   │
                                 └───────────┬───────────────┘
                                             │
   evidence_payload = {                       │
     baseline_metrics,                       │
     target_metrics,                         │
     actual_metrics,        ──────────────►   │
     evidence_clues *(新)*,                   │
     training_meta,                          │
   }                                         │
                                             │
                                             ▼
                            effect-evaluator（已有 agent）
                                             │
                                             ▼
                                verdict + reasons + summary
                                             │
                                             ▼
                       DecisionExecution.reasoning_chain_id
```

### 7.2 evidence_clues 线索源

为了让 AI 归因能"找到证据"，在 `ai_evaluate()` 上下文中**额外附带 evidence_clues**：

| 线索 | 数据来源 | 说明 |
|---|---|---|
| profile_delta | `ProfileHistory` 中 `source='training'` 的最近 N 条 | 培训直接贡献了哪几维 |
| exam_score | `ExamRecord` 中同一培训关联的考试 | 知识掌握程度 |
| visit_feedback_shift | `VisitFeedback.sentiment` 前后对比 | 行为落地 |
| behavior_points | `BehaviorPointRecord` 增量 | 行为积分变动 |
| decay_lifted | `AbilityProfile.decay_factor` 变化 | 抵消了衰减 |
| scenario_pass_count | `PracticeSession` 计数 | 演练通过率 |
| collateral_kpi | `VisitRecord.visit_count` 等同期数据 | 行为 KPI 是否提升 |

每条线索结构：

```json
{
  "clue_type": "profile_delta",
  "dimension": "visit_skill",
  "delta": 4.5,
  "source": "training",
  "source_id": 1234,
  "evidence_at": "2026-07-15T10:30:00Z",
  "weight_hint": 0.3
}
```

> `weight_hint` 是先验权重（基于来源可信度），AI 在归因时可参考、但不需要照搬——它只是输出框架的"倾向"。

### 7.3 output_schema（AI 输出结构）

复用 v1.1 中 `evaluate` 意图的输出（已落 `DecisionExecution.reasoning_chain_id`），并在 `reasons[]` 元素上加上"线索索引"以可追溯：

```json
{
  "verdict": "partial_achieved" | "achieved" | "not_achieved",
  "achievement_rate": 0.83,
  "summary": "本次《高端客户拜访实战》培训后 90 天内，拜访技巧 +3.2、客情 +1.8，对应月拜访量提升 11%，客情反馈正面率提升 4%……",
  "reasons": [
    {
      "factor": "visit_skill",
      "status": "above_target",
      "contribution": 0.55,
      "detail": "画像从 71 → 74.2，超出目标 +3.2",
      "evidence_clue_indices": [0, 5]
    },
    {
      "factor": "monthly_visit_count",
      "status": "above_target",
      "contribution": 0.35,
      "detail": "月拜访量从 15 → 17，提升 13.3%",
      "evidence_clue_indices": [6]
    }
  ],
  "confidence": 0.82,
  "reasoning_chain_id": "rc_xxx",
  "provenance": {
    "mode": "ai_orchestrated",
    "intent": "evaluate",
    "agent": "effect-evaluator",
    "model_version": "Qwen/Qwen3-...",
    "run_id": "..."
  },
  "trace_id": "..."
}
```

### 7.4 与 mock / 真实 LLM 的兼容

- mock 模式：编排器同样跑七步状态机，仅 LLM 调用返回静态 JSON，能完整产出 `verdict / reasons / reasoning_chain_id`；
- 真实 LLM 模式：把 `evidence_clues` + `training_meta` 一并塞进 prompt（见 §13）；
- 失败降级：`_compute_score` 确定性兜底返回，仍有 verdict（achieved/partial_achieved）与 reasons 数组对齐。

---

## 8. 数据流与表结构变更

### 8.1 现有 `DecisionExecution` 表与新增字段

**决策**：**不新增表，不新增任何字段**。原表已经够用：

```python
# database.py:669 已定义
class DecisionExecution(BusinessBase, BaseFields):
    __tablename__ = "decision_executions"
    user_id, decision_type, title, description,
    baseline_metrics, target_metrics, actual_metrics,
    status, started_at, completed_at,
    effectiveness_score, reasoning_chain_id
```

**唯一新增约束**：通过 Alembic 校验 5 个 JSON 字段的存储结构（非 schema 约束，而是 service 层契约）。

### 8.2 为什么不用新表

| 选项 | 评估 |
|---|---|
| 新增 `training_attribution` 表 | ❌ 与 `DecisionExecution` 重复，过度工程 |
| 新增 `training_signal_snapshot` 表 | ❌ `ProfileHistory` 已经有，冗余 |
| 复用 `DecisionExecution` | ✅ schema 已就绪 |

### 8.3 baseline / target / actual 三组指标的契约

为了让 3 种归因方法都能消费，**统一约定 metric_key 字典**（写在 `core/constants.py` 新增）：

```python
# 培训归因标准 metric 字典
TRAINING_EFFECT_METRICS = {
    # 5 维画像
    "product_knowledge":   {"kind": "ability", "weight": 0.20, "unit": "score_0_100"},
    "visit_skill":         {"kind": "ability", "weight": 0.25, "unit": "score_0_100"},
    "customer_relation":   {"kind": "ability", "weight": 0.20, "unit": "score_0_100"},
    "compliance":          {"kind": "ability", "weight": 0.15, "unit": "score_0_100"},
    "ai_application":      {"kind": "ability", "weight": 0.20, "unit": "score_0_100"},
    # 行为 KPI
    "monthly_visit_count": {"kind": "kpi",     "weight": 0.30, "unit": "count"},
    "feedback_positive_rate":{"kind": "kpi",   "weight": 0.25, "unit": "ratio_0_1"},
    "behavior_points":     {"kind": "kpi",     "weight": 0.20, "unit": "score_0_100"},
    "new_doctors_monthly": {"kind": "kpi",     "weight": 0.25, "unit": "count"},
}
```

`baseline` 用 `snapshot_at(t0-7d)` 抓画像 + 最近 30 天 KPI；`target` 用培训声称的目标（如 `Course.target_skills` 字段未建，可暂用规则：score 高于当前 baseline + `training_target_score` 配置项）；`actual` 用 `snapshot_at(t0+window)` 的同一份聚合函数。

---

## 9. 关键流程

### 9.1 培训完成 → 自动开 DecisionExecution

**触发点**：3 个事件

| 事件 | 触发 service | 当前是否触发？ | 改造 |
|---|---|---|---|
| `course_completed` | `training_service.update_course_progress` | ✅ 已发 | 新增订阅者 → 建 exec |
| `practice_session_completed` | `training_service.apply_session_to_ability` | ✅ 已发 | 新增订阅者 → 建 exec |
| `exam_passed` | `training_service.submit_exam` | （未发，需加） | 加事件触发 + 新增订阅者 |

**新增订阅者（伪代码）**：

```python
# event_subscribers.py (新增第 10 个)
def on_training_completed(payload):
    user_id = payload["user_id"]
    tenant_id = payload["tenant_id"]
    training_event_id = payload["session_id"] or payload["course_id"] or payload["exam_id"]

    # 1. baseline 快照
    baseline = snapshot_metrics(user_id, kind="baseline")
    # 2. target 推算
    target = compute_target_from_training_meta(payload)
    # 3. 建 DecisionExecution
    exec_row = effect_tracking_service.create_execution(
        user_id=user_id, tenant_id=tenant_id,
        decision_type="training",
        title=payload.get("title", f"Training #{training_event_id}"),
        description=payload.get("description"),
        baseline=baseline, target=target,
    )
    # 4. 调度回填（30/90/180 d）
    schedule_lag_callbacks(exec_row["execution_id"], user_id, tenant_id)
```

### 9.2 滞后窗口 → 异步回填 actual_metrics

**调度器**（v1.1 已有 `core/scheduler.py` 的轻量队列；如无大材小用方案，可用一个新文件 `services/lag_scheduler.py`）：

```python
def schedule_lag_callbacks(execution_id, user_id, tenant_id):
    for window_days in (30, 90, 180):
        fire_at = datetime.utcnow() + timedelta(days=window_days)
        register_callback(
            fire_at=fire_at,
            fn=cb_lag_window_expired,
            args={"execution_id": execution_id, "user_id": user_id,
                  "tenant_id": tenant_id, "window": window_days},
        )

def cb_lag_window_expired(args):
    actual = snapshot_metrics(args["user_id"], kind="actual_lag", window_days=args["window"])
    effect_tracking_service.update_progress(
        execution_id=args["execution_id"], tenant_id=args["tenant_id"],
        actual_metrics=actual,
    )

def cb_lag_window_terminal(args):
    # 180 天窗口到期时一次性 complete
    effect_tracking_service.complete_execution(
        execution_id=args["execution_id"], tenant_id=args["tenant_id"],
    )
```

### 9.3 KPI 看板拉取口径

CEO 看板（前端 `/v1/training/effect/overview`）按以下口径：

```
GET /v1/training/effect/overview?tenant_id=&period=30d
```

返回：

```json
{
  "summary": {
    "completion_count": 1247,
    "executions_count": 1247,
    "lag_curve_completed_count": 812,    // t0+30 已回填的
    "ai_attributed_count": 412,          // 已调用 ai_evaluate 的
    "overall_effectiveness_avg": 78.4    // overall_effectiveness_score 平均
  },
  "by_dimension": [
    {"dim": "visit_skill", "n": 812, "mean_delta": 4.1, "achievement_rate": 0.82},
    ...
  ],
  "by_course_category": [...],
  "top3_courses": [...]
}
```

---

## 10. API 设计

### 10.1 新增训练侧 API（4 个）

```
# 列表查询某次培训的归因报告
GET /v1/training/effect/executions
    query: tenant_id, user_id, period, status, page

# 单条归因详情（含 AI 报告）
GET /v1/training/effect/executions/{execution_id}
    response: {... exec_data + last_ai_evaluation ...}

# 触发 AI 归因评估（异步；秒级返回，已评估的直接命中缓存）
POST /v1/training/effect/evaluate
    body: {execution_id}
    response: {ok, task_id, cached_result?}

# 滞后期曲线（前端画图用）
GET /v1/training/effect/lag-curve
    query: execution_id | (training_id, user_id)
    response: {windows: [0, 30, 90, 180], series: {...}, diff: {...}}
```

### 10.2 复用 decision 域既有 API

```
GET /v1/decision/executions?decision_type=training  # 列表
GET /v1/decision/executions/{id}                    # 详情
POST /v1/decision/effect/evaluate                   # 已存在的 AI 归因入口
```

**新 API 与既有 API 的关系**：

| 既有 | 新增 | 关系 |
|---|---|---|
| `/v1/decision/executions?decision_type=training` | `/v1/training/effect/executions` | 新增路由是"training 域的视图包装"，加缓存、加业务字段；既有路由保留 |
| `/v1/decision/effect/evaluate` | `/v1/training/effect/evaluate` | 同上的对称设计；training 域入口 |

> 不动 `/v1/decision/*` 的现有响应/字段，新增的 `/v1/training/effect/*` 是"training 域的细化视图"。

---

## 11. 前端呈现（CEO 视角）

### 11.1 总览看板

`/training/effect/overview`（训练效果总览）

- 顶部 KPI 卡片：总培训次数 / 平均 effectiveness_score / "明显提升"占比 / "无明显变化"占比 / "负向"占比；
- 中间图表：6 个月 effectiveness_score 趋势；
- 下方表格：top10 高效果课程 / 培训类型。

### 11.2 单次培训归因报告

`/training/effect/{execution_id}`

- 头部：基本元数据 + effectiveness_score + verdict；
- 中部：方法 A 的 lag curve 4 点曲线；
- 下部：方法 B 的 cohort 对比（差值、p-value、CI）；
- 底部：方法 C 的 AI 报告，点击可展开 reasoning_chain + provenance + clues。

### 11.3 对接 AI Embedding Layer

- `AIInsightPanel` 自动推送"你的某次培训报告显示效果显著高于 cohort 中位数"；
- `AISidebar` 显示"本季度培训 ROI 评估"快捷入口；
- `ReasoningView` 复用 v1.1 已有的组件展示 effect-evaluator 的推理链。

---

## 12. 配置与可调阈值

新增 `config.py` 配置项（与 v1.1 风格一致）：

```python
# 培训效果归因相关
TRAINING_LAG_WINDOWS = (30, 90, 180)               # 滞后窗口
TRAINING_LAG_DELTA_THRESHOLD = 5.0                 # 画像显著提升阈值（分）
TRAINING_KPI_DELTA_THRESHOLD_RATIO = 0.10          # KPI 显著提升阈值（比例）
TRAINING_CO_HORT_MIN_SAMPLE = 8                    # 类比组最小样本
TRAINING_EVAL_CONFIDENCE_FLOOR = 0.6               # AI 评估置信度下限
TRAINING_EVAL_AUTO_RUN_HOURS = 24                  # 滞后窗口结束 N 小时后自动调用 ai_evaluate
TRAINING_TARGET_SCORE_DEFAULT = 3.0                # 培训声称目标缺省增量
```

---

## 13. AI 归因 prompt 模板（草案）

复用 v1.1 中 `effect-evaluator` 的 system prompt 上下文，**在 user 段追加训练场景专属 evidence**：

**system（已存在）**：

```text
你是医药代表培训效果归因专家。请基于 baseline / target / actual 三组指标，
结合提供的 evidence_clues，对一次"培训完成事件"输出归因结论。
```

**user 段（草案）**：

```text
## 执行基本情况
- execution_id: {exec_id}
- 培训主题: {title}
- 受训人 user_id: {user_id}
- 培训宣称目标（target_metrics 节选）:
{json.dumps(target_metrics, ensure_ascii=False, indent=2)}

## 培训前画像快照（baseline）
{json.dumps(baseline, ensure_ascii=False, indent=2)}

## 培训后实际表现（actual，取自 {window_days} 天滞后窗口）
{json.dumps(actual, ensure_ascii=False, indent=2)}

## Evidence Clues（线索）
{json.dumps(evidence_clues, ensure_ascii=False, indent=2)}

## 训练元数据
- 课程/演练类型: {meta.scenario_type | meta.course_type}
- 培训时长: {meta.duration_minutes} min
- 同期 cohort_key: {meta.cohort_key}
- 同期样本量: treated_n={meta.treated_n}, control_n={meta.control_n}

## 输出 JSON
{
  "verdict": "achieved|partial_achieved|not_achieved",
  "achievement_rate": 0.0~1.0,
  "summary": "≤ 200 字中文摘要",
  "reasons": [
    {"factor": "维度名", "status": "above_target|at_target|below_target",
     "contribution": 0.0~1.0, "detail": "一句话说明",
     "evidence_clue_indices": [int, ...]}
  ],
  "confidence": 0.0~1.0
}

## 严格约束
1. 任何"显著提升"声明必须有 evidence_clue_indices 指向；
2. achievement_rate 必须能由 baseline / target / actual 推算口径一致；
3. 不要给出 original 字段或 finance 数字（合规原因）；
4. 不确定时 confidence ≤ 0.5，并在 summary 中明示"证据不足以定论"。
```

---

## 14. 风险与前置条件

### 14.1 风险清单

| # | 风险 | 触发 | 缓解 |
|---|---|---|---|
| R1 | 培训完成后未自动触发 DecisionExecution（事件丢失） | 订阅者挂掉 | 写兜底 cron 每日扫 `ProfileHistory` 中 source=training 且无对应 exec 的孤儿记录 |
| R2 | 滞后窗口回填时找不到用户画像（用户已离职 / 已删档） | 用户删档 | 实际数据用 `last known snapshot` 兜底；status 标 `partial` |
| R3 | AI 归因的长 prompt 触发 token 超限 | evidence_clues 太多 | 限制 clues ≤ 12 条，按"距 t0 最近 + 最相关"排序裁剪 |
| R4 | mock 模式下产出的 verdict 不真实 | 测试环境 | mock verdict 与 _compute_score 保持一致；上线前在 staging 跑一次真实 LLM |
| R5 | 看板查询慢（5 维画像 × 4 时间点 × 全公司用户） | 数据量大 | Redis 缓存单次结果，TTL = 6h；看板按部门下钻 |
| R6 | 同期类比组样本不足（< 8） | 小部门 | 指标上标"样本不足"灰色；不下结论 |
| R7 | CEO 误读 verdict 文字 | 缺少校准说明 | 报告页顶部加"verdict 说明"解释（partial_achieved ≠ 失败） |

### 14.2 前置条件清单

| # | 前置 | 状态 |
|---|---|---|
| PR1 | 既有 `DecisionExecution` / `EffectTrackingService` / `effect-evaluator` agent 全部可用 | ✅ v1.1 已在 |
| PR2 | `ProfileHistory` 写入覆盖 `source='training'` 的能力分变化 | ✅ `profile_service.update_ability_score` 已处理 |
| PR3 | event_bus 允许新订阅者注册 | ✅ v1.1 的 9 个订阅者机制可扩 |
| PR4 | Neo4j 图数据库可用（治理查询） | ✅ v1.1 §1.4 强约束 |
| PR5 | Scheduler 轻量队列可挂载新回调 | ⚠ 需轻度扩展 `core/scheduler.py`（小工） |

---

## 15. 实施步骤（约 1 周）

| Day | 任务 | 交付物 | 负责人 |
|---|---|---|---|
| D1 | 在 `event_subscribers.py` 中新增 `on_training_completed`，挂到 3 个事件 | 新订阅者 + 单元测试 | 后端 |
| D1 | `services/training_service.py` 中给 `submit_exam` 通过后发 `exam_passed` 事件 | 事件补全 | 后端 |
| D1 | 在 `core/constants.py` 新增 `TRAINING_EFFECT_METRICS` 与 4 个配置项 | 常量 + config | 后端 |
| D2 | 新增 `services/training_effect_snapshot.py`：baseline / actual 快照聚合函数 | service + tests | 后端 |
| D2 | 新增 `services/lag_scheduler.py`：4 个调度回调函数 | service + tests | 后端 |
| D2 | 新增 `routers/training_effect.py`：4 个新 API + OpenAPI 文档 | router + smoke test | 后端 |
| D3 | 复用 / 适配 `effect-evaluator` 训练场景 prompt；补充 evidence_clues 装配 | prompt 模板 + mock 校验 | AI + 后端 |
| D3 | 端到端冒烟：构造 → 触发 → 调度（用 fake_today 跳过 lag）→ 看板拉取 | 截图 + curl 记录 | 后端 + QA |
| D4 | 新增前端页面 `/training/effect/overview` 与 `/training/effect/{id}` | 页面 + 路由 | 前端 |
| D5 | 真实数据集回归：拉 30 天历史培训数据比对 effectiveness_score 与人工评估 | 数据报告 | QA |
| D5 | 文档修订 v1.2：将本次新增管线、API、prompt 落 v1.1 修订版 | 文档 | 架构 |

---

## 16. 验收标准

### 16.1 功能验收

- [ ] 课程完成 → DecisionExecution 创建成功（status=planned）；
- [ ] 演练完成 → DecisionExecution 创建成功；
- [ ] 考试通过 → DecisionExecution 创建成功；
- [ ] 180 天滞后窗口到期 → actual_metrics 自动回填 + effectiveness_score 自动计算；
- [ ] M_a（滞后期曲线）能拉出 [0, 30, 90, 180] 4 点；
- [ ] M_b（同期类比组）能输出 t 检验 + 95% CI；
- [ ] M_c（AI 归因）能生成结构化 JSON，且 reasoning_chain_id 可追溯；
- [ ] 4 个新 API 全部 200，且 Swagger 文档完整。

### 16.2 非功能验收

- [ ] 培训完成的同步 P95 延迟 < 500 ms；
- [ ] mock / 真实 LLM 双链路均可走通；
- [ ] mock / 真实 LLM 切换不需要改业务代码（保持 v1.1 编排器边界）；
- [ ] 任一环节失败可降级到 `_compute_score` 确定性算法；
- [ ] 所有 AI 归因输出均含 provenance（model_version / run_id）；
- [ ] 0 Lint 错误（保持现有 PEP8 / lint 习惯）；
- [ ] 回滚成本 ≤ 1 个事件订阅者下线。

### 16.3 业务验收

- [ ] CEO 能在 1 次登录后看到"培训整体效果"总览；
- [ ] 任意 1 场培训能给出归因报告，含 verdict / reasons / 群组对比；
- [ ] 报告可分享、可导出 PDF（CEO 助理诉求）；
- [ ] 报告页含解释性"verdict 说明"避免误读。

---

## 17. 未来扩展（不在本次）

- C 路径（1 月产品化）：A/B 实验分组、自动化建议下架、内容 NLP 分析；
- 跨租户全局归因（药企并购场景）；
- "培训 ROI 仪表盘"嵌入 CEO 周报生成器；
- 跟 `insight` 意图打通：AI 自动推送"低效培训榜单"。

---

## 附录 A. 与 v1.1 的差异（修订点）

实施完成后，本次新增内容会同步落到 v1.1 → v1.2 的修订记录：

| 章节 | 修订 |
|---|---|
| §5 决策域 | 新增 §5.X 培训效果因果归因 |
| §6.24 AI 原生推理意图 | `evaluate` 补充 training 场景 evidence_clues |
| §11 事件总线 | 订阅者从 9 → 10 |
| §15 数据表 | 说明 DecisionExecution 复用 strategy |
| §16 API 列表 | 新增 4 个 `/v1/training/effect/*` 端点 |
| 附录 A. 配置项 | 增加 §12 的 7 个配置 |

---

## 附录 B. 验收测试用例（草案）

```python
# tests/test_training_effect_attribution.py

def test_course_completed_creates_decision_execution():
    # event 触发 → 异步建 exec
    publish("course_completed", {"user_id": 1, "course_id": 10})
    wait(0.5)
    execs = get_executions(decision_type="training", user_id=1)
    assert len(execs) >= 1

def test_lag_callback_updates_actual_metrics():
    # 用假时钟跳到 t0+30d
    with mock_time(days_offset=30):
        run_pending_callbacks()
        exec = get_execution(exec_id)
        assert exec.status == "executing"
        assert exec.actual_metrics != {}

def test_complete_execution_computes_effectiveness():
    with mock_time(days_offset=181):
        run_pending_callbacks()
        exec = get_execution(exec_id)
        assert exec.status == "completed"
        assert 0 <= exec.effectiveness_score <= 100

def test_ai_evaluate_with_mock_orchestrator():
    result = effect_tracking_service.ai_evaluate(exec_id, tenant_id, db)
    assert result["verdict"] in {"achieved", "partial_achieved", "not_achieved"}
    assert result["reasoning_chain_id"]

def test_cohort_comparison_small_sample_marks_gray():
    out = cohort_compare(cohort_key="region=East", n_min=8)
    if out["treated_n"] < 8 or out["control_n"] < 8:
        assert out["is_significant"] is False
        assert "样本不足" in out.get("warning", "")

def test_lag_curve_returns_4_points():
    out = lag_curve(user_id=1, execution_id=exec_id)
    assert len(out["series"]) == 4
    assert all(p["t"] in (0, 30, 90, 180) for p in out["series"])
```

---

**文档结束。**
