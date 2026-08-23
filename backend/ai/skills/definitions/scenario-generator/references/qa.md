# 落库前自检清单

在 `create_scene_record` 调用前，LLM 必须（或由 WorkflowSkillExecutor 自动）完成以下自检。任一项未通过，禁止调 create。

## 一、字段完整性自检

| 检查项 | 期望值 | 失败处理 |
|---|---|---|
| `draft.collection.doctor_persona` | 非空字符串 | 回退 Step2 重新生成 |
| `draft.collection.best_practice_points` | 非空列表（≥3 条） | 回退 Step2 重新生成 |
| `draft.collection.drug_name` | 非空字符串 | 回退 Step2 重新生成 |
| `draft.collection.user_confirmed` | true | 询问用户确认 |
| `draft.title_bg.title` | 非空字符串，≤20 字 | 回退 Step3 重新生成 |
| `draft.title_bg.scene_background` | 非空字符串，150-300 字 | 回退 Step3 重新生成 |
| `draft.title_bg.user_confirmed` | true | 询问用户确认 |
| `draft.knowledge.knowledge_ids` | 列表（可为空） | 允许空，但 finalized 必须为 true |
| `draft.knowledge.finalized` | true | 回退 Step4.1 调 finalize |
| `draft.context_payload.doctor` | dict 含 5 键 | 回退 Step4.2 重新生成 |
| `draft.context_payload.coach` | dict 含 3 键 | 回退 Step4.2 重新生成 |
| `draft.context_payload.ready` | true | 回退 Step4.2 |
| `draft.submit_confirmed` | true | 询问用户确认提交 |

## 二、门禁校验自检

| 门禁 | 检查 | 期望 |
|---|---|---|
| G1 | tenant_id 非空 | true |
| G2 | config 三列表非空 | true |
| G3 | collection.user_confirmed | true |
| G4 | title_bg.user_confirmed | true |
| G5 | knowledge.finalized | true |
| G6 | context_payload.ready | true |
| G7 | submit_confirmed | true |

## 三、业务规则自检

| 检查项 | 规则 | 失败处理 |
|---|---|---|
| 标题禁姓氏 | 不含"张/王/李/赵/刘/陈/杨/黄/周/吴/徐/孙" + "主任/医生/教授" | 重新生成 |
| 标题禁祈使句 | 不含"请/必须/应该/需要" | 重新生成 |
| 标题长度 | ≤ 20 字符 | 重新生成 |
| 背景禁药品剂量 | 不含"mg/ML/克" + 数字 | 重新生成 |
| 背景第三人称 | 不含"你/我/您" | 重新生成 |
| 同源性 | sceneBackground == description（落库字段） | 由工具保证 |
| 保密红线 | 不在 user_message 中暴露 contextPayload 键名 | LLM 自检 |

## 四、一致性自检

| 检查项 | 规则 |
|---|---|
| collection.drug_name 与 title_bg.title 中的品种一致 | 如不一致，回退 Step3 |
| collection.doctor_persona 的科室与 title_bg.title 中的科室一致 | 如不一致，回退 Step3 |
| knowledge.knowledge_ids 中的 ID 在数据库存在 | 由 finalize_scene_knowledge 校验 |

## 五、降级兜底自检

| 检查项 | 期望 | 失败处理 |
|---|---|---|
| LLM 不可用（provider=mock） | draft 各字段使用 mock 模板填充 | 允许落库，标注 `provider=mock` |
| EpisodicMemory 不可用 | draft 仅 in-memory | 警告用户"会话状态可能丢失" |
| RAG 检索无结果 | knowledge_ids=[] | 允许，跳过知识挂载 |

## 六、自检执行方式

1. **LLM 主动自检**：在 Step4.3 调 create_scene_record 前，LLM 应在 user_message 中输出"自检完成，准备落库"等表述
2. **WorkflowSkillExecutor 后置自检**：在调用 create_scene_record 工具前，自动调用 `scene_workspace.validate_gate(draft, "G7")` + 字段完整性校验
3. **create_scene_record 工具内部自检**：在调 training_service.create_scene_from_draft 前，再次校验同源性和必填字段

任一自检未通过，禁止落库，回退到对应 Step。
