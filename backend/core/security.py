"""安全工具 - JWT + 密码哈希"""
from datetime import datetime, timedelta, timezone
import jwt
import bcrypt

from config import settings


def hash_password(password: str) -> str:
    """使用 bcrypt 直接哈希密码（避免 passlib 与 bcrypt 4.x 不兼容问题）"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """使用 bcrypt 直接验证密码"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, tenant_id: str, role: str, permissions: list) -> str:
    payload = {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "permissions": permissions,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def create_refresh_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    """解码并验证 JWT，失败抛 jwt 异常"""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
