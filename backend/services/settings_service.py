"""设置服务层 - 用户偏好管理

提供用户个性化偏好读写能力。
数据来源：内存存储（无对应数据库模型），按 (tenant_id, user_id) 隔离。
"""
from sqlalchemy.orm import Session


# ──────────────────────────────────────────────
# 默认偏好
# ──────────────────────────────────────────────

_DEFAULT_PREFERENCES = {
    "default_homepage": "sales",
    "notification_frequency": "normal",
    "ai_suggestion_mode": "balanced",
    "language": "zh-CN",
    "timezone": "Asia/Shanghai",
}

# 内存存储：{(tenant_id, user_id): {key: value, ...}}
_PREFERENCES_STORE = {}


# ──────────────────────────────────────────────
# 用户偏好
# ──────────────────────────────────────────────

def get_preferences(db: Session, tenant_id: str, user_id: int) -> dict:
    """获取用户偏好：合并默认值"""
    key = (tenant_id, user_id)
    prefs = dict(_DEFAULT_PREFERENCES)
    prefs.update(_PREFERENCES_STORE.get(key, {}))
    return prefs


def update_preferences(db: Session, tenant_id: str, user_id: int, data: dict) -> dict:
    """更新用户偏好"""
    key = (tenant_id, user_id)
    if key not in _PREFERENCES_STORE:
        _PREFERENCES_STORE[key] = {}
    _PREFERENCES_STORE[key].update(data)
    return _PREFERENCES_STORE[key]
