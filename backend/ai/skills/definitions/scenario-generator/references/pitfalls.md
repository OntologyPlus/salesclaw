# 常见坑与排障（按 Step 分类）

## Step1 常见坑

### 坑 1.1：在 Step1 输出业务内容

**现象**：LLM 在 Step1 同一轮主动列出医生名、药品名等业务内容。

**原因**：LLM 未遵守"零业务输出"原则。

**处理**：在 system_prompt 中强制要求 Step1 仅输出环境准备提示；hallucination_detector 加规则识别业务内容泄露。

### 坑 1.2：fetch_scene_config 返回空

**现象**：`draft.config` 为空，G2 门禁失败。

**原因**：数据库无场景主题/受训对象配置数据；或 tenant_id 错误。

**处理**：提示用户"配置加载失败，请联系管理员初始化配置"。

## Step2 常见坑

### 坑 2.1：漏 sync 落盘

**现象**：LLM 生成了 doctorPersona 但未调用 sync_scene_draft，导致 draft.collection 为空。

**原因**：LLM 跳过原语直接输出回显清单。

**处理**：下一轮重新采集，强制 LLM 调用 sync_scene_draft 落盘。

### 坑 2.2：未等用户确认就推进

**现象**：LLM 在 Step2 同一轮 sync(confirm=true) 后直接进入 Step3。

**原因**：LLM 自行假设用户已确认。

**处理**：必须分两轮，第一轮 sync(confirm=false) + 回显询问，第二轮用户确认后 sync(confirm=true)。

### 坑 2.3：医生画像字段不完整

**现象**：doctorPersona 缺失职级或处方习惯。

**原因**：用户输入信息不足，LLM 未补充。

**处理**：LLM 应基于品种+科室主动生成合理的画像草案，标注"AI 推断"，让用户校对。

## Step3 常见坑

### 坑 3.1：漏 merge

**现象**：LLM 生成了 title + sceneBackground 但未调 merge_scene_draft。

**原因**：LLM 跳过原语直接展示。

**处理**：强制 LLM 调用 merge_scene_draft 落盘。

### 坑 3.2：标题含姓氏

**现象**：title 出现"张主任"等具体姓氏。

**原因**：LLM 未遵守标题写作规范。

**处理**：参考 `references/step3/title-and-scene-background.md`，重新生成。

### 坑 3.3：sceneBackground 与 repBriefing 不同源

**现象**：落库后 PracticeScenario.description 与 draft.title_bg.sceneBackground 不一致。

**原因**：LLM 在 merge 后又修改了内容。

**处理**：merge_scene_draft 工具内部校验同源性，落库时直接取 draft.title_bg.sceneBackground 写入 description。

## Step4.1 常见坑

### 坑 4.1.1：让用户新建知识

**现象**：LLM 提示用户"是否要新建一条知识？"

**原因**：LLM 未遵守"仅推荐已有知识"原则。

**处理**：在 system_prompt 中强制"禁止让用户新建知识"。

### 坑 4.1.2：未调 finalize

**现象**：用户选择了知识但 knowledgeIds 未锁定。

**原因**：LLM 漏调 finalize_scene_knowledge。

**处理**：强制 LLM 调用 finalize 锁定。

## Step4.2 常见坑

### 坑 4.2.1：§12 时序违例

**现象**：Step4.2 未完成就调 create_scene_record。

**原因**：LLM 跳过 generate_context_payload。

**处理**：WorkflowSkillExecutor 在 create_scene_record 调用前校验 G6 已通过；未通过则拒绝并回退到 Step4.2。

### 坑 4.2.2：对练 AI 角色为空

**现象**：场景落库后开始演练，AI 教练回复异常。

**原因**：contextPayload 未生成或字段缺失。

**处理**：在 generate_context_payload 工具内部校验 doctor 5 键 + coach 3 键完整性。

## Step4.3 常见坑

### 坑 4.3.1：自动重试 create

**现象**：create_scene_record 失败后，LLM 自行重试。

**原因**：LLM 未遵守"禁止自动重试"原则。

**处理**：create_scene_record 工具内部不重试；system_prompt 明确告知"失败一律报告并等待指示"。

### 坑 4.3.2：工作区未清理

**现象**：create 成功后，draft 仍存在于工作区。

**原因**：未调 scene_workspace.clear()。

**处理**：create_scene_record 工具内部成功后自动调用 scene_workspace.clear(session_id, db)。

## 通用坑

### 坑 X.1：门禁顺序错乱

**现象**：LLM 跳过 G3 直接调 G4 校验。

**原因**：LLM 未按顺序执行。

**处理**：WorkflowSkillExecutor 后置校验 gates_passed 列表，发现顺序错乱则回退到缺失门禁对应 Step。

### 坑 X.2：跨会话草稿丢失

**现象**：用户刷新页面后，草稿状态丢失。

**原因**：session_id 变化，EpisodicMemory 无法关联。

**处理**：前端在 sessionStorage 中保存 session_id，刷新时复用；如确实丢失，提示用户"会话状态丢失，请重新开始"。
