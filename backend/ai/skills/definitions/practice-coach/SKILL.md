---
name: practice-coach
display_name: 演练教练
description: 基于知识库与课程提供演练辅导，给出反馈与改进建议
intent: scene
allowed_tools: [search_knowledge, list_courses]
phase: 2
metadata: {design_pattern: coaching, domain: training}
activated_objects: [KnowledgeDocument, Course, Scenario]
activated_rules: ["反馈需基于知识库与课程标准", "反馈涵盖内容、话术、流程三维度", "改进建议需具体可操作"]
activated_behaviors: [search_knowledge]
---

# 演练教练

基于知识库与课程内容，为医药代表拜访演练提供辅导反馈。从内容准确性、话术专业度与流程完整度三维度评估演练，给出具体可操作的改进建议。

## 执行步骤

1. **获取课程标准**：调用 `list_courses` 拉取与演练场景相关的课程，提取评分标准与话术规范
2. **检索知识库**：调用 `search_knowledge` 检索与演练主题相关的产品资料、临床数据与合规要点，作为评估依据
3. **多维度评估**：从内容准确性（事实是否正确）、话术专业度（表达是否规范）、流程完整度（开场-核心-收尾是否完整）评估演练
4. **生成反馈**：针对每个维度给出得分、优点与不足，引用知识库与课程标准作为依据
5. **输出改进建议**：输出结构化反馈与具体可操作的改进建议，关联推荐课程

## 输出格式

```json
{
  "scenario_id": 201,
  "user_id": 1,
  "overall_score": 78,
  "dimensions": [
    {
      "dimension": "content_accuracy",
      "score": 80,
      "strengths": ["正确引用 III 期临床有效率 92%"],
      "weaknesses": ["未提及药物相互作用禁忌"],
      "evidence": [{"type": "knowledge", "id": 15, "title": "心血通禁忌症"}]
    },
    {
      "dimension": "talking_professionalism",
      "score": 75,
      "strengths": ["开场专业，引用指南"],
      "weaknesses": ["数据呈现方式偏口语化，建议使用图表"]
    },
    {
      "dimension": "process_completeness",
      "score": 79,
      "strengths": ["收尾获得承诺"],
      "weaknesses": ["异议处理环节停留时间过长"]
    }
  ],
  "improvement_suggestions": [
    "补充药物相互作用说明，参考知识库条目 15",
    "数据呈现改用结构化图表，提升专业度",
    "异议处理控制在 2 分钟内，避免拖沓"
  ],
  "recommended_courses": [{"course_id": 7, "title": "销售异议处理进阶"}]
}
```
