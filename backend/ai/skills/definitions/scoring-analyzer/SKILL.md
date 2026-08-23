---
name: scoring-analyzer
display_name: 积分分析器
description: 基于拜访记录与 KPI 计算积分，分析积分构成与达标情况
intent: scoring
allowed_tools: [list_visit_records, compute_kpi]
phase: 2
metadata: {design_pattern: aggregation, domain: sales}
activated_objects: [VisitRecord, Kpi, Doctor]
activated_rules: ["拜访积分按医院等级加权", "KPI达标需综合拜访与质量双维度", "未达标项需标注改进建议"]
activated_behaviors: [compute_kpi]
---

# 积分分析器

基于拜访记录与 KPI 计算，分析医药代表的积分构成与达标情况。结合拜访质量与数量双维度，识别未达标项并给出改进建议。

## 执行步骤

1. **获取拜访记录**：调用 `list_visit_records` 拉取指定周期内的拜访记录，统计拜访数量、类型与质量分布
2. **计算 KPI**：调用 `compute_kpi` 计算综合积分，包括拜访积分、质量积分、覆盖积分等维度
3. **拆解积分构成**：按积分维度拆解（拜访量、覆盖、质量、特殊贡献），识别高分项与短板项
4. **达标分析**：对比 KPI 目标值与实际值，标注达标项与未达标项，计算目标达成率
5. **生成建议**：针对未达标维度给出具体改进建议，如增加拜访频次、提升覆盖范围等

## 输出格式

```json
{
  "period": "2026-07",
  "user_id": 1,
  "total_score": 85,
  "target_score": 100,
  "achievement_rate": 0.85,
  "score_breakdown": [
    {"dimension": "visit_count", "score": 30, "target": 30, "achieved": true},
    {"dimension": "coverage", "score": 20, "target": 25, "achieved": false},
    {"dimension": "quality", "score": 25, "target": 30, "achieved": false},
    {"dimension": "special", "score": 10, "target": 15, "achieved": false}
  ],
  "visit_stats": {
    "total_visits": 18,
    "academic_visits": 5,
    "followup_visits": 8,
    "new_visits": 5
  },
  "gaps": ["coverage", "quality"],
  "suggestions": [
    "覆盖积分差 5 分，建议增加 2 家社区医院拜访",
    "质量积分差 5 分，建议提升学术拜访占比"
  ]
}
```
