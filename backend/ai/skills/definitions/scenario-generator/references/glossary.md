# 术语映射表

本表定义 `SceneDraft` 内部字段名与用户可见词的对应关系。LLM 在向用户展示信息时必须使用"用户可见词"，禁止暴露内部字段名。

## 字段映射

| 内部字段名 | 用户可见词 | 备注 |
|---|---|---|
| `doctorPersona` | 医生画像 | 含职级/科室/医院/处方习惯/学术偏好 |
| `bestPracticePoints` | 最佳实践要点 | 3-5 条结构化建议 |
| `drugName` | 品种 | 规范化药品名称 |
| `title` | 场景标题 | 20 字以内，禁姓氏 |
| `sceneBackground` | 场景背景 | 150-300 字，第三人称叙述 |
| `repBriefing` | 代表简报 | 与 sceneBackground 同源 |
| `contextPayload` | （不展示） | 对用户不可见，保密红线 |
| `knowledgeIds` | 关联知识 | 用户可看知识标题列表，但不可看 ID |
| `scenario_id` | 场景编号 | 落库成功后可告知用户 |
| `session_id` | （不展示） | 会话标识，内部使用 |
| `tenant_id` | （不展示） | 租户标识，内部使用 |
| `user_id` | （不展示） | 用户标识，内部使用 |

## 配置三列表（fetch_scene_config 返回）

| 内部键 | 用户可见词 |
|---|---|
| `scene_themes` | 推广场景主题列表 |
| `business_domains` | 业务领域列表（固定为"临床推广"） |
| `trainee_targets` | 受训对象列表 |

## doctor 5 键（contextPayload.doctor）

| 内部键 | 含义 |
|---|---|
| `position` | 职位（如"主任医师"） |
| `concerns` | 关注点（如"安全性、疗效、价格"） |
| `communication_style` | 沟通偏好（如"数据导向、时间敏感"） |
| `objection_points` | 异议点（如"对不良反应有顾虑"） |
| `decision_style` | 决策风格（如"保守、循证"） |

## coach 3 键（contextPayload.coach）

| 内部键 | 含义 |
|---|---|
| `scoring_dimensions` | 评分维度（如"开场、数据呈现、异议处理"） |
| `talking_points_ref` | 话术参考（指向 bestPracticePoints） |
| `red_lines` | 红线提示（如"禁止承诺未授权事项"） |

## 命令式原语（用户不可见）

| 原语名 | 用途 |
|---|---|
| `fetch_scene_config` | 拉取三列表配置 |
| `sync_scene_draft` | 落盘草稿（含确认标记） |
| `merge_scene_draft` | 合并标题背景到草稿 |
| `finalize_scene_knowledge` | 锁定知识 ID 列表 |
| `validate_scene_gate` | 校验门禁 |
| `suggest_scene_knowledge` | 知识库推荐 |
| `generate_context_payload` | 生成对练上下文 |
| `create_scene_record` | 落库 |
