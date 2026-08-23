# 异常 → 处理对照表

## Step1 异常

| 异常 | 错误码 | 处理 |
|---|---|---|
| 用户未登录 | 401 | 编排器拦截，不进入 Skill |
| 租户无效 | 403 | 编排器拦截 |
| fetch_scene_config 数据库错误 | E_CONFIG_FETCH | 提示"配置加载失败，请稍后重试" |
| 三列表为空 | E_CONFIG_EMPTY | 阻断，提示"租户未初始化场景配置" |

## Step2 异常

| 异常 | 错误码 | 处理 |
|---|---|---|
| 用户输入字段缺失 | E_INPUT_MISSING | 询问用户补全 |
| LLM 生成 doctorPersona 失败 | E_PERSONA_GEN | 降级到模板生成，标注"AI 推断" |
| sync_scene_draft 持久化失败 | E_SYNC_FAIL | 降级到 in-memory，提示"草稿暂存内存，可能丢失" |
| 用户拒绝确认 | OK_USER_REJECT | 询问修正点，重新生成 |

## Step3 异常

| 异常 | 错误码 | 处理 |
|---|---|---|
| LLM 生成 title 失败 | E_TITLE_GEN | 降级到模板："{科室}{品种}对练" |
| LLM 生成 sceneBackground 失败 | E_BG_GEN | 降级到模板："基于{品种}的{主题}场景" |
| 标题含姓氏 | E_TITLE_VIOLATION | 重新生成，参考 step3/title-and-scene-background.md |
| merge_scene_draft 失败 | E_MERGE_FAIL | 重新生成，提示用户稍候 |
| 用户拒绝确认 | OK_USER_REJECT | 询问修改方向，回炉重新生成 |

## Step4.1 异常

| 异常 | 错误码 | 处理 |
|---|---|---|
| RAG 检索无结果 | OK_NO_KNOWLEDGE | 提示"暂无相关知识，可跳过知识挂载" |
| suggest_scene_knowledge 失败 | E_SUGGEST_FAIL | 降级到 list_documents 工具返回通用知识 |
| 用户未选择任何知识 | OK_USER_SKIP | 允许跳过，但 finalize(knowledge_ids=[]) |
| finalize_scene_knowledge 失败 | E_FINALIZE_FAIL | 重新调用，提示稍候 |

## Step4.2 异常

| 异常 | 错误码 | 处理 |
|---|---|---|
| generate_context_payload LLM 失败 | E_PAYLOAD_GEN | 降级到模板 payload，标注"模板生成" |
| doctor 5 键缺失 | E_DOCTOR_KEYS_MISSING | 重新生成，提示"医生侧上下文不完整" |
| coach 3 键缺失 | E_COACH_KEYS_MISSING | 重新生成，提示"教练侧上下文不完整" |
| 时序违例（先调 create） | E_SEQ_VIOLATION | 拒绝 create，回退到 Step4.2 |

## Step4.3 异常

| 异常 | 错误码 | 处理 |
|---|---|---|
| 用户未确认提交 | OK_NOT_CONFIRMED | 再次询问，禁止跳过 |
| create_scene_record 数据库错误 | E_CREATE_FAIL | **不重试**，告知用户失败原因，保留 draft |
| 字段校验失败（如同源性） | E_FIELD_INVALID | 报告具体字段，回退到对应 Step 修正 |
| 工作区清理失败 | E_CLEANUP_FAIL | 不影响用户，仅记录日志 |

## 通用异常

| 异常 | 错误码 | 处理 |
|---|---|---|
| EpisodicMemory 不可用 | E_MEMORY_DOWN | 降级到 in-memory，提示"会话状态可能丢失" |
| LLM 超时 | E_LLM_TIMEOUT | 提示"AI 响应超时，请重试本轮" |
| 用户消息过长（>5000 字符） | E_MSG_TOO_LONG | 编排器 Guardrails 拦截 |
| 检测到 prompt 注入 | E_INJECTION | 编排器 Guardrails 拦截 |
| Skill 执行异常 | E_SKILL_CRASH | 降级到 mock 响应，提示"工作流异常，请联系管理员" |

## 错误码规范

- `E_` 前缀：错误（需处理）
- `OK_` 前缀：用户主动行为（非错误）
- `WARN_` 前缀：警告（可继续）
