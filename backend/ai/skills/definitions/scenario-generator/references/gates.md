# 8 道门禁详细规则（G1-G8）

本工作流通过 8 道门禁严格保证流程不跳步。每道门禁对应一个 `SceneDraft` 字段的检查，LLM 必须在对应 Step 调用 `validate_scene_gate(gate=...)` 工具校验。

## 门禁清单

### G1 — 启动门禁

| 项目 | 内容 |
|---|---|
| 检查点 | 用户已登录，租户有效 |
| 检查字段 | `SceneDraft.tenant_id` 非空 |
| 关联 Step | Step1 |
| 实际实现 | 由编排器 `Orchestrator.chat()` Step 1 Guardrails 保证，本门禁恒为 true |
| 失败处理 | 编排器拒绝请求，返回 401/403 |

### G2 — 配置就绪门禁

| 项目 | 内容 |
|---|---|
| 检查点 | 三列表配置非空（场景主题/业务领域/受训对象） |
| 检查字段 | `SceneDraft.config` 非空且含三个非空列表 |
| 关联 Step | Step1 |
| 实际实现 | `fetch_scene_config` 工具调用后写入；`validate_scene_gate(gate="G2")` 校验 |
| 失败处理 | 阻断 Step2，提示用户"配置加载失败，请稍后重试" |

### G3 — 采集完成门禁

| 项目 | 内容 |
|---|---|
| 检查点 | `doctorPersona` / `bestPracticePoints` / `drugName` 已生成并用户已确认 |
| 检查字段 | `SceneDraft.collection.user_confirmed == true` 且三项子字段非空 |
| 关联 Step | Step2 |
| 实际实现 | `sync_scene_draft(collection, confirm=true)` 标记确认；`validate_scene_gate(gate="G3")` 校验 |
| 失败处理 | 阻断 Step3，提示用户补全字段 |

### G4 — 标题背景就绪门禁

| 项目 | 内容 |
|---|---|
| 检查点 | `title` + `sceneBackground` 已生成并用户已确认 |
| 检查字段 | `SceneDraft.title_bg.user_confirmed == true` 且 `title` / `scene_background` 非空 |
| 关联 Step | Step3 |
| 实际实现 | `merge_scene_draft(title_bg, confirm=true)` 标记确认；`validate_scene_gate(gate="G4")` 校验 |
| 失败处理 | 阻断 Step4，提示用户回炉重新生成 |

### G5 — 知识已挂载门禁

| 项目 | 内容 |
|---|---|
| 检查点 | `knowledgeIds` 已锁定（finalize） |
| 检查字段 | `SceneDraft.knowledge.finalized == true` 且 `knowledge_ids` 非空 |
| 关联 Step | Step4.1 |
| 实际实现 | `finalize_scene_knowledge(knowledge_ids)` 锁定；`validate_scene_gate(gate="G5")` 校验 |
| 失败处理 | 阻断 Step4.3，提示用户重新选择知识 |

### G6 — Payload 已生成门禁

| 项目 | 内容 |
|---|---|
| 检查点 | `contextPayload.doctor` (5 键) + `contextPayload.coach` (3 键) 已就绪 |
| 检查字段 | `SceneDraft.context_payload.ready == true` |
| 关联 Step | Step4.2 |
| 实际实现 | `generate_context_payload()` 工具调用后写入；`validate_scene_gate(gate="G6")` 校验 |
| 失败处理 | 阻断 Step4.3，提示"对练 AI 角色上下文生成失败"，禁止调 create |

### G7 — 用户最终确认门禁

| 项目 | 内容 |
|---|---|
| 检查点 | 用户口头确认"确认提交" |
| 检查字段 | `SceneDraft.submit_confirmed == true` |
| 关联 Step | Step4.3 |
| 实际实现 | LLM 检测到用户回复"确认提交/提交/确认"等确认词，标记 submit_confirmed=true；`validate_scene_gate(gate="G7")` 校验 |
| 失败处理 | 阻断 create_scene_record，再次询问用户 |

### G8 — 落库成功门禁

| 项目 | 内容 |
|---|---|
| 检查点 | create_scene_record 返回 scenario_id |
| 检查字段 | `SceneDraft.scenario_id` 非空 |
| 关联 Step | Step4.3 |
| 实际实现 | `create_scene_record()` 工具落库后写入；`validate_scene_gate(gate="G8")` 校验 |
| 失败处理 | 禁止自动重试，明确告知用户失败原因，保留 draft 等待人工介入 |

## 门禁校验顺序

```
G1 (启动) → G2 (配置) → G3 (采集) → G4 (标题) → G5 (知识) → G6 (Payload) → G7 (确认) → G8 (落库)
```

任何门禁失败，禁止跳过。LLM 必须重新执行对应 Step，确保门禁通过后再推进。

## 后置校验机制

`WorkflowSkillExecutor` 在每轮执行完成后，会检查 `draft.gates_passed` 列表，确认本轮应该通过的门禁已通过。如果发现 LLM 漏调 `validate_scene_gate`，会在响应中追加警告并要求下一轮补调。
