---
name: territory-reporter
display_name: 辖区数据查询
description: 经理通过自然语言询问辖区数据，如"朝阳01辖区本周达成率多少？"
intent: territory
allowed_tools: [query_territory_metrics]
phase: 2
metadata: {design_pattern: query, domain: sales}
activated_objects: [Zone, CoverageAssignment, VisitRecord]
activated_rules: ["辖区权限过滤（4源分管+当日有效）", "时间周期按自然语言解析"]
activated_behaviors: [query_territory_metrics]
---

# 辖区数据查询

经理通过 AI 助手以自然语言询问辖区经营数据，系统自动解析辖区名称 + 时间周期，应用"辖区本位"权限过滤后返回指标。

## 执行步骤

1. **解析辖区**：从用户问题中识别辖区名称（如"朝阳01"、"海淀南区"），匹配 `Zone` 表
2. **解析时间**：识别"本周/本月/本季度/上周/上月"等时间词，计算起止日期
3. **权限过滤**：应用 `get_effective_coverage` 4 源分管 + 当日有效辖区快照
4. **指标聚合**：按辖区 + 时间范围聚合拜访数/计划数/达成率/覆盖率/积分
5. **自然语言回答**：将指标转为人话输出，附关键风险提示

## 输出格式

```json
{
  "zone_name": "朝阳01辖区",
  "period": "本周",
  "period_start": "2026-07-14",
  "period_end": "2026-07-20",
  "metrics": {
    "visit_count": 12,
    "plan_count": 15,
    "achievement_rate": 80.0,
    "coverage_rate": 71.2,
    "total_points": 340
  },
  "summary": "朝阳01辖区本周拜访达成率 80%，覆盖率 71.2%，积分 340。建议关注未达成的 3 家医院。",
  "risks": ["2 位代表本周零拜访", "覆盖率低于均值"]
}
```
