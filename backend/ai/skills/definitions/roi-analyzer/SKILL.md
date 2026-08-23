---
name: roi-analyzer
display_name: ROI 分析器
description: 基于拜访投入与产出计算投资回报率，识别高 ROI 客户与低效拜访
intent: roi
allowed_tools: [compute_roi, list_visit_records]
phase: 2
metadata: {design_pattern: cost_benefit, domain: sales}
activated_objects: [VisitRecord, Roi, Doctor, Hospital]
activated_rules: ["ROI按客户分层计算", "低ROI客户需优化投入策略", "高ROI客户应增加资源倾斜"]
activated_behaviors: [compute_roi]
---

# ROI 分析器

基于拜访投入（时间、差旅、资源）与产出（订单、覆盖、关系深化）计算投资回报率，识别高 ROI 客户与低效拜访，为资源分配提供依据。

## 执行步骤

1. **获取拜访记录**：调用 `list_visit_records` 拉取指定周期内的拜访记录，统计各客户的拜访次数、时长与投入成本
2. **计算 ROI**：调用 `compute_roi` 计算各客户与各区域的投入产出比，量化拜访价值
3. **分层分析**：按客户等级、医院等级、产品线分组统计 ROI，识别高 ROI 与低 ROI 客户群
4. **低效拜访识别**：标注 ROI 低于阈值的拜访，分析低效原因（频次过高、目标错配、产出不足）
5. **输出建议**：给出资源重分配建议，对高 ROI 客户增加投入，对低 ROI 客户优化策略

## 输出格式

```json
{
  "period": "2026-07",
  "overall_roi": 2.3,
  "total_investment": 12000,
  "total_return": 27600,
  "by_customer": [
    {
      "doctor_id": 5,
      "doctor_name": "王教授",
      "hospital_name": "市第一人民医院",
      "visit_count": 4,
      "investment": 2000,
      "return": 8000,
      "roi": 4.0,
      "tier": "high",
      "suggestion": "保持当前投入节奏"
    },
    {
      "doctor_id": 8,
      "doctor_name": "赵医生",
      "hospital_name": "社区医院",
      "visit_count": 6,
      "investment": 1800,
      "return": 900,
      "roi": 0.5,
      "tier": "low",
      "suggestion": "降低拜访频次，转为远程维护"
    }
  ],
  "low_efficiency_visits": [12, 15, 18],
  "suggestions": [
    "高 ROI 客户集中在前 20%，建议增加 15% 投入",
    "3 次低效拜访建议改为线上沟通"
  ]
}
```
