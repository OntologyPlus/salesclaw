---
name: course-recommender
display_name: 课程推荐器
description: 基于拜访异议与反馈推荐培训课程，排除已完成课程，优先推荐必修课
intent: course
allowed_tools: [get_my_learning, search_knowledge, list_courses, enroll_course]
phase: 2
metadata: {design_pattern: recommendation, domain: training}
activated_objects: [Course, CourseEnrollment, VisitRecord, VisitFeedback]
activated_rules: ["基于拜访异议推荐课程", "排除已完成的课程", "优先推荐必修课"]
activated_behaviors: [enroll_course]
---

# 课程推荐器

基于近期拜访中出现的异议与反馈，识别医药代表的能力缺口，推荐匹配的培训课程。排除已完成课程，优先推荐必修课与高匹配度课程。

## 执行步骤

1. **分析学习需求**：基于近期 VisitRecord 拜访异议与 VisitFeedback 反馈，识别能力缺口（如合规、产品知识、异议处理）
2. **排除已完成课程**：查询 CourseEnrollment 获取用户已完成（status=completed）课程列表，从候选集中排除
3. **匹配课程**：按异议类型匹配 Course 的 category 与 tags，计算匹配度得分；优先推荐必修课与高评分课程
4. **排序推荐**：按匹配度、课程评分、难度适配度综合排序，取 top N 推荐
5. **选课**：调用 `enroll_course` 为用户完成选课，关联学习路径建议

## 输出格式

```json
{
  "user_id": 1,
  "capability_gaps": ["合规知识", "异议处理"],
  "recommendations": [
    {
      "course_id": 3,
      "title": "医药合规培训",
      "category": "合规",
      "difficulty": "advanced",
      "duration_minutes": 60,
      "avg_rating": 85,
      "match_score": 0.92,
      "reason": "近期拜访出现合规相关异议，建议加强合规知识",
      "is_required": true
    },
    {
      "course_id": 5,
      "title": "销售话术与异议处理",
      "category": "销售技巧",
      "difficulty": "intermediate",
      "duration_minutes": 40,
      "avg_rating": 80,
      "match_score": 0.85,
      "reason": "近期出现价格异议，建议学习异议处理话术",
      "is_required": false
    }
  ],
  "excluded_courses": [1, 2],
  "learning_path_suggestion": "新代表入职路径 - 阶段 2"
}
```
