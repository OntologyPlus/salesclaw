---
name: path-optimizer
display_name: 路径优化器
description: 基于学习进度与课程库优化个人学习路径，补齐能力短板
intent: path
allowed_tools: [get_my_learning, list_courses]
phase: 2
metadata: {design_pattern: recommendation, domain: training}
activated_objects: [Course, CourseEnrollment, LearningPath]
activated_rules: ["学习路径按岗位能力模型构建", "已完成课程不重复推荐", "路径需先易后难循序渐进"]
activated_behaviors: [get_my_learning]
depends_on:
  - skill: course-recommender
    mode: sequential
---

# 路径优化器

基于用户当前学习进度与课程库，优化个人学习路径。识别能力短板，按岗位能力模型与先易后难原则推荐课程序列，补齐能力缺口。

## 执行步骤

1. **获取学习进度**：调用 `get_my_learning` 拉取用户已学课程、完成状态、考试成绩与积分，构建能力画像
2. **拉取课程库**：调用 `list_courses` 获取可选课程，含分类、难度、前置依赖与岗位匹配度
3. **识别能力短板**：对比岗位能力模型与用户已学内容，识别未覆盖或低分的能力维度
4. **生成优化路径**：按先易后难、前置依赖优先原则，为短板维度推荐课程序列，排除已完成课程
5. **输出路径建议**：输出结构化学习路径，含课程顺序、预计时长与能力提升映射

## 输出格式

```json
{
  "user_id": 1,
  "role": "医药代表",
  "current_level": "intermediate",
  "capability_gaps": ["合规知识", "异议处理"],
  "optimized_path": [
    {
      "order": 1,
      "course_id": 3,
      "title": "医药合规基础",
      "difficulty": "easy",
      "duration_minutes": 40,
      "target_capability": "合规知识",
      "prerequisite": null,
      "reason": "合规知识短板起点课程"
    },
    {
      "order": 2,
      "course_id": 7,
      "title": "销售异议处理进阶",
      "difficulty": "medium",
      "duration_minutes": 60,
      "target_capability": "异议处理",
      "prerequisite": 3,
      "reason": "补齐异议处理能力，需先完成合规基础"
    }
  ],
  "total_duration_minutes": 100,
  "estimated_completion_date": "2026-08-15",
  "excluded_courses": [1, 2, 5]
}
```
