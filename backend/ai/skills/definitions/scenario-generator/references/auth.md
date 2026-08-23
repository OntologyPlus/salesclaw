# 鉴权与 token 规则

本系统简化鉴权模型，复用现有 JWT 机制，不实现复杂的 token 刷新逻辑。

## 一、鉴权流程

```
用户登录 → 获取 JWT token → 携带 Authorization: Bearer <token> 访问 API
                                     ↓
                          middleware/auth.py 校验 JWT
                                     ↓
                          注入 user 对象（含 tenant_id, user_id, role）
                                     ↓
                          Orchestrator.chat() Step 1 Guardrails
                                     ↓
                          WorkflowSkillExecutor 从 ctx 获取 user
                                     ↓
                          draft.tenant_id / draft.user_id 写入
```

## 二、token 复用规则

| 规则 | 说明 |
|---|---|
| 会话内 token 复用 | 同一 session_id 内多次调用 AI 接口使用同一 token |
| token 过期 | 返回 401，前端自动跳转登录页 |
| 401/403 处理 | 不自动重试，由前端处理跳转 |

## 三、G1 门禁与编排器集成

G1 门禁由编排器 `Orchestrator.chat()` Step 1 Guardrails 保证：

```python
# backend/ai/orchestrator.py
def chat(self, message, user, session_id, db):
    # Step 1: Guardrails
    if not user or not getattr(user, "tenant_id", None):
        return self._error_response(session_id, "用户未登录")
    # ... 后续步骤
```

因此 `validate_scene_gate(gate="G1")` 工具调用时恒返回 `{passed: true}`，仅作为流程完整性记录。

## 四、租户隔离

| 规则 | 说明 |
|---|---|
| 数据查询 | 所有 SQL 必须带 `tenant_id` 过滤 |
| 跨租户禁止 | 禁止任何形式的跨租户数据访问 |
| fetch_scene_config | 仅返回当前租户的配置数据 |
| create_scene_record | 落库时强制写入当前 tenant_id |

## 五、权限矩阵

| 角色 | 场景创建权限 | 备注 |
|---|---|---|
| sales_rep | ✅ | 为自己创建场景 |
| regional_manager | ✅ | 为自己或下属创建场景 |
| sales_director | ✅ | 全域可创建 |
| training_manager | ✅ | 培训域全权 |
| admin | ✅ | 全权 |

## 六、安全红线

- ❌ 禁止在 user_message 中输出 token、user_id、tenant_id 等敏感信息
- ❌ 禁止在 draft 中存储密码或密钥
- ❌ 禁止跨租户查询数据
- ❌ 禁止绕过编排器直接调用 training_service

## 七、token 失效处理

| 场景 | 错误码 | 前端处理 |
|---|---|---|
| token 过期 | 401 | 跳转登录页 |
| token 无效 | 401 | 跳转登录页 |
| 权限不足 | 403 | 提示"无权限" |
| 租户禁用 | 403 | 提示"租户已禁用" |
