---
name: report-generator
display_name: 报告生成器
description: 生成含拜访与培训双域数据的周报，支持趋势对比与智能总结
intent: report
allowed_tools: [list_visit_records, compute_kpi, get_my_learning]
phase: 2
metadata: {design_pattern: aggregation, domain: cross}
activated_objects: [VisitRecord, VisitFeedback, Course, CourseEnrollment]
activated_rules: ["周报含拜访+培训双域数据", "趋势对比本周vs上周"]
activated_behaviors: [generate_report]
---

# 报告生成器

生成结构化周报，涵盖拜访与培训双域数据。支持本周与上周趋势对比，并基于数据模式生成 AI 摘要与改进建议。

## 执行步骤

1. **收集数据**：查询本周 VisitRecord、VisitFeedback、CourseEnrollment 等数据，同时拉取上周数据用于对比
2. **计算指标**：统计拜访次数、反馈分布（正面率）、培训完成数、考试次数、积分等核心指标
3. **趋势对比**：与上周数据对比，计算环比变化率，标注上升/下降趋势
4. **生成报告**：调用 `generate_report` 输出结构化周报，含拜访域 + 培训域双维度数据
5. **智能总结**：基于数据模式生成 AI 摘要与改进建议，识别需关注的异常项

## 输出格式

```json
{
  "period": "2026-W28",
  "week_start": "2026-07-06",
  "week_end": "2026-07-12",
  "visit_domain": {
    "visit_count": 12,
    "feedback_count": 8,
    "positive_rate": 0.625,
    "negative_count": 2,
    "week_over_week": 0.2
  },
  "training_domain": {
    "courses_completed": 1,
    "exams_taken": 1,
    "credits_earned": 5,
    "avg_exam_score": 80,
    "week_over_week": 0.0
  },
  "total_points": 45,
  "trend": {
    "visit_trend": "up",
    "feedback_trend": "stable",
    "training_trend": "up"
  },
  "ai_summary": "本周拜访量环比上升 20%，正面反馈占比 62.5%；培训完成 1 门课程，建议加强合规培训学习。",
  "suggestions": [
    "加快合规培训进度，月底前完成",
    "跟进 2 位负面反馈客户，安排区域经理复查",
    "维持当前拜访节奏，目标达成率良好"
  ]
}
```
