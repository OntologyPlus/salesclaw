---
name: attribution-analyzer
display_name: 归因分析器
description: 分析业绩变化归因，识别关键驱动因素与贡献度
intent: attribution
allowed_tools: [compute_kpi, list_visit_records]
phase: 2
metadata: {design_pattern: attribution, domain: decision}
activated_objects: [Kpi, VisitRecord, Doctor]
activated_rules: ["归因按多因素分解", "贡献度需量化为百分比", "关键驱动因素需排序"]
activated_behaviors: [compute_kpi]
depends_on:
  - skill: kpi-monitor
    mode: parallel
  - skill: territory-reporter
    mode: parallel
---

# 归因分析器

分析业绩（如销量、覆盖、积分）变化的归因，识别关键驱动因素与各因素贡献度。结合 KPI 与拜访记录，量化各因素对业绩变化的贡献，辅助决策优化。

## 执行步骤

1. **获取拜访记录**：调用 `list_visit_records` 拉取对比周期的拜访数据，识别拜访行为变化
2. **计算 KPI**：调用 `compute_kpi` 计算当前与对比周期的 KPI 值，量化业绩变化幅度
3. **因素分解**：将业绩变化分解为拜访频次、覆盖范围、拜访质量、客户结构等因素
4. **贡献度量化**：计算各因素对业绩变化的贡献度（百分比），排序识别关键驱动因素
5. **输出归因报告**：输出归因分解与关键驱动因素清单，给出优化建议

## 输出格式

```json
{
  "period": "2026-07",
  "compare_period": "2026-06",
  "metric": "visit_score",
  "current_value": 85,
  "previous_value": 70,
  "delta": 15,
  "delta_rate": 0.214,
  "attribution": [
    {
      "factor": "visit_count",
      "contribution": 6,
      "contribution_pct": 0.40,
      "detail": "拜访次数从 15 次增至 18 次"
    },
    {
      "factor": "coverage_expansion",
      "contribution": 5,
      "contribution_pct": 0.33,
      "detail": "新增覆盖 3 名三甲医生"
    },
    {
      "factor": "quality_improvement",
      "contribution": 4,
      "contribution_pct": 0.27,
      "detail": "学术拜访占比提升 15%"
    }
  ],
  "key_drivers": ["visit_count", "coverage_expansion"],
  "suggestions": ["覆盖扩展贡献显著，建议持续推进三甲医院覆盖"]
}
```
