---
name: matrix-builder
display_name: 矩阵构建器
description: 构建客户-产品-医院三维覆盖矩阵，支撑覆盖策略与资源分配
intent: matrix
allowed_tools: [get_coverage_matrix, list_doctors, list_hospitals]
phase: 2
metadata: {design_pattern: matrix_construction, domain: sales}
activated_objects: [CoverageMatrix, Doctor, Hospital, Product]
activated_rules: ["矩阵按医院-医生-产品三维度构建", "空白单元格需标注缺口", "矩阵更新频率为周级"]
activated_behaviors: [get_coverage_matrix]
---

# 矩阵构建器

构建客户-产品-医院三维覆盖矩阵，将医生、医院与覆盖状态关联，形成可视化矩阵。识别空白单元格与低覆盖区域，为覆盖策略与资源分配提供结构化依据。

## 执行步骤

1. **获取医院清单**：调用 `list_hospitals` 拉取医院基础信息，按等级与区域分组，作为矩阵行维度
2. **获取医生清单**：调用 `list_doctors` 拉取医生信息，关联医院与科室，作为矩阵的细分维度
3. **拉取覆盖矩阵**：调用 `get_coverage_matrix` 获取当前覆盖状态，关联到医生与医院维度
4. **构建三维矩阵**：以医院为行、医生为列、产品为层，填充覆盖状态（已覆盖/未覆盖/低覆盖），标注空白单元格
5. **输出矩阵报告**：生成矩阵概览与缺口清单，标注需重点补覆盖的单元格

## 输出格式

```json
{
  "period": "2026-W28",
  "matrix_dimensions": {"hospitals": 8, "doctors": 45, "products": 3},
  "matrix": [
    {
      "hospital_id": 1,
      "hospital_name": "市第一人民医院",
      "hospital_level": "三甲",
      "cells": [
        {"doctor_id": 1, "doctor_name": "王教授", "product_id": 1, "status": "covered", "last_visit": "2026-07-08"},
        {"doctor_id": 1, "doctor_name": "王教授", "product_id": 2, "status": "gap", "last_visit": null}
      ]
    }
  ],
  "gap_cells": [
    {"hospital_id": 1, "doctor_id": 1, "product_id": 2, "reason": "未拜访"}
  ],
  "summary": {
    "total_cells": 135,
    "covered_cells": 100,
    "gap_cells": 35,
    "coverage_rate": 0.74
  },
  "suggestions": ["产品 2 在三甲医院覆盖偏低，建议重点推进"]
}
```
