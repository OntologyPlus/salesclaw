---
name: content-outsender
display_name: 外发内容生成器
description: 基于知识库与文档生成对外发送的合规内容，支持多渠道外发
intent: outsend
allowed_tools: [search_knowledge, list_documents]
phase: 2
metadata: {design_pattern: content_generation, domain: sales}
activated_objects: [KnowledgeDocument, Document, Doctor]
activated_rules: ["外发内容必须经过合规审核", "内容需标注来源与版本", "禁止外发内部敏感数据"]
activated_behaviors: [search_knowledge, list_documents]
---

# 外发内容生成器

基于知识库与文档库，生成对外发送的合规内容（如产品资料、临床数据、学术资讯）。检索相关文档并组织结构化内容，确保来源可追溯、内容合规。

## 执行步骤

1. **理解外发需求**：分析目标对象（医生/医院）与内容主题（产品介绍、临床数据、学术资讯），明确外发场景
2. **检索知识库**：调用 `search_knowledge` 检索与主题相关的知识条目，按相关度排序
3. **拉取文档清单**：调用 `list_documents` 获取可外发的文档列表，筛选匹配主题且已审核的文档
4. **组织内容**：融合检索结果与文档，生成结构化外发内容，标注来源、版本与审核状态
5. **合规校验**：检查内容是否含敏感信息，标注合规状态与外发渠道建议

## 输出格式

```json
{
  "target": {"doctor_id": 1, "doctor_name": "王教授", "hospital_name": "市第一人民医院"},
  "topic": "心血通临床数据",
  "channel": "email",
  "content": {
    "title": "心血通（氨氯地平片）最新临床数据汇编",
    "summary": "本资料汇总心血通在高血压与心绞痛治疗中的最新临床数据...",
    "sections": [
      {"heading": "适应症", "body": "适用于高血压与稳定性心绞痛"},
      {"heading": "临床数据", "body": "III期临床显示有效率 92%..."}
    ],
    "attachments": [
      {"document_id": 5, "title": "心血通产品手册（2026 版）", "version": "v2.3", "review_status": "approved"}
    ]
  },
  "sources": [
    {"type": "knowledge", "id": 12, "title": "心血通临床数据"},
    {"type": "document", "id": 5, "title": "心血通产品手册"}
  ],
  "compliance": {
    "status": "approved",
    "checked_at": "2026-07-12T10:00:00Z",
    "warnings": []
  }
}
```
