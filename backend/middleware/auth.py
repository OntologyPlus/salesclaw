"""认证中间件 - JWT 解析 + 权限检查"""
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from core.security import decode_token
from core.exceptions import AppException, UnauthorizedError, TokenExpiredError, ForbiddenError
from database import get_db, User, Role

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """从 JWT 解析当前用户"""
    if not credentials:
        raise UnauthorizedError("缺少 Authorization 头")

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError()
    except jwt.InvalidTokenError:
        raise UnauthorizedError("无效的 Token")

    if payload.get("type") != "access":
        raise UnauthorizedError("Token 类型错误")

    user_id = payload.get("user_id")
    tenant_id = payload.get("tenant_id")

    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == tenant_id,
        User.is_deleted == 0,
        User.is_active == 1,
    ).first()

    if not user:
        raise UnauthorizedError("用户不存在或已禁用")

    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """可选认证，未登录返回 None"""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except AppException:
        return None


def require_permission(*permissions: str):
    """权限检查依赖工厂（fail-closed：默认拒绝，仅当明确具备所需权限才放行）"""
    async def checker(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        # 无角色、角色缺失或角色不属于当前租户 → 直接拒绝
        if not user.role_id:
            raise ForbiddenError("用户未分配角色，禁止访问")
        role = db.query(Role).filter(
            Role.id == user.role_id,
            Role.tenant_id == user.tenant_id,
        ).first()
        if not role:
            raise ForbiddenError("角色不存在或不属于当前租户")

        role_perms = set(role.permissions or [])
        # 超级权限通配符，或兼容性超级角色（admin 等历史角色）
        if "*" in role_perms or role.code in ("admin",):
            return user

        missing = [p for p in permissions if p not in role_perms]
        if missing:
            raise ForbiddenError(f"缺少权限: {', '.join(missing)}")
        return user
    return checker
