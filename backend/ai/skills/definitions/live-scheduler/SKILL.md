---
name: live-scheduler
display_name: 直播调度器
description: 基于课程安排生成直播计划，调度讲师与时间资源
intent: live
allowed_tools: [list_courses]
phase: 2
metadata: {design_pattern: scheduling, domain: training}
activated_objects: [Course, LiveSession, Instructor]
activated_rules: ["直播时长不超过90分钟", "同一讲师每日最多2场直播", "直播需提前3天预告"]
activated_behaviors: [list_courses]
---

# 直播调度器

基于课程安排与讲师资源，生成直播计划。调度讲师时间、课程主题与直播时段，避免冲突并提前预告，确保直播资源合理分配。

## 执行步骤

1. **获取课程清单**：调用 `list_courses` 拉取适合直播的课程（如必修课、新上线课程），作为直播候选
2. **筛选直播课程**：按课程类型、优先级与学员需求筛选需开展直播的课程，排序生成候选清单
3. **调度时段**：根据规则分配直播时段（避开午休、晚间 19-21 点优先），同一讲师每日最多 2 场
4. **生成直播计划**：为每门课程分配讲师、时间、时长（≤90 分钟）与预告信息
5. **输出计划与预告**：输出结构化直播计划，含预告信息用于提前 3 天通知学员

## 输出格式

```json
{
  "period": "2026-W29",
  "total_sessions": 5,
  "sessions": [
    {
      "session_id": 101,
      "course_id": 3,
      "course_title": "医药合规培训",
      "instructor": "张老师",
      "start_time": "2026-07-15T19:00:00+08:00",
      "end_time": "2026-07-15T20:30:00+08:00",
      "duration_minutes": 90,
      "platform": "internal_live",
      "max_audience": 200,
      "notice_date": "2026-07-12",
      "status": "scheduled"
    }
  ],
  "instructor_workload": {"张老师": 2, "李老师": 2, "王老师": 1},
  "conflicts": [],
  "suggestions": ["合规培训为必修课，建议优先预告"]
}
```
