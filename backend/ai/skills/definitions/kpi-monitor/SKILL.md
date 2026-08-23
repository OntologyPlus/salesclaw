---
name: kpi-monitor
display_name: KPI 监控器
description: 实时监控 KPI 达成情况，识别异常并触发预警
intent: kpi
allowed_tools: [compute_kpi, list_visit_records]
phase: 2
metadata: {design_pattern: monitoring, domain: decision}
activated_objects: [Kpi, VisitRecord, Alert]
activated_rules: ["KPI达成率低于80%触发预警", "监控频率为日级", "异常项需标注原因与责任主体"]
activated_behaviors: [compute_kpi]
---

# KPI 监控器

实时监控医药代表的 KPI 达成情况，包括拜访量、覆盖率、质量积分等核心指标。识别低于阈值的异常项并触发预警，辅助管理层及时干预。

## 执行步骤

1. **获取拜访记录**：调用 `list_visit_records` 拉取当前周期内的拜访数据，作为 KPI 计算输入
2. **计算 KPI**：调用 `compute_kpi` 计算各维度 KPI 值与目标达成率，含拜访量、覆盖率、质量等
3. **阈值检测**：按规则检测达成率低于 80% 的指标，标注为异常项
4. **根因分析**：结合拜访记录分析异常原因（如拜访不足、覆盖偏科、质量偏低）
5. **生成监控报告**：输出 KPI 监控面板与异常清单，含责任主体与干预建议

## 输出格式

```json
{
  "period": "2026-07",
  "monitored_at": "2026-07-12T09:00:00+08:00",
  "user_id": 1,
  "overall_achievement": 0.82,
  "kpi_items": [
    {
      "name": "visit_count",
      "target": 20,
      "actual": 18,
      "achievement": 0.90,
      "status": "normal",
      "trend": "up"
    },
    {
      "name": "coverage_rate",
      "target": 0.85,
      "actual": 0.65,
      "achievement": 0.76,
      "status": "alert",
      "trend": "down",
      "root_cause": "三甲医院覆盖不足，2名重点医生未拜访"
    }
  ],
  "alerts": [
    {
      "kpi_name": "coverage_rate",
      "severity": "high",
      "message": "覆盖率达成 76%，低于 80% 阈值",
      "owner": "区域经理",
      "suggestion": "本周补拜访 2 名三甲医院医生"
    }
  ],
  "summary": "整体达成 82%，覆盖率需重点关注"
}
```
