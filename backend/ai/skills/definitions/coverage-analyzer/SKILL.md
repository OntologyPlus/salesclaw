---
name: coverage-analyzer
display_name: 覆盖分析器
description: 分析客户覆盖缺口与矩阵分布，识别未覆盖与低覆盖区域
intent: coverage
allowed_tools: [compute_coverage_gap, get_coverage_matrix, list_hospitals]
phase: 2
metadata: {design_pattern: gap_analysis, domain: sales}
activated_objects: [CoverageMatrix, Hospital, Doctor, CoverageAssignment]
activated_rules: ["覆盖率低于阈值需预警", "三甲医院必须全覆盖", "30天未拜访计入覆盖缺口"]
activated_behaviors: [compute_coverage_gap, get_coverage_matrix]
---

# 覆盖分析器

基于覆盖矩阵与医院信息，计算客户覆盖缺口，识别未覆盖与低覆盖区域。结合医院等级与覆盖规则，输出覆盖优化建议，确保高价值客户优先获得资源。

## 执行步骤

1. **获取覆盖矩阵**：调用 `get_coverage_matrix` 拉取当前覆盖分布，统计各医院、各医生的覆盖状态与最近拜访日期
2. **查询医院清单**：调用 `list_hospitals` 获取医院基础信息（等级、科室、区域），用于按等级与区域分组分析
3. **计算覆盖缺口**：调用 `compute_coverage_gap` 识别未覆盖与低覆盖客户，按缺口严重程度排序，标注 30 天未拜访客户
4. **分层分析**：按医院等级（三甲 > 二甲 > 社区）与区域分组统计覆盖率，识别三甲医院全覆盖情况
5. **输出建议**：针对覆盖缺口生成优化建议，包括需补拜访的客户清单与优先级排序

## 输出格式

```json
{
  "period": "2026-07",
  "total_doctors": 120,
  "covered_doctors": 90,
  "coverage_rate": 0.75,
  "gap_doctors": [
    {
      "doctor_id": 15,
      "doctor_name": "李主任",
      "hospital_id": 3,
      "hospital_name": "市第一人民医院",
      "hospital_level": "三甲",
      "last_visit_date": "2026-05-10",
      "gap_days": 62,
      "priority": "high",
      "reason": "三甲医院62天未拜访"
    }
  ],
  "coverage_by_level": {
    "三甲": {"total": 40, "covered": 38, "rate": 0.95},
    "二甲": {"total": 50, "covered": 38, "rate": 0.76},
    "社区": {"total": 30, "covered": 14, "rate": 0.47}
  },
  "suggestions": [
    "三甲医院覆盖率达标，保持当前节奏",
    "社区医院覆盖率偏低，建议安排集中拜访"
  ]
}
```
