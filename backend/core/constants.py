"""全局常量定义 — N+4 深度融合版本

包含能力画像维度、衰减系数、建议采纳率阈值等跨域共享常量。
"""

# ──────────────────────────────────────────────
# 能力画像 5 维定义
# ──────────────────────────────────────────────

ABILITY_DIMENSIONS = [
    ("product_knowledge", "产品知识"),
    ("visit_skill", "拜访技巧"),
    ("customer_relation", "客户关系"),
    ("compliance", "合规意识"),
    ("ai_application", "AI 应用"),
]

# 维度名称 → 中文名称映射
ABILITY_DIMENSION_MAP = {key: label for key, label in ABILITY_DIMENSIONS}

# 所有维度键列表
ABILITY_DIMENSION_KEYS = [key for key, _ in ABILITY_DIMENSIONS]


# ──────────────────────────────────────────────
# 画像衰减机制
# ──────────────────────────────────────────────

# 无训练天数阈值（超过此天数开始衰减）
DECAY_THRESHOLD_DAYS = 30
# 衰减比例（每次衰减降低的分数百分比）
DECAY_RATE = 0.05  # 5%


# ──────────────────────────────────────────────
# 建议行动闭环
# ──────────────────────────────────────────────

# 建议采纳率低于此阈值时降权
SUGGESTION_LOW_ADOPTION_THRESHOLD = 0.30
# 降权后生成概率下降比例
SUGGESTION_DEMOTE_FACTOR = 0.5
# 延迟评估时间（小时）
SUGGESTION_EVALUATION_DELAY_HOURS = 24


# ──────────────────────────────────────────────
# 因果链深度限制
# ──────────────────────────────────────────────

# 洞察因果链最大深度
MAX_CAUSAL_CHAIN_DEPTH = 3
# Skill 依赖链最大深度
MAX_SKILL_DEPENDENCY_DEPTH = 5


# ──────────────────────────────────────────────
# 画像更新来源类型
# ──────────────────────────────────────────────

ABILITY_SOURCE_TRAINING = "training"
ABILITY_SOURCE_VISIT = "visit"
ABILITY_SOURCE_COLLECTION = "collection"
ABILITY_SOURCE_FEEDBACK = "feedback"
ABILITY_SOURCE_AI = "ai"

ABILITY_SOURCE_TYPES = [
    ABILITY_SOURCE_TRAINING,
    ABILITY_SOURCE_VISIT,
    ABILITY_SOURCE_COLLECTION,
    ABILITY_SOURCE_FEEDBACK,
    ABILITY_SOURCE_AI,
]


# ──────────────────────────────────────────────
# 培训效果因果归因（B 路径）
# 设计文档：SalesClaw_培训效果因果归因_B路径_规划.md §8.3 / §11
# ──────────────────────────────────────────────

# 培训归因的 9 个标准 metric：5 维画像 + 4 个行为 KPI
# 统一 baseline / target / actual 三组指标的 key 字典
# 含义：kind=ability/kpi，weight=综合得分权重，unit=单位（用于前端标签渲染）
TRAINING_EFFECT_METRICS: dict[str, dict] = {
    # 5 维画像（来源：AbilityProfile + ProfileHistory）
    "product_knowledge":     {"kind": "ability", "weight": 0.20, "unit": "score_0_100"},
    "visit_skill":           {"kind": "ability", "weight": 0.25, "unit": "score_0_100"},
    "customer_relation":     {"kind": "ability", "weight": 0.20, "unit": "score_0_100"},
    "compliance":            {"kind": "ability", "weight": 0.15, "unit": "score_0_100"},
    "ai_application":        {"kind": "ability", "weight": 0.20, "unit": "score_0_100"},
    # 4 个行为 KPI（同期 30/90/180 天聚合，来自 VisitRecord/BehaviorPointRecord/VisitFeedback）
    "monthly_visit_count":        {"kind": "kpi", "weight": 0.30, "unit": "count"},
    "feedback_positive_rate":     {"kind": "kpi", "weight": 0.25, "unit": "ratio_0_1"},
    "behavior_points":            {"kind": "kpi", "weight": 0.20, "unit": "score_0_100"},
    "new_doctors_monthly":        {"kind": "kpi", "weight": 0.25, "unit": "count"},
}

# metric_key 的有序列表，供 baseline/target/actual 三组字典一致
TRAINING_EFFECT_METRIC_KEYS: list[str] = list(TRAINING_EFFECT_METRICS.keys())

# 维度中文别名映射（用于 AI 归因中文输出）
TRAINING_EFFECT_METRIC_LABELS: dict[str, str] = {
    "product_knowledge":         "产品知识",
    "visit_skill":               "拜访技巧",
    "customer_relation":         "客户关系",
    "compliance":                "合规意识",
    "ai_application":            "AI 应用",
    "monthly_visit_count":       "月拜访量",
    "feedback_positive_rate":    "反馈正面率",
    "behavior_points":           "行为积分",
    "new_doctors_monthly":       "月新增医生数",
}

# AI 归因证据线索类型
# 设计文档 §7.2：每条 evidence_clue 携带 kind + weight_hint（先验可信度）
TRAINING_EVIDENCE_CLUE_KINDS: tuple = (
    "profile_delta",       # 画像维度分增量
    "exam_score",          # 考试分数
    "visit_feedback_shift",# 拜访反馈情感变化
    "behavior_points",     # 行为积分变动
    "decay_lifted",        # 抵消了衰减
    "scenario_pass_count", # 演练通过率
    "collateral_kpi",      # 行为 KPI 提升
)
