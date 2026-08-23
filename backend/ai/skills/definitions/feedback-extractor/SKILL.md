---
name: feedback-extractor
display_name: 反馈提取器
description: 从拜访记录中抽取反馈要素，识别情感倾向、兴趣点、异议与行动项
intent: feedback
allowed_tools: [list_visit_records, search_knowledge]
phase: 2
metadata: {design_pattern: information_extraction, domain: sales}
activated_objects: [VisitFeedback, VisitRecord, Doctor]
activated_rules: ["负面反馈需24小时内跟进", "反馈关键词需归纳分类"]
activated_behaviors: [create_followup_task]
---

# 反馈提取器

从拜访记录摘要中抽取结构化反馈要素，包括情感倾向、兴趣点、异议点与行动项。对负面反馈自动生成跟进任务，确保 24 小时内响应。

## 执行步骤

1. **获取拜访记录**：调用 `list_visit_records` 获取指定时间范围或指定医生的拜访记录，关联 Doctor 信息
2. **提取反馈要素**：分析拜访摘要文本，识别情感倾向（positive/neutral/negative）、兴趣点、异议点、行动项
3. **分类归纳**：按异议关键词归类（价格、疗效、副作用、合规、剂量等），统计高频异议，形成异议分布概览
4. **生成跟进任务**：对负面反馈调用 `create_followup_task` 生成跟进任务，设定 24 小时内截止时间，指派区域经理

## 输出格式

```json
{
  "total_records": 10,
  "feedbacks": [
    {
      "record_id": 1,
      "doctor_name": "王教授",
      "visit_date": "2026-06-10",
      "sentiment": "neutral",
      "interest_points": ["临床数据", "药物相互作用"],
      "objections": ["副作用"],
      "action_items": ["寄送最新临床指南", "3周后回访"],
      "followup_task": {
        "task_id": 101,
        "title": "跟进王教授副作用疑虑",
        "due_date": "2026-06-11",
        "assignee_role": "regional_manager"
      }
    }
  ],
  "objection_summary": {
    "副作用": 3,
    "价格": 2,
    "疗效": 1
  },
  "sentiment_distribution": {
    "positive": 4,
    "neutral": 4,
    "negative": 2
  }
}
```
