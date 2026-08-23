---
name: rag-qa
display_name: 知识问答
description: 基于知识库的检索增强问答，引用来源标注，无匹配时建议人工查询
intent: knowledge
allowed_tools: [search_knowledge, list_documents]
phase: 2
metadata: {design_pattern: rag, domain: knowledge}
activated_objects: [KnowledgeDocument, FaqItem]
activated_rules: ["引用来源必须标注", "无匹配结果时建议人工查询"]
activated_behaviors: [search_knowledge]
---

# 知识问答

基于知识库（KnowledgeDocument + FaqItem）的检索增强问答。检索相关文档与常见问题，组织结构化回答并标注引用来源；无匹配结果时建议人工查询或转交医学部。

## 执行步骤

1. **理解查询**：分析用户问题，提取关键词与意图，识别查询所属领域（产品、临床、合规、销售）
2. **检索知识库**：调用 `search_knowledge` 在 KnowledgeDocument 与 FaqItem 中检索相关内容，按相关度得分排序
3. **排序筛选**：融合关键词匹配分与语义相似度，取 top_k 结果，过滤低质量匹配
4. **生成回答**：基于检索结果组织结构化回答，每个要点标注引用来源（文档标题与路径）
5. **兜底处理**：无匹配结果或置信度过低时，建议人工查询或转交医学部，避免编造答案

## 输出格式

```json
{
  "query": "心血通的适应症是什么？",
  "answer": "心血通（氨氯地平片）适用于高血压与稳定性心绞痛的治疗。起始剂量为 10mg/日，最大剂量 40mg/日。常见不良反应包括头痛、水肿、潮红。",
  "references": [
    {
      "type": "document",
      "title": "心血通产品手册（2026 版）",
      "source": "/knowledge/documents/1",
      "snippet": "【适应症】高血压、稳定性心绞痛",
      "score": 0.92
    },
    {
      "type": "faq",
      "title": "心血通与 ACEI 可以联合使用吗？",
      "source": "/knowledge/faq/1",
      "snippet": "可以。氨氯地平与 ACEI 联合是高血压治疗的优选方案",
      "score": 0.78
    }
  ],
  "total_results": 2,
  "confidence": 0.92,
  "fallback": false
}
```
