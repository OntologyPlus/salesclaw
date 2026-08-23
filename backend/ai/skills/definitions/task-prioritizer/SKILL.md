---
name: task-prioritizer
display_name: 任务优先级排序器
description: 基于拜访记录与 KPI 对任务排序，辅助代表聚焦高价值任务
intent: task
allowed_tools: [list_visit_records, compute_kpi]
phase: 2
metadata: {design_pattern: prioritization, domain: collaboration}
activated_objects: [VisitRecord, Kpi, Task]
activated_rules: ["任务优先级按紧急度×重要度计算", "KPI短板相关任务优先级提升", "高风险客户任务需当日处理"]
activated_behaviors: [compute_kpi]
---

# 任务优先级排序器

基于拜访记录与 KPI 达成情况，对医药代表的待办任务进行优先级排序。结合紧急度、重要度与 KPI 短板，辅助代表聚焦高价值任务，提升时间利用率。

## 执行步骤

1. **获取拜访记录**：调用 `list_visit_records` 拉取近期拜访数据，识别待跟进任务（如负面反馈客户、未拜访客户）
2. **计算 KPI**：调用 `compute_kpi` 计算各维度 KPI 达成率，识别短板维度并提升相关任务优先级
3. **评分排序**：按紧急度（截止时间）×重要度（客户价值、KPI 关联）计算任务优先级得分
4. **风险标注**：标注高风险客户任务（如负面反馈、长期未拜访），要求当日处理
5. **输出任务清单**：输出按优先级排序的任务清单，含建议处理时段与理由

## 输出格式

```json
{
  "user_id": 1,
  "generated_at": "2026-07-12T08:00:00+08:00",
  "total_tasks": 8,
  "kpi_gaps": ["coverage", "quality"],
  "tasks": [
    {
      "task_id": 1,
      "title": "跟进王教授副作用疑虑",
      "type": "followup",
      "doctor_id": 1,
      "doctor_name": "王教授",
      "urgency": 5,
      "importance": 5,
      "priority_score": 25,
      "priority_level": "P0",
      "due_date": "2026-07-12",
      "reason": "负面反馈客户，需当日处理；关联质量 KPI 短板"
    },
    {
      "task_id": 2,
      "title": "拜访三甲医院李主任",
      "type": "visit",
      "doctor_id": 7,
      "doctor_name": "李主任",
      "urgency": 4,
      "importance": 5,
      "priority_score": 20,
      "priority_level": "P1",
      "due_date": "2026-07-13",
      "reason": "60天未拜访，关联覆盖 KPI 短板"
    }
  ],
  "suggestions": ["P0 任务当日完成，P1 任务本周内完成"]
}
```
